import { useCallback, useEffect, useState } from "react"
import { useAuth } from "@/features/auth/AuthContext"
import { api } from "@/shared/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Activity, BarChart3 } from "lucide-react"

interface SchedulingKpi {
  days: number
  scheduling_turns: number
  deterministic_count: number
  llm_count: number
  deterministic_rate_pct: number
  by_channel: Record<string, number>
  avg_tokens_scheduling: number
}

interface ConversationRow {
  thread_id?: string
  agent_type?: string
  scheduling_path?: string | null
  triage_source?: string | null
  channel?: string | null
  tokens_total?: number
  created_at?: string
}

function PathBadge({ path }: { path: string | null | undefined }) {
  if (!path) return <span className="text-xs text-slate-400">—</span>
  const isDeterministic = path === "deterministic"
  return (
    <span
      className={`inline-block px-1.5 py-0.5 border-2 text-[10px] font-black uppercase ${
        isDeterministic
          ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
          : "border-[var(--accent)] text-[var(--accent)]"
      }`}
    >
      {path}
    </span>
  )
}

export function AgentObservability() {
  const { orgHeader } = useAuth()
  const [kpi, setKpi] = useState<SchedulingKpi | null>(null)
  const [conversations, setConversations] = useState<ConversationRow[]>([])
  const [channelFilter, setChannelFilter] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const channelQuery = channelFilter ? `&channel=${encodeURIComponent(channelFilter)}` : ""
      const [kpiRes, convRes] = await Promise.all([
        api.get(`/metrics/scheduling-observability?days=7${channelQuery}`, orgHeader),
        api.get("/metrics/conversations?limit=30", orgHeader),
      ])
      setKpi(kpiRes as SchedulingKpi)
      setConversations(convRes as ConversationRow[])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar métricas")
    } finally {
      setLoading(false)
    }
  }, [orgHeader, channelFilter])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
            <Activity className="w-6 h-6" /> Observabilidade do agente
          </h1>
          <p className="text-sm text-slate-500 mt-1 font-mono">
            KPIs híbridos — últimos 7 dias (dev only)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-bold uppercase text-slate-500">Canal</label>
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="border-2 border-[var(--border)] bg-[var(--surface)] px-2 py-1 font-mono text-xs"
          >
            <option value="">Todos</option>
            <option value="chat_test">chat_test</option>
            <option value="whatsapp">whatsapp</option>
          </select>
          <button
            type="button"
            onClick={() => void load()}
            className="px-3 py-1 border-2 border-[var(--border)] font-black text-xs uppercase bg-[var(--surface)]"
          >
            Atualizar
          </button>
        </div>
      </div>

      {error && (
        <div className="border-2 border-red-600 bg-red-50 dark:bg-red-950/30 p-4 font-mono text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {loading && !kpi ? (
        <p className="font-mono text-sm">Carregando...</p>
      ) : kpi ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="card-brutal">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-black uppercase flex items-center gap-2">
                <BarChart3 className="w-4 h-4" /> Path determinístico
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-black">{kpi.deterministic_rate_pct}%</p>
              <p className="text-xs font-mono text-slate-500 mt-1">
                {kpi.deterministic_count} / {kpi.scheduling_turns} turnos scheduling
              </p>
            </CardContent>
          </Card>
          <Card className="card-brutal">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-black uppercase">Tokens médios</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-black">{kpi.avg_tokens_scheduling}</p>
              <p className="text-xs font-mono text-slate-500 mt-1">por turno scheduling</p>
            </CardContent>
          </Card>
          <Card className="card-brutal">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-black uppercase">Por canal</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 font-mono text-xs">
              {Object.entries(kpi.by_channel).map(([ch, count]) => (
                <div key={ch} className="flex justify-between">
                  <span>{ch}</span>
                  <span className="font-black">{count}</span>
                </div>
              ))}
              {Object.keys(kpi.by_channel).length === 0 && (
                <span className="text-slate-400">Sem dados</span>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      <Card className="card-brutal">
        <CardHeader>
          <CardTitle className="text-sm font-black uppercase">Conversas recentes</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b-2 border-[var(--border)]">
                <th className="py-2 pr-4">Thread</th>
                <th className="py-2 pr-4">Agente</th>
                <th className="py-2 pr-4">Path</th>
                <th className="py-2 pr-4">Triage</th>
                <th className="py-2 pr-4">Canal</th>
                <th className="py-2 pr-4">Tokens</th>
              </tr>
            </thead>
            <tbody>
              {conversations.map((row) => (
                <tr key={row.thread_id} className="border-b border-slate-200 dark:border-slate-800">
                  <td className="py-2 pr-4 truncate max-w-[120px]">{row.thread_id?.slice(0, 8)}…</td>
                  <td className="py-2 pr-4">{row.agent_type ?? "—"}</td>
                  <td className="py-2 pr-4">
                    <PathBadge path={row.scheduling_path} />
                  </td>
                  <td className="py-2 pr-4">{row.triage_source ?? "—"}</td>
                  <td className="py-2 pr-4">{row.channel ?? "—"}</td>
                  <td className="py-2 pr-4">{row.tokens_total ?? 0}</td>
                </tr>
              ))}
              {conversations.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="py-4 text-slate-400">
                    Nenhuma conversa registrada
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
