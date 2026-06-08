import { expect, test } from '@playwright/test'
import { loginAsSuperAdmin } from './mock-api'

test.describe('Audit #6 — chat test scheduling', () => {
  test('returns available slots from mocked chat response', async ({ page }) => {
    await loginAsSuperAdmin(page)
    await page.goto('/admin/chat-test')

    await page.getByRole('button', { name: /Quero agendar manicure amanhã/i }).click()
    await expect(page.getByText(/10:00|horários/i)).toBeVisible({ timeout: 10000 })
  })

  test('shows deterministic path badge for mechas sexta', async ({ page }) => {
    await loginAsSuperAdmin(page)
    await page.goto('/admin/chat-test')

    await page.getByRole('textbox').fill('Quero mechas sexta')
    await page.getByRole('button', { name: /Enviar/i }).click()

    await expect(page.getByText(/path=deterministic/i)).toBeVisible({ timeout: 10000 })
    await expect(page.getByText(/triage=keyword/i)).toBeVisible()
    await expect(page.getByText(/Coloração Completa/i)).toBeVisible()
    await expect(page.getByText(/14:00/)).toBeVisible()
    await expect(page.getByText(/agent=scheduling/i)).toBeVisible()
    await expect(page.getByText(/tokens=0/i)).toBeVisible()
  })

  test('multi-turn booking flow reaches confirmation', async ({ page }) => {
    await loginAsSuperAdmin(page)
    await page.goto('/admin/chat-test')

    const input = page.getByRole('textbox')
    const send = page.getByRole('button', { name: /Enviar/i })

    await input.fill('Quero mechas sexta')
    await send.click()
    await expect(page.getByText(/Qual horário você prefere/i)).toBeVisible({ timeout: 10000 })

    await input.fill('14:00')
    await send.click()
    await expect(page.getByText(/nome completo e telefone/i)).toBeVisible({ timeout: 10000 })
    await expect(page.getByText(/path=deterministic/i)).toHaveCount(2)

    await input.fill('Maria Silva, telefone 11987654321')
    await send.click()
    await expect(page.getByText(/SUCESSO! Agendamento confirmado/i)).toBeVisible({ timeout: 10000 })
    await expect(page.getByText(/path=deterministic/i)).toHaveCount(3)
  })
})
