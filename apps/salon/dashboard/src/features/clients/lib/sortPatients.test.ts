import { describe, expect, it } from "vitest"
import { parsePatientSort, sortPatients } from "./sortPatients"

const patients = [
  { name: "Bruno", created_at: "2026-06-01T10:00:00Z", no_show_count: 1 },
  { name: "Ana", created_at: "2026-06-09T10:00:00Z", no_show_count: 0 },
  { name: "Carla", created_at: "2026-06-05T10:00:00Z", no_show_count: 3 },
]

describe("sortPatients", () => {
  it("sorts by name with pt-BR locale", () => {
    expect(sortPatients(patients, "nome").map((p) => p.name)).toEqual(["Ana", "Bruno", "Carla"])
  })

  it("sorts by no-shows descending", () => {
    expect(sortPatients(patients, "faltas").map((p) => p.name)).toEqual(["Carla", "Bruno", "Ana"])
  })

  it("sorts by most recent registration by default", () => {
    expect(sortPatients(patients, "recente").map((p) => p.name)).toEqual(["Ana", "Carla", "Bruno"])
  })

  it("does not mutate the input array", () => {
    const copy = [...patients]
    sortPatients(patients, "nome")
    expect(patients).toEqual(copy)
  })
})

describe("parsePatientSort", () => {
  it("accepts known values and falls back to recente", () => {
    expect(parsePatientSort("faltas")).toBe("faltas")
    expect(parsePatientSort("nome")).toBe("nome")
    expect(parsePatientSort("xyz")).toBe("recente")
    expect(parsePatientSort(null)).toBe("recente")
  })
})
