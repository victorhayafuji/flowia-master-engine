import { expect, test } from '@playwright/test'
import { createMockState, loginAsOrgAdmin } from './mock-api'

test.describe('Audit #3 — create appointment', () => {
  test('creates appointment from agenda modal', async ({ page }) => {
    const state = createMockState()
    state.patients.push({
      id: 'p1',
      name: 'Maria',
      phone: '11999998888',
      created_at: new Date().toISOString(),
    })
    state.professionals.push({ id: 'prof1', name: 'João', specialty: 'Cabeleireiro' })
    state.services.push({
      id: 'svc1',
      name: 'Corte feminino',
      duration_minutes: 60,
      price: 120,
      professional_id: 'prof1',
    })

    await loginAsOrgAdmin(page, state)
    await page.goto('/agenda')
    await expect(page.getByRole('button', { name: 'Novo Agendamento' })).toBeVisible()
    await expect(page.locator('.animate-spin')).toHaveCount(0, { timeout: 10000 })

    await page.getByRole('button', { name: 'Semana' }).click()
    await expect(page.getByText('Profissional:')).toBeVisible()
    await page.locator('select').filter({ has: page.locator('option', { hasText: 'João' }) }).selectOption('prof1')

    await page.getByRole('button', { name: 'Novo Agendamento' }).click()

    const modalForm = page.locator('form').filter({ has: page.locator('input[type="date"]') })
    await modalForm.locator('select').nth(0).selectOption('p1')
    await modalForm.locator('select').nth(1).selectOption('prof1')
    await modalForm.locator('select').nth(2).selectOption('svc1')

    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    const dateValue = tomorrow.toISOString().split('T')[0]
    await modalForm.locator('input[type="date"]').fill(dateValue)
    await modalForm.locator('input[type="time"]').fill('10:00')
    await modalForm.getByRole('button', { name: 'Confirmar Agendamento' }).click()

    await expect(page.getByText('Sem Nome')).not.toBeVisible({ timeout: 10000 })
    await expect(page.getByText(/10:00.*Maria/)).toBeVisible()
  })
})
