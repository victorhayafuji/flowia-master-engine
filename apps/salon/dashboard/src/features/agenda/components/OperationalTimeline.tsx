import Timeline, {
  DateHeader,
  SidebarHeader,
  TimelineHeaders,
  TimelineMarkers,
  TodayMarker,
} from "react-calendar-timeline"
import "react-calendar-timeline/dist/style.css"
import "../operationalTimeline.css"
import { format } from "date-fns"
import { ptBR } from "date-fns/locale"
import type { Appointment } from "../types"
import { toLocalIso, useOperationalTimeline, type TimelineItem } from "../hooks/useOperationalTimeline"
import { TimelineItemRenderer } from "./TimelineItemRenderer"

interface Professional {
  id: string
  name: string
}

interface OperationalTimelineProps {
  day: Date
  appointments: Appointment[]
  professionals: Professional[]
  onEdit: (appt: Appointment) => void
  onMove: (appointmentId: string, scheduledAt: string) => Promise<void>
  onResize: (appointmentId: string, scheduledAt: string, durationMinutes: number) => Promise<void>
}

export function OperationalTimeline({
  day,
  appointments,
  professionals,
  onEdit,
  onMove,
  onResize,
}: OperationalTimelineProps) {
  const { groups, items, visibleTimeStart, visibleTimeEnd } = useOperationalTimeline(
    day,
    appointments,
    professionals,
    onEdit,
  )

  if (professionals.length === 0) {
    return (
      <div className="border-4 border-[var(--border)] bg-[var(--surface)] p-8 text-center font-mono text-sm font-bold uppercase text-[var(--foreground)]/60">
        Cadastre profissionais no catálogo para ver a agenda operacional.
      </div>
    )
  }

  return (
    <div className="operational-timeline border-4 border-[var(--border)] bg-[var(--surface)] shadow-[8px_8px_0px_0px_var(--border)] min-h-[480px]">
      <div className="px-3 py-1.5 border-b-2 border-[var(--border)] bg-[var(--background)] font-mono text-[10px] uppercase tracking-widest text-[var(--foreground)]/50">
        Clique para selecionar · arraste para mover · duplo-clique para editar
      </div>
      <Timeline
        key={day.toISOString()}
        groups={groups}
        items={items}
        visibleTimeStart={visibleTimeStart}
        visibleTimeEnd={visibleTimeEnd}
        lineHeight={64}
        itemHeightRatio={0.82}
        canMove
        canResize="both"
        canChangeGroup={false}
        stackItems={false}
        traditionalZoom
        dragSnap={15 * 60 * 1000}
        timeSteps={{ minute: 15, hour: 1, day: 1, month: 1, year: 1 }}
        itemRenderer={({ item, getItemProps, getResizeProps }) => (
          <TimelineItemRenderer
            item={item as TimelineItem}
            getItemProps={getItemProps}
            getResizeProps={getResizeProps}
          />
        )}
        onItemMove={(itemId, dragTime) => {
          // dragTime is the new start, in unix ms.
          void onMove(String(itemId), toLocalIso(dragTime))
        }}
        onItemResize={(itemId, time, edge) => {
          const item = items.find((i) => i.id === String(itemId))
          if (!item) return
          // `time` is the dragged edge position, in unix ms.
          if (edge === "left") {
            const durationMinutes = Math.max(15, Math.round((item.end_time.valueOf() - time) / 60000))
            void onResize(String(itemId), toLocalIso(time), durationMinutes)
            return
          }
          const durationMinutes = Math.max(15, Math.round((time - item.start_time.valueOf()) / 60000))
          void onResize(String(itemId), toLocalIso(item.start_time), durationMinutes)
        }}
      >
        <TimelineHeaders>
          <SidebarHeader>{({ getRootProps }) => <div {...getRootProps()} />}</SidebarHeader>
          <DateHeader
            unit="primaryHeader"
            labelFormat={([start]) => format(start.toDate(), "EEEE, dd/MM", { locale: ptBR })}
          />
          <DateHeader unit="hour" labelFormat={([start]) => format(start.toDate(), "HH:mm")} />
        </TimelineHeaders>
        <TimelineMarkers>
          <TodayMarker />
        </TimelineMarkers>
      </Timeline>
    </div>
  )
}
