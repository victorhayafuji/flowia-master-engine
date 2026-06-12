import { Clock, Edit2, GripVertical } from "lucide-react"
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core"
import { slotOnlyCollisionDetection } from "../lib/agendaDropTarget"
import { format } from "date-fns"
import { ptBR } from "date-fns/locale"
import type { Appointment } from "../types"
import { AGENDA_END_HOUR, AGENDA_HOURS, AGENDA_QUARTERS, AGENDA_START_HOUR } from "../types"

// Vertical scale: every minute maps to a fixed pixel height so cards reflect
// the time they actually occupy in the day.
const HOUR_PX = 72
const SLOT_PX = HOUR_PX / 4 // 18px per 15-minute slot
const PX_PER_MIN = HOUR_PX / 60

interface AgendaGridProps {
  days: Date[]
  appointments: Appointment[]
  activeAppt?: Appointment
  onDragStart: (event: { active: { id: string | number } }) => void
  onDragEnd: (event: import("@dnd-kit/core").DragEndEvent) => void
  onEdit: (appt: Appointment) => void
  onSlotClick?: (slotIso: string) => void
}

function isSameDay(d: Date, day: Date): boolean {
  return (
    d.getDate() === day.getDate() &&
    d.getMonth() === day.getMonth() &&
    d.getFullYear() === day.getFullYear()
  )
}

export function AgendaGrid({
  days,
  appointments,
  activeAppt,
  onDragStart,
  onDragEnd,
  onEdit,
  onSlotClick,
}: AgendaGridProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  )
  const totalHeight = AGENDA_HOURS.length * HOUR_PX

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={slotOnlyCollisionDetection}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
    >
      <div className="border-4 border-[var(--border)] bg-[var(--surface)] shadow-[8px_8px_0px_0px_var(--border)] min-w-[1000px]">
        <div className="grid grid-cols-[80px_1fr_1fr_1fr_1fr_1fr] border-b-4 border-[var(--border)]">
          <div className="p-4 border-r-2 border-[var(--border)] bg-[var(--background)] flex items-center justify-center">
            <Clock className="w-5 h-5 text-[var(--foreground)]" />
          </div>
          {days.map((day) => (
            <div
              key={day.toISOString()}
              className="p-4 border-r-2 border-[var(--border)] bg-[var(--background)] last:border-r-0 flex flex-col items-center"
            >
              <div className="font-black uppercase tracking-widest">{format(day, "EEEE", { locale: ptBR })}</div>
              <div className="font-mono text-sm font-bold bg-[var(--foreground)] text-[var(--background)] px-2 mt-1">
                {format(day, "dd/MM", { locale: ptBR })}
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-[80px_1fr_1fr_1fr_1fr_1fr]">
          {/* Time gutter */}
          <div
            className="relative border-r-2 border-[var(--border)] bg-[var(--background)]"
            style={{ height: totalHeight }}
          >
            {AGENDA_HOURS.map((hour, i) => (
              <div
                key={hour}
                className="absolute left-0 right-0 flex justify-center pt-1 font-mono text-sm font-bold text-[var(--foreground)] border-t-2 border-[var(--border)]"
                style={{ top: i * HOUR_PX, height: HOUR_PX }}
              >
                {hour.toString().padStart(2, "0")}:00
              </div>
            ))}
          </div>

          {/* One relative column per day: drop slots as background + sized cards on top */}
          {days.map((day) => {
            const dayAppts = appointments.filter((a) => {
              const d = new Date(a.scheduled_at)
              return isSameDay(d, day) && d.getHours() >= AGENDA_START_HOUR && d.getHours() < AGENDA_END_HOUR
            })
            return (
              <div
                key={day.toISOString()}
                className="relative border-r-2 border-[var(--border)] bg-[var(--surface)] last:border-r-0"
                style={{ height: totalHeight }}
              >
                {AGENDA_HOURS.map((hour, hi) =>
                  AGENDA_QUARTERS.map((minute, qi) => {
                    const localDate = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour, minute, 0)
                    const slotId = format(localDate, "yyyy-MM-dd'T'HH:mm:ssXXX")
                    return (
                      <DroppableSlot
                        key={slotId}
                        id={slotId}
                        top={(hi * 4 + qi) * SLOT_PX}
                        height={SLOT_PX}
                        hourStart={minute === 0}
                        onSlotClick={onSlotClick}
                      />
                    )
                  }),
                )}
                {dayAppts.map((appt) => {
                  const start = new Date(appt.scheduled_at)
                  const minutesFromStart = (start.getHours() - AGENDA_START_HOUR) * 60 + start.getMinutes()
                  const top = Math.max(0, minutesFromStart * PX_PER_MIN)
                  const dur = appt.duration_minutes || 30
                  const height = Math.min(totalHeight - top, Math.max(SLOT_PX, dur * PX_PER_MIN))
                  return (
                    <DraggableAppointment key={appt.id} appointment={appt} onEdit={onEdit} top={top} height={height} />
                  )
                })}
              </div>
            )
          })}
        </div>
      </div>
      <DragOverlay>{activeAppt ? <DraggableAppointment appointment={activeAppt} isOverlay /> : null}</DragOverlay>
    </DndContext>
  )
}

