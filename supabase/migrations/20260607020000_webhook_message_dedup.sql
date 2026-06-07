-- Webhook message deduplication (persists across process restarts)

CREATE TABLE IF NOT EXISTS webhook_message_dedup (
  message_id TEXT PRIMARY KEY,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_dedup_processed_at ON webhook_message_dedup(processed_at);
