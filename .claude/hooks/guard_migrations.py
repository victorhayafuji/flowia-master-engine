#!/usr/bin/env python3
"""PreToolUse hook — protege migrations já existentes.

Migrations são versionadas e imutáveis depois de escritas: nunca editar/sobrescrever
uma já aplicada. Este guard BLOQUEIA Edit/Write sobre um arquivo que JÁ EXISTE em
supabase/migrations/*.sql, mas PERMITE criar uma migration NOVA (Write num caminho
que ainda não existe — com timestamp posterior).
"""
from __future__ import annotations

import json
import os
import sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = data.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or ""
    if not raw_path:
        return 0

    normalized = raw_path.replace("\\", "/")
    is_migration = "supabase/migrations/" in normalized and normalized.endswith(".sql")

    if is_migration and os.path.exists(raw_path):
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Migration já existente é imutável (versionada). Não edite uma "
                    "migration aplicada — crie uma NOVA com timestamp posterior."
                ),
            }
        }
        print(json.dumps(out))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
