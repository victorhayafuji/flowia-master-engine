import type { CollisionDetection, DragEndEvent } from "@dnd-kit/core"
import { pointerWithin, rectIntersection } from "@dnd-kit/core"

const ISO_SLOT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/

export function isAgendaSlotDropTarget(id: string | number, data?: { type?: string }): boolean {
  if (data?.type === "slot") return true
  return ISO_SLOT_PATTERN.test(String(id))
}

export function resolveSlotDatetime(event: DragEndEvent): string | null {
  const { over } = event
  if (!over) return null

  const data = over.data.current as { type?: string; datetime?: string } | undefined
  if (data?.type === "slot" && data.datetime) return data.datetime

  const overId = String(over.id)
  if (isAgendaSlotDropTarget(overId)) return overId

  return null
}

/** Prefer droppable slots over draggable appointment cards. */
export const slotOnlyCollisionDetection: CollisionDetection = (args) => {
  const pointerCollisions = pointerWithin(args)
  const slotHits = pointerCollisions.filter((c) =>
    isAgendaSlotDropTarget(c.id, c.data?.current as { type?: string } | undefined),
  )
  if (slotHits.length > 0) return slotHits

  const rectCollisions = rectIntersection(args)
  return rectCollisions.filter((c) =>
    isAgendaSlotDropTarget(c.id, c.data?.current as { type?: string } | undefined),
  )
}
