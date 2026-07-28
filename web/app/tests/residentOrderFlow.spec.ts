// @vitest-environment happy-dom

import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('resident order flow', () => {
  beforeEach(() => stubCatalogFetch())

  it('opens a service directly from a LINE-ready deep link', async () => {
    const { wrapper } = await mountApp('/user/services/aircon')

    expect(wrapper.get('.service-detail h2').text()).toBe('冷氣清洗')
    expect(wrapper.get('[data-field-id="airconType"]').attributes('required')).toBeDefined()
  })

  it('moves from the service catalog through confirmation into order tracking', async () => {
    const { wrapper, router } = await mountApp('/user/services', { attach: true })

    expect(wrapper.get('h1').text()).toBe('需要什麼服務？')
    expect(wrapper.findAll('[data-testid="service-card"]')).toHaveLength(9)

    await wrapper.get('[data-service-id="service-shopping"]').trigger('click')
    await flushPromises()   // 題組定義由後端載入
    await wrapper.get('[data-testid="continue-service"]').trigger('click')
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(wrapper.text()).toContain('請填寫補貨組合')

    await wrapper.get('[data-field-id="bundle"]').setValue('restock')
    await wrapper.get('[data-field-id="coupon"]').setValue('apply')
    await wrapper.get('[data-field-id="points"]').setValue('50')
    await wrapper.get('[data-field-id="delivery"]').setValue('store')
    await wrapper.get('[data-field-id="payment"]').setValue('icash-pay')
    await flushPromises()   // 金額由後端統一 API 試算
    expect(wrapper.text()).toContain('NT$ 579')

    await wrapper.get('[data-testid="continue-service"]').trigger('click')
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')
    expect(dialog?.textContent).toContain('確認商城購物')
    expect(dialog?.textContent).toContain('icash Pay（本次加碼）')

    const confirmAction = document.querySelector<HTMLButtonElement>('[data-testid="confirm-action"]')
    expect(confirmAction).not.toBeNull()
    if (confirmAction) await new DOMWrapper(confirmAction).trigger('click')
    await flushPromises()
    await nextTick()

    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/user/orders'))
    expect(wrapper.text()).toContain('OP-0725-001')
    expect(wrapper.text()).toContain('已成立')
  })

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
