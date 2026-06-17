import moment from "moment"
import {
  formatTimelineItemTime,
  formatTimelineItemTooltip,
  type TimelineItem,
} from "../hooks/useOperationalTimeline"

interface TimelineItemRendererProps {
  item: TimelineItem
  getItemProps: (props?: Record<string, unknown>) => Record<string, unknown>
  getResizeProps: () => {
    left: Record<string, unknown>
    right: Record<string, unknown>
  }
}

/** Renders card text from item.start_time (updated by the lib on drag) instead of stale title. */
export function TimelineItemRenderer({
  item,
  getItemProps,
  getResizeProps,
}: TimelineItemRendererProps) {
  const { left: leftResizeProps, right: rightResizeProps } = getResizeProps()
  const start = moment(item.start_time)
  // Minimal bar: show only the time; full info (name · service · status) is in the tooltip.
  const time = formatTimelineItemTime(start)
  const tooltip = formatTimelineItemTooltip(item.appointment, start)

  return (
    <div {...getItemProps({ ...item.itemProps, title: tooltip })}>
      <div {...leftResizeProps} />
      <div {...rightResizeProps} />
      <div className="rct-item-content rct-item-content--minimal">{time}</div>
    </div>
  )
}
