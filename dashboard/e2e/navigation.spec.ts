import { test, expect } from '@playwright/test'

test.describe('Navigation loop tests', () => {
  test('signed out user can navigate landing -> sample console -> exit without loops', async ({ page }) => {
    // 1. Visit landing
    await page.goto('/')
    await expect(page.getByRole('link', { name: 'Try the Playground' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'View sample console' })).toBeVisible()

    // 2. Click "View sample console"
    await page.getByRole('link', { name: 'View sample console' }).click()
    await expect(page).toHaveURL(/.*\/console\?demo=1/)
    await expect(page.getByText('Sample data. No real transactions.')).toBeVisible()

    // 3. Click "Exit sample mode"
    await page.getByRole('button', { name: 'Exit sample mode' }).click()
    await expect(page).toHaveURL(/.*\/console\/login/)
    await expect(page.getByText('Operator authentication')).toBeVisible()

    // 4. Click "Explore in demo mode" on login page -> goes directly to sample console, NOT playground
    await page.getByRole('button', { name: 'Explore in demo mode' }).click()
    await expect(page).toHaveURL(/.*\/console\?demo=1/)
    await expect(page.getByText('Sample data. No real transactions.')).toBeVisible()
  })

  test('playground header links navigate to Home and Sample console', async ({ page }) => {
    await page.route('**/demo/sessions', async (route) => route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        session_secret: 'mock-secret',
        session: {
          id: 'demo-test', created_at: new Date().toISOString(), expires_at: new Date().toISOString(),
          quota: { limit: 10, used: 0, remaining: 10 }, config: { canary_enabled: true, judge_enabled: true },
          agents: [
            { id: 'A', name: 'Agent A', description: 'Buyer', mandate: { mandate_id: 'mnd-a', budget_total_cents: 10000, per_transaction_cap_cents: 5000, allowlist_merchants: ['seller@example.com'], allowed_currencies: ['USD'], period: 'lifetime', valid_from: new Date().toISOString(), valid_until: new Date().toISOString(), escalation_threshold_cents: null, spent_cents: 0, reserved_cents: 0, remaining_cents: 10000, status: 'active' } }
          ]
        }
      })
    }))
    await page.route('**/demo/attacks', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) }))
    await page.route('**/demo/sessions/demo-test/state', async (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session: {
          id: 'demo-test', created_at: new Date().toISOString(), expires_at: new Date().toISOString(),
          quota: { limit: 10, used: 0, remaining: 10 }, config: { canary_enabled: true, judge_enabled: true },
          agents: []
        }
      })
    }))

    await page.goto('/playground')
    await expect(page.getByRole('link', { name: 'Home' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Sample console' })).toBeVisible()

    // Click Sample console from playground
    await page.getByRole('link', { name: 'Sample console' }).click()
    await expect(page).toHaveURL(/.*\/console\?demo=1/)
  })
})
