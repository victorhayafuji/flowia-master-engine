import { Calendar, Users } from "lucide-react"
import { useAuth } from "@/features/auth/AuthContext"
import { GlassCard, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { useOverviewStats } from "./hooks/useOverviewStats"

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

        <div className="grid gap-6 md:grid-cols-2">
          <GlassCard className="bg-gradient-to-br from-primary-500/10 to-primary-600/10 border-primary-500/20">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Agendamentos Hoje</CardTitle>
              <Calendar className="w-4 h-4 text-primary-500" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{stats.appointmentsToday}</div>
            </CardContent>
          </GlassCard>

          <GlassCard>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Clientes Cadastrados</CardTitle>
              <Users className="w-4 h-4 text-slate-500" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{stats.patients}</div>
            </CardContent>
          </GlassCard>
        </div>
      </div>

      <GlassCard className="flex flex-col min-h-0 flex-1">
        <CardHeader className="shrink-0">
          <CardTitle>Próximos Horários</CardTitle>
          <CardDescription>Agenda dos próximos dias.</CardDescription>
        </CardHeader>
        <CardContent className="panel-scroll flex-1 min-h-0 pr-2">
          {stats.upcoming.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <p>Nenhum agendamento próximo.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {stats.upcoming.map((appt) => {
                const date = new Date(appt.scheduled_at)
                return (
                  <div
                    key={appt.id}
                    className="flex items-center gap-4 p-3 bg-[var(--background)] border-2 border-[var(--border)]"
                  >
                    <div className="bg-[var(--accent)]/10 text-[var(--accent)] p-2 font-mono font-bold border-2 border-[var(--border)]">
                      {date.getHours().toString().padStart(2, "0")}:{date.getMinutes().toString().padStart(2, "0")}
                    </div>
                    <div>
                      <p className="font-bold uppercase tracking-tight text-sm">{appt.patient?.name || "Cliente"}</p>
                      <p className="text-xs text-[var(--foreground)]/60 font-mono">{appt.service?.name || "Serviço"}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </GlassCard>
    </div>
  )
}
