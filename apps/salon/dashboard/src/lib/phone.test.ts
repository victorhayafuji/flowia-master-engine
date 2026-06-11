import { describe, expect, it } from "vitest"
import { formatPhoneBR } from "./phone"

describe("formatPhoneBR", () => {
  it("formats 13-digit numbers with country code (mobile)", () => {
    expect(formatPhoneBR("5511987654323")).toBe("+55 (11) 98765-4323")
  })

  it("formats 12-digit numbers with country code (landline)", () => {
    expect(formatPhoneBR("551133334444")).toBe("+55 (11) 3333-4444")
  })

  it("formats 11-digit local mobile numbers", () => {
    expect(formatPhoneBR("11988887777")).toBe("(11) 98888-7777")
  })

  it("formats 10-digit local landline numbers", () => {
    expect(formatPhoneBR("1133334444")).toBe("(11) 3333-4444")
  })

  it("ignores existing punctuation when formatting", () => {
    expect(formatPhoneBR("(11) 98888-7777")).toBe("(11) 98888-7777")
  })

  it("returns wa_ids and other out-of-range values untouched", () => {
    expect(formatPhoneBR("182084464137453080")).toBe("182084464137453080")
    expect(formatPhoneBR("55119053d2b9f")).toBe("55119053d2b9f")
    expect(formatPhoneBR("")).toBe("")
  })
})
