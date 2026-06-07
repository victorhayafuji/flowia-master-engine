-- Many-to-many eligibility: which professionals can perform which services.
-- Replaces the optional 1:1 service_catalog.professional_id (kept for backward compat).
-- Rule: if a service has rows here, only those professionals are eligible; if empty,
-- any active professional may perform it (explicit fallback in the booking logic).

CREATE TABLE IF NOT EXISTS service_professionals (
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    service_id UUID NOT NULL REFERENCES service_catalog(id) ON DELETE CASCADE,
    professional_id UUID NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (service_id, professional_id)
);

CREATE INDEX IF NOT EXISTS idx_svc_prof_professional ON service_professionals(professional_id);
CREATE INDEX IF NOT EXISTS idx_svc_prof_org ON service_professionals(organization_id);

-- Backfill from the legacy single-professional FK.
INSERT INTO service_professionals (organization_id, service_id, professional_id)
SELECT organization_id, id, professional_id
FROM service_catalog
WHERE professional_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- RLS: same tenant-isolation pattern as the other business tables.
ALTER TABLE service_professionals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_read" ON service_professionals FOR SELECT USING (
    organization_id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
CREATE POLICY "tenant_insert" ON service_professionals FOR INSERT WITH CHECK (
    organization_id = current_setting('app.current_org_id', true)::UUID
);
CREATE POLICY "tenant_update" ON service_professionals FOR UPDATE USING (
    organization_id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
CREATE POLICY "tenant_delete" ON service_professionals FOR DELETE USING (
    organization_id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
