import { Page, expect } from '@playwright/test'

export const ORG_A = '22222222-2222-2222-2222-222222222222'

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v1'

type UserRole = 'org_admin' | 'super_admin' | 'professional'

const PROFESSIONAL_ID = 'prof1'

interface MockState {
  patients: Array<{
    id: string
    name: string
    phone: string
    created_at: string
    no_show_count?: number
    total_appointments?: number
    last_visit_at?: string | null
  }>
  services: Array<{ id: string; name: string; duration_minutes: number; price: number; professional_id?: string }>
  professionals: Array<{
    id: string
    name: string
    specialty?: string
    working_hours?: Record<string, { start: string; end: string }>
    break_times?: Array<{ start: string; end: string }>
    appointment_buffer_minutes?: number
  }>
  serviceProfessionals: Record<string, string[]>
  appointments: Array<Record<string, unknown>>
  chatResponses: Record<string, string>
}

export function createMockState(): MockState {
  return {
    patients: [],
    services: [],
    professionals: [],
    serviceProfessionals: {},
    appointments: [],
    chatResponses: {
      'quanto custa corte feminino': 'O corte feminino custa R$ 120,00.',
      'quero agendar corte feminino amanhã': 'Temos horários às 10:00, 10:30 e 14:00. Qual prefere?',
      'quero mechas sexta':
        "Horários para 'Coloração Completa' em 2026-06-12 (Brasília / America/Sao_Paulo):\n- Ana Costa: 14:00, 14:30, 15:00\n\nQual horário você prefere? (horário de Brasília)",
    },
  }
}

function buildMockChatResponse(message: string, state: MockState) {
  const base = {
    thread_id: 'thread-mock-e2e',
    messages_count: 2,
    handoff: false,
    estimated_cost_brl: 0,
  }

  if (message.includes('quanto') && message.includes('corte')) {
    return {
      ...base,
      response: state.chatResponses['quanto custa corte feminino'],
      agent: 'receptionist',
      tokens_used: 120,
      tokens_in: 80,
      tokens_out: 40,
      estimated_cost_brl: 0.002,
      scheduling_path: null,
      triage_source: 'llm',
    }
  }

  const hasPhone = /\d{10,13}/.test(message)
  const hasName = /maria|joao|pedro|silva|nome/.test(message)
  const hasTime = /\b([01]?\d|2[0-3]):[0-5]\d\b/.test(message)
  const isScheduling =
    message.includes('mecha') ||
    message.includes('agendar') ||
    message.includes('horário') ||
    message.includes('horario') ||
    hasTime ||
    (hasPhone && hasName)

  if (hasPhone && hasName && (hasTime || message.includes('telefone'))) {
    return {
      ...base,
      response:
        "SUCESSO! Agendamento confirmado para Maria Silva: 'Coloração Completa' em 12/06/2026 14:00.",
      agent: 'scheduling',
      tokens_used: 0,
      tokens_in: 0,
      tokens_out: 0,
      scheduling_path: 'deterministic',
      triage_source: 'conversation',
    }
  }

  if (hasTime && isScheduling) {
    return {
      ...base,
      response:
        "Anotei Coloração Completa no dia 2026-06-12 às 14:00. Para confirmar, me informe seu nome completo e telefone com DDD.",
      agent: 'scheduling',
      tokens_used: 0,
      tokens_in: 0,
      tokens_out: 0,
      scheduling_path: 'deterministic',
      triage_source: 'conversation',
    }
  }

  if (message.includes('mecha') || (message.includes('agendar') && message.includes('manicure'))) {
    const response =
      state.chatResponses['quero mechas sexta'] ||
      state.chatResponses['quero agendar corte feminino amanhã']
    return {
      ...base,
      response,
      agent: 'scheduling',
      tokens_used: 0,
      tokens_in: 0,
      tokens_out: 0,
      scheduling_path: 'deterministic',
      triage_source: message.includes('mecha') ? 'keyword' : 'keyword',
    }
  }

  if (message.includes('agendar')) {
    return {
      ...base,
      response: state.chatResponses['quero agendar corte feminino amanhã'],
      agent: 'scheduling',
      tokens_used: 0,
      tokens_in: 0,
      tokens_out: 0,
      scheduling_path: 'deterministic',
      triage_source: 'keyword',
    }
  }

  return {
    ...base,
    response: 'Resposta mock do agente.',
    agent: 'receptionist',
    tokens_used: 10,
    tokens_in: 5,
    tokens_out: 5,
    estimated_cost_brl: 0.01,
    scheduling_path: null,
    triage_source: 'llm',
  }
}

const USERNAMES: Record<UserRole, string> = {
  org_admin: 'owner@salao.com',
  super_admin: 'admin@flowia.com',
  professional: 'pro@salao.com',
}

