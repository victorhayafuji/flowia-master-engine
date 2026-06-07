-- Patient handoff fields (WhatsApp human transfer) — replaces legacy leads table writes

ALTER TABLE patients
  ADD COLUMN IF NOT EXISTS handoff_requested_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS handoff_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_patients_legacy_sender
  ON patients(organization_id, legacy_sender_id)
  WHERE legacy_sender_id IS NOT NULL;
