import { expect, test } from '@playwright/test'
import { createMockState, loginAsOrgAdmin } from './mock-api'

test.describe('Audit #4 — catalog with professional', () => {
  test('creates professional and service', async ({ page }) => {
    const state = createMockState()
    await loginAsOrgAdmin(page, state)
    await page.goto('/catalog')

    await page.getByRole('button', { name: 'Novo' }).nth(1).click()
    await page.getByPlaceholder('EX: MARIA SILVA').fill('Carla Pro')
    await page.getByRole('button', { name: 'Confirmar Profissional' }).click()
    await expect(page.getByText('Carla Pro')).toBeVisible()

    await page.getByRole('button', { name: 'Novo' }).first().click()
    await page.getByPlaceholder('EX: CORTE FEMININO').fill('Corte feminino')
    await page.getByRole('button', { name: 'Confirmar Serviço' }).click()
    await expect(page.getByText('Corte feminino')).toBeVisible()
  })

  test('edits professional schedule and service eligibility', async ({ page }) => {
    const state = createMockState()
    state.professionals.push({
      id: 'prof1',
      name: 'Maria Silva',
      specialty: 'Cabeleireira',
      appointment_buffer_minutes: 15,
      working_hours: { mon: { start: '08:00', end: '18:00' } },
      break_times: [],
    })
    state.services.push({
      id: 'svc1',
      name: 'Corte feminino',
      duration_minutes: 60,
      price: 120,
    })

    await loginAsOrgAdmin(page, state)
    await page.goto('/catalog')

    await page.getByRole('button', { name: 'Editar' }).click()
    await page.locator('select').filter({ hasText: '15 minutos' }).selectOption('30')
    await page.getByRole('button', { name: 'Salvar Profissional' }).click()
    await expect(page.getByText('buffer 30min')).toBeVisible()

    await page.getByRole('button', { name: 'Profissionais' }).click()
    await page.getByLabel('Maria Silva').check()
    await page.getByRole('button', { name: 'Salvar Elegibilidade' }).click()
    const serviceRow = page.getByRole('heading', { name: 'Corte feminino' }).locator('..')
    await expect(serviceRow.getByText('Maria', { exact: true })).toBeVisible()
  })
})
