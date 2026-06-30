import { useCallback, useEffect, useState } from "react"
import { AlertCircle, Check, Copy, Loader2, Monitor, Plus, Trash2 } from "lucide-react"
import { useAuth } from "@/features/auth/AuthContext"
import {
  createKioskDevice,
  listKioskDevices,
  revokeKioskDevice,
  type KioskDevice,
} from "@/shared/lib/api"

// Where the kiosk PWA is hosted (operator opens this on the tablet, then pastes the token).
const TOTEM_URL = import.meta.env.VITE_TOTEM_URL || "https://flowia-totem.onrender.com"

const inputClass =
  "w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono text-xs font-bold focus:outline-none focus:border-[var(--accent)]"

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      aria-label={`Copiar ${label}`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value)
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        } catch {
          // Clipboard may be unavailable (insecure context) — fail silently.
        }
      }}
      className="shrink-0 flex items-center gap-1 border-2 border-[var(--border)] bg-[var(--surface)] px-3 py-2 font-mono text-[10px] font-bold uppercase hover:bg-[var(--accent)] hover:text-[var(--background)] transition-colors"
    >
      {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "Copiado" : "Copiar"}
    </button>
  )
}

export function TotemDevices() {
  const { orgHeader, organizationId } = useAuth()
  const [loading, setLoading] = useState(true)
  const [devices, setDevices] = useState<KioskDevice[]>([])
  const [label, setLabel] = useState("")
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // The freshly-minted token, shown exactly once until the operator dismisses it.
  const [newToken, setNewToken] = useState<{ label: string; token: string } | null>(null)

  const load = useCallback(async () => {
    if (!organizationId) {
      setLoading(false)
      return
    }
    try {
      const res = await listKioskDevices(orgHeader)
      setDevices((res?.data as KioskDevice[]) || [])
    } catch (err) {
      console.error("Erro ao carregar totems:", err)
    } finally {
      setLoading(false)
    }
  }, [orgHeader, organizationId])

  useEffect(() => {
    void load()
  }, [load])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = label.trim()
    if (!trimmed) return
    setCreating(true)
    setError(null)
    try {
      const res = await createKioskDevice(trimmed, orgHeader)
      setNewToken({ label: res.data.label, token: res.data.token })
      setLabel("")
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar dispositivo.")
    } finally {
      setCreating(false)
    }
  }

  const handleRevoke = async (id: string) => {
    if (!window.confirm("Revogar este totem? O tablet pareado deixará de funcionar.")) return
    try {
      await revokeKioskDevice(id, orgHeader)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao revogar dispositivo.")
    }
  }

  const active = devices.filter((d) => d.is_active)

  return (
    <div className="card-brutal p-4 space-y-4">
      <div className="flex items-center gap-2 border-b-2 border-[var(--border)] pb-3">
        <Monitor className="w-5 h-5 text-[var(--accent)]" />
        <h3 className="font-bold uppercase tracking-widest text-sm">Totem de autoatendimento</h3>
      </div>

      <p className="font-mono text-xs text-[var(--foreground)]/70">
        Gere um token, abra <code className="text-[var(--accent)]">{TOTEM_URL}</code> no tablet e cole
        o token para parear. O cliente poderá agendar, fazer check-in e tirar dúvidas sozinho.
      </p>

      {/* One-time token reveal */}
      {newToken && (
        <div className="rounded-[var(--radius-lg)] border-2 border-[var(--accent)] bg-[var(--purple-soft)] p-4 space-y-2">
          <p className="font-mono text-xs font-bold">
            Token de “{newToken.label}” criado. Copie agora — ele não será mostrado de novo.
          </p>
          <div className="flex items-stretch gap-2">
            <code className="flex-1 min-w-0 truncate bg-[var(--background)] border-2 border-[var(--border)] px-2 py-2 font-mono text-xs">
              {newToken.token}
            </code>
            <CopyButton value={newToken.token} label="token" />
          </div>
          <button
            type="button"
            onClick={() => setNewToken(null)}
            className="font-mono text-[10px] font-bold uppercase underline text-[var(--foreground)]/60"
          >
            Já copiei, fechar
          </button>
        </div>
      )}

      {/* Create form */}
      <form onSubmit={handleCreate} className="flex flex-col sm:flex-row gap-2">
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className={inputClass}
          placeholder="Nome do totem (ex.: Recepção)"
          maxLength={80}
          autoComplete="off"
        />
        <button
          type="submit"
          disabled={creating || !label.trim()}
          className="shrink-0 flex justify-center items-center gap-2 px-4 py-2 bg-[image:var(--grad)] text-white font-bold uppercase tracking-widest text-xs rounded-[var(--radius-md)] glow-accent hover:-translate-y-0.5 disabled:opacity-50 transition-all"
        >
          {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          Gerar token
        </button>
      </form>

      {error && (
        <p className="flex items-center gap-2 font-mono text-xs font-bold text-[var(--danger)]">
          <AlertCircle className="w-4 h-4" /> {error}
        </p>
      )}

      {/* Device list */}
      {loading ? (
        <div className="flex justify-center py-4">
          <Loader2 className="w-5 h-5 animate-spin text-[var(--accent)]" />
        </div>
      ) : active.length === 0 ? (
        <p className="font-mono text-xs text-[var(--muted)]">Nenhum totem pareado ainda.</p>
      ) : (
        <ul className="space-y-2">
          {active.map((d) => (
            <li
              key={d.id}
              className="flex items-center justify-between gap-3 border-2 border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            >
              <div className="min-w-0">
                <p className="font-mono text-xs font-bold truncate">{d.label}</p>
                <p className="font-mono text-[10px] text-[var(--foreground)]/50">
                  {d.last_seen_at
                    ? `Visto por último: ${new Date(d.last_seen_at).toLocaleString("pt-BR")}`
                    : "Ainda não pareado"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleRevoke(d.id)}
                aria-label={`Revogar ${d.label}`}
                className="shrink-0 flex items-center gap-1 border-2 border-[var(--border)] px-2 py-1.5 font-mono text-[10px] font-bold uppercase hover:bg-[var(--danger)] hover:text-white hover:border-[var(--danger)] transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" /> Revogar
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
