import { describe, expect, it } from "vitest"
import { isAgendaSlotDropTarget, resolveSlotDatetime } from "./agendaDropTarget"

describe("agendaDropTarget", () => {
  it("accepts ISO slot ids", () => {
    expect(isAgendaSlotDropTarget("2026-06-10T14:00:00-03:00")).toBe(true)
  })

  it("rejects appointment UUIDs", () => {
    expect(isAgendaSlotDropTarget("22222222-2222-2222-2222-222222222222")).toBe(false)
  })

  it("accepts slot data type", () => {
    expect(isAgendaSlotDropTarget("any-id", { type: "slot" })).toBe(true)
  })

  it("resolves datetime from slot data", () => {
    const event = {
      active: { id: "appt-1" },
      over: {
        id: "slot-1",
        data: { current: { type: "slot", datetime: "2026-06-10T14:00:00-03:00" } },
      },
    } as Parameters<typeof resolveSlotDatetime>[0]

    expect(resolveSlotDatetime(event)).toBe("2026-06-10T14:00:00-03:00")
  })

  it("returns null when over is an appointment card", () => {
    const event = {
      active: { id: "appt-1" },
      over: { id: "22222222-2222-2222-2222-222222222222", data: { current: {} } },
    } as Parameters<typeof resolveSlotDatetime>[0]

    expect(resolveSlotDatetime(event)).toBeNull()
  })
})
