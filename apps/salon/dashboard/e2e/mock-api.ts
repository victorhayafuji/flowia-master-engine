import { Page, expect } from '@playwright/test'

export const ORG_A = '22222222-2222-2222-2222-222222222222'

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v1'

type UserRole = 'org_admin' | 'super_admin'

interface MockState {
  patients: Array<{ id: string; name: string; phone: string; created_at: string }>
  services: Array<{ id: string; name: string; duration_minutes: number; price: number; professional_id?: string }>
  professionals: Array<{ id: string; name: string; specialty?: string }>
  appointments: Array<Record<string, unknown>>
  chatResponses: Record<string, string>
}

export function createMockState(): MockState {
  return {
    patients: [],
    services: [],
    professionals: [],
    appointments: [],
    chatResponses: {
      'quanto custa corte feminino': 'O corte feminino custa R$ 120,00.',
      'quero agendar corte feminino amanhã': 'Temos horários às 10:00, 10:30 e 14:00. Qual prefere?',
    },
  }
}

export async function setupApiMocks(page: Page, role: UserRole = 'org_admin', state = createMockState()) {
  const user = {
    username: role === 'org_admin' ? 'owner@salao.com' : 'admin@flowia.com',
    role,
    organization_id: ORG_A,
    organization_name: 'Salão Beauty Express',
  }

  await page.route(`${API_BASE}/**`, async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace('/api/v1', '')
    const method = route.request().method()

    if (path === '/auth/me' && method === 'GET') {
      return route.fulfill({ json: { status: 'success', user } })
    }

    if (path === '/auth/login' && method === 'POST') {
      return route.fulfill({ json: { status: 'success' } })
    }

    if (path === '/auth/logout' && method === 'POST') {
      return route.fulfill({ json: { status: 'success' } })
    }

    if (path.startsWith('/organizations') && path.endsWith('/') && method === 'GET' && role === 'super_admin') {
      return route.fulfill({
        json: {
          status: 'success',
          data: [
            { id: ORG_A, name: 'Salão Beauty Express', vertical: 'salon' },
            { id: '33333333-3333-3333-3333-333333333333', name: 'Outro Salão', vertical: 'salon' },
          ],
        },
      })
    }

    if (path === '/patients/' && method === 'GET') {
      return route.fulfill({ json: { status: 'success', data: state.patients } })
    }

    if (path === '/patients/' && method === 'POST') {
      const body = route.request().postDataJSON() as { name: string; phone: string }
      const row = {
        id: `pat-${state.patients.length + 1}`,
        name: body.name,
        phone: body.phone,
        created_at: new Date().toISOString(),
      }
      state.patients.unshift(row)
      return route.fulfill({ json: { status: 'success', data: row } })
    }

    if (path === '/organizations/services' && method === 'GET') {
      return route.fulfill({ json: { status: 'success', data: state.services } })
    }

    if (path === '/organizations/services' && method === 'POST') {
      const body = route.request().postDataJSON() as {
        name: string
        duration_minutes: number
        price: number
        professional_id?: string
      }
      const row = {
        id: `svc-${state.services.length + 1}`,
        ...body,
        professional_id: body.professional_id || state.professionals[0]?.id,
      }
      state.services.push(row)
      return route.fulfill({ json: { status: 'success', data: row } })
    }

    if (path === '/organizations/professionals' && method === 'GET') {
      return route.fulfill({ json: { status: 'success', data: state.professionals } })
    }

    if (path === '/organizations/professionals' && method === 'POST') {
      const body = route.request().postDataJSON() as { name: string; specialty?: string }
      const row = { id: `prof-${state.professionals.length + 1}`, name: body.name, specialty: body.specialty }
      state.professionals.push(row)
      return route.fulfill({ json: { status: 'success', data: row } })
    }

    if (path.startsWith('/scheduling/calendar') && method === 'GET') {
      return route.fulfill({ json: { status: 'success', data: state.appointments } })
    }

    if (path === '/scheduling/' && method === 'POST') {
      const body = route.request().postDataJSON() as Record<string, unknown>
      const patient = state.patients.find((p) => p.id === body.patient_id)
      const service = state.services.find((s) => s.id === body.service_id)
      const row = {
        id: `appt-${state.appointments.length + 1}`,
        ...body,
        status: 'confirmed',
        patient: patient ? { name: patient.name } : { name: 'Cliente' },
        service: service ? { name: service.name } : { name: 'Serviço' },
      }
      state.appointments.push(row)
      return route.fulfill({ json: { status: 'success', data: row } })
    }

    if (path === '/chat/test' && method === 'POST') {
      const body = route.request().postDataJSON() as { message: string }
      const msg = body.message.toLowerCase()
      let response = 'Resposta mock do agente.'
      if (msg.includes('quanto') && msg.includes('corte')) {
        response = state.chatResponses['quanto custa corte feminino']
      } else if (msg.includes('agendar')) {
        response = state.chatResponses['quero agendar corte feminino amanhã']
      }
      return route.fulfill({
        json: {
          response,
          agent: 'recepcionista',
          thread_id: 'thread-mock',
          tokens_used: 10,
          tokens_in: 5,
          tokens_out: 5,
          estimated_cost_brl: 0.01,
        },
      })
    }

    return route.fulfill({ status: 404, json: { detail: `Unmocked ${method} ${path}` } })
  })

  return state
}

export async function loginAsOrgAdmin(page: Page, state = createMockState()) {
  await setupApiMocks(page, 'org_admin', state)
  await page.addInitScript(() => localStorage.clear())
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Agenda' })).toBeVisible()
  return state
}

export async function loginAsSuperAdmin(page: Page, state = createMockState()) {
  await setupApiMocks(page, 'super_admin', state)
  await page.addInitScript(() => localStorage.clear())
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Agenda' })).toBeVisible()
  return state
}
