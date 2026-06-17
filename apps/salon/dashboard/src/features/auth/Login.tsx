import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Lock, ArrowRight, Zap } from "lucide-react"
import { useAuth } from "@/features/auth/AuthContext"
import { Wordmark } from "@/components/ui/Wordmark"

export function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const navigate = useNavigate()
  const { devLogin, session, loginWithCredentials } = useAuth()

  useEffect(() => {
    if (session) {
      navigate("/", { replace: true })
    }
  }, [session, navigate])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError("")

    try {
      await loginWithCredentials(email, password)
      navigate("/", { replace: true })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro de autenticação")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-[var(--background)] bg-glow font-sans overflow-hidden">

      {/*
        Extreme Asymmetry:
        Left Side (60%) - Massive Typographic Hero
      */}
      <div className="hidden lg:flex lg:w-[60%] flex-col justify-between p-12 border-r border-[var(--border)] relative">
        {/* Technical grid texture */}
        <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none"></div>

        <div className="z-10">
          <Wordmark size="md" />
        </div>

        <div className="z-10 mt-auto mb-24 max-w-2xl">
          <h1 className="font-display gradient-text text-[5.5rem] leading-[0.9] tracking-tight break-words" style={{ fontFamily: "var(--font-display)" }}>
            FlowIA
          </h1>
          <p className="mt-8 text-lg font-mono uppercase font-bold text-[var(--muted)] max-w-md border-l-2 border-[var(--accent)] pl-6 py-2">
            Atendimento e agendamento com IA — o SaaS proprietário da GAUSSIX. Acesso restrito a administradores.
          </p>
        </div>

        <div className="z-10 font-mono text-xs font-bold uppercase tracking-widest text-[var(--muted)]">
          GAUSSIX © {new Date().getFullYear()} // FlowIA v1.1.0
        </div>
      </div>

      {/* 
        Right Side (40%) - Raw Login Form
      */}
      <div className="w-full lg:w-[40%] flex flex-col justify-center p-8 sm:p-16 xl:p-24 relative">

        <div className="w-full max-w-md mx-auto">
          {/* Mobile Logo */}
          <div className="lg:hidden mb-16">
            <Wordmark size="md" />
          </div>

          <div className="mb-12">
            <h2 className="text-3xl font-bold uppercase tracking-tight">Autenticação</h2>
            <div className="h-1 w-16 brand-bar mt-4 rounded-full"></div>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            {error && (
              <div className="p-4 glass-panel border-l-4 border-[var(--danger)] font-mono text-sm font-bold uppercase flex items-center gap-3 animate-in slide-in-from-top-2">
                <Zap className="w-4 h-4 text-[var(--danger)]" />
                {error}
              </div>
            )}
            
            <div className="space-y-2 group">
              <label className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--muted)] transition-colors group-focus-within:text-[var(--accent)] flex justify-between">
                <span>Identificação</span>
                <span className="text-[var(--muted)]">01</span>
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@salao.com"
                className="w-full px-5 py-4 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-glass)] text-[var(--foreground)] text-sm font-mono focus:outline-none focus:border-[var(--accent)] focus:glow-accent transition-all placeholder:text-[var(--muted)]"
                required
              />
            </div>
            
            <div className="space-y-2 group">
              <label className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--muted)] transition-colors group-focus-within:text-[var(--accent)] flex justify-between">
                <span>Chave de Acesso</span>
                <span className="text-[var(--muted)]">02</span>
              </label>
              <div className="relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-5 py-4 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-glass)] text-[var(--foreground)] text-sm font-mono focus:outline-none focus:border-[var(--accent)] focus:glow-accent transition-all placeholder:text-[var(--muted)] pr-12"
                  required
                />
                <Lock className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
              </div>
            </div>

            <button 
              type="submit" 
              className="w-full mt-8 flex items-center justify-between px-6 py-5 bg-[image:var(--grad)] text-white font-bold uppercase tracking-widest rounded-[var(--radius-md)] border border-transparent glow-accent hover:-translate-y-0.5 hover:brightness-110 active:translate-y-0 transition-all disabled:opacity-50 disabled:cursor-not-allowed group"
              disabled={loading}
            >
              <span>{loading ? "Processando..." : "Autorizar Acesso"}</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            
            {import.meta.env.DEV && devLogin && (
              <button
                type="button"
                className="w-full mt-6 py-4 font-mono text-xs font-bold uppercase tracking-widest rounded-[var(--radius-md)] border border-dashed border-[var(--border)] text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors hover:bg-[var(--purple-soft)]"
                onClick={async () => {
                  setLoading(true)
                  setError("")
                  const { error: err } = await devLogin()
                  if (err) {
                    setError(err.message)
                    setLoading(false)
                  } else {
                    window.location.href = '/'
                  }
                }}
                disabled={loading}
              >
                [ Modo Desenvolvedor ]
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  )
}
