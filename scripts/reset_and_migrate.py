import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("SUPABASE_DB_URL")

sql = """
DROP TABLE IF EXISTS reminders CASCADE;
DROP TABLE IF EXISTS anamnesis_templates CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS service_catalog CASCADE;
DROP TABLE IF EXISTS services CASCADE;
DROP TABLE IF EXISTS professionals CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS dashboard_users CASCADE;
DROP TABLE IF EXISTS conversation_metrics CASCADE;
DROP TABLE IF EXISTS knowledge_chunks CASCADE;
DROP TABLE IF EXISTS knowledge_gaps CASCADE;
DROP TABLE IF EXISTS docs_bronze CASCADE;
DROP TABLE IF EXISTS docs_silver CASCADE;
DROP TABLE IF EXISTS docs_gold_vectors CASCADE;
DROP TABLE IF EXISTS _archive_fato_faturamento CASCADE;
DROP TABLE IF EXISTS _archive_fato_carteira_v2 CASCADE;
DROP TABLE IF EXISTS _archive_contratos CASCADE;
DROP TABLE IF EXISTS _archive_servicos CASCADE;
DROP TABLE IF EXISTS organizations CASCADE;

CREATE TABLE IF NOT EXISTS dashboard_users (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), username TEXT);
CREATE TABLE IF NOT EXISTS conversation_metrics (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), thread_id TEXT);
CREATE TABLE IF NOT EXISTS knowledge_chunks (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE IF NOT EXISTS knowledge_gaps (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE IF NOT EXISTS docs_bronze (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE IF NOT EXISTS docs_silver (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE IF NOT EXISTS docs_gold_vectors (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE IF NOT EXISTS fato_faturamento (id UUID PRIMARY KEY);
CREATE TABLE IF NOT EXISTS fato_carteira_v2 (id UUID PRIMARY KEY);
CREATE TABLE IF NOT EXISTS contratos (id UUID PRIMARY KEY);
CREATE TABLE IF NOT EXISTS servicos (id UUID PRIMARY KEY);
"""

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    print("Dropping tables and recreating base schema...")
    cur.execute(sql)
    
    migrations = [
        "supabase/migrations/20260531200000_multi_tenant_foundation.sql",
        "supabase/migrations/20260531210000_phase3_anamnesis.sql",
        "supabase/migrations/20260531220000_rls_jwt_support.sql",
        "supabase/migrations/20260605000000_phase4_data_lake.sql",
    ]
    
    for mig in migrations:
        if os.path.exists(mig):
            print(f"Applying {mig}...")
            with open(mig, 'r', encoding='utf-8') as f:
                cur.execute(f.read())
        else:
            print(f"Warning: Migration {mig} not found")
            
    conn.commit()
    print("Reset and Migrations applied successfully!")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    if 'conn' in locals():
        conn.rollback()
