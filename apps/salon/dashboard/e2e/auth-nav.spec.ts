import { expect, test } from '@playwright/test'
import { loginAsOrgAdmin } from './mock-api'

test.describe('Audit #1 — org_admin nav', () => {
  test('no org selector and no dev admin links', async ({ page }) => {
    await loginAsOrgAdmin(page)

    await expect(page.getByText('Salão ativo')).toHaveCount(0)
    await expect(page.getByText('Data Lake (dev)')).toHaveCount(0)
    await expect(page.getByText('Chat Test (dev)')).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Agenda' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Clientes' })).toBeVisible()
  })
})
