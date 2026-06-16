/**
 * Builds the WhatsApp webhook callback URL the owner pastes into Meta.
 * The API base already ends in `/api/v1`, so the webhook lives at `/api/v1/webhook/whatsapp`.
 */
export function buildWebhookUrl(apiBase: string): string {
  const trimmed = (apiBase || "").trim().replace(/\/+$/, "")
  return `${trimmed}/webhook/whatsapp`
}
