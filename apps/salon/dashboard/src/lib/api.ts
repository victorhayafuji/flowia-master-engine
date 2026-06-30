const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

function networkErrorMessage(): string {
  return (
    `Não foi possível conectar ao backend em ${API_BASE_URL}. ` +
    'Verifique se o servidor FastAPI está rodando (porta 8000). ' +
    'Execute start_flowia.bat ou: python -m uvicorn main:app --port 8000'
  )
}

async function parseResponse(res: Response) {
  if (!res.ok) {
    let errorDetail = res.statusText
    try {
      const errorData = await res.json()
      if (errorData?.detail) {
        errorDetail = typeof errorData.detail === 'string'
          ? errorData.detail
          : JSON.stringify(errorData.detail)
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(errorDetail)
  }
  return res.json()
}

async function safeFetch(input: RequestInfo, init?: RequestInit) {
  try {
    return await fetch(input, init)
  } catch {
    throw new Error(networkErrorMessage())
  }
}

export const api = {
  get: async (endpoint: string, headers: HeadersInit = {}) => {
    const res = await safeFetch(`${API_BASE_URL}${endpoint}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      credentials: 'include',
    })
    return parseResponse(res)
  },
  post: async (endpoint: string, body: unknown, headers: HeadersInit = {}) => {
    const res = await safeFetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(body),
      credentials: 'include',
    })
    return parseResponse(res)
  },
  put: async (endpoint: string, body: unknown, headers: HeadersInit = {}) => {
    const res = await safeFetch(`${API_BASE_URL}${endpoint}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(body),
      credentials: 'include',
    })
    return parseResponse(res)
  },
  patch: async (endpoint: string, body: unknown, headers: HeadersInit = {}) => {
    const res = await safeFetch(`${API_BASE_URL}${endpoint}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(body),
      credentials: 'include',
    })
    return parseResponse(res)
  },
  upload: async (endpoint: string, formData: FormData, headers: HeadersInit = {}) => {
    const res = await safeFetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: { ...headers },
      body: formData,
      credentials: 'include',
    })
    return parseResponse(res)
  },
  del: async (endpoint: string, headers: HeadersInit = {}) => {
    const res = await safeFetch(`${API_BASE_URL}${endpoint}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      credentials: 'include',
    })
    return parseResponse(res)
  },
}

/** Update an appointment's status via PATCH /scheduling/calendar/{id}/status. */
export const updateAppointmentStatus = (
  id: string,
  status: string,
  orgHeader: Record<string, string> = {},
) => api.patch(`/scheduling/calendar/${id}/status`, { status }, orgHeader)

export interface WhatsAppConfigPayload {
  whatsapp_phone_id?: string
  whatsapp_access_token?: string
  whatsapp_business_id?: string
}

/** Read the org's WhatsApp config (token is returned masked). */
export const getWhatsAppConfig = (orgHeader: Record<string, string> = {}) =>
  api.get('/organizations/whatsapp', orgHeader)

/** Update the org's WhatsApp credentials. A blank token keeps the current one. */
export const updateWhatsAppConfig = (
  payload: WhatsAppConfigPayload,
  orgHeader: Record<string, string> = {},
) => api.patch('/organizations/whatsapp', payload, orgHeader)

/** Validate WhatsApp credentials against the Meta Graph API. */
export const testWhatsAppConfig = (
  payload: { whatsapp_phone_id?: string; whatsapp_access_token?: string },
  orgHeader: Record<string, string> = {},
) => api.post('/organizations/whatsapp/test', payload, orgHeader)

export interface KioskDevice {
  id: string
  label: string
  is_active: boolean
  created_at?: string
  last_seen_at?: string | null
}

/** List the org's totem (kiosk) devices — metadata only, never the token. */
export const listKioskDevices = (orgHeader: Record<string, string> = {}) =>
  api.get('/organizations/kiosk-devices', orgHeader)

/** Provision a new totem device. The returned token is shown ONCE. */
export const createKioskDevice = (
  label: string,
  orgHeader: Record<string, string> = {},
) => api.post('/organizations/kiosk-devices', { label }, orgHeader)

/** Revoke (deactivate) a totem device. */
export const revokeKioskDevice = (
  deviceId: string,
  orgHeader: Record<string, string> = {},
) => api.del(`/organizations/kiosk-devices/${deviceId}`, orgHeader)
