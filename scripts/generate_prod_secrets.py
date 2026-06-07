"""Generate fresh production secrets (stdout only — never commit output)."""
import secrets
import sys


def main() -> int:
    print("# Cole estes valores no Render Dashboard / .env de produção (NUNCA commitar)")
    print(f"DASHBOARD_JWT_SECRET={secrets.token_urlsafe(48)}")
    print(f"DASHBOARD_API_KEY={secrets.token_hex(32)}")
    print(f"WHATSAPP_VERIFY_TOKEN={secrets.token_urlsafe(32)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
