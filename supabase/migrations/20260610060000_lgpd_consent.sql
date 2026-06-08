-- LGPD consent tracking on patients (WhatsApp/chat titular)

ALTER TABLE patients
  ADD COLUMN IF NOT EXISTS privacy_notice_version TEXT,
  ADD COLUMN IF NOT EXISTS privacy_notice_shown_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS privacy_consent_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS privacy_consent_channel TEXT
    CHECK (privacy_consent_channel IS NULL OR privacy_consent_channel IN ('whatsapp', 'chat_test', 'dashboard'));

CREATE INDEX IF NOT EXISTS idx_patients_org_legacy_sender
  ON patients (organization_id, legacy_sender_id)
  WHERE legacy_sender_id IS NOT NULL;

COMMENT ON COLUMN patients.privacy_notice_version IS 'Versão do aviso LGPD exibido (ex. 2026-06)';
COMMENT ON COLUMN patients.privacy_consent_at IS 'Consentimento tácito ao continuar conversa após aviso';
