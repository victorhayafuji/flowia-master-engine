import {
  ArrowRight,
  Bot,
  Calendar,
  Gauge,
  MessageSquare,
  Shield,
  Sparkles,
  Zap,
} from 'lucide-react'

const DEMO_MAIL =
  'mailto:contato@gaussix.com.br?subject=Demo%20FlowIA%20Sal%C3%A3o'

const FEATURES = [
  {
    icon: Calendar,
    title: 'Agenda operacional',
    text: 'Timeline por profissional, reagendamento drag-and-drop e visão do dia em tempo real.',
  },
  {
    icon: MessageSquare,
    title: 'Base de conhecimento',
    text: 'Preços e políticas via RAG — a IA consulta a fonte oficial antes de responder.',
  },
  {
    icon: Shield,
    title: 'Multi-tenant SaaS',
    text: 'Cada salão isolado por organização. WhatsApp white-label por cliente.',
  },
  {
    icon: Gauge,
    title: 'Observabilidade',
    text: 'Métricas scheduling_path — prove ROI do híbrido vs chatbot 100% LLM.',
  },
]

const STEPS = [
  { n: '01', title: 'Mensagem', text: 'Cliente no WhatsApp ou chat de teste' },
  { n: '02', title: 'Triage', text: 'Classifica preço, política ou agendamento' },
  { n: '03', title: 'Executor', text: 'Consulta catálogo e disponibilidade real' },
  { n: '04', title: 'Composer', text: 'Resposta natural — tokens≈0 no happy path' },
  { n: '05', title: 'Fallback', text: 'LLM só quando a conversa foge do script' },
]

