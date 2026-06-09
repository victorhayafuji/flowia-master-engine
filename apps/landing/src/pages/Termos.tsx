import { Link } from 'react-router-dom'
import { LandingLayout } from '../components/LandingLayout'

export default function TermosPage() {
  return (
    <LandingLayout>
      <article className="max-w-3xl mx-auto px-4 py-16">
        <p className="font-mono text-xs uppercase text-amber-700 border-2 border-amber-600 p-3 mb-8">
          DRAFT — rascunho técnico. Não substitui assessoria jurídica.
        </p>
        <h1 className="text-4xl font-black uppercase">Termos de Uso</h1>
        <p className="text-sm text-slate-500 mt-2">Versão 2026-06 · FlowIA / Gaussix</p>

        <section className="mt-8 space-y-4 text-base leading-relaxed">
          <p>
            Estes termos regem o uso da plataforma FlowIA (dashboard, API, assistente WhatsApp)
            por salões contratantes.
          </p>
          <p>
            O salão é controlador dos dados de seus clientes; a Gaussix é operadora. O salão deve
            informar titulares e cumprir a LGPD na relação com clientes finais.
          </p>
          <p>
            É proibido usar o serviço para spam, fraude, acesso cross-tenant ou coleta de dados
            sem finalidade legítima.
          </p>
          <p>
            O assistente usa IA (OpenAI). Confirmações de agendamento dependem de
            ferramentas validadas; respostas podem conter imprecisões.
          </p>
          <p>
            Consulte também a{' '}
            <Link to="/privacidade" className="underline font-bold">
              Política de Privacidade
            </Link>
            .
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
