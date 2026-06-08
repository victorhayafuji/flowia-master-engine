import { describe, expect, it } from "vitest"
import { normalizeWorkingHours, summarizeSchedule, workingHoursForApi } from "./workingHours"

describe("workingHours helpers", () => {
  it("summarizes Mon-Fri schedule with buffer", () => {
    const summary = summarizeSchedule({
      id: "1",
      name: "Maria",
      appointment_buffer_minutes: 15,
      working_hours: {
        mon: { start: "08:00", end: "18:00" },
        tue: { start: "08:00", end: "18:00" },
        wed: { start: "08:00", end: "18:00" },
        thu: { start: "08:00", end: "18:00" },
        fri: { start: "08:00", end: "18:00" },
        sat: null,
        sun: null,
      },
    })
    expect(summary).toContain("buffer 15min")
    expect(summary).toContain("08:00")
  })

  it("exports only active days for API", () => {
    const hours = normalizeWorkingHours({ mon: { start: "09:00", end: "17:00" }, sun: null })
    const payload = workingHoursForApi(hours)
    expect(payload.mon).toEqual({ start: "09:00", end: "17:00" })
    expect(payload.sun).toBeUndefined()
  })
})
