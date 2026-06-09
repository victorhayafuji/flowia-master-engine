# FlowIA Master Engine - Roadmap Estratégico

**Foco ativo:** MVP salão (`PRODUCT_LINE=salon`) — dashboard, agendamento, RAG, multi-tenant. Capítulo 2 (Sales Analytics / SG-Vendas) é visão futura desacoplada do produto salão.

Este documento centraliza o planejamento estratégico e a arquitetura futura do projeto FlowIA Master Engine. O ecossistema está dividido em capítulos temáticos e universos de dados isolados por segurança.

---

## 🏗️ CAPÍTULO 1: AI Chatbot & CRM Analytics (Universo Externo)
**Objetivo:** Criador de experiências conversacionais autônomas para clientes e leads.
**Acesso a Dados:** Base de Conhecimento, Catálogo de Produtos (público) e Telemetria de Conversão.

### 🟢 Fase 1-3: Estabilização e Dashboard CRM (CONCLUÍDO)
- **Foco:** Persistência, RAG Semântico e Roteamento SDR/Suporte.

### 🟢 Fase 4: Data Lake & Auto-Vetorização (CONCLUÍDO)
- **Foco:** Ingestão de materiais brutos e OCR via OpenAI Vision.
- **Entregas:** Upload Bronze (Supabase Storage), pipeline Silver/Gold assíncrono, busca RAG tenant-aware, dashboard `/data-lake`.

### 🔵 Fase 5: Expansão Omnichannel (BLOQUEADO — aguardando API WhatsApp)
- **Foco:** Voz e integrações de canais externos (ex: WhatsApp e Slack).
- **Bloqueio:** Credenciais Meta/WhatsApp Business API ainda não disponíveis.
- **Infra pronta:** Webhook prod `https://flowia-api.onrender.com/api/v1/webhook/whatsapp` — código em `packages/integrations/webhook/`. Setup: [`WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md).
- **Próximo passo:** Configurar Meta Business API + campos `organizations.whatsapp_*` por tenant. Doc: [`WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md).

---

## 📈 CAPÍTULO 2: Sales Analytics (Universo Interno / Executivo)
**Objetivo:** Dashboards de alta fidelidade e IA analítica para tomada de decisão estratégica.
**⚠️ RESTRIÇÃO DE SEGURANÇA:** Este capítulo utiliza dados sensíveis do `SG-Vendas-Monitor` (Faturamento, Margem, Carteira Financeira). Estes dados são **ESTRITAMENTE ISOLADOS** do chatbot do Capítulo 1.

### 🚀 Visão Geral: "O Oráculo Interno"
Integração com o **Data Warehouse Executivo** para consultas estratégicas via interface interna protegida.

### 🧩 Pilares do Capítulo 2:
1.  **Data Warehouse Integration:** Consumo de `fato_faturamento` e `fato_carteira_v2`.
2.  **Supply Chain Intelligence:** Lógica de CKD e previsão de reposição (Ordens de Compra).
3.  **High-Fidelity Dashboard (Neon/Dark):** Faturamento vs Meta por Departamento (DPH, UD, PETS).
4.  **IA Analítica (Internal Only):** Consultas Text-to-SQL em ambiente controlado para diretoria.

### 🤖 Copilot Interno (Dashboard Chat Widget)
**Objetivo:** Reaproveitar o widget de chat flutuante interno (atualmente em modo de testes) para empoderar a equipe operacional e de vendas com produtividade e automação em tempo real.

*   **Pilar 1: O Oráculo dos Leads (Sales Copilot)**
    *   *Foco:* Consulta em linguagem natural à base de dados do CRM de leads.
    *   *Exemplo:* *"Quais leads estão estagnados na etapa de proposta há mais de 3 dias?"* ou *"Me dê o resumo do lead Victor"*.
    *   *UX:* Respostas rápidas em texto com cards dinâmicos inline e links para a ficha do lead no CRM.
*   **Pilar 2: O Preparador de Pitch (Lead Briefing)**
    *   *Foco:* Geração de roteiros de abordagem sob medida com base no histórico de conversas do lead com o bot externo.
    *   *Exemplo:* *"Prepare um roteiro para abordar a Acme Corp (Lead #1042)."*
    *   *UX:* Análise de sentimentos e pontos de atrito resumidos em tópicos acionáveis para o vendedor.
*   **Pilar 3: Assistente do Criador de Fluxo (Prompt-to-Flow)**
    *   *Foco:* Criação e depuração guiada de novos fluxos conversacionais via chat.
    *   *Exemplo:* *"Adicione um nó de reembolso ao fluxo de suporte"*.
    *   *UX:* Geração de rascunhos em formato JSON com botões inline para simulação imediata no playground.
*   **Pilar 4: Terminal Conversacional de Operações (Text-to-Action)**
    *   *Foco:* Automação de tarefas da dashboard via comandos de texto.
    *   *Exemplo:* *"Gere o relatório PDF de faturamento de abril e envie para financeiro@flowia.com.br"*.
    *   *UX:* Renderização de widgets dinâmicos de progresso e ações interativas no próprio chat.

