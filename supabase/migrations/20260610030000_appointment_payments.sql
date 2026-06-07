-- Payments stub: schema only. No webhook is active; this prepares the data model
-- and tenant isolation for a future payment-provider integration (see
-- packages/integrations/payments). Per-org credentials live in organizations.settings.

CREATE TABLE IF NOT EXISTS appointment_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    amount_cents INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'BRL',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'synced', 'failed', 'refunded')),
    provider TEXT,
    external_id TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_appointment_payments_org ON appointment_payments(organization_id);
CREATE INDEX IF NOT EXISTS idx_appointment_payments_appt ON appointment_payments(appointment_id);

-- RLS: same tenant-isolation pattern as the other business tables.
ALTER TABLE appointment_payments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_read" ON appointment_payments FOR SELECT USING (
    organization_id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
CREATE POLICY "tenant_insert" ON appointment_payments FOR INSERT WITH CHECK (
    organization_id = current_setting('app.current_org_id', true)::UUID
);
CREATE POLICY "tenant_update" ON appointment_payments FOR UPDATE USING (
    organization_id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
CREATE POLICY "tenant_delete" ON appointment_payments FOR DELETE USING (
    organization_id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);

-- Keep updated_at fresh on every change (set_updated_at() defined in 20260609000000).
DROP TRIGGER IF EXISTS trg_set_updated_at ON appointment_payments;
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON appointment_payments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
