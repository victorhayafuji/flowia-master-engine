import { Link } from 'react-router-dom'

const DEMO_MAIL =
  'mailto:contato@gaussix.com.br?subject=Demo%20FlowIA%20Sal%C3%A3o'

export function LandingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b-4 border-[var(--border)] bg-[var(--surface)] sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link to="/" className="text-xl font-black uppercase tracking-tighter">
            FlowIA
          </Link>
          <a href={DEMO_MAIL} className="btn-brutal btn-primary text-xs py-2 px-4 hidden sm:inline-flex">
            Agendar demo
          </a>
        </div>
      </header>
      {children}
      <footer className="border-t-4 border-[var(--border)] bg-[var(--surface)] mt-auto">
        <div className="max-w-6xl mx-auto px-4 py-8 flex flex-col sm:flex-row justify-between gap-4 text-sm">
          <div>
            <span className="font-black uppercase">FlowIA</span>
            <span className="text-slate-500"> — um produto </span>
            <span className="font-bold">Gaussix</span>
          </div>
          <div className="flex flex-wrap gap-4 font-mono text-xs">
            <Link to="/privacidade" className="underline hover:text-[var(--accent)]">
              Privacidade
            </Link>
            <Link to="/termos" className="underline hover:text-[var(--accent)]">
              Termos de uso
            </Link>
          </div>
          <div className="font-mono text-xs text-slate-500">
            © 2026 Gaussix · Salões de beleza · SaaS multi-tenant
          </div>
        </div>
      </footer>
    </div>
  )
}

export { DEMO_MAIL }
