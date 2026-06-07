"""Verifica se SUPABASE_URL e SUPABASE_DB_URL apontam para o mesmo projeto."""
import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

api_url = os.environ.get("SUPABASE_URL", "")
db_url = os.environ.get("SUPABASE_DB_URL", "")

api_host = urlparse(api_url).hostname or ""
db_host = urlparse(db_url).hostname or ""

api_ref = api_host.replace(".supabase.co", "").replace("db.", "") if api_host else ""
db_ref = db_host.replace("db.", "").replace(".supabase.co", "") if db_host else ""

print(f"SUPABASE_URL host:     {api_host}")
print(f"SUPABASE_DB_URL host:  {db_host}")
print(f"Mesmo projeto: {'SIM' if api_ref and api_ref == db_ref else 'NAO'}")
