import { expect, test } from '@playwright/test'
import { loginAsSuperAdmin } from './mock-api'

test.describe('Audit #5 — chat test RAG', () => {
  test('returns price from mocked chat response', async ({ page }) => {
    await loginAsSuperAdmin(page)
    await page.goto('/chat-test')

    await page.getByRole('button', { name: /Quanto custa corte feminino/i }).click()
    await expect(page.getByText(/R\$ 120/)).toBeVisible({ timeout: 10000 })
  })
})
