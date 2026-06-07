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
  upload: async (endpoint: string, formData: FormData, headers: HeadersInit = {}) => {
    const res = await safeFetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: { ...headers },
      body: formData,
      credentials: 'include',
    })
    return parseResponse(res)
  },
}
