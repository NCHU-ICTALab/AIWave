// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

const ADMIN_FREE_PARTNER = { role: 'partner' as const, accountId: null, displayName: '合作廠商' }

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

const SUBMITTED = {
  id: 'INQ-20260725-001',
  form_id: 105,
  service_id: 'service-repair',
  status: 'pending_quote',
  status_label: '待廠商報價',
  official_status: '12',
  summary: [{ label: '修繕項目', value: '燈具／開關' }],
  quote: null,
  created_at: '2026-07-25T00:00:00Z',
  events: [{ type: 'inquiry.created', occurred_at: '2026-07-25T00:00:00Z' }],
}

const QUOTED = {
  ...SUBMITTED,
  status: 'quoted',
  status_label: '待您確認報價',
  official_status: '13',
  quote: {
    items: [{ name: '材料費', amount: 300 }, { name: '施工費', amount: 900 }],
    amount: 1200,
    vendorName: '安心修繕',
    quotedAt: '2026-07-25T01:00:00Z',
  },
  events: [...SUBMITTED.events, { type: 'quote.created', occurred_at: '2026-07-25T01:00:00Z', detail: '安心修繕 NT$1200' }],
}

describe('inquiry lifecycle across roles', () => {
  it('shows a submitted request as awaiting a quote, not as a dead end', async () => {
    stubCatalogFetch((url) => (url.endsWith('/api/v1/inquiries') ? json({ data: [SUBMITTED] }) : undefined))
    const { wrapper } = await mountApp('/user/orders')

    expect(wrapper.text()).toContain('INQ-20260725-001')
    expect(wrapper.text()).toContain('待廠商報價')
    expect(wrapper.text()).toContain('報價回覆後會顯示在這裡')
    expect(wrapper.text()).toContain('燈具／開關')
  })

  it('lets the resident see and accept the vendor’s quote', async () => {
    const confirmed = { ...QUOTED, status: 'confirmed', status_label: '已確認，等待服務' }
    stubCatalogFetch((url, init) => {
      if (url.endsWith('/api/v1/inquiries')) return json({ data: [QUOTED] })
      if (url.includes('/confirm') && init?.method === 'POST') return json({ data: confirmed })
      return undefined
    })
    const { wrapper } = await mountApp('/user/orders')

    expect(wrapper.text()).toContain('安心修繕 的報價')
    expect(wrapper.text()).toContain('NT$ 1,200')

    await wrapper.get('[data-testid="confirm-quote-INQ-20260725-001"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('已確認，等待服務')
  })

  it('shows the resident’s actual request in the vendor workspace', async () => {
    stubCatalogFetch((url) => (url.endsWith('/api/v1/vendor/workload')
      ? json({ data: { pendingQuote: [SUBMITTED], awaitingResident: [], scheduled: [] } })
      : undefined))
    const { wrapper } = await mountApp('/partner', { identity: ADMIN_FREE_PARTNER })

    expect(wrapper.text()).toContain('INQ-20260725-001')
    expect(wrapper.text()).toContain('燈具／開關')   // 看得到住戶填了什麼
    expect(wrapper.find('[data-testid="send-quote-INQ-20260725-001"]').exists()).toBe(true)
  })

  it('sends the itemised quote the vendor typed', async () => {
    const posted: Array<Record<string, unknown>> = []
    stubCatalogFetch((url, init) => {
      if (url.endsWith('/api/v1/vendor/workload')) {
        return json({ data: { pendingQuote: [SUBMITTED], awaitingResident: [], scheduled: [] } })
      }
      if (url.includes('/quote') && init?.method === 'POST') {
        posted.push(JSON.parse(String(init.body)))
        return json({ data: QUOTED })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/partner', { identity: ADMIN_FREE_PARTNER })

    await wrapper.get('[data-material-for="INQ-20260725-001"]').setValue(500)
    await wrapper.get('[data-labour-for="INQ-20260725-001"]').setValue(1500)
    await wrapper.get('[data-testid="send-quote-INQ-20260725-001"]').trigger('click')
    await flushPromises()

    expect(posted[0]).toMatchObject({
      items: [{ name: '材料費', amount: 500 }, { name: '施工費', amount: 1500 }],
    })
  })

  it('reports a rejected transition instead of pretending it worked', async () => {
    stubCatalogFetch((url, init) => {
      if (url.endsWith('/api/v1/inquiries')) return json({ data: [QUOTED] })
      if (url.includes('/confirm') && init?.method === 'POST') {
        return new Response(JSON.stringify({ detail: '目前是「待廠商報價」，無法直接確認' }), {
          status: 409, headers: { 'Content-Type': 'application/json' },
        })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/orders')

    await wrapper.get('[data-testid="confirm-quote-INQ-20260725-001"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('無法直接確認')
  })

  it('survives an inquiry payload without the newer fields', async () => {
    const legacy = { id: 'INQ-OLD-001', form_id: 901, status: 'pending_quote', created_at: '2026-07-25T00:00:00Z' }
    stubCatalogFetch((url) => (url.endsWith('/api/v1/inquiries') ? json({ data: [legacy] }) : undefined))
    const { wrapper } = await mountApp('/user/orders')

    expect(wrapper.text()).toContain('INQ-OLD-001')
  })

  it('tells the resident when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
    const { wrapper } = await mountApp('/user/orders')
    expect(wrapper.text()).toContain('無法取得委託紀錄')
  })
})
