import { expect, test } from '@playwright/test'
import { createMockState, loginAsSuperAdmin } from './mock-api'

function seededState() {
  const state = createMockState()
  state.services.push({ id: 'svc-1', name: 'Corte Feminino', duration_minutes: 30, price: 120 })
  state.professionals.push({ id: 'prof-1', name: 'Ana Costa' })
  state.patients.push({
    id: 'pat-1',
    name: 'Maria Silva',
    phone: '5511999999999',
    created_at: new Date().toISOString(),
  })
  return state
}

test.describe('Hybrid agent — menu + guided booking + FAQ', () => {
  test('greeting → menu → Agendar → service → ... → confirm creates appointment', async ({ page }) => {
    const state = seededState()
    await loginAsSuperAdmin(page, state)
    await page.goto('/chat-test')

    const input = page.getByRole('textbox')
    const send = page.getByRole('button', { name: /Enviar/i })

    // Client chosen on the test page (simulates phone identification).
    await page.getByTestId('chat-patient-select').selectOption('pat-1')

    // Greeting → entry menu.
    await input.fill('oi')
    await send.click()
    await expect(page.getByText('Como posso te ajudar?')).toBeVisible({ timeout: 10000 })
    await page.getByTestId('guided-option-menu_book').click()

    await expect(page.getByText('Qual serviço você deseja?')).toBeVisible()
    await page.getByTestId('guided-option-svc-1').click()
    await expect(page.getByText('Com qual profissional?')).toBeVisible()
    await page.getByTestId('guided-option-prof-1').click()
    await expect(page.getByText('Para qual dia?')).toBeVisible()
    await page.locator('[data-testid^="guided-option-"]').first().click()
    await expect(page.getByText('Qual horário?')).toBeVisible()
    await page.getByTestId('guided-option-2027-01-04T09:00:00').click()
    await expect(page.getByText('Confirmar agendamento?')).toBeVisible()
    await page.getByTestId('guided-option-confirm').click()

    await expect(page.getByText(/confirmado/i)).toBeVisible()
    // Post-booking actions appear.
    await expect(page.getByTestId('guided-option-book_again')).toBeVisible()
    expect(state.appointments.length).toBe(1)
  })

  test('greeting → menu → FAQ → topic returns an answer from the KB', async ({ page }) => {
    const state = seededState()
    await loginAsSuperAdmin(page, state)
    await page.goto('/chat-test')

    const input = page.getByRole('textbox')
    const send = page.getByRole('button', { name: /Enviar/i })

    // Pick a client so the post-FAQ "Agendar serviço" goes straight to the service step.
    await page.getByTestId('chat-patient-select').selectOption('pat-1')

    await input.fill('oi')
    await send.click()
    await expect(page.getByText('Como posso te ajudar?')).toBeVisible({ timeout: 10000 })
    await page.getByTestId('guided-option-menu_faq').click()

    await expect(page.getByText('Sobre o que é sua dúvida?')).toBeVisible()
    await page.getByTestId('guided-option-faq_precos').click()
    await expect(page.getByText(/R\$ 120,00/)).toBeVisible()

    // FAQ answer is not a dead-end: buttons return to the deterministic flow.
    await expect(page.getByTestId('guided-option-menu_book')).toBeVisible()
    await page.getByTestId('guided-option-menu_book').click()
    await expect(page.getByText('Qual serviço você deseja?')).toBeVisible()
  })

  test('unregistered client → onboarding asks name/phone then proceeds', async ({ page }) => {
    const state = seededState()
    await loginAsSuperAdmin(page, state)
    await page.goto('/chat-test')

    const input = page.getByRole('textbox')
    const send = page.getByRole('button', { name: /Enviar/i })

    // Selector defaults to "Cliente não cadastrado" (value "").
    await input.fill('quero agendar')
    await send.click()
    await expect(page.getByText(/nome e o telefone/i)).toBeVisible({ timeout: 10000 })

    await input.fill('Joana Souza 11988887777')
    await send.click()
    await expect(page.getByText('Qual serviço você deseja?')).toBeVisible()
  })
})
