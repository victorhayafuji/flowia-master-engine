import { describe, expect, it } from "vitest"
import { buildWebhookUrl } from "./webhookUrl"

describe("buildWebhookUrl", () => {
  it("appends the webhook path to the API base", () => {
    expect(buildWebhookUrl("https://flowia-api.onrender.com/api/v1")).toBe(
      "https://flowia-api.onrender.com/api/v1/webhook/whatsapp",
    )
  })

  it("strips a trailing slash from the base", () => {
    expect(buildWebhookUrl("http://localhost:8000/api/v1/")).toBe(
      "http://localhost:8000/api/v1/webhook/whatsapp",
    )
  })

  it("handles multiple trailing slashes", () => {
    expect(buildWebhookUrl("http://localhost:8000/api/v1///")).toBe(
      "http://localhost:8000/api/v1/webhook/whatsapp",
    )
  })

  it("trims surrounding whitespace", () => {
    expect(buildWebhookUrl("  http://localhost:8000/api/v1  ")).toBe(
      "http://localhost:8000/api/v1/webhook/whatsapp",
    )
  })
})
