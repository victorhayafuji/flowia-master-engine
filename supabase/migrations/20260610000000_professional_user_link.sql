-- Link dashboard_users to a professional so an employee login can see only their agenda.
-- professional_id is required at the application layer when role = 'professional'.

ALTER TABLE dashboard_users
    ADD COLUMN IF NOT EXISTS professional_id UUID REFERENCES professionals(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_dashboard_users_professional
    ON dashboard_users(professional_id) WHERE professional_id IS NOT NULL;
