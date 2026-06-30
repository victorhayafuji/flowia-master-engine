// Kiosk API client. Auth is the device token (no cookie); the org is resolved
// server-side from the token. A 403 means the device is unpaired/revoked.

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"

export interface StepOption {
  id: string
  title: string
  description?: string | null
}

export interface GuidedStep {
  step: string
  text: string
  kind: "list" | "buttons" | "input"
  options: StepOption[]
}

export interface TurnResponse {
  session_id: string
  response: string
  step: GuidedStep | null
  done: boolean
}

/** Thrown on HTTP 403 — the device token is missing/invalid/revoked. */
export class DeviceUnauthorized extends Error {}

async function post<T>(path: string, token: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-device-token": token },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new Error("Sem conexão com o servidor. Tente novamente.")
  }
  if (res.status === 403) throw new DeviceUnauthorized("device unauthorized")
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      if (data?.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

/** Begin an attendance; returns the identification step. Also validates the token. */
export const startSession = (token: string) => post<TurnResponse>("/kiosk/session", token)

/** Apply one selection/input and get the next step or a terminal result. */
export const advance = (token: string, sessionId: string, selection: string) =>
  post<TurnResponse>("/kiosk/advance", token, { session_id: sessionId, selection })