export async function setupApiMocks(page: Page, role: UserRole = 'org_admin', state = createMockState()) {
  const user = {
    username: USERNAMES[role],
    role,
    organization_id: ORG_A,
    organization_name: 'Salão Beauty Express',
    ...(role === 'professional' ? { professional_id: PROFESSIONAL_ID } : {}),
  }

  // Per-thread state for the guided booking flow mock, driven through /chat/test.
  type GuidedMockOption = { id: string; title: string; description?: string | null }
  type GuidedMockData =
    | { type: 'step'; step: string; text: string; kind: string; options: GuidedMockOption[] }
    | { type: 'outcome'; success: boolean; message: string }
  const guidedSessions = new Map<string, { step: string; serviceId?: string }>()

  const dateOptions = () =>
    Array.from({ length: 5 }, (_, i) => {
      const d = new Date()
      d.setDate(d.getDate() + i)
      return d.toISOString().slice(0, 10)
    })
  const slotOptions = ['2027-01-04T09:00:00', '2027-01-04T09:30:00']

  function guidedReply(threadId: string, data: GuidedMockData) {
    const base = {
      agent: 'scheduling',
      tokens_used: 0,
      tokens_in: 0,
      tokens_out: 0,
      estimated_cost_brl: 0,
      thread_id: threadId,
      scheduling_path: 'deterministic',
      triage_source: 'guided',
      messages_count: 0,
      handoff: false,
    }
    return data.type === 'step'
      ? { ...base, response: data.text, step: data }
      : { ...base, response: data.message, step: null }
  }

  const serviceStep = (threadId: string) =>
    guidedReply(threadId, {
      type: 'step',
      step: 'service',
      text: 'Qual serviço você deseja?',
      kind: 'list',
      options: state.services.map((sv) => ({
        id: sv.id,
        title: sv.name,
        description: sv.price ? `R$ ${sv.price}` : null,
      })),
    })

  const faqAnswers: Record<string, string> = {
    faq_precos: 'O corte feminino custa R$ 120,00.',
    faq_horario: 'Funcionamos de segunda a sábado, das 9h às 19h.',
    faq_cancelamento: 'Cancele com até 24h de antecedência sem custo.',
    faq_pagamento: 'Aceitamos dinheiro, Pix e cartões.',
  }

  function startBooking(threadId: string, patientId: string | null) {
    if (patientId) {
      guidedSessions.set(threadId, { step: 'service' })
      return serviceStep(threadId)
    }
    guidedSessions.set(threadId, { step: 'patient_capture' })
    return guidedReply(threadId, {
      type: 'step',
      step: 'patient_capture',
      text: 'Qual o nome e o telefone (com DDD) do cliente?',
      kind: 'input',
      options: [],
    })
  }

  function mockGuidedTurn(message: string, threadId: string, patientId: string | null) {
    const active = guidedSessions.get(threadId)
    const sel = message
    const isIntent = /\bagendar\b|\bagendamento\b|\bmarcar\b/i.test(message)
    const isGreeting =
      /^(oi|ola|olá|opa|ei|bom dia|boa tarde|boa noite|menu|ajuda)\b/i.test(message.trim()) ||
      /^(sim|ok|okay|claro|beleza|blz|aceito|concordo|certo|pode)$/i.test(message.trim())

    // FAQ topic → mock RAG answer + buttons back to the deterministic flow.
    if (faqAnswers[sel]) {
      return {
        agent: 'receptionist',
        tokens_used: 50,
        tokens_in: 40,
        tokens_out: 10,
        estimated_cost_brl: 0.001,
        thread_id: threadId,
        scheduling_path: null,
        triage_source: 'llm',
        messages_count: 2,
        handoff: false,
        response: faqAnswers[sel],
        step: {
          type: 'step',
          step: 'faq_followup',
          text: 'Posso ajudar com mais alguma coisa?',
          kind: 'buttons',
          options: [
            { id: 'menu_book', title: 'Agendar serviço' },
            { id: 'menu_faq', title: 'Tirar outra dúvida' },
          ],
        },
      }
    }

    if (!active) {
      if (sel === 'menu_book' || isIntent) return startBooking(threadId, patientId)
      if (sel === 'menu_faq') {
        return guidedReply(threadId, {
          type: 'step',
          step: 'faq',
          text: 'Sobre o que é sua dúvida?',
          kind: 'list',
          options: [
            { id: 'faq_precos', title: 'Preços' },
            { id: 'faq_horario', title: 'Horário de funcionamento' },
            { id: 'faq_cancelamento', title: 'Cancelamento' },
            { id: 'faq_pagamento', title: 'Formas de pagamento' },
            { id: 'menu', title: '↩ Voltar ao menu' },
          ],
        })
      }
      if (isGreeting) {
        return guidedReply(threadId, {
          type: 'step',
          step: 'menu',
          text: 'Como posso te ajudar?',
          kind: 'buttons',
          options: [
            { id: 'menu_book', title: 'Agendar serviço' },
            { id: 'menu_faq', title: 'Tirar uma dúvida' },
          ],
        })
      }
      return null
    }

    const s = active
    if (s.step === 'patient_capture') {
      s.step = 'service'
      return serviceStep(threadId)
    } else if (s.step === 'service') {
      s.serviceId = sel
      s.step = 'professional'
      return guidedReply(threadId, {
        type: 'step',
        step: 'professional',
        text: 'Com qual profissional?',
        kind: 'list',
        options: state.professionals.map((p) => ({ id: p.id, title: p.name })),
      })
    } else if (s.step === 'professional') {
      s.step = 'date'
      return guidedReply(threadId, {
        type: 'step',
        step: 'date',
        text: 'Para qual dia?',
        kind: 'list',
        options: dateOptions().map((d) => ({ id: d, title: d })),
      })
    } else if (s.step === 'date') {
      s.step = 'slot'
      return guidedReply(threadId, {
        type: 'step',
        step: 'slot',
        text: 'Qual horário?',
        kind: 'list',
        options: slotOptions.map((sl) => ({ id: sl, title: sl.slice(11, 16) })),
      })
    } else if (s.step === 'slot') {
      s.step = 'confirm'
      return guidedReply(threadId, {
        type: 'step',
        step: 'confirm',
        text: 'Confirmar agendamento?',
        kind: 'buttons',
        options: [
          { id: 'confirm', title: 'Confirmar' },
          { id: 'back', title: '↩ Voltar' },
          { id: 'cancel', title: '✕ Cancelar' },
        ],
      })
    } else if (s.step === 'confirm') {
      if (sel === 'cancel') {
        guidedSessions.delete(threadId)
        return guidedReply(threadId, { type: 'outcome', success: false, message: 'Agendamento cancelado.' })
      }
      const svc = state.services.find((x) => x.id === s.serviceId)
      state.appointments.push({
        id: `appt-${state.appointments.length + 1}`,
        status: 'confirmed',
        service: svc ? { name: svc.name } : { name: 'Serviço' },
      })
      s.step = 'post'
      return guidedReply(threadId, {
        type: 'step',
        step: 'post',
        text: 'Agendamento confirmado para 09:00.',
        kind: 'buttons',
        options: [
          { id: 'book_again', title: 'Agendar outro' },
          { id: 'finish', title: 'Encerrar' },
        ],
      })
    } else if (s.step === 'post') {
      if (sel === 'book_again') {
        s.step = 'service'
        return serviceStep(threadId)
      }
      guidedSessions.delete(threadId)
      return guidedReply(threadId, { type: 'outcome', success: true, message: 'Tudo certo! 👋' })
    }

    return null
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
        no_show_count: 0,
        total_appointments: 0,
        last_visit_at: null,
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
      const row = {
        id: `prof-${state.professionals.length + 1}`,
        name: body.name,
        specialty: body.specialty,
        appointment_buffer_minutes: 15,
        working_hours: {
          mon: { start: '08:00', end: '18:00' },
          tue: { start: '08:00', end: '18:00' },
          wed: { start: '08:00', end: '18:00' },
          thu: { start: '08:00', end: '18:00' },
          fri: { start: '08:00', end: '18:00' },
        },
        break_times: [],
      }
      state.professionals.push(row)
      return route.fulfill({ json: { status: 'success', data: row } })
    }

    const profPutMatch = path.match(/^\/organizations\/professionals\/([^/]+)$/)
    if (profPutMatch && method === 'PUT') {
      const id = profPutMatch[1]
      const body = route.request().postDataJSON() as Record<string, unknown>
      const idx = state.professionals.findIndex((p) => p.id === id)
      if (idx < 0) return route.fulfill({ status: 404, json: { detail: 'Not found' } })
      state.professionals[idx] = { ...state.professionals[idx], ...body }
      return route.fulfill({ json: { status: 'success', data: state.professionals[idx] } })
    }

    const svcProGetMatch = path.match(/^\/organizations\/services\/([^/]+)\/professionals$/)
    if (svcProGetMatch && method === 'GET') {
      const serviceId = svcProGetMatch[1]
      const ids = state.serviceProfessionals[serviceId] || []
      const data = ids.map((pid) => {
        const pro = state.professionals.find((p) => p.id === pid)
        return { professional_id: pid, professional: pro ? { id: pro.id, name: pro.name } : { id: pid, name: pid } }
      })
      return route.fulfill({ json: { status: 'success', data } })
    }

    if (svcProGetMatch && method === 'PUT') {
      const serviceId = svcProGetMatch[1]
      const body = route.request().postDataJSON() as { professional_ids: string[] }
      state.serviceProfessionals[serviceId] = body.professional_ids || []
      return route.fulfill({
        json: { status: 'success', data: { service_id: serviceId, professional_ids: body.professional_ids } },
      })
    }

    if (path === '/dashboard/stats' && method === 'GET') {
      const totalNoShows = state.patients.reduce((sum, p) => sum + (p.no_show_count ?? 0), 0)
      return route.fulfill({
        json: {
          status: 'success',
          data: {
            patients: state.patients.length,
            totalNoShows,
            appointmentsToday: state.appointments.length,
            upcoming: state.appointments.slice(0, 5),
          },
        },
      })
    }

    if (path === '/dashboard/today-board' && method === 'GET') {
      return route.fulfill({
        json: {
          status: 'success',
          data: {
            date: new Date().toISOString().slice(0, 10),
            counts: { total: 0, in_progress: 0, completed: 0, no_show: 0, upcoming: 0 },
            board: [],
          },
        },
      })
    }

    if (path.startsWith('/scheduling/calendar') && method === 'GET') {
      return route.fulfill({ json: { status: 'success', data: state.appointments } })
    }

    const statusMatch = path.match(/^\/scheduling\/calendar\/([^/]+)\/status$/)
    if (statusMatch && method === 'PATCH') {
      const appointmentId = statusMatch[1]
      const body = route.request().postDataJSON() as { status?: string }
      const appt = state.appointments.find((a) => a.id === appointmentId)
      if (!appt) {
        return route.fulfill({ status: 404, json: { detail: 'Agendamento não encontrado.' } })
      }
      appt.status = body.status
      return route.fulfill({ json: { status: 'success', data: appt } })
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

    if (path === '/organizations/whatsapp' && method === 'GET') {
      return route.fulfill({
        json: {
          status: 'success',
          data: {
            whatsapp_phone_id: '',
            whatsapp_business_id: '',
            token_configured: false,
            token_preview: null,
            verify_token: 'mock-verify-token',
            webhook_url: 'https://flowia-api.onrender.com/api/v1/webhook/whatsapp',
          },
        },
      })
    }

    if (path === '/organizations/whatsapp' && method === 'PATCH') {
      return route.fulfill({ json: { status: 'success', data: { updated: true } } })
    }

    if (path === '/organizations/whatsapp/test' && method === 'POST') {
      const body = route.request().postDataJSON() as { whatsapp_phone_id?: string }
      const ok = Boolean(body.whatsapp_phone_id)
      return route.fulfill({
        json: {
          status: 'success',
          data: ok
            ? { ok: true, verified_name: 'Salão Beauty Express', display_phone_number: '+55 11 99999-0000' }
            : { ok: false, error: 'Credenciais inválidas ou sem permissão.' },
        },
      })
    }

    if (path === '/chat/test' && method === 'POST') {
      const body = route.request().postDataJSON() as {
        message: string
        thread_id?: string
        patient_id?: string | null
      }
      const threadId = body.thread_id || `mock-thread-${guidedSessions.size + 1}`
      const guided = mockGuidedTurn(body.message, threadId, body.patient_id || null)
      if (guided) return route.fulfill({ json: guided })
      const chat = buildMockChatResponse(body.message.toLowerCase(), state)
      return route.fulfill({ json: chat })
    }

    if (path === '/dashboard/agent-summary' && method === 'GET') {
      return route.fulfill({
        json: {
          status: 'success',
          data: { handoffsPending: 0, appointmentsWhatsappToday: 0, conversationsThisWeek: 0 },
        },
      })
    }

    if (path === '/dashboard/financial' && method === 'GET') {
      const zero = { amount: 0, count: 0 }
      const period = { billed: zero, to_bill: zero, loss: zero }
      return route.fulfill({
        json: { status: 'success', data: { day: period, month: period, year: period } },
      })
    }

    if (path === '/dashboard/professional-kpi' && method === 'GET') {
      const zero = { appointments: 0, clients: 0 }
      return route.fulfill({
        json: {
          status: 'success',
          data: {
            dates: { prev: '', current: '', next: '' },
            professionals: state.professionals.map((p) => ({
              professional: { id: p.id, name: p.name },
              prev: zero,
              current: zero,
              next: zero,
            })),
          },
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

export async function loginAsProfessional(page: Page, state = createMockState()) {
  await setupApiMocks(page, 'professional', state)
  await page.addInitScript(() => localStorage.clear())
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Agenda' })).toBeVisible()
  return state
}
