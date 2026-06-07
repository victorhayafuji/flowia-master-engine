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
})
