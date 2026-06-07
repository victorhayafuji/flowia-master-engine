import { Edit2 } from "lucide-react"
import { format } from "date-fns"
import type { Appointment } from "../types"
import { AGENDA_END_HOUR, AGENDA_SLOT_MINUTES, AGENDA_START_HOUR, TEAM_ROW_HEIGHT } from "../types"

interface Professional {
  id: string
  name: string
}

interface TeamDayViewProps {
  day: Date
  appointments: Appointment[]
  professionals: Professional[]
  onEdit: (appt: Appointment) => void
}

const TOTAL_MINUTES = (AGENDA_END_HOUR - AGENDA_START_HOUR) * 60
const SLOT_COUNT = TOTAL_MINUTES / AGENDA_SLOT_MINUTES
const PX_PER_MINUTE = TEAM_ROW_HEIGHT / AGENDA_SLOT_MINUTES

function timeRows(): string[] {
  const rows: string[] = []
  for (let i = 0; i <= SLOT_COUNT; i++) {
    const totalMin = AGENDA_START_HOUR * 60 + i * AGENDA_SLOT_MINUTES
    const h = Math.floor(totalMin / 60)
    const m = totalMin % 60
    rows.push(`${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`)
  }
  return rows
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getDate() === b.getDate() && a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear()
}

export function TeamDayView({ day, appointments, professionals, onEdit }: TeamDayViewProps) {
  const rows = timeRows()
  const dayAppointments = appointments.filter((a) => isSameDay(new Date(a.scheduled_at), day))

  if (professionals.length === 0) {
    return (
      <div className="border-4 border-[var(--border)] bg-[var(--surface)] p-8 text-center font-mono text-sm font-bold uppercase text-[var(--foreground)]/60">
        Cadastre profissionais no catálogo para ver a agenda por equipe.
      </div>
    )
  }

  return (
    <div
      className="border-4 border-[var(--border)] bg-[var(--surface)] shadow-[8px_8px_0px_0px_var(--border)] grid"
      style={{ gridTemplateColumns: `80px repeat(${professionals.length}, minmax(160px, 1fr))`, minWidth: 80 + professionals.length * 160 }}
    >
      {/* Header row */}
      <div className="border-b-4 border-r-2 border-[var(--border)] bg-[var(--background)] p-2 font-mono text-xs font-bold flex items-center justify-center">
        {format(day, "dd/MM")}
      </div>
      {professionals.map((prof) => (
        <div
          key={prof.id}
          className="border-b-4 border-r-2 border-[var(--border)] last:border-r-0 bg-[var(--background)] p-2 text-center font-black uppercase tracking-tight text-sm truncate"
        >
          {prof.name}
        </div>
      ))}

      {/* Time gutter */}
      <div className="border-r-2 border-[var(--border)] bg-[var(--background)]">
        {rows.slice(0, -1).map((label) => (
          <div
            key={label}
            style={{ height: TEAM_ROW_HEIGHT }}
            className="border-b border-dashed border-[var(--border)]/30 px-1 text-right font-mono text-[10px] font-bold text-[var(--foreground)]/60"
          >
            {label}
          </div>
        ))}
      </div>

      {/* Professional columns */}
      {professionals.map((prof) => {
        const colAppts = dayAppointments.filter((a) => a.professional_id === prof.id)
        return (
          <div
            key={prof.id}
            className="relative border-r-2 border-[var(--border)] last:border-r-0"
            style={{ height: SLOT_COUNT * TEAM_ROW_HEIGHT }}
          >
            {rows.slice(0, -1).map((label, i) => (
              <div
                key={label}
                style={{ height: TEAM_ROW_HEIGHT }}
                className={`border-b border-dashed border-[var(--border)]/20 ${i % 4 === 0 ? "bg-[var(--surface)]" : "bg-[var(--surface)]/60"}`}
              />
            ))}
            {colAppts.map((appt) => {
              const start = new Date(appt.scheduled_at)
              const minutesFromStart = (start.getHours() - AGENDA_START_HOUR) * 60 + start.getMinutes()
              const top = Math.max(0, minutesFromStart * PX_PER_MINUTE)
              const height = Math.max(TEAM_ROW_HEIGHT, (appt.duration_minutes || AGENDA_SLOT_MINUTES) * PX_PER_MINUTE)
              return (
                <button
                  key={appt.id}
                  onClick={() => onEdit(appt)}
                  style={{ top, height }}
                  className="group absolute left-1 right-1 flex flex-col overflow-hidden border-2 border-[var(--border)] bg-[var(--background)] p-1 text-left shadow-[2px_2px_0px_0px_var(--border)] transition-transform hover:-translate-y-0.5"
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-mono text-[11px] font-bold truncate">
                      {format(start, "HH:mm")} {appt.patient?.name || "Sem Nome"}
                    </span>
                    <Edit2 className="w-3 h-3 shrink-0 text-[var(--foreground)]/30 group-hover:text-[var(--accent)]" />
                  </div>
                  <span className="text-[10px] font-mono text-[var(--foreground)]/60 truncate">
                    {appt.service?.name || "Serviço"} · {appt.duration_minutes || AGENDA_SLOT_MINUTES}min
                  </span>
                </button>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
