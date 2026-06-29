"""CI guard: business-table writes must be scoped by organization_id.

WHY
---
The backend talks to Supabase with SERVICE_ROLE, which BYPASSES Postgres RLS.
So multi-tenant no-leak does NOT come from the database — it comes from every
business query carrying an `.eq("organization_id", ...)` filter in code. This
linter is an anti-regression net: it flags `.update(...)` / `.delete(...)` on a
business table that has no organization_id filter on the same query object.

WHAT IT CHECKS (AST, best-effort)
---------------------------------
For each chained call that includes `.update(...)` or `.delete(...)` and whose
chain root is `<...>.table("<T>")` where <T> is a business table, it requires
that the SAME QUERY OBJECT carrying the write also carries an
`.eq("organization_id", ...)` filter. Two shapes are recognized:

  1. Inline chain:
       table("X").update(...).eq("id", i).eq("organization_id", org)
     — the org `.eq` is collected straight from the write's own chain.

  2. Query variable:
       q = table("X").update(...).eq("id", i)
       if org and org != "ALL":
           q = q.eq("organization_id", org)   # extends the SAME object q
       q.execute()
     — we collect the `.eq` filters from every assignment to `q` whose RHS chains
     from `table(<business>)` or from `q` itself.

Crucially, an org filter applied to a DIFFERENT variable (e.g. the preceding
SELECT's `query`/`select_query`) does NOT credit the write. That is the exact
regression this guard exists to catch: if someone removes the org `.eq` from the
UPDATE while the SELECT above it still has one, the write is flagged.

LIMITATIONS (this is a net, NOT a proof)
----------------------------------------
- Object-scope via syntactic variable tracking, not full data-flow: it follows
  `V = V.eq(...)`-style reassignment within one function, not aliasing across
  helpers or through containers. The real guarantees are the explicit per-write
  scoping (Task 1) and the cross-tenant test matrix (Wave 2).
- It does not evaluate conditional filters (`if org and org != "ALL"`). A
  conditional `.eq("organization_id", ...)` on the write's object counts as
  present — which matches the super_admin (ALL/None) convention in the codebase.
- Table name must be a string literal in `.table("...")`. Dynamic table names
  are not analyzed (and are not used for business tables today).

EXEMPTIONS
----------
- Internal/infra tables (checkpoints*, webhook_message_dedup, whatsapp_inbound_jobs)
  are not in the business set — they are deny-by-default via RLS REVOKE, not
  org-scoped (CLAUDE.md §17).
- A legitimate cross-tenant write (super_admin path, platform cron) can be
  marked with a comment carrying `tenant-scope-exempt: <reason>` on any line of
  the write's chain or within a 3-line window directly above it (so a write
  wrapped in `asyncio.to_thread(...)` can be documented with a readable
  preceding comment rather than a trailing one). Keep the window tight so the
  marker stays local to the write it exempts.

USAGE
-----
    py -3.12 scripts/check_tenant_scoped_writes.py [path ...]

Exit 0 if clean, exit 1 if any unscoped business-table write is found.
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Default roots to scan.
DEFAULT_PATHS = (ROOT / "packages", ROOT / "apps")

# Business tables (CLAUDE.md §14). Writes to these must carry organization_id.
BUSINESS_TABLES: frozenset[str] = frozenset(
    {
        "appointments",
        "patients",
        "service_catalog",
        "professionals",
        "service_professionals",
        "schedule_blocks",
        "reminders",
        "docs_bronze",
        "docs_silver",
        "docs_gold_vectors",
        "conversation_metrics",
        "knowledge_gaps",
        "anamnesis_templates",
        "anamnesis_responses",
        "appointment_payments",
    }
)

WRITE_METHODS = {"update", "delete"}

EXEMPT_MARKER = "tenant-scope-exempt"


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    table: str
    method: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.table}.{self.method} sem filtro organization_id"


def _chain_calls(node: ast.Call) -> list[ast.Call]:
    """Walk an attribute-call chain bottom-up, returning every Call node in it.

    For `db.client.table("x").update(...).eq(...).execute()` the outermost Call
    is `.execute()`; following `.func.value` yields each preceding Call.
    """
    calls: list[ast.Call] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Call):
        calls.append(cur)
        func = cur.func
        if isinstance(func, ast.Attribute):
            cur = func.value
        else:
            break
    return calls


def _chain_top(node: ast.Call, parents: dict[int, ast.AST]) -> ast.Call:
    """Ascend from a write Call to the OUTERMOST Call of its fluent chain.

    Filters applied AFTER the write (`.update(...).eq("organization_id", ...)`)
    are ancestors of the write node, so `_chain_calls(write)` alone misses them.
    Walking up while the parent keeps the chain going (Attribute access or a Call
    whose function is the current node's attribute) yields the full chain top.
    """
    cur: ast.Call = node
    while True:
        parent = parents.get(id(cur))
        if isinstance(parent, ast.Attribute) and parent.value is cur:
            grand = parents.get(id(parent))
            if isinstance(grand, ast.Call) and grand.func is parent:
                cur = grand
                continue
        return cur


def _attr_name(call: ast.Call) -> str | None:
    """Method name of a chained call, e.g. `.update(...)` -> 'update'."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _table_literal(call: ast.Call) -> str | None:
    """If `call` is `.table("literal")`, return the literal table name."""
    if _attr_name(call) != "table":
        return None
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def _is_org_eq(call: ast.Call) -> bool:
    """True if `call` is `.eq("organization_id", ...)`."""
    if _attr_name(call) != "eq":
        return False
    return bool(
        call.args
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value == "organization_id"
    )


def _enclosing_function(node: ast.AST, parents: dict[int, ast.AST]) -> ast.AST | None:
    cur: ast.AST | None = node
    while cur is not None:
        parent = parents.get(id(cur))
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent
        cur = parent
    return None


def _chain_root(node: ast.AST) -> ast.AST:
    """Walk to the bottom of an attribute/call chain and return the root expr.

    For `db.client.table("x").update(...).eq(...)` the root is `db` (a Name);
    for `q.update(...).eq(...)` the root is the Name `q`.
    """
    cur = node
    while True:
        if isinstance(cur, ast.Call):
            cur = cur.func
        elif isinstance(cur, ast.Attribute):
            cur = cur.value
        else:
            return cur


def _root_var_name(node: ast.AST) -> str | None:
    """If the chain rooted at `node` starts from a bare Name (a query variable),
    return that name; otherwise None (e.g. roots at `db`/`self`)."""
    root = _chain_root(node)
    return root.id if isinstance(root, ast.Name) else None


def _chain_starts_from(expr: ast.AST, var_names: set[str]) -> bool:
    """True if the attribute/call chain `expr` is rooted at `table(<business>)`
    or at one of the given query-variable names."""
    cur = expr
    while isinstance(cur, (ast.Call, ast.Attribute)):
        if isinstance(cur, ast.Call) and (tbl := _table_literal(cur)) is not None:
            return tbl in BUSINESS_TABLES
        cur = cur.func if isinstance(cur, ast.Call) else cur.value
    return isinstance(cur, ast.Name) and cur.id in var_names


def _eq_calls_in(expr: ast.AST) -> list[ast.Call]:
    """All `.eq(...)` Call nodes within an expression."""
    return [
        sub
        for sub in ast.walk(expr)
        if isinstance(sub, ast.Call) and _attr_name(sub) == "eq"
    ]


def _contains(outer: ast.AST, target: ast.AST) -> bool:
    """True if `target` is `outer` or nested anywhere inside it."""
    return any(sub is target for sub in ast.walk(outer))


def _chain_has_table(chain: list[ast.Call]) -> bool:
    """True if the write's full inline chain freshly builds from a `table(...)`."""
    return any(_table_literal(c) is not None for c in chain)


def _query_var_for_write(top: ast.Call, chain: list[ast.Call], func: ast.AST) -> str | None:
    """Find the query variable the write's chain is bound to, if any.

    `top` is the outermost Call of the write's fluent chain; `chain` its calls.

    Two bindings:
      - The chain is built fresh from `table(...)` (rooted at `self`/`db`) and
        assigned to a variable: `V = ...table(X).update(...).eq("id", i)`. We
        resolve `V` from the enclosing assignment so later `V = V.eq(...)`
        reassignments can be tracked.
      - The chain is applied to an existing query variable: `V.update(...)` /
        `V = V.update(...)` — the chain root is the bare Name `V`.
    """
    if _chain_has_table(chain):
        # Freshly-built chain — its result lives in the assignment target (if any).
        for sub in ast.walk(func):
            if isinstance(sub, ast.Assign) and _contains(sub.value, top):
                names = [t.id for t in sub.targets if isinstance(t, ast.Name)]
                if names:
                    return names[0]
        return None
    # No table() in the chain → it is rooted at a query variable.
    return _root_var_name(top)


def _write_query_has_org_eq(top: ast.Call, chain: list[ast.Call], func: ast.AST) -> bool:
    """True iff the org filter lives on the SAME query object as the write.

    `top`/`chain` describe the write's full fluent chain (filters applied AFTER
    the write included). Two cases:
      1. Inline chain — the chain carries `.eq("organization_id", ...)`.
      2. Query variable — the write builds/extends a variable `V`
         (`V = ...table(X).update(...).eq("id", i); ...; V = V.eq("organization_id",
         org)`). We collect the org `.eq` from every assignment to `V` whose RHS
         chains from `table(<business>)` or from `V`. A filter applied to a
         DIFFERENT variable (e.g. the preceding SELECT's `query`/`select_query`)
         does NOT count — that is exactly the false-negative this guard must catch.
    """
    # Case 1: inline chain on the write itself (full chain, incl. post-write .eq).
    for call in chain:
        if _is_org_eq(call):
            return True

    # Case 2: track the org filter through the write's query variable.
    var = _query_var_for_write(top, chain, func)
    if var is None:
        return False

    for sub in ast.walk(func):
        if not isinstance(sub, ast.Assign):
            continue
        targets = {t.id for t in sub.targets if isinstance(t, ast.Name)}
        if var not in targets:
            continue
        # Only assignments that build/extend this same query object count: the RHS
        # must chain from a business table() or from the variable V itself.
        if not _chain_starts_from(sub.value, {var}):
            continue
        if any(_is_org_eq(c) for c in _eq_calls_in(sub.value)):
            return True
    return False


def _exempt_lines(source: str) -> set[int]:
    return {
        i
        for i, line in enumerate(source.splitlines(), start=1)
        if EXEMPT_MARKER in line
    }


# How many lines above a write's chain start to scan for the exemption marker.
# Covers a preceding comment that sits above a call wrapper (e.g.
# `await asyncio.to_thread(` opens one line, the chained write is the next line).
_MARKER_LOOKBACK = 3


def _marker_window_above(start_line: int) -> set[int]:
    """Return the 1-based line numbers in the small lookback window above
    ``start_line`` (1-based) that may carry a preceding exemption comment."""
    lo = max(1, start_line - _MARKER_LOOKBACK)
    return set(range(lo, start_line))


def scan_source(source: str, filename: str) -> list[Finding]:
    """Scan one source string; return findings for unscoped business writes."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    exempt = _exempt_lines(source)
    findings: list[Finding] = []
    seen: set[tuple[int, str, str]] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        method = _attr_name(node)
        if method not in WRITE_METHODS:
            continue

        # Full fluent chain incl. filters applied AFTER the write
        # (`.update(...).eq("organization_id", ...)`): ascend to the chain top,
        # then collect every Call from there down.
        top = _chain_top(node, parents)
        chain = _chain_calls(top)
        table = next((t for c in chain if (t := _table_literal(c)) is not None), None)
        if table is None or table not in BUSINESS_TABLES:
            continue

        line = node.lineno
        key = (line, table, method)
        if key in seen:
            continue
        seen.add(key)

        # A marker counts if it sits on any line of the write's chain or in the
        # contiguous comment block immediately above it (readable preceding style).
        chain_lines = [c.lineno for c in chain if hasattr(c, "lineno")]
        chain_min = min(chain_lines) if chain_lines else line
        chain_max = max(chain_lines) if chain_lines else line
        covered = set(range(chain_min, chain_max + 1))
        covered |= _marker_window_above(chain_min)
        if covered & exempt:
            continue

        func = _enclosing_function(node, parents)
        if func is not None and _write_query_has_org_eq(top, chain, func):
            continue

        findings.append(Finding(file=filename, line=line, table=table, method=method))

    return findings


def scan_paths(paths: list[Path] | tuple[Path, ...]) -> list[Finding]:
    """Scan every .py file under the given paths; return all findings sorted."""
    findings: list[Finding] = []
    for base in paths:
        base = Path(base)
        if base.is_file() and base.suffix == ".py":
            files = [base]
        else:
            files = sorted(base.rglob("*.py"))
        for file in files:
            try:
                source = file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            try:
                rel = str(file.relative_to(ROOT))
            except ValueError:
                rel = str(file)
            findings.extend(scan_source(source, rel))
    return sorted(findings, key=lambda f: (f.file, f.line))


def main(argv: list[str]) -> int:
    raw = argv[1:]
    paths = [Path(p) for p in raw] if raw else list(DEFAULT_PATHS)
    findings = scan_paths(paths)
    if findings:
        for f in findings:
            print(f)
        print(
            f"\n{len(findings)} write(s) de tabela de negócio sem filtro organization_id.",
            file=sys.stderr,
        )
        return 1
    print("OK: nenhum write de tabela de negócio sem filtro organization_id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
