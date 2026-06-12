import { describe, expect, it } from "vitest"
import { allowedTransitions } from "./appointmentStatus"

const MANUAL = ["confirmed", "arrived", "in_progress", "completed", "no_show", "cancelled"]

describe("allowedTransitions", () => {
  it("terminal states can be corrected (have transitions)", () => {
    expect(allowedTransitions("no_show").length).toBeGreaterThan(0)
    expect(allowedTransitions("completed").length).toBeGreaterThan(0)
    expect(allowedTransitions("cancelled").length).toBeGreaterThan(0)
  })

  it("offers every manual target except the current status", () => {
    for (const status of MANUAL) {
      const targets = allowedTransitions(status)
      expect(targets).not.toContain(status)
      expect(new Set(targets)).toEqual(new Set(MANUAL.filter((s) => s !== status)))
    }
  })

  it("a wrongly-marked no_show can be corrected back to confirmed", () => {
    expect(allowedTransitions("no_show")).toContain("confirmed")
  })

  it("never offers pending or rescheduled as a manual target", () => {
    for (const status of [...MANUAL, "pending", "rescheduled", "bogus"]) {
      expect(allowedTransitions(status)).not.toContain("pending")
      expect(allowedTransitions(status)).not.toContain("rescheduled")
    }
  })
})
