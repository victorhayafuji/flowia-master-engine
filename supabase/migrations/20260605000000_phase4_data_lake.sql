-- Phase 4: Data Lake Medallion (Bronze / Silver / Gold)
-- Requires: pgvector extension (enabled in Supabase Dashboard → Database → Extensions)

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Bronze: raw document registry
-- ---------------------------------------------------------------------------
ALTER TABLE docs_bronze ADD COLUMN IF NOT EXISTS file_name TEXT;
ALTER TABLE docs_bronze ADD COLUMN IF NOT EXISTS storage_path TEXT;
ALTER TABLE docs_bronze ADD COLUMN IF NOT EXISTS mime_type TEXT;
ALTER TABLE docs_bronze ADD COLUMN IF NOT EXISTS file_size BIGINT;
ALTER TABLE docs_bronze ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'PENDING';
ALTER TABLE docs_bronze ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE docs_bronze ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE docs_bronze ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ---------------------------------------------------------------------------
-- Silver: OCR-cleaned text
-- ---------------------------------------------------------------------------
ALTER TABLE docs_silver ADD COLUMN IF NOT EXISTS bronze_id UUID REFERENCES docs_bronze(id) ON DELETE CASCADE;
ALTER TABLE docs_silver ADD COLUMN IF NOT EXISTS raw_text TEXT;
ALTER TABLE docs_silver ADD COLUMN IF NOT EXISTS cleaned_text TEXT;
ALTER TABLE docs_silver ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'SILVER_READY';
ALTER TABLE docs_silver ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE docs_silver ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE docs_silver ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id);

-- ---------------------------------------------------------------------------
-- Gold: vector chunks for RAG
-- ---------------------------------------------------------------------------
ALTER TABLE docs_gold_vectors ADD COLUMN IF NOT EXISTS silver_id UUID REFERENCES docs_silver(id) ON DELETE CASCADE;
ALTER TABLE docs_gold_vectors ADD COLUMN IF NOT EXISTS chunk_index INT DEFAULT 0;
ALTER TABLE docs_gold_vectors ADD COLUMN IF NOT EXISTS content TEXT;
ALTER TABLE docs_gold_vectors ADD COLUMN IF NOT EXISTS embedding vector(768);
ALTER TABLE docs_gold_vectors ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_docs_bronze_org_status ON docs_bronze(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_docs_silver_org_status ON docs_silver(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_docs_gold_org ON docs_gold_vectors(organization_id);

-- ---------------------------------------------------------------------------
-- Semantic search RPC (tenant-aware)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 5,
    filter_org_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    content text,
    similarity float
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        g.id,
        g.content,
        1 - (g.embedding <=> query_embedding) AS similarity
    FROM docs_gold_vectors g
    WHERE g.embedding IS NOT NULL
      AND (filter_org_id IS NULL OR g.organization_id = filter_org_id)
      AND 1 - (g.embedding <=> query_embedding) > match_threshold
    ORDER BY g.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
