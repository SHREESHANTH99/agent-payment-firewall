import { test, expect } from '@playwright/test'

test('renders the playground with a mocked demo session', async ({ page }) => {
  await page.route('**/demo/sessions', async (route) => route.fulfill({
    status: 201,
    contentType: 'application/json',
    body: JSON.stringify({
      session_secret: 'playwright-session-secret',
      session: {
        id: 'playwright-session', created_at: '2026-11-06T00:00:00Z', expires_at: '2026-11-07T00:00:00Z',
        quota: { limit: 10, used: 0, remaining: 10 }, config: { canary_enabled: true, judge_enabled: true },
        agents: [
          { id: 'A', name: 'Checkout agent', description: 'Sandbox buyer', mandate: { mandate_id: 'mnd-a', budget_total_cents: 10000, per_transaction_cap_cents: 5000, allowlist_merchants: ['seller-one@example.test'], allowed_currencies: ['USD'], period: 'lifetime', valid_from: '2026-11-06T00:00:00Z', valid_until: '2026-11-07T00:00:00Z', escalation_threshold_cents: 4000, spent_cents: 0, reserved_cents: 0, remaining_cents: 10000, status: 'active' } },
          { id: 'B', name: 'Research agent', description: 'Sandbox buyer', mandate: { mandate_id: 'mnd-b', budget_total_cents: 10000, per_transaction_cap_cents: 5000, allowlist_merchants: ['seller-one@example.test'], allowed_currencies: ['USD'], period: 'lifetime', valid_from: '2026-11-06T00:00:00Z', valid_until: '2026-11-07T00:00:00Z', escalation_threshold_cents: 4000, spent_cents: 0, reserved_cents: 0, remaining_cents: 10000, status: 'active' } },
        ],
      },
    }),
  }))
  await page.route('**/demo/attacks', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [{ id: 'clean_purchase', category: 'policy', name: 'Clean purchase', title: 'Clean purchase', description: 'Normal purchase', explanation: 'Safe', default_agent_id: 'A', default_intent: { amount: '25.00', merchant: 'seller-one@example.test', user_task: 'Buy the item.', source_context: 'The page lists the item.' } }] }) }))
  await page.route('**/demo/sessions/playwright-session/state', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      session: {
        id: 'playwright-session', created_at: '2026-11-06T00:00:00Z', expires_at: '2026-11-07T00:00:00Z',
        quota: { limit: 10, used: 0, remaining: 10 }, config: { canary_enabled: true, judge_enabled: true },
        agents: [
          { id: 'A', name: 'Checkout agent', description: 'Sandbox buyer', mandate: { mandate_id: 'mnd-a', budget_total_cents: 10000, per_transaction_cap_cents: 5000, allowlist_merchants: ['seller-one@example.test'], allowed_currencies: ['USD'], period: 'lifetime', valid_from: '2026-11-06T00:00:00Z', valid_until: '2026-11-07T00:00:00Z', escalation_threshold_cents: 4000, spent_cents: 0, reserved_cents: 0, remaining_cents: 10000, status: 'active' } },
          { id: 'B', name: 'Research agent', description: 'Sandbox buyer', mandate: { mandate_id: 'mnd-b', budget_total_cents: 10000, per_transaction_cap_cents: 5000, allowlist_merchants: ['seller-one@example.test'], allowed_currencies: ['USD'], period: 'lifetime', valid_from: '2026-11-06T00:00:00Z', valid_until: '2026-11-07T00:00:00Z', escalation_threshold_cents: 4000, spent_cents: 0, reserved_cents: 0, remaining_cents: 10000, status: 'active' } },
        ],
        escalations: [], recent_intents: [],
      },
    }),
  }))

  await page.goto('/playground')
  await expect(page.getByRole('heading', { name: 'Judge Playground' })).toBeVisible()
  await expect(page.getByText('Clean purchase')).toBeVisible()
  await expect(page.getByText('Use it as an API')).toBeVisible()
})
