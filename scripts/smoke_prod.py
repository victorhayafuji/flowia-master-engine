"""Smoke test for production API + optional dashboard URL."""
from __future__ import annotations

import argparse
import json
import sys

import httpx


def _normalize_api_base(raw: str) -> tuple[str, str]:
    base = raw.rstrip("/")
    if base.endswith("/api/v1"):
        api_v1 = base
        origin = base[: -len("/api/v1")]
    else:
        origin = base
        api_v1 = f"{origin}/api/v1"
    return origin, api_v1


def main() -> int:
    parser = argparse.ArgumentParser(description="FlowIA production smoke test")
    parser.add_argument(
        "--api-url",
        required=True,
        help="API base, e.g. https://flowia-api.onrender.com or .../api/v1",
    )
    parser.add_argument(
        "--dashboard-url",
        default="",
        help="Optional dashboard URL to verify static site responds",
    )
    args = parser.parse_args()

    origin, api_v1 = _normalize_api_base(args.api_url)
    failures: list[str] = []

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        health_url = f"{origin}/health"
        try:
            resp = client.get(health_url)
            resp.raise_for_status()
            payload = resp.json()
            print(f"OK health {health_url}: {json.dumps(payload, ensure_ascii=False)}")
            if payload.get("status") != "ok":
                failures.append("health status != ok")
            if payload.get("database") != "connected":
                failures.append("database != connected")
        except Exception as exc:
            failures.append(f"health check failed: {exc}")

        if args.dashboard_url:
            dash = args.dashboard_url.rstrip("/")
            try:
                resp = client.get(dash)
                resp.raise_for_status()
                print(f"OK dashboard {dash}: HTTP {resp.status_code}")
            except Exception as exc:
                failures.append(f"dashboard check failed: {exc}")

    if failures:
        print("\nFALHOU:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("\nSmoke API OK. Próximo: login manual no dashboard (cookie JWT).")
    print(f"  Login POST: {api_v1}/auth/login")
    return 0


if __name__ == "__main__":
    sys.exit(main())
