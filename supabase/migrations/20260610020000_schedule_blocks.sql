-- Manual schedule blocks: time off, holidays and ad-hoc unavailability.
-- professional_id NULL = block applies to the whole organization (e.g. holiday).
-- The availability engine subtracts these intervals when generating free slots.

CREATE TABLE IF NOT EXISTS schedule_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    professional_id UUID REFERENCES professionals(id) ON DELETE CASCADE,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    reason TEXT,
    block_type TEXT NOT NULL DEFAULT 'manual' CHECK (block_type IN ('time_off', 'manual', 'holiday')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT schedule_blocks_valid_range CHECK (ends_at > starts_at)
);

CREATE INDEX IF NOT EXISTS idx_schedule_blocks_prof ON schedule_blocks(professional_id, starts_at, ends_at);
CREATE INDEX IF NOT EXISTS idx_schedule_blocks_org ON schedule_blocks(organization_id, starts_at);

-- RLS: same tenant-isolation pattern as the other business tables.
ALTER TABLE schedule_blocks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_read" ON schedule_blocks FOR SELECT USING (
    organization_id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
CREATE POLICY "tenant_insert" ON schedule_blocks FOR INSERT WITH CHECK (
    organization_id = current_setting('app.current_org_id', true)::UUID
);
CREATE POLICY "tenant_update" ON schedule_blocks FOR UPDATE USING (
    organization_id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
CREATE POLICY "tenant_delete" ON schedule_blocks FOR DELETE USING (
    organization_id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
