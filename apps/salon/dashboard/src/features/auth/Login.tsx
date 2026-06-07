import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Lock, ArrowRight, Zap } from "lucide-react"
import { useAuth } from "@/features/auth/AuthContext"
import { api } from "@/shared/lib/api"

export function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const navigate = useNavigate()
  const { devLogin, session } = useAuth()

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
      const data = await api.post('/auth/login', {
        username: email,
        password: password
      })

      if (data.status === 'success') {
        window.location.href = '/'
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro de autenticação")
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-[var(--background)] font-sans overflow-hidden">
      
      {/* 
        Extreme Asymmetry: 
        Left Side (60%) - Massive Typographic Hero
      */}
      <div className="hidden lg:flex lg:w-[60%] flex-col justify-between p-12 border-r-4 border-[var(--border)] relative bg-[var(--surface)]">
        {/* Background Grid Pattern for texture */}
        <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: 'radial-gradient(var(--foreground) 1px, transparent 1px)', backgroundSize: '32px 32px' }}></div>
        
        <div className="z-10 flex items-center gap-3">
          <div className="w-12 h-12 bg-[var(--foreground)] text-[var(--background)] flex items-center justify-center font-black text-2xl tracking-tighter shadow-[4px_4px_0px_0px_var(--accent)] border-2 border-[var(--foreground)]">
            F.
          </div>
          <span className="font-mono font-bold tracking-widest uppercase text-sm">Engine</span>
        </div>

        <div className="z-10 mt-auto mb-24 max-w-2xl">
          <h1 className="text-[6rem] leading-[0.85] font-black tracking-tighter uppercase break-words text-[var(--foreground)]">
            Master<br />
            <span className="text-[var(--accent)]">Engine</span>
          </h1>
          <p className="mt-8 text-xl font-mono uppercase font-bold text-[var(--foreground)]/60 max-w-md border-l-4 border-[var(--accent)] pl-6 py-2">
            Protocolo de segurança ativado. Acesso restrito a administradores do sistema.
          </p>
        </div>
        
        <div className="z-10 font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/40">
          Flowia Systems © {new Date().getFullYear()} // v1.1.0-STABLE
        </div>
      </div>

      {/* 
        Right Side (40%) - Raw Login Form
      */}
      <div className="w-full lg:w-[40%] flex flex-col justify-center p-8 sm:p-16 xl:p-24 bg-[var(--background)] relative">
        
        <div className="w-full max-w-md mx-auto">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-3 mb-16">
            <div className="w-12 h-12 bg-[var(--foreground)] text-[var(--background)] flex items-center justify-center font-black text-2xl tracking-tighter shadow-[4px_4px_0px_0px_var(--accent)] border-2 border-[var(--foreground)]">
              F.
            </div>
            <span className="font-mono font-bold tracking-widest uppercase text-sm">Engine</span>
          </div>

          <div className="mb-12">
            <h2 className="text-3xl font-black uppercase tracking-tight">Autenticação</h2>
            <div className="h-1 w-16 bg-[var(--accent)] mt-4"></div>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            {error && (
              <div className="p-4 bg-[var(--foreground)] text-[var(--background)] border-l-8 border-red-500 font-mono text-sm font-bold uppercase flex items-center gap-3 shadow-[4px_4px_0px_0px_var(--border)] animate-in slide-in-from-top-2">
                <Zap className="w-4 h-4 text-red-500" />
                {error}
              </div>
            )}
            
            <div className="space-y-2 group">
              <label className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--foreground)]/70 transition-colors group-focus-within:text-[var(--accent)] flex justify-between">
                <span>Identificação</span>
                <span className="text-[var(--foreground)]/30">01</span>
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@salao.com"
                className="w-full px-5 py-4 border-2 border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)] shadow-[4px_4px_0px_0px_var(--border)] text-sm font-mono focus:outline-none focus:border-[var(--accent)] focus:shadow-[6px_6px_0px_0px_var(--accent)] transition-all placeholder:text-[var(--foreground)]/30 rounded-none"
                required
              />
            </div>
            
            <div className="space-y-2 group">
              <label className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--foreground)]/70 transition-colors group-focus-within:text-[var(--accent)] flex justify-between">
                <span>Chave de Acesso</span>
                <span className="text-[var(--foreground)]/30">02</span>
              </label>
              <div className="relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-5 py-4 border-2 border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)] shadow-[4px_4px_0px_0px_var(--border)] text-sm font-mono focus:outline-none focus:border-[var(--accent)] focus:shadow-[6px_6px_0px_0px_var(--accent)] transition-all placeholder:text-[var(--foreground)]/30 rounded-none pr-12"
                  required
                />
                <Lock className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground)]/30" />
              </div>
            </div>

            <button 
              type="submit" 
              className="w-full mt-8 flex items-center justify-between px-6 py-5 bg-[var(--foreground)] text-[var(--background)] font-black uppercase tracking-widest border-2 border-[var(--border)] shadow-[6px_6px_0px_0px_var(--accent)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[4px_4px_0px_0px_var(--accent)] active:translate-y-[6px] active:translate-x-[6px] active:shadow-[0px_0px_0px_0px_var(--accent)] transition-all disabled:opacity-50 disabled:cursor-not-allowed group rounded-none"
              disabled={loading}
            >
              <span>{loading ? "Processando..." : "Autorizar Acesso"}</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            
            {import.meta.env.DEV && devLogin && (
              <button
                type="button"
                className="w-full mt-6 py-4 font-mono text-xs font-bold uppercase tracking-widest border-2 border-dashed border-[var(--foreground)]/20 text-[var(--foreground)]/50 hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors hover:bg-[var(--accent)]/5 rounded-none"
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
