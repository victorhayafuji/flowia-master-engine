-- Bronze content hash for duplicate detection on upload
ALTER TABLE docs_bronze ADD COLUMN IF NOT EXISTS content_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_docs_bronze_org_hash
  ON docs_bronze(organization_id, content_hash);
