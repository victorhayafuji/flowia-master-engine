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
import { AGENDA_HOURS, AGENDA_QUARTERS } from "../types"

interface AgendaGridProps {
  days: Date[]
  appointments: Appointment[]
  activeAppt?: Appointment
  onDragStart: (event: { active: { id: string | number } }) => void
  onDragEnd: (event: import("@dnd-kit/core").DragEndEvent) => void
  onEdit: (appt: Appointment) => void
  onSlotClick?: (slotIso: string) => void
}

export function AgendaGrid({ days, appointments, activeAppt, onDragStart, onDragEnd, onEdit, onSlotClick }: AgendaGridProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor),
  )

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

          {AGENDA_HOURS.map((hour) => (
            <div key={hour} className="grid grid-cols-[80px_1fr_1fr_1fr_1fr_1fr] border-b-2 border-[var(--border)] last:border-b-0">
              <div className="p-2 border-r-2 border-[var(--border)] bg-[var(--background)] flex items-start justify-center font-mono text-sm font-bold text-[var(--foreground)]">
                {hour.toString().padStart(2, "0")}:00
              </div>
              {days.map((day) => (
                <div key={day.toISOString()} className="flex flex-col border-r-2 border-[var(--border)] bg-[var(--surface)] last:border-r-0">
                  {AGENDA_QUARTERS.map((minute) => {
                    const localDate = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour, minute, 0)
                    const slotId = format(localDate, "yyyy-MM-dd'T'HH:mm:ssXXX")
                    const slotAppointments = appointments.filter((a) => {
                      const d = new Date(a.scheduled_at)
                      return (
                        d.getDate() === day.getDate() &&
                        d.getMonth() === day.getMonth() &&
                        d.getFullYear() === day.getFullYear() &&
                        d.getHours() === hour &&
                        d.getMinutes() === minute
                      )
                    })
                    return (
                      <DroppableSlot key={slotId} id={slotId} onSlotClick={onSlotClick}>
                        {slotAppointments.map((appt) => (
                          <DraggableAppointment key={appt.id} appointment={appt} onEdit={onEdit} />
                        ))}
                      </DroppableSlot>
                    )
                  })}
                </div>
              ))}
            </div>
          ))}
      </div>
      <DragOverlay>{activeAppt ? <DraggableAppointment appointment={activeAppt} isOverlay /> : null}</DragOverlay>
    </DndContext>
  )
}

function DroppableSlot({
  id,
  children,
  onSlotClick,
}: {
  id: string
  children: React.ReactNode
  onSlotClick?: (slotIso: string) => void
}) {
  const { isOver, setNodeRef } = useDroppable({ id, data: { type: "slot", datetime: id } })
  return (
    <div
      ref={setNodeRef}
      onClick={(e) => {
        // Only empty slot area — clicks on appointment cards don't bubble here as target.
        if (onSlotClick && e.target === e.currentTarget) onSlotClick(id)
      }}
      title={onSlotClick ? "Clique para agendar neste horário" : undefined}
      className={`min-h-[40px] p-1 border-b border-dashed border-[var(--border)]/20 last:border-b-0 transition-colors ${
        isOver ? "bg-[var(--accent)]/10 ring-inset ring-2 ring-[var(--accent)]" : "bg-transparent"
      } ${onSlotClick ? "cursor-pointer hover:bg-[var(--accent)]/5" : ""}`}
    >
      {children}
    </div>
  )
}

function DraggableAppointment({
  appointment,
  isOverlay = false,
  onEdit,
}: {
  appointment: Appointment
  isOverlay?: boolean
  onEdit?: (appt: Appointment) => void
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: appointment.id,
    data: appointment,
  })
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined

  if (isDragging && !isOverlay) {
    return (
      <div
        ref={setNodeRef}
        className="h-16 w-full border-2 border-dashed border-[var(--border)] opacity-30 rounded-none bg-[var(--accent)]/10"
      />
    )
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={`
        group relative flex flex-col p-2 mb-2 cursor-grab active:cursor-grabbing
        border-2 border-[var(--border)] bg-[var(--background)]
        shadow-[3px_3px_0px_0px_var(--border)] transition-transform hover:-translate-y-0.5 hover:shadow-[5px_5px_0px_0px_var(--border)]
        ${isOverlay ? "scale-105 shadow-[8px_8px_0px_0px_var(--accent)] border-[var(--accent)] rotate-2 cursor-grabbing z-50" : ""}
      `}
    >
      <div className="absolute top-0 right-0 w-1.5 h-full bg-[var(--accent)] border-l-2 border-[var(--border)]" />
      <div className="flex items-center gap-1 mb-1 pr-1">
        <GripVertical className="w-3 h-3 shrink-0 text-[var(--foreground)]/40 group-hover:text-[var(--foreground)]" />
        <span className="font-mono text-xs font-bold truncate flex-1">{appointment.patient?.name || "Sem Nome"}</span>
        {!isOverlay && onEdit && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onEdit(appointment)
            }}
            className="shrink-0 text-[var(--foreground)]/40 hover:text-[var(--accent)] transition-colors p-1"
          >
            <Edit2 className="w-3 h-3" />
          </button>
        )}
      </div>
      {appointment.professional?.name && (
        <div className="text-[10px] font-mono text-[var(--foreground)]/60 truncate pl-4 mb-1">
          {appointment.professional.name}
        </div>
      )}
      <div className="flex items-center gap-1 mt-auto">
        <div className="text-[10px] font-bold uppercase px-1 py-0.5 bg-[var(--border)] text-[var(--background)] self-start">
          {appointment.service?.name || "Serviço"}
        </div>
        {appointment.duration_minutes ? (
          <span className="text-[10px] font-mono text-[var(--foreground)]/50">{appointment.duration_minutes}min</span>
        ) : null}
      </div>
    </div>
  )
}
