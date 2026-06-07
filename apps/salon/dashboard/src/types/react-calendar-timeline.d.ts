declare module "react-calendar-timeline" {
  import type { ComponentType, ReactNode } from "react"
  import type { Moment } from "moment"

  export interface TimelineGroupBase {
    id: string | number
    title: string
  }

  export interface TimelineItemBase {
    id: string | number
    group: string | number
    title?: string
    start_time: Moment
    end_time: Moment
    canMove?: boolean
    canResize?: boolean | "left" | "right" | "both"
    itemProps?: Record<string, unknown>
  }

  export interface TimelineProps {
    groups: TimelineGroupBase[]
    items: TimelineItemBase[]
    visibleTimeStart: Moment
    visibleTimeEnd: Moment
    lineHeight?: number
    itemHeightRatio?: number
    canMove?: boolean
    canResize?: boolean | "left" | "right" | "both"
    canChangeGroup?: boolean
    stackItems?: boolean
    traditionalZoom?: boolean
    timeSteps?: Record<string, number>
    onItemMove?: (itemId: string | number, dragTime: Moment, newGroupOrder: number) => void
    onItemResize?: (itemId: string | number, time: Moment, edge: "left" | "right") => void
    onItemClick?: (itemId: string | number, e: React.MouseEvent, time: Moment) => void
    children?: ReactNode
  }

  const Timeline: ComponentType<TimelineProps>
  export default Timeline

  export const TimelineMarkers: ComponentType<{ children?: ReactNode }>
  export const TodayMarker: ComponentType<Record<string, never>>
}
