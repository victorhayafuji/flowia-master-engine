import { useMemo } from "react"
import moment, { type Moment } from "moment"
import type { Appointment } from "../types"
import { AGENDA_END_HOUR, AGENDA_START_HOUR } from "../types"

interface Professional {
  id: string
  name: string
}

export interface TimelineGroup {
  id: string
  title: string
}

export interface TimelineItem {
  id: string
  group: string
  title: string
  start_time: Moment
  end_time: Moment
  appointment: Appointment
  canMove: boolean
  canResize: false | "left" | "right" | "both"
  itemProps: {
    className: string
    title: string
    onDoubleClick: () => void
  }
}

const STATUS_CLASS: Record<string, string> = {
  confirmed: "timeline-item--confirmed",
  arrived: "timeline-item--arrived",
  in_progress: "timeline-item--in-progress",
  completed: "timeline-item--completed",
  no_show: "timeline-item--no-show",
  cancelled: "timeline-item--cancelled",
}

const STATUS_LABEL: Record<string, string> = {
  pending: "Pendente",
  confirmed: "Confirmado",
  arrived: "Chegou",
  in_progress: "Em atendimento",
  completed: "Concluído",
  no_show: "Falta",
  cancelled: "Cancelado",
}

function statusClass(status: string): string {
  return STATUS_CLASS[status] ?? "timeline-item--pending"
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getDate() === b.getDate() && a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear()
}

export function useOperationalTimeline(
  day: Date,
  appointments: Appointment[],
  professionals: Professional[],
  onEdit: (appt: Appointment) => void,
) {
  const groups = useMemo<TimelineGroup[]>(
    () => professionals.map((p) => ({ id: p.id, title: p.name })),
    [professionals],
  )

  const items = useMemo<TimelineItem[]>(() => {
    const dayAppointments = appointments.filter((a) => isSameDay(new Date(a.scheduled_at), day))
    return dayAppointments
      .filter((a) => a.professional_id && professionals.some((p) => p.id === a.professional_id))
      .map((appt) => {
        const start = moment(appt.scheduled_at)
        const duration = appt.duration_minutes || 30
        const end = moment(start).add(duration, "minutes")
        const label = `${start.format("HH:mm")} ${appt.patient?.name || "Sem Nome"} · ${appt.service?.name || "Serviço"}`
        return {
          id: appt.id,
          group: appt.professional_id!,
          title: label,
          start_time: start,
          end_time: end,
          appointment: appt,
          canMove: appt.status !== "cancelled",
          canResize: appt.status === "cancelled" ? false : ("both" as const),
          itemProps: {
            className: statusClass(appt.status),
            title: `${label} · ${STATUS_LABEL[appt.status] ?? appt.status}`,
            onDoubleClick: () => onEdit(appt),
          },
        }
      })
  }, [appointments, day, onEdit, professionals])

  const visibleTimeStart = useMemo(
    () => moment(day).startOf("day").hour(AGENDA_START_HOUR).minute(0).second(0),
    [day],
  )
  const visibleTimeEnd = useMemo(
    () => moment(day).startOf("day").hour(AGENDA_END_HOUR).minute(0).second(0),
    [day],
  )

  return { groups, items, visibleTimeStart, visibleTimeEnd }
}

export function toLocalIso(momentValue: Moment): string {
  return momentValue.format("YYYY-MM-DD[T]HH:mm:ssZ")
}
