-- Migration: Multi-Tenant Foundation (Phase 1)
-- Description: Creates organizations, professionals, service_catalog, patients, appointments, reminders, anamnesis_templates
-- Adds organization_id to existing tables, creates indexes and RLS policies, archives legacy tables.

-- 1.1 Tabelas Novas

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    vertical TEXT NOT NULL CHECK (vertical IN ('salon', 'dental', 'medical')),
    phone TEXT,
    email TEXT,
    address JSONB,
    timezone TEXT DEFAULT 'America/Sao_Paulo',
    settings JSONB DEFAULT '{}',
    whatsapp_phone_id TEXT,
    whatsapp_access_token TEXT,
    whatsapp_business_id TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    subscription_plan TEXT DEFAULT 'basic',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE professionals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    specialty TEXT,
    phone TEXT,
    email TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    avatar_url TEXT,
    working_hours JSONB DEFAULT '{
        "mon": {"start": "08:00", "end": "18:00"},
        "tue": {"start": "08:00", "end": "18:00"},
        "wed": {"start": "08:00", "end": "18:00"},
        "thu": {"start": "08:00", "end": "18:00"},
        "fri": {"start": "08:00", "end": "18:00"}
    }',
    break_times JSONB DEFAULT '[{"start": "12:00", "end": "13:00"}]',
    appointment_buffer_minutes INT DEFAULT 15,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE service_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    duration_minutes INT NOT NULL,
    price NUMERIC(10,2),
    category TEXT,
    requires_anamnesis BOOLEAN DEFAULT FALSE,
    recall_days INT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    cpf TEXT,
    birth_date DATE,
    gender TEXT,
    notes TEXT,
    tags JSONB DEFAULT '[]',
    insurance_plan TEXT,
    insurance_number TEXT,
    no_show_count INT DEFAULT 0,
    total_appointments INT DEFAULT 0,
    last_visit_at TIMESTAMPTZ,
    legacy_sender_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, phone)
);

CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id),
    professional_id UUID NOT NULL REFERENCES professionals(id),
    service_id UUID NOT NULL REFERENCES service_catalog(id),
    scheduled_at TIMESTAMPTZ NOT NULL,
    duration_minutes INT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'confirmed', 'arrived', 'in_progress',
        'completed', 'no_show', 'cancelled', 'rescheduled'
    )),
    anamnesis_completed BOOLEAN DEFAULT FALSE,
    anamnesis_data JSONB,
    pre_service_notes TEXT,
    post_service_notes TEXT,
    treatment_plan TEXT,
    satisfaction_score INT CHECK (satisfaction_score BETWEEN 1 AND 5),
    feedback_text TEXT,
    recall_scheduled_at TIMESTAMPTZ,
    recall_sent BOOLEAN DEFAULT FALSE,
    source TEXT DEFAULT 'whatsapp' CHECK (source IN ('whatsapp', 'dashboard', 'api', 'phone')),
    cancellation_reason TEXT,
    rescheduled_from UUID REFERENCES appointments(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id),
    type TEXT NOT NULL CHECK (type IN (
        'confirmation_24h', 'reminder_2h', 'post_service',
        'recall', 'satisfaction', 'reactivation'
    )),
    channel TEXT DEFAULT 'whatsapp',
    scheduled_for TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'delivered', 'failed', 'cancelled')),
    response TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE anamnesis_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    vertical TEXT NOT NULL,
    name TEXT NOT NULL,
    fields JSONB NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 1.2 Modificações em Tabelas Existentes

-- dashboard_users: multi-org + roles
ALTER TABLE dashboard_users
    ADD COLUMN organization_id UUID REFERENCES organizations(id),
    ADD COLUMN role TEXT DEFAULT 'org_admin' CHECK (role IN ('super_admin', 'org_admin', 'professional'));

-- conversation_metrics: vincular a org
ALTER TABLE conversation_metrics ADD COLUMN organization_id UUID REFERENCES organizations(id);

-- KB por organização
ALTER TABLE knowledge_chunks ADD COLUMN organization_id UUID REFERENCES organizations(id);
ALTER TABLE knowledge_gaps ADD COLUMN organization_id UUID REFERENCES organizations(id);
ALTER TABLE docs_bronze ADD COLUMN organization_id UUID REFERENCES organizations(id);
ALTER TABLE docs_silver ADD COLUMN organization_id UUID REFERENCES organizations(id);
ALTER TABLE docs_gold_vectors ADD COLUMN organization_id UUID REFERENCES organizations(id);

