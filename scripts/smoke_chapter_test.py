"""Smoke test for Agenda/Equipe chapter against a running local API."""
from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

BASE = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000")
ORG = (
    os.getenv("DEV_SALON_ORG_ID")
    or os.getenv("DEV_ADMIN_ORG_ID")
    or "22222222-2222-2222-2222-222222222222"
)
EMAIL = os.getenv("VITE_DEV_EMAIL") or os.getenv("DEV_ADMIN_EMAIL")
PASSWORD = os.getenv("VITE_DEV_PASSWORD") or os.getenv("DEV_ADMIN_PASSWORD")


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    with httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=True) as client:
        r = client.get("/health")
        check("health", r.status_code == 200, r.text[:120])

        if not EMAIL or not PASSWORD:
            check("login", False, "DEV credentials missing in .env")
        else:
            r = client.post("/api/v1/auth/login", json={"username": EMAIL, "password": PASSWORD})
            check("login", r.status_code == 200, f"status={r.status_code}")
            headers = {"x-organization-id": ORG}

            r = client.get("/api/v1/auth/me", headers=headers)
            me = r.json() if r.status_code == 200 else {}
            check("auth/me", r.status_code == 200, f"role={me.get('role')}")

            r = client.get("/api/v1/dashboard/stats", headers=headers)
            stats = r.json().get("data", {}) if r.status_code == 200 else {}
            check(
                "dashboard/stats",
                r.status_code == 200,
                f"today={stats.get('appointmentsToday')}",
            )

            r = client.get("/api/v1/dashboard/today-board", headers=headers)
            board = r.json().get("data", {}) if r.status_code == 200 else {}
            check(
                "dashboard/today-board",
                r.status_code == 200,
                f"pros={len(board.get('board', []))} total={board.get('counts', {}).get('total')}",
            )

            r = client.get("/api/v1/integrations/payments/status", headers=headers)
            pdata = r.json().get("data", {}) if r.status_code == 200 else {}
            check(
                "payments/status",
                r.status_code == 200 and pdata.get("enabled") is False,
                f"enabled={pdata.get('enabled')}",
            )

            r = client.get(
                "/api/v1/scheduling/blocks",
                headers=headers,
                params={"start_date": "2026-06-10", "end_date": "2026-06-10"},
            )
            check(
                "scheduling/blocks",
                r.status_code == 200,
                f"count={len(r.json().get('data', []))}",
            )

            r = client.get("/api/v1/organizations/professionals", headers=headers)
            check(
                "organizations/professionals",
                r.status_code == 200,
                f"count={len(r.json().get('data', []))}",
            )

            r = client.get("/api/v1/organizations/services", headers=headers)
            svcs = r.json().get("data", []) if r.status_code == 200 else []
            check("organizations/services", r.status_code == 200, f"count={len(svcs)}")

            if svcs:
                sid = svcs[0]["id"]
                r = client.get(
                    f"/api/v1/organizations/services/{sid}/professionals",
                    headers=headers,
                )
                check(
                    "services/{id}/professionals M:N",
                    r.status_code == 200,
                    f"links={len(r.json().get('data', []))}",
                )

            r = client.post("/api/v1/integrations/payments/webhook", json={})
            check("payments/webhook 501", r.status_code == 501, f"status={r.status_code}")

    print("=== SMOKE TEST (Agenda/Equipe) ===")
    passed = 0
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"[{status}] {name}: {detail}")
    print(f"--- {passed}/{len(results)} passed ---")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
