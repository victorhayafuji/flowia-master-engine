-- Formaliza `knowledge_gaps` (tabela legada que tinha apenas id + organization_id)
-- para CAPTURAR as perguntas que o assistente não respondeu a partir da base.
-- Aditivo e idempotente: ADD COLUMN IF NOT EXISTS não afeta dados existentes (0 linhas hoje).
-- RLS já está habilitada com tenant policies (migrations de fundação) — nada a alterar aqui.

ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS question TEXT;
ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS agent_type TEXT;
ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS occurrences INTEGER NOT NULL DEFAULT 1;
ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Dedup por org + pergunta (case-insensitive): incrementa occurrences em vez de duplicar linhas.
CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_gaps_org_question
    ON knowledge_gaps (organization_id, lower(question))
    WHERE question IS NOT NULL;

-- Consulta da observabilidade: top lacunas recentes por org.
CREATE INDEX IF NOT EXISTS idx_knowledge_gaps_org_seen
    ON knowledge_gaps (organization_id, last_seen_at DESC);

-- Upsert atômico: registra a lacuna ou incrementa as ocorrências. Chamado só pelo backend
-- (service role). Guarda contra entradas vazias.
CREATE OR REPLACE FUNCTION record_knowledge_gap(p_org UUID, p_question TEXT, p_agent TEXT DEFAULT NULL)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_org IS NULL OR p_question IS NULL OR length(btrim(p_question)) = 0 THEN
        RETURN;
    END IF;
    INSERT INTO knowledge_gaps (organization_id, question, agent_type)
    VALUES (p_org, left(btrim(p_question), 500), p_agent)
    ON CONFLICT (organization_id, lower(question)) WHERE question IS NOT NULL
    DO UPDATE SET occurrences = knowledge_gaps.occurrences + 1,
                  last_seen_at = NOW(),
                  agent_type = COALESCE(EXCLUDED.agent_type, knowledge_gaps.agent_type);
END;
$$;

-- Função interna: não expor a anon/authenticated (service role bypassa grants).
REVOKE ALL ON FUNCTION record_knowledge_gap(UUID, TEXT, TEXT) FROM PUBLIC;
