import { expect, test } from '@playwright/test'
import { loginAsProfessional } from './mock-api'

test.describe('Professional role — scoped navigation', () => {
  test('sees agenda but not clients or catalog', async ({ page }) => {
    await loginAsProfessional(page)

    await expect(page.getByRole('link', { name: 'Visão Geral' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Agenda' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Clientes' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Catálogo' })).toHaveCount(0)
    await expect(page.getByText('Salão ativo')).toHaveCount(0)
  })
})
