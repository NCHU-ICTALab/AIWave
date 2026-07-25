// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

const PERSISTED_INQUIRY = {
  id: 'INQ-20260725-009',
  form_id: 901,
  status: 'pending_quote',
  created_at: '2026-07-25T00:00:00Z',
  events: [{ type: 'inquiry.created', occurred_at: '2026-07-25T00:00:00Z' }],
}

describe('order backend projection', () => {
  it('restores a persisted AI inquiry after a fresh page load', async () => {
    stubCatalogFetch((url) =>
      url.endsWith('/api/v1/inquiries')
        ? new Response(JSON.stringify({ data: [PERSISTED_INQUIRY] }), {
            status: 200, headers: { 'Content-Type': 'application/json' },
          })
        : undefined,
    )
    const { wrapper } = await mountApp('/user/orders')

    expect(wrapper.text()).toContain('INQ-20260725-009')
    expect(wrapper.text()).toContain('已同步後端諮詢紀錄')
  })
})
