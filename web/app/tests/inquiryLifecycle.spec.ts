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

  /**
   * 收到報價後不是只有「同意」一條路。
   *
   * 先前住戶唯一能做的事就是接受報價——那不是流程設計，是缺漏：
   * 真實情況下住戶會嫌貴、會想換一家、會乾脆不修了。
   */
  it('offers more than agreeing when a quote arrives', async () => {
    stubCatalogFetch((url) => (url.endsWith('/api/v1/inquiries') ? json({ data: [QUOTED] }) : undefined))
    const { wrapper } = await mountApp('/user/orders')

    expect(wrapper.find('[data-testid="confirm-quote-INQ-20260725-001"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="revise-quote-INQ-20260725-001"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="cancel-inquiry-INQ-20260725-001"]').exists()).toBe(true)
  })

  it('sends the case back for a new quote with the resident’s note', async () => {
    const posted: Array<Record<string, unknown>> = []
    stubCatalogFetch((url, init) => {
      if (url.endsWith('/api/v1/inquiries')) return json({ data: [QUOTED] })
      if (url.includes('/revise') && init?.method === 'POST') {
        posted.push(JSON.parse(String(init.body)))
        return json({ data: { ...SUBMITTED, status_label: '待廠商報價' } })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/orders')

    await wrapper.get('[data-testid="revise-quote-INQ-20260725-001"]').trigger('click')
    await wrapper.get('[data-testid="revision-note-INQ-20260725-001"]').setValue('預算希望壓在 1000 以內')
    // happy-dom 不會因為點了 type="submit" 就送出表單，直接觸發 submit
    await wrapper.get('form.quote-revision').trigger('submit')
    await flushPromises()

    expect(posted[0]).toEqual({ note: '預算希望壓在 1000 以內' })
    expect(wrapper.text()).toContain('待廠商報價')
  })

  it('will not send a revision without saying what to change', async () => {
    stubCatalogFetch((url) => (url.endsWith('/api/v1/inquiries') ? json({ data: [QUOTED] }) : undefined))
    const { wrapper } = await mountApp('/user/orders')

    await wrapper.get('[data-testid="revise-quote-INQ-20260725-001"]').trigger('click')
    const submit = wrapper.get('[data-testid="revision-submit-INQ-20260725-001"]')

    // 沒說要改什麼，廠商只能重猜一次
    expect(submit.attributes('disabled')).toBeDefined()
  })

  it('asks before cancelling, because cancelling cannot be undone', async () => {
    const posted: string[] = []
    stubCatalogFetch((url, init) => {
      if (url.endsWith('/api/v1/inquiries')) return json({ data: [QUOTED] })
      if (url.includes('/cancel') && init?.method === 'POST') {
        posted.push(url)
        return json({ data: { ...QUOTED, status: 'cancelled', status_label: '已取消', quote: null } })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/orders')

    await wrapper.get('[data-testid="cancel-inquiry-INQ-20260725-001"]').trigger('click')
    expect(posted).toEqual([])   // 只是打開確認，還沒送出

    await wrapper.get('[data-testid="cancel-confirm-INQ-20260725-001"]').trigger('click')
    await flushPromises()

    expect(posted).toHaveLength(1)
    expect(wrapper.text()).toContain('已取消')
  })

  it('lets a resident cancel while still waiting for a quote', async () => {
    stubCatalogFetch((url) => (url.endsWith('/api/v1/inquiries') ? json({ data: [SUBMITTED] }) : undefined))
    const { wrapper } = await mountApp('/user/orders')

    expect(wrapper.find('[data-testid="cancel-inquiry-INQ-20260725-001"]').exists()).toBe(true)
  })

  it('turns a free-text service problem into a previewed and trackable support ticket', async () => {
    const confirmed = { ...QUOTED, status: 'confirmed', status_label: '已確認，等待服務' }
    const createdBodies: Array<Record<string, unknown>> = []
    stubCatalogFetch((url, init) => {
      if (url.endsWith('/api/v1/inquiries')) return json({ data: [confirmed] })
      if (url.endsWith('/api/v1/support/tickets') && !init?.method) return json({ data: [] })
      if (url.endsWith('/api/v1/support/diagnose') && init?.method === 'POST') {
        return json({ data: {
          subject: { type: 'inquiry', id: confirmed.id, status: 'confirmed', statusLabel: '已確認，等待服務' },
          issueText: '師傅晚兩小時還沒來，也沒有通知',
          category: 'delay', categoryLabel: '服務延遲／未到場', priority: 'high',
          slaHours: 4, dueAt: '2026-07-28T13:00:00+00:00', recommendedRoute: 'service_coordination',
          evidence: ['訂單目前狀態：已確認，等待服務'], computedBy: 'deterministic_rules',
          diagnosisToken: 'diagnosis-456', previewExpiresInSeconds: 300,
        } })
      }
      if (url.endsWith('/api/v1/support/tickets') && init?.method === 'POST') {
        createdBodies.push(JSON.parse(String(init.body)))
        return json({ data: {
          id: 'SUP-20260728-001', accountId: 'A001', subjectId: confirmed.id,
          categoryLabel: '服務延遲／未到場', issueText: '師傅晚兩小時還沒來，也沒有通知',
          status: 'open', statusLabel: '等待客服處理', priority: 'high', slaHours: 4,
          dueAt: '2026-07-28T13:00:00+00:00', events: [{ type: 'support.created', actor: '住戶', occurred_at: '2026-07-28T09:00:00+00:00' }],
        } })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/orders')

    await wrapper.get('[data-testid="support-action-INQ-20260725-001"]').trigger('click')
    await wrapper.get('[data-testid="support-issue-INQ-20260725-001"]').setValue('師傅晚兩小時還沒來，也沒有通知')
    await wrapper.get('[data-testid="support-diagnose-INQ-20260725-001"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('服務延遲／未到場')
    expect(wrapper.text()).toContain('4 小時內開始處理')
    expect(wrapper.text()).toContain('訂單目前狀態：已確認，等待服務')
    expect(createdBodies).toEqual([])

    await wrapper.get('[data-testid="support-confirm-INQ-20260725-001"]').trigger('click')
    await flushPromises()

    expect(createdBodies).toHaveLength(1)
    expect(createdBodies[0]).toMatchObject({ diagnosis_token: 'diagnosis-456' })
    expect(wrapper.text()).toContain('SUP-20260728-001')
    expect(wrapper.text()).toContain('等待客服處理')
  })

  it('keeps resolved history while allowing a later issue on the same order', async () => {
    const confirmed = { ...QUOTED, status: 'confirmed', status_label: '已確認，等待服務' }
    stubCatalogFetch((url, init) => {
      if (url.endsWith('/api/v1/inquiries')) return json({ data: [confirmed] })
      if (url.endsWith('/api/v1/support/tickets') && !init?.method) return json({ data: [{
        id: 'SUP-20260728-001', accountId: 'A001', subjectId: confirmed.id,
        categoryLabel: '服務延遲／未到場', issueText: '上次師傅未到', status: 'resolved',
        statusLabel: '已處理完成', priority: 'high', slaHours: 4, dueAt: '2026-07-28T13:00:00+00:00',
        events: [{ type: 'support.resolved', actor: '社區客服', occurred_at: '2026-07-28T10:00:00+00:00', detail: '已重新安排' }],
      }] })
      return undefined
    })
    const { wrapper } = await mountApp('/user/orders')

    expect(wrapper.text()).toContain('已處理完成')
    expect(wrapper.get('[data-testid="support-action-INQ-20260725-001"]').text()).toContain('建立新的客服工單')
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