---

## 📊 CAPÍTULO 3: Workspace Analítico (Estilo Databricks UI) (CONCLUÍDO)
**Objetivo:** Dar visibilidade e controle direto sobre o nosso lakehouse, aproximando o usuário final das camadas Bronze, Silver e Gold e unificando o nosso motor de RAG e consultas SQL assistidas por IA.

### 🧩 Pilares do Capítulo 3:
1. **Catalog Explorer (Unity Catalog):**
   - Navegador de árvore estrutural para navegar pelas camadas Bronze, Silver e Gold.
   - Exibição de esquemas (nome da coluna, tipo, descrição) e prévia em tabela (data sample).
2. **SQL Editor com Assistente de IA:**
   - Editor de queries SQL integrado com botão de execução rápida.
   - Geração de SQL por IA (OpenAI) a partir de instruções em linguagem natural.
   - Visualização por gráficos dinâmica integrada (Chart.js) para agregações numéricas.
3. **Data Lineage (Linhagem de Dados):**
   - Grafo de fluxo SVG interativo e animado mostrando a linhagem Bronze -> Silver -> Gold -> Dashboard.
   - Animação por CSS pulsação nos nós selecionados e rotas mapeadas.

---

## 🛡️ SEGURANÇA E GOVERNANÇA DE DADOS
- **Isolamento de Contexto:** A IA do Chatbot (SDR/Suporte) não possui "awareness" ou acesso às tabelas financeiras do Capítulo 2.
- **Camada de Permissões e LGPD:** O acesso ao Data Warehouse e às tabelas internas é restrito por controle de acesso (RBAC). Usuários sem perfil de Administrador ou Executivo visualizam dados sensíveis de leads (e-mail e telefone) mascarados automaticamente nas tabelas Silver e Bronze (Fase 4 - Concluída).
- **Auditoria:** Toda consulta realizada ao banco de dados executivo será logada para auditoria de compliance.

---

## 📅 CAPÍTULO 4: Motor de Agendamento Multi-Tenant (CONCLUÍDO)
**Objetivo:** Centralizar e escalar agendamentos para dezenas de clientes (B2B), transformando a FlowIA em uma plataforma SaaS omnichannel real.

### 🧩 Pilares do Capítulo 4:
1. **Multi-Tenancy Foundation (Row-Level Security):**
   - Políticas de banco de dados onde `Org A` não enxerga dados de `Org B`.
2. **AI Nodes & Lembretes Autônomos:**
   - Agendamento de disparo de lembretes ativos (via API de Background Tasks / APScheduler).
   - Confirmação de presença e política de Reagendamento guiada por IA.
3. **Anamnese & Pós-Atendimento (NPS):** **DEFERIDO**
   - Schema (`anamnesis_*`, `nps_*`) existe; fluxo de produto não implementado no MVP salão.
   - Questionário dinâmico pré-consulta e pesquisa pós-serviço ficam para ciclo futuro.
4. **Operação de Equipe & Disponibilidade Real:**
   - Motor de disponibilidade lê dados reais do profissional (`working_hours`, `break_times`, `appointment_buffer_minutes`, `schedule_blocks`) no fuso da organização — fim dos horários hardcoded.
   - Elegibilidade serviço↔profissional em M:N (`service_professionals`); fallback para todos os profissionais ativos quando vazio.
   - Agenda com duas visões: **Operacional** (timeline/Gantt por profissional — default) e **Semana** (grade 5 dias de **um** profissional; visão da equipe na Operacional).
   - **Overview operacional** (`GET /dashboard/today-board`): atendimentos por profissional, status e horário de fim estimado.
   - Login de funcionário via role `professional` (JWT com `professional_id`, nav e queries reduzidas à própria agenda).
   - **Stub de pagamentos:** schema `appointment_payments` + pacote `packages/integrations/payments` (NoOp, `enabled=false`); execução deferida para Fase 2.

---

## Recuperador de Lucros — epics pós-Cap. 4 (Jun/2026)

Paradigma detalhado em [`CLAUDE.md` §4.5](../CLAUDE.md). Ordem acordada:

1. **Epic 4 — UI Catálogo** (concluído): horários/buffer/M:N no dashboard
2. **Epic 1A — No-show audit** (concluído): `no_show_count` na UI Clientes + Overview; refresh reminders no reagendamento
3. **Epic 1B — Lembretes WhatsApp:** implementado em `reminder_service.py` via `WhatsAppService` — requer credenciais Meta por org (Cap. 5)
4. **Epic 2 — Lei Salão Parceiro:** RBAC API + comissões — **adiado** até integração pagamentos/PDV
5. **Epic 3 — IA booking** (concluído): multi-pro `check_availability`, upsert telefone, validação M:N no create; **motor híbrido** (`routing.py` → `booking_executor` → `response_composer` → fallback LLM) + observability (`scheduling_path`, `triage_source`, `channel` em `conversation_metrics`)

---
*Documento atualizado em: 08/06/2026 (pós-merge motor híbrido)*