function DroppableSlot({
  id,
  top,
  height,
  hourStart,
  onSlotClick,
}: {
  id: string
  top: number
  height: number
  hourStart: boolean
  onSlotClick?: (slotIso: string) => void
}) {
  const { isOver, setNodeRef } = useDroppable({ id, data: { type: "slot", datetime: id } })
  return (
    <div
      ref={setNodeRef}
      onClick={(e) => {
        if (onSlotClick && e.target === e.currentTarget) onSlotClick(id)
      }}
      title={onSlotClick ? "Clique para agendar neste horário" : undefined}
      style={{ top, height }}
      className={`absolute left-0 right-0 transition-colors ${
        hourStart ? "border-t-2 border-[var(--border)]" : "border-t border-dashed border-[var(--border)]/20"
      } ${isOver ? "bg-[var(--accent)]/15 ring-inset ring-2 ring-[var(--accent)]" : ""} ${
        onSlotClick ? "cursor-pointer hover:bg-[var(--accent)]/5" : ""
      }`}
    />
  )
}

function DraggableAppointment({
  appointment,
  isOverlay = false,
  onEdit,
  top,
  height,
}: {
  appointment: Appointment
  isOverlay?: boolean
  onEdit?: (appt: Appointment) => void
  top?: number
  height?: number
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: appointment.id,
    data: appointment,
  })

  const overlayHeight = Math.max(SLOT_PX, (appointment.duration_minutes || 30) * PX_PER_MIN)
  const pos: React.CSSProperties = isOverlay
    ? { width: 200, height: overlayHeight }
    : { position: "absolute", top, height, left: 4, right: 4 }
  const style: React.CSSProperties = {
    ...pos,
    ...(transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : {}),
  }

  const start = new Date(appointment.scheduled_at)
  const hhmm = `${String(start.getHours()).padStart(2, "0")}:${String(start.getMinutes()).padStart(2, "0")}`
  const compact = (height ?? overlayHeight) < 46

  if (isDragging && !isOverlay) {
    return (
      <div
        ref={setNodeRef}
        style={{ position: "absolute", top, height, left: 4, right: 4 }}
        className="border-2 border-dashed border-[var(--border)] opacity-30 bg-[var(--accent)]/10"
      />
    )
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={`group flex flex-col p-1.5 overflow-hidden cursor-grab active:cursor-grabbing border-2 border-[var(--border)] bg-[var(--background)] shadow-[3px_3px_0px_0px_var(--border)] ${
        isOverlay ? "scale-105 shadow-[6px_6px_0px_0px_var(--accent)] border-[var(--accent)] z-50" : ""
      }`}
    >
      <div className="flex items-center gap-1 pr-0.5">
        <GripVertical className="w-3 h-3 shrink-0 text-[var(--foreground)]/40 group-hover:text-[var(--foreground)]" />
        <span className="font-mono text-[11px] font-bold truncate flex-1">
          {hhmm} {appointment.patient?.name || "Sem Nome"}
        </span>
        {!isOverlay && onEdit && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onEdit(appointment)
            }}
            className="shrink-0 text-[var(--foreground)]/40 hover:text-[var(--accent)] transition-colors"
          >
            <Edit2 className="w-3 h-3" />
          </button>
        )}
      </div>
      {!compact && (
        <div className="text-[10px] font-mono text-[var(--foreground)]/60 truncate mt-0.5 pl-4">
          {appointment.service?.name || "Serviço"}
          {appointment.duration_minutes ? ` · ${appointment.duration_minutes}min` : ""}
        </div>
      )}
    </div>
  )
}
