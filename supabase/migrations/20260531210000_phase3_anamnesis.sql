-- Migração Fase 3: Pré e Pós-Atendimento (Anamnese e Recall)

-- 1. Adicionar coluna de Recall na tabela de serviços
ALTER TABLE service_catalog 
ADD COLUMN IF NOT EXISTS recall_days INTEGER DEFAULT 0;

-- 2. Criar tabela de Respostas de Anamnese
CREATE TABLE IF NOT EXISTS anamnesis_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Habilitar RLS e Políticas
ALTER TABLE anamnesis_responses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation_anamnesis_responses"
    ON anamnesis_responses
    FOR ALL
    USING (organization_id = NULLIF(current_setting('app.current_org_id', TRUE), '')::uuid);

-- 4. Adicionar Trigger para updated_at (opcional, mas boa prática)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_anamnesis_responses_modtime ON anamnesis_responses;

CREATE TRIGGER update_anamnesis_responses_modtime
    BEFORE UPDATE ON anamnesis_responses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