-- 1.4 Arquivar legadas
ALTER TABLE fato_faturamento RENAME TO _archive_fato_faturamento;
ALTER TABLE fato_carteira_v2 RENAME TO _archive_fato_carteira_v2;
ALTER TABLE contratos RENAME TO _archive_contratos;
ALTER TABLE servicos RENAME TO _archive_servicos;

-- 1.3 Índices
CREATE INDEX idx_appt_org_date ON appointments(organization_id, scheduled_at);
CREATE INDEX idx_appt_prof_date ON appointments(professional_id, scheduled_at);
CREATE INDEX idx_appt_patient ON appointments(patient_id);
CREATE INDEX idx_appt_status ON appointments(organization_id, status);
CREATE INDEX idx_rem_pending ON reminders(status, scheduled_for) WHERE status = 'pending';
CREATE INDEX idx_pat_org_phone ON patients(organization_id, phone);
CREATE INDEX idx_prof_org_active ON professionals(organization_id) WHERE is_active = TRUE;
CREATE INDEX idx_svc_org_active ON service_catalog(organization_id) WHERE is_active = TRUE;
CREATE INDEX idx_cm_org ON conversation_metrics(organization_id);
CREATE INDEX idx_cm_thread ON conversation_metrics(thread_id);

-- 1.3 RLS Policies
-- Enable RLS on all tenant tables
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE professionals ENABLE ROW LEVEL SECURITY;
ALTER TABLE service_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;
ALTER TABLE anamnesis_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboard_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_gaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE docs_bronze ENABLE ROW LEVEL SECURITY;
ALTER TABLE docs_silver ENABLE ROW LEVEL SECURITY;
ALTER TABLE docs_gold_vectors ENABLE ROW LEVEL SECURITY;

-- organizations policies (super_admin has full access, org_admin can read/update their own)
CREATE POLICY "org_read" ON organizations FOR SELECT USING (
    id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
CREATE POLICY "org_update" ON organizations FOR UPDATE USING (
    id = current_setting('app.current_org_id', true)::UUID
    OR current_setting('app.user_role', true) = 'super_admin'
);
CREATE POLICY "org_insert" ON organizations FOR INSERT WITH CHECK (
    current_setting('app.user_role', true) = 'super_admin'
);
CREATE POLICY "org_delete" ON organizations FOR DELETE USING (
    current_setting('app.user_role', true) = 'super_admin'
);

-- Template for other tenant-specific tables
CREATE OR REPLACE FUNCTION create_tenant_policies(table_name TEXT) RETURNS VOID AS $$
BEGIN
    EXECUTE format('
        CREATE POLICY "tenant_read" ON %I FOR SELECT USING (
            organization_id = current_setting(''app.current_org_id'', true)::UUID
            OR current_setting(''app.user_role'', true) = ''super_admin''
        );
        CREATE POLICY "tenant_insert" ON %I FOR INSERT WITH CHECK (
            organization_id = current_setting(''app.current_org_id'', true)::UUID
        );
        CREATE POLICY "tenant_update" ON %I FOR UPDATE USING (
            organization_id = current_setting(''app.current_org_id'', true)::UUID
            OR current_setting(''app.user_role'', true) = ''super_admin''
        );
        CREATE POLICY "tenant_delete" ON %I FOR DELETE USING (
            organization_id = current_setting(''app.current_org_id'', true)::UUID
            OR current_setting(''app.user_role'', true) = ''super_admin''
        );
    ', table_name, table_name, table_name, table_name);
END;
$$ LANGUAGE plpgsql;

SELECT create_tenant_policies('professionals');
SELECT create_tenant_policies('service_catalog');
SELECT create_tenant_policies('patients');
SELECT create_tenant_policies('appointments');
SELECT create_tenant_policies('reminders');
SELECT create_tenant_policies('anamnesis_templates');
SELECT create_tenant_policies('dashboard_users');
SELECT create_tenant_policies('conversation_metrics');
SELECT create_tenant_policies('knowledge_chunks');
SELECT create_tenant_policies('knowledge_gaps');
SELECT create_tenant_policies('docs_bronze');
SELECT create_tenant_policies('docs_silver');
SELECT create_tenant_policies('docs_gold_vectors');

DROP FUNCTION create_tenant_policies;
