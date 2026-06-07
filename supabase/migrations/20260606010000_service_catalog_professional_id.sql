-- Vincula serviço ao profissional responsável (agendamento via chat e catálogo)
ALTER TABLE service_catalog
    ADD COLUMN IF NOT EXISTS professional_id UUID REFERENCES professionals(id);

CREATE INDEX IF NOT EXISTS idx_svc_professional ON service_catalog(professional_id)
    WHERE professional_id IS NOT NULL;
