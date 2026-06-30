-- Kiosk (totem) device provisioning — backend-only table.
-- A device token (high-entropy, SHA-256 hashed) maps a tablet to its organization,
-- mirroring how organizations.whatsapp_phone_id maps a Meta sender to a tenant.
-- Resolved server-side via service_role; never exposed to PostgREST anon/authenticated.

CREATE TABLE IF NOT EXISTS kiosk_devices (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  label           TEXT NOT NULL,
  token_hash      TEXT NOT NULL,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at    TIMESTAMPTZ
);

-- Lookup by token hash must be unique and fast (the resolver's hot path).
CREATE UNIQUE INDEX IF NOT EXISTS idx_kiosk_devices_token_hash ON kiosk_devices(token_hash);
CREATE INDEX IF NOT EXISTS idx_kiosk_devices_org ON kiosk_devices(organization_id) WHERE is_active;

-- Internal table: deny PostgREST anon & authenticated (no policies = deny by default).
-- Backend (service_role) and direct postgres still work.
ALTER TABLE kiosk_devices ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE kiosk_devices FROM anon, authenticated;
