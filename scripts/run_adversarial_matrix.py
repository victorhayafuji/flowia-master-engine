#!/usr/bin/env python3
"""Run adversarial pytest matrix (excludes live LLM behavior tests)."""
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run adversarial / temporal test matrix")
    parser.add_argument(
        "--temporal",
        action="store_true",
        help="Include PT-BR colloquial date parsing matrix",
    )
    args = parser.parse_args()

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_engine_input_guard.py",
        "tests/test_lakehouse_governance.py",
        "tests/test_search_kb_security.py",
        "tests/test_prompt_guardrails_static.py",
        "tests/test_chat_security.py",
        "tests/test_webhook_input_guard.py",
        "tests/test_agent_flow_adversarial.py",
    ]
    if args.temporal:
        cmd.extend(
            [
                "tests/test_date_parsing.py",
                "tests/test_date_parsing_operational.py",
                "tests/test_support_executor.py",
            ]
        )
    cmd.extend(["-m", "not llm_behavior", "-q"])
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())