import { Link } from 'react-router-dom'
import { LandingLayout } from '../components/LandingLayout'

export default function PrivacidadePage() {
  return (
    <LandingLayout>
      <article className="max-w-3xl mx-auto px-4 py-16 prose prose-slate dark:prose-invert">
        <p className="font-mono text-xs uppercase text-amber-700 border-2 border-amber-600 p-3 mb-8">
          DRAFT — rascunho técnico. Não substitui assessoria jurídica.
        </p>
        <h1 className="text-4xl font-black uppercase">Política de Privacidade</h1>
        <p className="text-sm text-slate-500">Versão 2026-06 · FlowIA / Gaussix</p>

        <section className="mt-8 space-y-4 text-base leading-relaxed">
          <h2 className="text-xl font-black uppercase">Quem somos</h2>
          <p>
            O FlowIA é operado pela Gaussix como plataforma SaaS para salões. Cada salão cliente
            é controlador dos dados de seus clientes finais; a Gaussix atua como operadora.
          </p>

          <h2 className="text-xl font-black uppercase">Dados tratados</h2>
          <p>
            Nome, telefone, e-mail, agendamentos, conversas via WhatsApp/chat, documentos da base
            de conhecimento e métricas operacionais (sem corpo completo de mensagens em telemetria).
          </p>

          <h2 className="text-xl font-black uppercase">Finalidades</h2>
          <p>
            Agendamento, atendimento via IA, suporte, segurança e melhoria do serviço, conforme
            bases legais da LGPD (contrato, consentimento, legítimo interesse).
          </p>

          <h2 className="text-xl font-black uppercase">Subprocessadores</h2>
          <p>
            Supabase, OpenAI, Meta (WhatsApp), Render — podem processar dados fora do
            Brasil conforme contratos dos provedores.
          </p>

          <h2 className="text-xl font-black uppercase">Retenção</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Dedup webhook: 7 dias</li>
            <li>Histórico de conversa (checkpoints): 90 dias</li>
            <li>Métricas: 365 dias</li>
          </ul>

          <h2 className="text-xl font-black uppercase">Seus direitos</h2>
          <p>
            Acesso, correção, eliminação, portabilidade e revogação de consentimento. Entre em
            contato com o salão (controlador) ou pelo canal de privacidade informado no aviso
            WhatsApp.
          </p>

          <h2 className="text-xl font-black uppercase">Consentimento</h2>
          <p>
            No primeiro contato via WhatsApp ou chat, você recebe aviso sobre tratamento de dados.
            Ao continuar a conversa, registra-se consentimento tácito.
          </p>
        </section>

        <p className="mt-12">
          <Link to="/" className="font-bold underline">
            ← Voltar
          </Link>
        </p>
      </article>
    </LandingLayout>
  )
}
