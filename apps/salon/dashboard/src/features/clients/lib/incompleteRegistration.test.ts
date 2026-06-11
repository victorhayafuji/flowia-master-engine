import { describe, expect, it } from "vitest"
import { isIncompleteRegistration } from "./incompleteRegistration"

describe("isIncompleteRegistration", () => {
  it("flags WhatsApp auto-created names", () => {
    expect(isIncompleteRegistration({ name: "WhatsApp 8D0F", phone: "182084464137453080" })).toBe(true)
    expect(isIncompleteRegistration({ name: "whatsapp 008e", phone: "" })).toBe(true)
  })

  it("flags wa_id-length phones even with a real-looking name", () => {
    expect(isIncompleteRegistration({ name: "Cliente", phone: "8309909154086575680" })).toBe(true)
  })

  it("keeps real registrations", () => {
    expect(isIncompleteRegistration({ name: "Juliana Pereira", phone: "11988887777" })).toBe(false)
    expect(isIncompleteRegistration({ name: "João Silva", phone: "5511987654323" })).toBe(false)
    expect(isIncompleteRegistration({ name: "", phone: "" })).toBe(false)
  })

  it("does not flag names merely containing whatsapp", () => {
    expect(isIncompleteRegistration({ name: "Maria do WhatsApp", phone: "11988887777" })).toBe(false)
  })
})
