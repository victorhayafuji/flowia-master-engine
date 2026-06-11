/**
 * WhatsApp ghost registrations — patients auto-created by the webhook before
 * the booking flow captured a real name/phone. They show up as
 * "WhatsApp XXXX" with the wa_id (15+ digits) stored in the phone field.
 */
export interface RegistrationLike {
  name?: string | null
  phone?: string | null
}

export function isIncompleteRegistration(p: RegistrationLike): boolean {
  if (/^whatsapp\b/i.test(p.name ?? "")) return true
  const digits = (p.phone ?? "").replace(/\D/g, "")
  return digits.length > 13
}
