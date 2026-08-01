// @vitest-environment happy-dom

import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

/** 直接對 platform stub 造資料:與前端頁面共用同一個有狀態假後端。 */
async function postJson(url: string, body: unknown) {
  const response = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  expect(response.ok).toBe(true)
  return (await response.json()).data
}

async function createBooking() {
  const draft = await postJson('/api/v1/platform/task-drafts', {
    domain_type: 'home_repair',
    values: {
      offering_id: 'off-prince-electric-repair',
      location_id: 'loc-prince-electric-01',
      slot_id: 'slot-prince-electric-1',
      starts_at: '2026-08-01T09:00:00+08:00',
      ends_at: '2026-08-01T11:00:00+08:00',
    },
  })
  const result = await postJson(`/api/v1/platform/task-drafts/${draft.id}/submit`, {
    expected_version: draft.version,
  })
  return result.booking
}

async function createCommerceOrder() {
  const draft = await postJson('/api/v1/platform/task-drafts', {
    domain_type: 'ec_preorder',
    values: { offering_id: 'off-711-shop-preorder-coffee', quantity: 1 },
  })
  const result = await postJson(`/api/v1/platform/task-drafts/${draft.id}/submit`, {
    expected_version: draft.version,
  })
  return result.order
}

/** ConfirmDialog 以 Teleport 掛在 body,要從 document 找確認鈕。 */
async function confirmDialog() {
  const button = document.querySelector<HTMLButtonElement>('[data-testid="confirm-action"]')
  expect(button).not.toBeNull()
  await new DOMWrapper(button!).trigger('click')
  await flushPromises()
}

describe('order detail', () => {
  beforeEach(() => stubCatalogFetch())

  it('shows the booking status and its StatusEvent timeline', async () => {
    const booking = await createBooking()
    const { wrapper } = await mountApp(`/user/orders/${booking.id}`)

    expect(wrapper.get('[data-testid="detail-status"]').text()).toBe('需求送出')
    const timeline = wrapper.get('[data-testid="detail-timeline"]')
    expect(timeline.text()).toContain('需求送出')
    // actorRole=member 要翻成「你」
    expect(timeline.text()).toContain('你')
    expect(wrapper.text()).toContain('進度、通知與行事曆來自同一份 StatusEvent')
  })

  it('cancels a booking only after explicit confirmation', async () => {
    const booking = await createBooking()
    const { wrapper } = await mountApp(`/user/orders/${booking.id}`, { attach: true })

    await wrapper.get('[data-testid="cancel-booking"]').trigger('click')
    await flushPromises()
    await confirmDialog()

    expect(wrapper.get('[data-testid="detail-status"]').text()).toBe('已取消')
    // 已取消後不該再出現取消/改期操作
    expect(wrapper.find('[data-testid="cancel-booking"]').exists()).toBe(false)
  })

  it('recovers a payment_failed commerce order back to placed by repaying', async () => {
    const order = await createCommerceOrder()
    // 用 stub 的 transition 直接造出付款失敗狀態
    await postJson(`/api/v1/platform/commerce-orders/${order.id}/transition`, {
      expected_version: order.version, status: 'payment_failed',
    })
    const { wrapper } = await mountApp(`/user/orders/${order.id}`, { attach: true })

    expect(wrapper.get('[data-testid="detail-status"]').text()).toBe('付款失敗')

    await wrapper.get('[data-testid="retry-payment"]').trigger('click')
    await flushPromises()
    await confirmDialog()

    expect(wrapper.get('[data-testid="detail-status"]').text()).toBe('收到訂單')
    expect(wrapper.find('[data-testid="retry-payment"]').exists()).toBe(false)
  })
})
