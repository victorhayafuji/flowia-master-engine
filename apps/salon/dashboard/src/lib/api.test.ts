import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

describe('api client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('parses error detail from failed GET', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      json: async () => ({ detail: 'Organização não autorizada' }),
    }))

    await expect(api.get('/scheduling/calendar')).rejects.toThrow(
      'Organização não autorizada'
    )
  })

  it('shows friendly message on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(api.post('/auth/login', { username: 'a', password: 'b' })).rejects.toThrow(
      /Não foi possível conectar ao backend/
    )
  })

  it('returns JSON on successful POST', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success' }),
    }))

    const result = await api.post('/auth/login', { username: 'a', password: 'b' })
    expect(result).toEqual({ status: 'success' })
  })
})
