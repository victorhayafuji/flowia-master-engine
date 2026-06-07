import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("SUPABASE_DB_URL")

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    tables = cur.fetchall()
    print("Tables in public schema:")
    for table in tables:
        print(f"- {table[0]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
