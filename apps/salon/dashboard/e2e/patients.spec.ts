import { expect, test } from '@playwright/test'
import { createMockState, loginAsOrgAdmin } from './mock-api'

test.describe('Audit #2 — create client', () => {
  test('creates patient with name and phone', async ({ page }) => {
    await loginAsOrgAdmin(page)
    await page.goto('/patients')

    await page.getByRole('button', { name: /Novo Registro/i }).click()
    await page.getByPlaceholder('EX: MARIA SILVA').fill('Ana Silva')
    await page.getByPlaceholder('EX: (11) 99999-9999').fill('11988887777')
    await page.getByRole('button', { name: 'Confirmar Registro' }).click()

    await expect(page.getByText('Ana Silva')).toBeVisible()
    // Phones are displayed formatted (formatPhoneBR)
    await expect(page.getByText('(11) 98888-7777')).toBeVisible()
    await expect(page.getByText('0 faltas')).toBeVisible()
  })

  test('shows no-show history for patients with absences', async ({ page }) => {
    const state = createMockState()
    state.patients.push({
      id: 'pat-risk',
      name: 'João Risco',
      phone: '11977776666',
      created_at: new Date().toISOString(),
      no_show_count: 3,
      total_appointments: 8,
      last_visit_at: '2026-05-01T14:00:00Z',
    })

    await loginAsOrgAdmin(page, state)
    await page.goto('/patients')

    await expect(page.getByText('João Risco')).toBeVisible()
    await expect(page.getByTestId('patient-no-show-pat-risk')).toHaveText('3 faltas')
    await expect(page.getByText('8 visitas')).toBeVisible()
  })
})
