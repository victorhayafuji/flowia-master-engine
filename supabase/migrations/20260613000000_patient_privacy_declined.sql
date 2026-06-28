-- Persist an explicit LGPD consent refusal ("Discordo") so it is not overridden
-- by the tacit-consent gate on the next message. Nullable, additive, idempotent.
-- When set (and no privacy_consent_at), the consent gate re-presents the notice
-- and never proceeds with tacit consent. RLS already enabled on patients.

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS privacy_declined_at TIMESTAMPTZ;

COMMENT ON COLUMN patients.privacy_declined_at IS
    'When the data subject explicitly declined the privacy notice (LGPD). '
    'Cleared on explicit consent or DSAR erase.';
