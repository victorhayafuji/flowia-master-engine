"""HTTP security checks against prod API (read-only + auth probes)."""
from __future__ import annotations

import json
import sys

import httpx

API = "https://flowia-api.onrender.com"
API_V1 = f"{API}/api/v1"


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        status = "OK" if ok else "FAIL"
        print(f"{status} {name}" + (f" — {detail}" if detail else ""))

    with httpx.Client(timeout=120.0, follow_redirects=True) as c:
        # health — no secrets
        r = c.get(f"{API}/health")
        body = r.json() if r.status_code == 200 else {}
        leaked = any(k in body for k in ("SUPABASE", "SECRET", "KEY", "TOKEN", "password"))
        record("GET /health", r.status_code == 200 and not leaked, json.dumps(body, ensure_ascii=False)[:120])

        # privacy notice public
        r = c.get(f"{API_V1}/compliance/privacy-notice")
        record(
            "GET /compliance/privacy-notice",
            r.status_code == 200 and r.json().get("version"),
            f"version={r.json().get('version') if r.status_code == 200 else r.status_code}",
        )

        # unauth patients
        r = c.get(f"{API_V1}/patients/", headers={"x-organization-id": "22222222-2222-2222-2222-222222222222"})
        record("GET /patients/ sem cookie", r.status_code == 401, f"HTTP {r.status_code}")

        # webhook verify bad token
        r = c.get(
            f"{API_V1}/webhook/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "invalid", "hub.challenge": "x"},
        )
        record("GET /webhook/whatsapp token inválido", r.status_code == 403, f"HTTP {r.status_code}")

        # webhook POST bad signature
        r = c.post(
            f"{API_V1}/webhook/whatsapp",
            content=b"{}",
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=deadbeef"},
        )
        record(
            "POST /webhook/whatsapp assinatura inválida",
            r.status_code in (403, 400),
            f"HTTP {r.status_code}",
        )

        # login rate limit (6 attempts)
        codes = []
        for i in range(6):
            lr = c.post(f"{API_V1}/auth/login", json={"username": f"audit{i}@test.com", "password": "wrong"})
            codes.append(lr.status_code)
        record("POST /auth/login rate limit", 429 in codes, f"codes={codes}")

        # security headers sample
        hr = c.get(f"{API}/health")
        h = hr.headers
        record(
            "Security headers",
            h.get("x-frame-options", "").upper() == "DENY"
            and "nosniff" in h.get("x-content-type-options", ""),
            f"frame={h.get('x-frame-options')} nosniff={h.get('x-content-type-options')}",
        )

    fails = [n for n, ok, _ in results if not ok]
    print("\n" + "=" * 50)
    if fails:
        print("Falhas:", ", ".join(fails))
        return 1
    print("Auditoria HTTP OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
