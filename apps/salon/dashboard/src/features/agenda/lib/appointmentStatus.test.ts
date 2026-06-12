import { describe, expect, it } from "vitest"
import { allowedTransitions } from "./appointmentStatus"

describe("allowedTransitions", () => {
  it("terminal states have no outgoing transitions", () => {
    expect(allowedTransitions("completed")).toEqual([])
    expect(allowedTransitions("no_show")).toEqual([])
    expect(allowedTransitions("cancelled")).toEqual([])
    expect(allowedTransitions("rescheduled")).toEqual([])
  })

  it("pre-arrival states can move to no_show; all active states can cancel", () => {
    for (const status of ["pending", "confirmed", "arrived"]) {
      expect(allowedTransitions(status)).toContain("no_show")
    }
    for (const status of ["pending", "confirmed", "arrived", "in_progress"]) {
      expect(allowedTransitions(status)).toContain("cancelled")
    }
    // A client already in service cannot be a no_show.
    expect(allowedTransitions("in_progress")).not.toContain("no_show")
  })

  it("does not allow reopening a terminal state", () => {
    for (const status of ["pending", "confirmed", "arrived", "in_progress"]) {
      expect(allowedTransitions(status)).not.toContain("completed_undo")
    }
    // in_progress cannot go back to arrived (linear flow)
    expect(allowedTransitions("in_progress")).not.toContain("arrived")
    expect(allowedTransitions("in_progress")).toEqual(["completed", "cancelled"])
  })

  it("returns empty for unknown status", () => {
    expect(allowedTransitions("bogus")).toEqual([])
  })
})
