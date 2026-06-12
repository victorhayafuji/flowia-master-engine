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
    dragSnap?: number
    timeSteps?: Record<string, number>
    // v0.30 (dayjs rewrite) passes unix-ms numbers to these callbacks, not Moment.
    onItemMove?: (itemId: string | number, dragTime: number, newGroupOrder: number) => void
    onItemResize?: (itemId: string | number, time: number, edge: "left" | "right") => void
    onItemClick?: (itemId: string | number, e: React.MouseEvent, time: number) => void
    children?: ReactNode
  }

  const Timeline: ComponentType<TimelineProps>
  export default Timeline

  export const TimelineMarkers: ComponentType<{ children?: ReactNode }>
  export const TodayMarker: ComponentType<Record<string, never>>

  /** Minimal shape of the dayjs values the header passes to labelFormat. */
  export interface HeaderLabelTime {
    toDate(): Date
  }

  export const TimelineHeaders: ComponentType<{ children?: ReactNode; className?: string }>
  export const SidebarHeader: ComponentType<{
    children?: (props: { getRootProps: () => { style: React.CSSProperties } }) => ReactNode
  }>
  export const DateHeader: ComponentType<{
    unit?: string
    height?: number
    className?: string
    labelFormat?:
      | string
      | ((timeRange: [HeaderLabelTime, HeaderLabelTime], unit: string, labelWidth?: number) => string)
  }>
}
