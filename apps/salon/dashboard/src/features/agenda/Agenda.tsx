import { useEffect, useMemo, useState, useCallback } from "react"
import { format } from "date-fns"
import { ptBR } from "date-fns/locale"
import type { DragEndEvent } from "@dnd-kit/core"
import { useAuth } from "@/features/auth/AuthContext"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/PageHeader"
import { AgendaGrid } from "./components/AgendaGrid"
import { OperationalTimeline } from "./components/OperationalTimeline"
import { AgendaModals } from "./components/AgendaModals"
import { useAgenda } from "./hooks/useAgenda"
import { resolveSlotDatetime } from "./lib/agendaDropTarget"
import { orgWorksOnDay, professionalWorksOnDay } from "./lib/workdays"
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

  const selectedProfessional = useMemo(() => {
    const id = isProfessionalUser ? user?.professional_id : filterProfessionalId
    return professionals.find((p) => p.id === id)
  }, [filterProfessionalId, isProfessionalUser, professionals, user?.professional_id])

  const weekDayEnabled = useMemo(
    () => agenda.days.map((day) => professionalWorksOnDay(selectedProfessional, day)),
    [agenda.days, selectedProfessional],
  )

  const isSlotOnEnabledWeekDay = useCallback(
    (slotIso: string) => {
      const slotDay = new Date(slotIso)
      const dayIndex = agenda.days.findIndex(
        (day) =>
          day.getDate() === slotDay.getDate() &&
          day.getMonth() === slotDay.getMonth() &&
          day.getFullYear() === slotDay.getFullYear(),
      )
      return dayIndex < 0 || weekDayEnabled[dayIndex] !== false
    },
    [agenda.days, weekDayEnabled],
  )

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

  // Days no professional works are disabled in the tabs (fail-open without data).
  const dayEnabled = useMemo(
    () => agenda.days.map((day) => orgWorksOnDay(professionals, day)),
    [agenda.days, professionals],
  )

  useEffect(() => {
    if (dayEnabled[timelineDayIndex] === false) {
      const firstEnabled = dayEnabled.findIndex(Boolean)
      if (firstEnabled >= 0) setTimelineDayIndex(firstEnabled)
    }
  }, [dayEnabled, timelineDayIndex])

  const openNewAppointment = () => {
    agenda.setNewApptData((prev) => ({
      ...prev,
      // Operational view: prefill the selected day; week view: prefill the filtered professional.
      date: view === "timeline" && timelineDay ? format(timelineDay, "yyyy-MM-dd") : prev.date,
      professional_id: view === "week" && filterProfessionalId ? filterProfessionalId : prev.professional_id,
    }))
    agenda.setIsNewModalOpen(true)
  }

  const handleSlotClick = (slotIso: string) => {
    if (!isSlotOnEnabledWeekDay(slotIso)) return
    agenda.setNewApptData((prev) => ({
      ...prev,
      professional_id: filterProfessionalId || prev.professional_id,
      date: slotIso.slice(0, 10),
      time: slotIso.slice(11, 16),
    }))
    agenda.setIsNewModalOpen(true)
  }

  const handleWeekDragEnd = (event: DragEndEvent) => {
    const newDate = resolveSlotDatetime(event)
    if (newDate && !isSlotOnEnabledWeekDay(newDate)) return
    agenda.handleDragEnd(event)
  }

  return (
    <div className="page-shell">
      <PageHeader
        title="Agenda"
        subtitle={subtitle}
        actions={
          <>
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
            <Button variant="default" onClick={openNewAppointment}>
              Novo Agendamento
            </Button>
          </>
        }
      />

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
                  disabled={!dayEnabled[i]}
                  title={dayEnabled[i] ? undefined : "Sem expediente"}
                  onClick={() => setTimelineDayIndex(i)}
                  className={`px-2 py-1 text-xs font-mono font-bold border-2 border-[var(--border)] ${
                    i === timelineDayIndex
                      ? "bg-[var(--accent)] text-[var(--background)]"
                      : "bg-[var(--surface)]"
                  } ${dayEnabled[i] ? "" : "opacity-40 cursor-not-allowed line-through"}`}
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
              dayEnabled={weekDayEnabled}
              onDragStart={agenda.handleDragStart}
              onDragEnd={handleWeekDragEnd}
              onEdit={agenda.openEdit}
              onSlotClick={handleSlotClick}
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
        onStatusChange={agenda.handleStatusUpdate}
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
