"""Simula inbound WhatsApp (Meta payload) sem celular — valida channel=whatsapp + motor híbrido.

Requisitos locais:
  1. Backend rodando (uvicorn / start_flowia.bat)
  2. Backend rodando com SIM_WHATSAPP_ORG_ID no .env (dev) **ou**
     organizations.whatsapp_phone_id = SIM_WHATSAPP_PHONE_ID na org demo

Exemplo .env (simulação local, sem Meta):
  SIM_WHATSAPP_ORG_ID=22222222-2222-2222-2222-222222222222
  SIM_WHATSAPP_PHONE_ID=123456789

Exemplo Supabase SQL (produção/staging):
  UPDATE organizations
  SET whatsapp_phone_id = '123456789'
  WHERE id = '22222222-2222-2222-2222-222222222222';

Uso:
  py scripts/simulate_whatsapp_webhook.py
  py scripts/simulate_whatsapp_webhook.py "Quero mechas sexta" "14:00" "Maria, 11987654321"
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DEFAULT_BASE = os.getenv("FLOWIA_API_BASE", "http://127.0.0.1:8000/api/v1")
DEFAULT_PHONE_NUMBER_ID = os.getenv("SIM_WHATSAPP_PHONE_ID", "123456789")
DEFAULT_ORG_ID = os.getenv("SIM_WHATSAPP_ORG_ID", "22222222-2222-2222-2222-222222222222")
DEFAULT_SENDER = os.getenv("SIM_WHATSAPP_SENDER", "5511998765432")
DEFAULT_TURNS = (
    "Quero mechas sexta",
    "14:00",
    "Maria Silva, telefone 11987654321",
)


def _make_payload(
    text: str,
    *,
    message_id: str,
    phone_number_id: str,
    sender: str,
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_sim",
                "changes": [
                    {
                        "value": {
                            "metadata": {
                                "display_phone_number": "5511888888888",
                                "phone_number_id": phone_number_id,
                            },
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": sender,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate WhatsApp webhook turns locally")
    parser.add_argument("--base", default=DEFAULT_BASE, help="API base including /api/v1")
    parser.add_argument(
        "--phone-number-id",
        default=DEFAULT_PHONE_NUMBER_ID,
        help="Must match organizations.whatsapp_phone_id",
    )
    parser.add_argument("--sender", default=DEFAULT_SENDER, help="Simulated customer phone (sender_id)")
    parser.add_argument(
        "--org-id",
        default=DEFAULT_ORG_ID,
        help="Organization UUID (thread_id esperado = {org_id}:{sender})",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=10.0,
        help="Seconds to wait after each POST (background worker is async)",
    )
    parser.add_argument(
        "messages",
        nargs="*",
        default=list(DEFAULT_TURNS),
        help="Messages to send in sequence (same sender = same thread)",
    )
    args = parser.parse_args()

    app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    url = f"{args.base.rstrip('/')}/webhook/whatsapp"

    print(f"POST {url}")
    print(f"phone_number_id={args.phone_number_id} sender={args.sender}")
    print(f"thread_id esperado em metrics/checkpoints: {args.org_id}:{args.sender}")
    if not app_secret:
        print("WHATSAPP_APP_SECRET vazio — request sem assinatura (ok se .env local assim)\n")
    else:
        print("Assinatura X-Hub-Signature-256 ativa\n")

    failures: list[str] = []

    with httpx.Client(timeout=30.0) as client:
        for i, text in enumerate(args.messages, 1):
            message_id = f"sim_{uuid.uuid4().hex[:16]}"
            payload = _make_payload(
                text,
                message_id=message_id,
                phone_number_id=args.phone_number_id,
                sender=args.sender,
            )
            body = json.dumps(payload).encode()
            headers = {"Content-Type": "application/json"}
            if app_secret:
                headers["X-Hub-Signature-256"] = _sign(body, app_secret)

            print(f"--- Turno {i} ---")
            print(f"Cliente: {text}")
            try:
                resp = client.post(url, content=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                print(f"Webhook HTTP {resp.status_code} | status={data.get('status')}")
                if data.get("status") != "success":
                    failures.append(f"Turno {i}: webhook status={data.get('status')}")
            except Exception as exc:
                failures.append(f"Turno {i}: {exc}")
                print(f"ERRO: {exc}")
                return 1

            if i < len(args.messages):
                print(f"Aguardando {args.wait}s (processamento async)...\n")
                time.sleep(args.wait)

    print(
        "\nProcessamento roda em background — veja logs do uvicorn e "
        "conversation_metrics (channel=whatsapp, scheduling_path, triage_source)."
    )
    print(
        f"SQL: SELECT thread_id, scheduling_path FROM conversation_metrics "
        f"WHERE channel='whatsapp' AND thread_id LIKE '{args.org_id}:%' ORDER BY created_at DESC LIMIT 5;"
    )
    print("Resposta outbound só aparece se whatsapp_access_token estiver configurado na org.")

    if failures:
        print("\nFALHAS:")
        for item in failures:
            print(f"  - {item}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
