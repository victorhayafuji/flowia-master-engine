-- WhatsApp thread_id/sender_id are phone strings, not UUIDs (patients.id)

ALTER TABLE conversation_metrics
    ALTER COLUMN sender_id TYPE TEXT USING sender_id::text;

COMMENT ON COLUMN conversation_metrics.sender_id IS 'Sender identifier: WhatsApp phone or chat_test thread UUID string';
