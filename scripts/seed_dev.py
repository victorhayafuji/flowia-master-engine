"""
Orquestra seed completo do ambiente de desenvolvimento salão.

Uso:
  python scripts/seed_dev.py
  python scripts/seed_dev.py --skip-user
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(script: str, extra: list[str] | None = None) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / script)] + (extra or [])
    print(f"\n>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed dev salão (operacional + KB + usuário)")
    parser.add_argument("--skip-user", action="store_true", help="Não cria usuário org_admin")
    parser.add_argument("--skip-datalake", action="store_true", help="Não ingere KB")
    args = parser.parse_args()

    steps = [
        ("seed_salon.py", []),
    ]
    if not args.skip_datalake:
        steps.append(("seed_datalake.py", ["--ensure-org"]))
    if not args.skip_user:
        steps.append(("create_salon_user.py", []))

    for script, extra in steps:
        code = _run(script, extra)
        if code != 0:
            print(f"Falha em {script} (exit {code})")
            return code

    print("\nOK: ambiente dev salão pronto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
