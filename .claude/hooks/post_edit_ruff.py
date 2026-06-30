#!/usr/bin/env python3
"""PostToolUse hook — best-effort ruff fix+format no arquivo .py editado.

Lê o payload do hook em stdin, roda ruff só em arquivos .py e NUNCA derruba o
turno (best-effort). Garante que código entra já lintado/formatado, sem depender
de eu lembrar de rodar ruff.
"""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = data.get("tool_input") or {}
    tool_response = data.get("tool_response") or {}
    path = tool_input.get("file_path") or tool_response.get("filePath") or ""

    if not path or not path.endswith(".py"):
        return 0

    # Roda ruff via o módulo do Python atual (robusto: não depende de um binário
    # `ruff` no PATH, que pode não existir mesmo com ruff instalado no ambiente).
    base = [sys.executable, "-m", "ruff"]
    for args in (
        ["check", "--fix", "--quiet", path],
        ["format", path],
    ):
        try:
            subprocess.run(base + args, capture_output=True, timeout=30)
        except Exception:
            # best-effort: ruff ausente/erro nunca bloqueia o turno
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
