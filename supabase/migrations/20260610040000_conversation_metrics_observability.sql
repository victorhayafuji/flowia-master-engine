-- Observability: scheduling path, triage source, channel, tools for hybrid agent metrics

ALTER TABLE conversation_metrics
    ADD COLUMN IF NOT EXISTS scheduling_path TEXT,
    ADD COLUMN IF NOT EXISTS triage_source TEXT,
    ADD COLUMN IF NOT EXISTS channel TEXT,
    ADD COLUMN IF NOT EXISTS tools_called JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN conversation_metrics.scheduling_path IS 'deterministic | llm | null when not scheduling agent';
COMMENT ON COLUMN conversation_metrics.triage_source IS 'keyword | conversation | sticky | llm';
COMMENT ON COLUMN conversation_metrics.channel IS 'chat_test | whatsapp';
COMMENT ON COLUMN conversation_metrics.tools_called IS 'Tool names invoked in the turn (LLM path)';

CREATE INDEX IF NOT EXISTS idx_cm_scheduling_path ON conversation_metrics (organization_id, scheduling_path)
    WHERE scheduling_path IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cm_channel ON conversation_metrics (organization_id, channel)
    WHERE channel IS NOT NULL;
