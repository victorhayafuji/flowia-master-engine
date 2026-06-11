/**
 * Brazilian phone display formatting.
 *
 * Accepts the raw values stored in patients.phone (10–13 digits per the
 * booking guardrails). Anything outside that range — e.g. WhatsApp wa_ids
 * with 15+ digits, empty strings — is returned untouched.
 */
export function formatPhoneBR(raw: string): string {
  // Strip common phone punctuation; anything else left (letters, ids) means
  // this is not a phone number — return it untouched.
  const stripped = (raw || "").replace(/[\s().+-]/g, "")
  if (!/^\d*$/.test(stripped)) return raw
  const digits = stripped

  if (digits.length === 13 && digits.startsWith("55")) {
    return `+55 (${digits.slice(2, 4)}) ${digits.slice(4, 9)}-${digits.slice(9)}`
  }
  if (digits.length === 12 && digits.startsWith("55")) {
    return `+55 (${digits.slice(2, 4)}) ${digits.slice(4, 8)}-${digits.slice(8)}`
  }
  if (digits.length === 11) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`
  }
  return raw
}
