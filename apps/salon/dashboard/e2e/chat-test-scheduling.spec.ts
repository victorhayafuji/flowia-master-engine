import { expect, test } from '@playwright/test'
import { loginAsSuperAdmin } from './mock-api'

test.describe('Audit #6 — chat test scheduling', () => {
  test('returns available slots from mocked chat response', async ({ page }) => {
    await loginAsSuperAdmin(page)
    await page.goto('/admin/chat-test')

    await page.getByRole('button', { name: /Quero agendar manicure amanhã/i }).click()
    await expect(page.getByText(/10:00|horários/i)).toBeVisible({ timeout: 10000 })
  })
})
