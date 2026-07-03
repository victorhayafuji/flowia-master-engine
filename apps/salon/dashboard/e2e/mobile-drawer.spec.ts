import { expect, test } from '@playwright/test'
import { loginAsOrgAdmin } from './mock-api'

// Regression coverage for the mobile drawer visual-hardening pass: the drawer must
// be opaque enough to block reading the page behind it, the backdrop must actually
// block clicks (not just look darker), and the header's own wordmark must not stay
// visible (duplicated) once the drawer is open.
test.describe('Mobile drawer (412×890 viewport)', () => {
  test.use({ viewport: { width: 412, height: 890 } })

  test('opens via hamburger with legible, visible nav items', async ({ page }) => {
    await loginAsOrgAdmin(page)

    await page.getByRole('button', { name: 'Abrir menu' }).click()

    const drawer = page.getByTestId('mobile-drawer')
    await expect(drawer).toBeVisible()
    await expect(drawer.getByRole('link', { name: 'Visão Geral' })).toBeVisible()
    await expect(drawer.getByRole('link', { name: 'Agenda' })).toBeVisible()
    await expect(drawer.getByRole('link', { name: 'Clientes' })).toBeVisible()
    await expect(drawer.getByRole('link', { name: 'Catálogo' })).toBeVisible()
  })

  test('exactly one "FlowIA" wordmark is visible while the drawer is open', async ({ page }) => {
    await loginAsOrgAdmin(page)

    // Count wordmarks that are actually rendered on-screen. `display:none` shows up
    // as offsetParent === null; the header uses `invisible` (visibility:hidden)
    // instead — to avoid layout shift — so computed visibility is checked too; and
    // the drawer stays translated off-canvas while closed, so its bounding box must
    // also fall outside the viewport.
    const countVisibleWordmarks = () =>
      page.getByText('FlowIA', { exact: true }).evaluateAll((nodes) =>
        nodes.filter((n) => {
          const el = n as HTMLElement
          if (el.offsetParent === null) return false
          if (getComputedStyle(el).visibility === 'hidden') return false
          const rect = el.getBoundingClientRect()
          return rect.right > 0 && rect.left < window.innerWidth
        }).length
      )

    // Before opening: the drawer sits off-screen (translate-x-full), so only the
    // mobile header's wordmark is on-screen.
    expect(await countVisibleWordmarks()).toBe(1)

    await page.getByRole('button', { name: 'Abrir menu' }).click()

    // After opening: the header wordmark must hide (not just render behind
    // translucent glass), leaving only the drawer's own wordmark in view.
    await expect(page.getByTestId('mobile-drawer').getByText('FlowIA', { exact: true })).toBeInViewport()
    expect(await countVisibleWordmarks()).toBe(1)
  })

  test('backdrop blocks interaction with the page behind it and closes the drawer', async ({ page }) => {
    await loginAsOrgAdmin(page)

    await page.getByRole('button', { name: 'Abrir menu' }).click()
    const backdrop = page.getByTestId('mobile-drawer-backdrop')
    await expect(backdrop).toBeVisible()

    // Clicking the backdrop must only close the drawer — not navigate/act on
    // whatever page content sits behind it. Click near the right edge, clear of
    // the 256px-wide drawer, so the click can't land on the drawer itself.
    const urlBeforeClick = page.url()
    await backdrop.click({ position: { x: 400, y: 400 } })

    await expect(page.getByTestId('mobile-drawer-backdrop')).toHaveCount(0)
    expect(page.url()).toBe(urlBeforeClick)
    await expect(page.getByTestId('mobile-drawer')).not.toBeInViewport()
  })

  test('closes via the X button', async ({ page }) => {
    await loginAsOrgAdmin(page)

    await page.getByRole('button', { name: 'Abrir menu' }).click()
    await expect(page.getByTestId('mobile-drawer-backdrop')).toBeVisible()

    await page.getByRole('button', { name: 'Fechar menu' }).click()

    await expect(page.getByTestId('mobile-drawer-backdrop')).toHaveCount(0)
  })

  test('closes via Escape', async ({ page }) => {
    await loginAsOrgAdmin(page)

    await page.getByRole('button', { name: 'Abrir menu' }).click()
    await expect(page.getByTestId('mobile-drawer-backdrop')).toBeVisible()

    await page.keyboard.press('Escape')

    await expect(page.getByTestId('mobile-drawer-backdrop')).toHaveCount(0)
  })

  test('main content is inert while the drawer is open (native focus trap)', async ({ page }) => {
    await loginAsOrgAdmin(page)

    await page.getByRole('button', { name: 'Abrir menu' }).click()

    // `inert` makes descendants unfocusable/unclickable for assistive tech — a link
    // in the page behind the drawer must not be reachable while the drawer is open.
    await expect(page.locator('main')).toHaveJSProperty('inert', true)

    await page.getByRole('button', { name: 'Fechar menu' }).click()
    await expect(page.locator('main')).toHaveJSProperty('inert', false)
  })
})
