-- FIFO queue for inbound WhatsApp processing (backend-only, internal RLS)

CREATE TABLE IF NOT EXISTS whatsapp_inbound_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    message_id TEXT NOT NULL UNIQUE,
    sender_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    attempts INT NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_wij_pending_fifo
  ON whatsapp_inbound_jobs (created_at)
  WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_wij_thread_processing
  ON whatsapp_inbound_jobs (thread_id, status)
  WHERE status = 'processing';

ALTER TABLE whatsapp_inbound_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE whatsapp_inbound_jobs FROM anon, authenticated;
