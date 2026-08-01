// @vitest-environment happy-dom

// 2026-07-31 產品決策:服務頁移除 legacy「用需求描述找服務」區塊後,
// 本檔原本兩個走 legacy 目錄→表單→送出的測試已退場(見 progress log);
// 保留的是仍存在的訂單頁功能(手風琴卡片與跨服務任務 deep link)。

import { beforeEach, describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('resident order flow', () => {
  beforeEach(() => stubCatalogFetch())

  it('presents orders as accessible disclosure cards instead of one long wall', async () => {
    const inquiries = [
      {
        id: 'INQ-001', status: 'quoted', status_label: '等待你確認',
        summary: [{ label: '服務', value: '居家清潔' }], events: [],
        quote: { vendorName: '安心清潔', amount: 1200, items: [{ name: '基本清潔', amount: 1200 }] },
      },
      {
        id: 'INQ-002', status: 'pending_quote', status_label: '等待報價',
        summary: [{ label: '服務', value: '冷氣清洗' }], events: [], quote: null,
      },
    ]
    stubCatalogFetch((url) => (url.endsWith('/api/v1/inquiries')
      ? new Response(JSON.stringify({ data: inquiries }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      : undefined))
    const { wrapper } = await mountApp('/user/orders')

    const cards = wrapper.findAll('[data-testid="order-disclosure"]')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.element.tagName).toBe('DETAILS')
    expect(cards[0]!.attributes('open')).toBeDefined()
    expect(cards[1]!.attributes('open')).toBeUndefined()
    expect(cards[0]!.get('summary').text()).toContain('居家清潔')
    expect(cards[0]!.get('summary').text()).toContain('等待你確認')
  })

  it('shows a deep-linked cross-service task as one open accordion with both vendor states', async () => {
    const task = {
      id: 'TASK-20260725-001', accountId: 'member', displayName: '小圓', utterance: '安排修繕與清洗',
      status: 'quoted', statusLabel: '廠商已報價', scheduledDate: '2026-08-01',
      address: { choice: 'home', label: '會員中心住家' }, scope: 'personal', version: 4, lastError: null,
      requirements: [], missingFields: [], readyForConfirmation: false, dataUse: [],
      estimate: { baseAmount: 3100, pointsApplied: 180, finalAmount: 2920, savedAmount: 180, source: 'rules' },
      items: [
        { id: 'one', serviceId: 'service-repair', title: '浴室燈修繕', needSummary: '', vendorId: 'vendor-prince-electric', vendorName: '王子水電', basePrice: 1200, slot: 'weekend', candidates: [], externalInquiryId: 'vinq-1', externalOrderId: null, status: 'quoted', quotes: [{ id: 'vqt-1', vendorId: 'vendor-prince-electric', total: 1200, currency: 'TWD', status: 'proposed', validUntil: '2026-08-05', items: [] }] },
        { id: 'two', serviceId: 'service-aircon', title: '冷氣清洗', needSummary: '', vendorId: 'vendor-duskin', vendorName: 'DUSKIN 樂清', basePrice: 1900, slot: 'weekend', candidates: [], externalInquiryId: 'vinq-2', externalOrderId: null, status: 'quoted', quotes: [{ id: 'vqt-2', vendorId: 'vendor-duskin', total: 1900, currency: 'TWD', status: 'proposed', validUntil: '2026-08-05', items: [] }] },
      ],
    }
    stubCatalogFetch((url) => url.endsWith('/api/v1/life-tasks')
      ? new Response(JSON.stringify({ data: [task] }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      : undefined)
    const { wrapper } = await mountApp('/user/orders?task=TASK-20260725-001')

    const disclosure = wrapper.get('[data-testid="life-task-disclosure"]')
    expect(disclosure.attributes('open')).toBeDefined()
    expect(disclosure.get('summary').text()).toContain('浴室燈修繕＋冷氣清洗')
    expect(disclosure.text()).toContain('王子水電')
    expect(disclosure.text()).toContain('DUSKIN 樂清')
    expect(disclosure.text()).toContain('NT$ 2,920')
    expect(disclosure.find('button.button.primary').text()).toContain('確認全部報價')
  })
})
