import { useEffect, useMemo, useState } from "react"
import { format } from "date-fns"
import { ptBR } from "date-fns/locale"
import { useAuth } from "@/features/auth/AuthContext"
import { Button } from "@/components/ui/button"
import { AgendaGrid } from "./components/AgendaGrid"
import { OperationalTimeline } from "./components/OperationalTimeline"
import { AgendaModals } from "./components/AgendaModals"
import { useAgenda } from "./hooks/useAgenda"
import type { AgendaView } from "./types"

export function Agenda() {
  const { user, orgHeader } = useAuth()
  const agenda = useAgenda(user, orgHeader)
  const [view, setView] = useState<AgendaView>("timeline")
  const [filterProfessionalId, setFilterProfessionalId] = useState<string>("")
  const [timelineDayIndex, setTimelineDayIndex] = useState(0)

  const professionals = agenda.options.professionals
  const timelineDay = agenda.days[timelineDayIndex] ?? agenda.days[0]
  const isProfessionalUser = user?.role === "professional" && !!user.professional_id

  const visibleProfessionals = useMemo(() => {
    if (isProfessionalUser && user?.professional_id) {
      return professionals.filter((p) => p.id === user.professional_id)
    }
    return professionals
  }, [professionals, isProfessionalUser, user?.professional_id])

  useEffect(() => {
    if (isProfessionalUser && user?.professional_id) {
      setFilterProfessionalId(user.professional_id)
      return
    }
    if (professionals.length === 0) return
    if (!filterProfessionalId || !professionals.some((p) => p.id === filterProfessionalId)) {
      setFilterProfessionalId(professionals[0].id)
    }
  }, [filterProfessionalId, isProfessionalUser, professionals, user?.professional_id])

  const selectedProfessionalName = useMemo(() => {
    return professionals.find((p) => p.id === filterProfessionalId)?.name ?? "Profissional"
  }, [filterProfessionalId, professionals])

  const weekAppointments = useMemo(() => {
    if (isProfessionalUser && user?.professional_id) {
      return agenda.appointments.filter((a) => a.professional_id === user.professional_id)
    }
    if (!filterProfessionalId) return []
    return agenda.appointments.filter((a) => a.professional_id === filterProfessionalId)
  }, [agenda.appointments, filterProfessionalId, isProfessionalUser, user?.professional_id])

  const timelineAppointments = useMemo(() => {
    if (isProfessionalUser && user?.professional_id) {
      return agenda.appointments.filter((a) => a.professional_id === user.professional_id)
    }
    return agenda.appointments
  }, [agenda.appointments, isProfessionalUser, user?.professional_id])

  const subtitle =
    view === "week"
      ? `Semana — ${selectedProfessionalName}`
      : `Equipe — ${format(timelineDay, "EEEE dd/MM", { locale: ptBR })}`

  return (
    <div className="page-shell">
      <div className="page-header mb-6 sm:mb-8 flex flex-col md:flex-row md:justify-between md:items-end border-b-4 border-[var(--border)] pb-6">
        <div>
          <h1 className="text-4xl font-black uppercase tracking-tight text-[var(--foreground)]">Agenda</h1>
          <p className="text-[var(--foreground)]/70 font-mono mt-1 uppercase text-sm font-bold">{subtitle}</p>
        </div>
        <div className="mt-4 md:mt-0 flex flex-wrap items-center gap-2">
          <div className="flex border-2 border-[var(--border)]">
            <button
              type="button"
              onClick={() => setView("timeline")}
              className={`px-3 py-2 text-xs font-bold uppercase ${view === "timeline" ? "bg-[var(--foreground)] text-[var(--background)]" : "bg-[var(--surface)]"}`}
            >
              Operacional
            </button>
            <button
              type="button"
              onClick={() => setView("week")}
              className={`px-3 py-2 text-xs font-bold uppercase border-l-2 border-[var(--border)] ${view === "week" ? "bg-[var(--foreground)] text-[var(--background)]" : "bg-[var(--surface)]"}`}
            >
              Semana
            </button>
          </div>
          <Button variant="default" onClick={() => agenda.setIsNewModalOpen(true)}>
            Novo Agendamento
          </Button>
        </div>
      </div>

      {!agenda.loading && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          {view === "week" && !isProfessionalUser && (
            <label className="flex items-center gap-2 text-xs font-bold uppercase">
              Profissional:
              <select
                value={filterProfessionalId}
                onChange={(e) => setFilterProfessionalId(e.target.value)}
                className="border-2 border-[var(--border)] bg-[var(--surface)] px-2 py-1 font-mono text-xs"
              >
                {visibleProfessionals.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {view === "timeline" && (
            <div className="flex items-center gap-1">
              {agenda.days.map((day, i) => (
                <button
                  key={day.toISOString()}
                  type="button"
                  onClick={() => setTimelineDayIndex(i)}
                  className={`px-2 py-1 text-xs font-mono font-bold border-2 border-[var(--border)] ${i === timelineDayIndex ? "bg-[var(--accent)] text-[var(--background)]" : "bg-[var(--surface)]"}`}
                >
                  {format(day, "EEE dd/MM", { locale: ptBR })}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {agenda.loading ? (
        <div className="border-4 border-[var(--border)] bg-[var(--surface)] flex-1 min-h-[240px] flex items-center justify-center">
          <div className="animate-spin rounded-none h-12 w-12 border-4 border-[var(--border)] border-t-[var(--accent)]" />
        </div>
      ) : (
        <div className="flex-1 min-h-0 panel-scroll-both">
          {view === "week" ? (
            <AgendaGrid
              days={agenda.days}
              appointments={weekAppointments}
              activeAppt={agenda.activeAppt}
              onDragStart={agenda.handleDragStart}
              onDragEnd={agenda.handleDragEnd}
              onEdit={agenda.openEdit}
            />
          ) : (
            <OperationalTimeline
              day={timelineDay}
              appointments={timelineAppointments}
              professionals={visibleProfessionals}
              onEdit={agenda.openEdit}
              onMove={agenda.handleCalendarMove}
              onResize={agenda.handleCalendarResize}
            />
          )}
        </div>
      )}

      <AgendaModals
        editingAppt={agenda.editingAppt}
        setEditingAppt={agenda.setEditingAppt}
        editTime={agenda.editTime}
        setEditTime={agenda.setEditTime}
        onEditSave={agenda.handleEditSave}
        isNewModalOpen={agenda.isNewModalOpen}
        setIsNewModalOpen={agenda.setIsNewModalOpen}
        submitting={agenda.submitting}
        newApptData={agenda.newApptData}
        setNewApptData={agenda.setNewApptData}
        options={agenda.options}
        quickAdd={agenda.quickAdd}
        setQuickAdd={agenda.setQuickAdd}
        quickData={agenda.quickData}
        setQuickData={agenda.setQuickData}
        onQuickSave={agenda.handleQuickSave}
        onCreateSubmit={agenda.handleCreateSubmit}
      />
    </div>
  )
}
