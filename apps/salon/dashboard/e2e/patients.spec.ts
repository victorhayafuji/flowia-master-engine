import { expect, test } from '@playwright/test'
import { loginAsOrgAdmin } from './mock-api'

test.describe('Audit #2 — create client', () => {
  test('creates patient with name and phone', async ({ page }) => {
    await loginAsOrgAdmin(page)
    await page.goto('/patients')

    await page.getByRole('button', { name: /Novo Registro/i }).click()
    await page.getByPlaceholder('EX: MARIA SILVA').fill('Ana Silva')
    await page.getByPlaceholder('EX: (11) 99999-9999').fill('11988887777')
    await page.getByRole('button', { name: 'Confirmar Registro' }).click()

    await expect(page.getByText('Ana Silva')).toBeVisible()
    await expect(page.getByText('11988887777')).toBeVisible()
  })
})