const COMPARE = [
  { label: 'Agendamento', bad: '100% LLM', good: 'Executor + regras' },
  { label: 'Custo/turno', bad: 'Tokens sempre', good: '~0 tokens determinístico' },
  { label: 'Confiabilidade', bad: 'Alucinação possível', good: 'Overlap + M:N validados' },
]

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b-4 border-[var(--border)] bg-[var(--surface)] sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <span className="text-xl font-black uppercase tracking-tighter">FlowIA</span>
          <a href={DEMO_MAIL} className="btn-brutal btn-primary text-xs py-2 px-4 hidden sm:inline-flex">
            Agendar demo
          </a>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="max-w-6xl mx-auto px-4 py-16 md:py-24">
          <div className="inline-block mb-6 px-3 py-1 border-2 border-[var(--border)] font-mono text-xs font-bold uppercase">
            Agente Híbrido · Multi-tenant · Salões
          </div>
          <h1 className="text-4xl md:text-6xl font-black uppercase tracking-tight leading-[1.05] max-w-4xl">
            Recepcionista IA que conversa como humano.
            <span className="text-[var(--accent)]"> Agenda com precisão de sistema.</span>
          </h1>
          <p className="mt-6 text-lg md:text-xl max-w-2xl text-slate-600 dark:text-slate-400 leading-relaxed">
            FlowIA combina inteligência conversacional com motor determinístico de agendamento —
            menos custo de tokens, zero double booking, resposta em segundos.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <a href={DEMO_MAIL} className="btn-brutal btn-primary">
              Agendar demo <ArrowRight className="w-4 h-4" />
            </a>
            <a href="#como-funciona" className="btn-brutal btn-secondary">
              Ver como funciona
            </a>
          </div>
        </section>

        {/* Problem */}
        <section className="border-y-4 border-[var(--border)] bg-[var(--surface)]">
          <div className="max-w-6xl mx-auto px-4 py-16">
            <h2 className="text-2xl md:text-3xl font-black uppercase mb-8">O problema</h2>
            <ul className="grid md:grid-cols-3 gap-6">
              {[
                'WhatsApp caótico — recepção manual e horário comercial limitado',
                'Chatbots que inventam preço ou horário e confirmam sem registrar',
                'Agenda cega — dono sem visão do dia por profissional',
              ].map((item) => (
                <li key={item} className="card-brutal p-6 font-medium">{item}</li>
              ))}
            </ul>
          </div>
        </section>

        {/* Hybrid diff */}
        <section className="max-w-6xl mx-auto px-4 py-16">
          <div className="flex items-center gap-3 mb-4">
            <Sparkles className="w-8 h-8 text-[var(--accent)]" />
            <h2 className="text-2xl md:text-3xl font-black uppercase">Agente Híbrido</h2>
          </div>
          <p className="text-xl font-bold mb-8">Conversa generativa. Agendamento determinístico.</p>
          <div className="overflow-x-auto">
            <table className="w-full border-4 border-[var(--border)] font-mono text-sm">
              <thead>
                <tr className="border-b-4 border-[var(--border)] bg-[var(--accent)] text-[var(--background)]">
                  <th className="p-4 text-left font-black uppercase">Aspecto</th>
                  <th className="p-4 text-left font-black uppercase">Chatbot tradicional</th>
                  <th className="p-4 text-left font-black uppercase">FlowIA</th>
                </tr>
              </thead>
              <tbody>
                {COMPARE.map((row) => (
                  <tr key={row.label} className="border-b-2 border-[var(--border)]">
                    <td className="p-4 font-black">{row.label}</td>
                    <td className="p-4 text-slate-500">{row.bad}</td>
                    <td className="p-4 font-bold text-[var(--accent)]">{row.good}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-6 font-mono text-sm border-l-4 border-[var(--accent)] pl-4">
            A IA explica. O motor de agenda decide. A IA sabe quando <strong>não</strong> usar IA.
          </p>
        </section>

        {/* Features */}
        <section className="border-y-4 border-[var(--border)] bg-[var(--surface)]">
          <div className="max-w-6xl mx-auto px-4 py-16">
            <h2 className="text-2xl md:text-3xl font-black uppercase mb-10">Plataforma completa</h2>
            <div className="grid md:grid-cols-2 gap-6">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <article key={title} className="card-brutal p-6">
                  <Icon className="w-8 h-8 mb-4 text-[var(--accent)]" />
                  <h3 className="text-lg font-black uppercase mb-2">{title}</h3>
                  <p className="text-slate-600 dark:text-slate-400">{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="como-funciona" className="max-w-6xl mx-auto px-4 py-16">
          <div className="flex items-center gap-3 mb-10">
            <Bot className="w-8 h-8" />
            <h2 className="text-2xl md:text-3xl font-black uppercase">Como funciona</h2>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {STEPS.map((step) => (
              <div key={step.n} className="card-brutal p-4">
                <span className="font-mono text-[var(--accent)] font-black text-2xl">{step.n}</span>
                <h3 className="font-black uppercase mt-2 text-sm">{step.title}</h3>
                <p className="text-xs mt-2 text-slate-600 dark:text-slate-400">{step.text}</p>
              </div>
            ))}
          </div>
          <div className="mt-10 card-brutal p-6 inline-flex flex-wrap items-center gap-3 font-mono text-xs font-bold uppercase">
            <Zap className="w-4 h-4 text-[var(--accent)]" />
            <span className="border-2 border-emerald-600 text-emerald-700 dark:text-emerald-400 px-2 py-1">
              path=deterministic
            </span>
            <span>tokens≈0</span>
            <span className="text-slate-500">· slots reais do catálogo</span>
          </div>
        </section>

        {/* CTA */}
        <section className="border-t-4 border-[var(--border)] bg-[var(--accent)] text-[var(--background)]">
          <div className="max-w-6xl mx-auto px-4 py-16 text-center">
            <h2 className="text-3xl md:text-4xl font-black uppercase">Pronto para ver na prática?</h2>
            <p className="mt-4 text-lg opacity-90 max-w-xl mx-auto">
              Demo de 20 minutos: agenda, agente híbrido e métricas ao vivo.
            </p>
            <a
              href={DEMO_MAIL}
              className="btn-brutal mt-8 bg-[var(--background)] text-[var(--foreground)] border-[var(--background)]"
            >
              Agendar demo <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </section>
      </main>

      <footer className="border-t-4 border-[var(--border)] bg-[var(--surface)]">
        <div className="max-w-6xl mx-auto px-4 py-8 flex flex-col sm:flex-row justify-between gap-4 text-sm">
          <div>
            <span className="font-black uppercase">FlowIA</span>
            <span className="text-slate-500"> — um produto </span>
            <span className="font-bold">Gaussix</span>
          </div>
          <div className="font-mono text-xs text-slate-500">
            © 2026 Gaussix · Salões de beleza · SaaS multi-tenant
          </div>
        </div>
      </footer>
    </div>
  )
}
