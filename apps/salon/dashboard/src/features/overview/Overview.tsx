import { Calendar, CheckCircle2, Clock, UserX, Users } from "lucide-react"
import { useAuth } from "@/features/auth/AuthContext"
import { GlassCard, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { useOverviewStats } from "./hooks/useOverviewStats"

function hhmm(iso: string): string {
  const d = new Date(iso)
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`
}

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  confirmed: "Confirmado",
  arrived: "Aguardando",
  in_progress: "Em atendimento",
  completed: "Concluído",
  no_show: "Falta",
  cancelled: "Cancelado",
}

export function Overview() {
  const { user, orgHeader } = useAuth()
  const stats = useOverviewStats(user, orgHeader)

  return (
    <div className="page-shell">
      <div className="page-header space-y-8 shrink-0">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-50">Visão Geral</h1>
          <p className="text-slate-500 dark:text-slate-400">Resumo operacional do salão para hoje.</p>
        </div>

        <div className="grid gap-4 grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          <StatCard icon={<Calendar className="w-4 h-4 text-primary-500" />} label="Agendamentos Hoje" value={stats.appointmentsToday} />
          <StatCard icon={<Clock className="w-4 h-4 text-amber-500" />} label="Em Atendimento" value={stats.counts.in_progress} />
          <StatCard icon={<CheckCircle2 className="w-4 h-4 text-emerald-500" />} label="Concluídos" value={stats.counts.completed} />
          <StatCard icon={<UserX className="w-4 h-4 text-rose-500" />} label="Faltas Hoje" value={stats.counts.no_show} />
          <StatCard icon={<UserX className="w-4 h-4 text-rose-600" />} label="Faltas no Cadastro" value={stats.totalNoShows} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2 flex-1 min-h-0">
        <GlassCard className="flex flex-col min-h-0">
          <CardHeader className="shrink-0">
            <CardTitle>Quadro de Hoje</CardTitle>
            <CardDescription>Quem atende, qual serviço e quando.</CardDescription>
          </CardHeader>
          <CardContent className="panel-scroll flex-1 min-h-0 pr-2">
            {stats.board.length === 0 ? (
              <EmptyState text="Nenhum profissional ou agendamento para hoje." />
            ) : (
              <div className="space-y-4">
                {stats.board.map((item) => (
                  <div key={item.professional.id || "none"}>
                    <div className="flex items-center gap-2 mb-2">
                      <Users className="w-4 h-4 text-[var(--accent)]" />
                      <span className="font-bold uppercase tracking-tight text-sm">{item.professional.name}</span>
                      <span className="text-xs font-mono text-[var(--foreground)]/50">
                        {item.appointments.length} agend.
                      </span>
                    </div>
                    {item.appointments.length === 0 ? (
                      <p className="text-xs text-[var(--foreground)]/40 font-mono pl-6">Livre o dia todo.</p>
                    ) : (
                      <div className="space-y-2 pl-6">
                        {item.appointments.map((appt) => (
                          <div
                            key={appt.id}
                            className="flex items-center gap-3 p-2 bg-[var(--background)] border-2 border-[var(--border)]"
                          >
                            <div className="font-mono font-bold text-xs whitespace-nowrap">
                              {hhmm(appt.scheduled_at)}
                              {appt.ends_at ? `–${hhmm(appt.ends_at)}` : ""}
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-bold text-sm truncate">{appt.patient?.name || "Cliente"}</p>
                              <p className="text-xs text-[var(--foreground)]/60 font-mono truncate">
                                {appt.service?.name || "Serviço"}
                              </p>
                            </div>
                            <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 border-2 border-[var(--border)] whitespace-nowrap">
                              {STATUS_LABELS[appt.status || ""] || appt.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </GlassCard>

        <GlassCard className="flex flex-col min-h-0">
          <CardHeader className="shrink-0">
            <CardTitle>Próximos Horários</CardTitle>
            <CardDescription>Agenda dos próximos dias.</CardDescription>
          </CardHeader>
          <CardContent className="panel-scroll flex-1 min-h-0 pr-2">
            {stats.upcoming.length === 0 ? (
              <EmptyState text="Nenhum agendamento próximo." />
            ) : (
              <div className="space-y-3">
                {stats.upcoming.map((appt) => (
                  <div
                    key={appt.id}
                    className="flex items-center gap-4 p-3 bg-[var(--background)] border-2 border-[var(--border)]"
                  >
                    <div className="bg-[var(--accent)]/10 text-[var(--accent)] p-2 font-mono font-bold border-2 border-[var(--border)]">
                      {hhmm(appt.scheduled_at)}
                    </div>
                    <div className="min-w-0">
                      <p className="font-bold uppercase tracking-tight text-sm truncate">{appt.patient?.name || "Cliente"}</p>
                      <p className="text-xs text-[var(--foreground)]/60 font-mono truncate">
                        {appt.service?.name || "Serviço"}
                        {appt.professional?.name ? ` · ${appt.professional.name}` : ""}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </GlassCard>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <GlassCard>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{label}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
      </CardContent>
    </GlassCard>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-slate-400">
      <p>{text}</p>
    </div>
  )
}
