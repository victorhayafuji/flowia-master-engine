import { describe, expect, it } from "vitest"
import { orgWorksOnDay, professionalWorksOnDay } from "./workdays"

const MON_FRI = {
  mon: { start: "08:00", end: "18:00" },
  tue: { start: "08:00", end: "18:00" },
  wed: { start: "08:00", end: "18:00" },
  thu: { start: "08:00", end: "18:00" },
  fri: { start: "08:00", end: "18:00" },
}

const saturday = new Date(2026, 5, 13) // Jun 13 2026 = Saturday
const thursday = new Date(2026, 5, 11) // Jun 11 2026 = Thursday

describe("orgWorksOnDay", () => {
  it("disables days no professional works", () => {
    expect(orgWorksOnDay([{ working_hours: MON_FRI }], saturday)).toBe(false)
  })

  it("enables days at least one professional works", () => {
    expect(orgWorksOnDay([{ working_hours: MON_FRI }], thursday)).toBe(true)
    expect(
      orgWorksOnDay(
        [{ working_hours: MON_FRI }, { working_hours: { sat: { start: "09:00", end: "13:00" } } }],
        saturday,
      ),
    ).toBe(true)
  })

  it("fails open without working_hours data", () => {
    expect(orgWorksOnDay([], saturday)).toBe(true)
    expect(orgWorksOnDay([{}, { working_hours: null }], saturday)).toBe(true)
  })

  it("treats incomplete day entries as closed", () => {
    expect(orgWorksOnDay([{ working_hours: { sat: null } }], saturday)).toBe(false)
    expect(orgWorksOnDay([{ working_hours: { sat: { start: "09:00" } } }], saturday)).toBe(false)
  })
})

describe("professionalWorksOnDay", () => {
  it("disables days the professional does not work", () => {
    expect(professionalWorksOnDay({ working_hours: MON_FRI }, saturday)).toBe(false)
    expect(professionalWorksOnDay({ working_hours: MON_FRI }, thursday)).toBe(true)
  })

  it("fails open without working_hours data", () => {
    expect(professionalWorksOnDay(undefined, saturday)).toBe(true)
    expect(professionalWorksOnDay({}, saturday)).toBe(true)
  })
})
