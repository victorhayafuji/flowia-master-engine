import { describe, expect, it } from "vitest"
import { isServiceEligible } from "./serviceEligibility"

const PRO_A = "prof-a"
const PRO_B = "prof-b"

describe("isServiceEligible", () => {
  it("service with no eligibility rows is available to any professional (fallback)", () => {
    expect(isServiceEligible({ professional_ids: [] }, PRO_A)).toBe(true)
    expect(isServiceEligible({}, PRO_A)).toBe(true)
  })

  it("service is shown only for professionals in its eligibility list", () => {
    expect(isServiceEligible({ professional_ids: [PRO_A] }, PRO_A)).toBe(true)
    expect(isServiceEligible({ professional_ids: [PRO_A] }, PRO_B)).toBe(false)
  })

  it("with no professional selected, every service is eligible", () => {
    expect(isServiceEligible({ professional_ids: [PRO_A] }, "")).toBe(true)
  })
})
