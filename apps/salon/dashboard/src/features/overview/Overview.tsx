import { Calendar, CheckCircle2, Clock, MessageCircle, UserX, Users } from "lucide-react"
import { Link } from "react-router-dom"
import { format } from "date-fns"
import { ptBR } from "date-fns/locale"
import { useAuth } from "@/features/auth/AuthContext"
import { GlassCard, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { PageHeader } from "@/components/PageHeader"
import { RowMenu } from "@/components/ui/row-menu"
import { updateAppointmentStatus } from "@/shared/lib/api"
import {
  ACTION_LABEL,
  DESTRUCTIVE_STATUSES,
  allowedTransitions,
} from "@/features/agenda/lib/appointmentStatus"
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
  const showAgentSummary = user?.role !== "professional"

  const handleStatusChange = async (appointmentId: string, status: string) => {
    try {
      await updateAppointmentStatus(appointmentId, status, orgHeader)
      await stats.refreshBoard()
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar status.")
    }
  }

  return (
    <div className="page-shell overflow-y-auto lg:overflow-hidden">
      <PageHeader title="Visão Geral" subtitle="Resumo operacional do salão para hoje" />
      <div className="space-y-8 shrink-0 mb-6">
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          <StatCard icon={<Calendar className="w-4 h-4 text-primary-500" />} label="Agendamentos Hoje" value={stats.appointmentsToday} to="/agenda" />
          <StatCard icon={<Clock className="w-4 h-4 text-amber-500" />} label="Em Atendimento" value={stats.counts.in_progress} to="/agenda" />
          <StatCard icon={<CheckCircle2 className="w-4 h-4 text-emerald-500" />} label="Concluídos" value={stats.counts.completed} to="/agenda" />
          <StatCard icon={<UserX className="w-4 h-4 text-rose-500" />} label="Faltas Hoje" value={stats.counts.no_show} to="/agenda" />
          <StatCard
            icon={<UserX className="w-4 h-4 text-rose-600" />}
            label="Faltas acumuladas"
            value={stats.totalNoShows}
            to={showAgentSummary ? "/patients?sort=faltas" : undefined}
          />
        </div>

        {showAgentSummary && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-black uppercase tracking-widest text-[var(--foreground)]/60">
                Assistente IA
              </h2>
            </div>
            <div className="grid gap-4 grid-cols-1 sm:grid-cols-3">
              <StatCard
                icon={<Users className="w-4 h-4 text-amber-600" />}
                label="Precisa de humano"
                value={stats.agentSummary.handoffsPending}
                to="/patients?handoff=1"
                urgent={stats.agentSummary.handoffsPending > 0}
              />
              <StatCard
                icon={<MessageCircle className="w-4 h-4 text-emerald-600" />}
                label="Agenda via WhatsApp hoje"
                value={stats.agentSummary.appointmentsWhatsappToday}
              />
              <StatCard
                icon={<MessageCircle className="w-4 h-4 text-slate-500" />}
                label="Conversas na semana"
                value={stats.agentSummary.conversationsThisWeek}
              />
            </div>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2 lg:flex-1 lg:min-h-0">
        <GlassCard className="lg:flex lg:flex-col lg:min-h-0">
          <CardHeader className="shrink-0">
            <CardTitle>Quadro de Hoje</CardTitle>
            <CardDescription>Quem atende, qual serviço e quando.</CardDescription>
          </CardHeader>
          <CardContent className="lg:panel-scroll lg:flex-1 lg:min-h-0 pr-2">
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
                            {allowedTransitions(appt.status || "").length > 0 && (
                              <RowMenu
                                label="Alterar status"
                                items={allowedTransitions(appt.status || "").map((target) => ({
                                  label: ACTION_LABEL[target] ?? target,
                                  onClick: () => handleStatusChange(appt.id, target),
                                  destructive: DESTRUCTIVE_STATUSES.has(target),
                                  testId: `board-status-${target}`,
                                }))}
                              />
                            )}
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

        <GlassCard className="lg:flex lg:flex-col lg:min-h-0">
          <CardHeader className="shrink-0">
            <CardTitle>Próximos Horários</CardTitle>
            <CardDescription>Agenda dos próximos dias.</CardDescription>
          </CardHeader>
          <CardContent className="lg:panel-scroll lg:flex-1 lg:min-h-0 pr-2">
            {stats.upcoming.length === 0 ? (
              <EmptyState text="Nenhum agendamento próximo." />
            ) : (
              <div className="space-y-3">
                {stats.upcoming.map((appt) => (
                  <div
                    key={appt.id}
                    className="flex items-center gap-4 p-3 bg-[var(--background)] border-2 border-[var(--border)]"
                  >
                    <div className="bg-[var(--accent)]/10 text-[var(--accent)] p-2 font-mono font-bold border-2 border-[var(--border)] text-center">
                      <div className="text-[10px] uppercase leading-tight">
                        {format(new Date(appt.scheduled_at), "EEE dd/MM", { locale: ptBR })}
                      </div>
                      <div>{hhmm(appt.scheduled_at)}</div>
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

function StatCard({
  icon,
  label,
  value,
  to,
  urgent = false,
}: {
  icon: React.ReactNode
  label: string
  value: number
  to?: string
  urgent?: boolean
}) {
  const card = (
    <GlassCard
      className={`h-full ${urgent ? "border-[var(--accent)] shadow-[4px_4px_0px_0px_var(--accent)]" : ""}`}
    >
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className={`text-sm font-medium ${urgent ? "text-[var(--accent)]" : ""}`}>
          {label}
        </CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
      </CardContent>
    </GlassCard>
  )
  if (!to) return card
  return (
    <Link to={to} className="block h-full hover-lift" aria-label={label}>
      {card}
    </Link>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-slate-400">
      <p>{text}</p>
    </div>
  )
}
