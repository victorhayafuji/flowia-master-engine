import os
import sys

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE")
email = os.environ.get("DEV_ADMIN_EMAIL", "admin@flowia.com")
password = os.environ.get("DEV_ADMIN_PASSWORD")

if not url or not key:
    print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_ROLE são obrigatórios no .env")
    sys.exit(1)

if not password:
    print("ERRO: DEV_ADMIN_PASSWORD não definido no .env")
    print("Execute: python scripts/setup_dev_env.py --email admin@flowia.com --password SUA_SENHA")
    sys.exit(1)

supabase: Client = create_client(url, key)

try:
    user = supabase.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {
            "org_id": os.environ.get("DEV_ADMIN_ORG_ID", "22222222-2222-2222-2222-222222222222"),
        },
    })
    print(f"User created: {user.user.email}")
except Exception as e:
    print(f"Error creating user: {e}")
