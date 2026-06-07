import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
cur = conn.cursor()
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='docs_bronze' ORDER BY ordinal_position"
)
print("docs_bronze columns:", [r[0] for r in cur.fetchall()])
cur.execute("NOTIFY pgrst, 'reload schema'")
conn.commit()
print("PostgREST schema reload notified.")
cur.close()
conn.close()
