// @vitest-environment happy-dom

import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

async function clickNext(wrapper: VueWrapper) {
  await wrapper.get('[data-testid="wizard-next"]').trigger('click')
  await flushPromises()
}

/** 走完 booking 流程的前三步(據點/方案/時段),停在需求內容。 */
async function reachDetailsStep(wrapper: VueWrapper, locationId: string) {
  await wrapper.get(`input[type="radio"][value="${locationId}"]`).setValue()
  await clickNext(wrapper) // 據點 → 方案(query 已預選)
  await clickNext(wrapper) // 方案 → 時段
  await wrapper.get('[data-testid="slot-option"]').trigger('click')
  await clickNext(wrapper) // 時段 → 需求內容
  expect(wrapper.get('[data-testid="step-title"]').text()).toBe('需求內容')
}

describe('booking wizard', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
  })

  it('walks the five home_repair steps and creates exactly one booking', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp(
      '/user/booking?provider=vendor-prince-electric&offering=off-prince-electric-repair',
    )
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('預約服務')
    expect(wrapper.text()).toContain('partner-demo-v5')

    await reachDetailsStep(wrapper, 'loc-prince-electric-01')

    await wrapper.get('[data-testid="field-problem"]').setValue('浴室水龍頭持續漏水')
    await wrapper.get('[data-testid="field-address"]').setValue('臺北市信義區示範路 1 號')
    await wrapper.get('[data-testid="field-phone"]').setValue('0912345678')
    await clickNext(wrapper) // 需求內容 → 確認送出

    expect(wrapper.get('[data-testid="step-title"]').text()).toBe('確認送出')
    // booking 不預收款:顯示預估費用而非應付金額
    expect(wrapper.get('[data-testid="quote-summary"]').text()).toContain('預估費用')
    expect(wrapper.get('[data-testid="quote-summary"]').text()).toContain('1,200')

    await wrapper.get('[data-testid="wizard-submit"]').trigger('click')
    await flushPromises()

    const orderId = wrapper.get('[data-testid="order-id"]').text()
    expect(orderId).toMatch(/^booking-/)
    expect(wrapper.get(`a[href="/user/orders/${orderId}"]`).text()).toContain('查看訂單')
    expect(wrapper.get('a[href="/user/calendar"]').text()).toContain('行事曆')

    // stub 裡真的有這筆 booking,且只有一筆
    const response = await fetch('/api/v1/platform/bookings')
    const body = (await response.json()) as { data: Array<{ id: string; offeringId: string }> }
    expect(body.data).toHaveLength(1)
    expect(body.data[0]!.id).toBe(orderId)
    expect(body.data[0]!.offeringId).toBe('off-prince-electric-repair')
  })

  it('blocks the details step until required fields are filled', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp(
      '/user/booking?provider=vendor-prince-electric&offering=off-prince-electric-repair',
    )
    await flushPromises()

    await reachDetailsStep(wrapper, 'loc-prince-electric-01')

    await wrapper.get('[data-testid="field-phone"]').setValue('0912345678')
    await clickNext(wrapper)

    // 仍停在需求內容,缺漏欄位以 .field-error 提示
    expect(wrapper.get('[data-testid="step-title"]').text()).toBe('需求內容')
    const errors = wrapper.findAll('.field-error')
    expect(errors.length).toBeGreaterThanOrEqual(2)
    expect(errors.some((item) => item.text().includes('問題描述'))).toBe(true)
  })

  it('requires the pharmacy rx_confirmed checkbox before continuing', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp(
      '/user/booking?provider=vendor-cosmed&offering=off-cosmed-rx-pickup',
    )
    await flushPromises()

    await reachDetailsStep(wrapper, 'loc-cosmed-01')
    expect(wrapper.text()).toContain('不提供診斷或用藥建議')

    await wrapper.get('[data-testid="field-rx_type-chronic"]').setValue()
    await wrapper.get('[data-testid="field-patient_name"]').setValue('王小圓')
    await wrapper.get('[data-testid="field-phone"]').setValue('0987654321')
    await wrapper.get('[data-testid="field-pickup_in_person-yes"]').setValue()
    // 未勾 rx_confirmed
    await clickNext(wrapper)

    expect(wrapper.get('[data-testid="step-title"]').text()).toBe('需求內容')
    expect(wrapper.text()).toContain('我已逐欄確認辨識結果')
    expect(wrapper.findAll('.field-error').some((item) => item.text().includes('我已逐欄確認辨識結果'))).toBe(true)

    await wrapper.get('[data-testid="field-rx_confirmed"]').setValue(true)
    await clickNext(wrapper)
    expect(wrapper.get('[data-testid="step-title"]').text()).toBe('確認送出')
  })

  it('booking confirm step has no prepayment (2026-07-31 product rule)', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp(
      '/user/booking?provider=vendor-prince-electric&offering=off-prince-electric-repair',
    )
    await flushPromises()

    await reachDetailsStep(wrapper, 'loc-prince-electric-01')
    await wrapper.get('[data-testid="field-problem"]').setValue('插座跳電')
    await wrapper.get('[data-testid="field-address"]').setValue('臺北市信義區示範路 1 號')
    await wrapper.get('[data-testid="field-phone"]').setValue('0912345678')
    await clickNext(wrapper)

    // 2026-07-31 產品規則:預約類不預收款——無折抵輸入,顯示誠實文案
    expect(wrapper.find('[data-testid="points-input"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="no-prepayment-note"]').text()).toContain('不預收款')
  })

  it('shows the backend 422 on a commerce flow when points exceed the cap', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp(
      '/user/booking?provider=vendor-711-c2c&offering=off-711-c2c-standard',
    )
    await flushPromises()
    await clickNext(wrapper) // 選方案 → 需求內容
    await wrapper.get('[data-testid="field-sender_name"]').setValue('林小圓')
    await wrapper.get('[data-testid="field-receiver_name"]').setValue('陳伯伯')
    await wrapper.get('[data-testid="field-item_name"]').setValue('書一本')
    await wrapper.get('[data-testid="field-phone"]').setValue('0912345678')
    await clickNext(wrapper)

    await wrapper.get('[data-testid="points-input"]').setValue('999')
    await flushPromises()

    expect(wrapper.get('[data-testid="quote-error"]').text()).toContain('點數折抵超過上限')
    expect(wrapper.get('[data-testid="wizard-submit"]').attributes('disabled')).toBeDefined()
  })

  it('runs the c2c_shipping commerce flow: blocks on missing fields, then submits', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp(
      '/user/booking?provider=vendor-711-c2c&offering=off-711-c2c-standard',
    )
    await flushPromises()

    // commerce 三步:選方案(query 已預選)→ 需求內容 → 確認付款
    expect(wrapper.get('[data-testid="step-title"]').text()).toBe('選方案')
    await clickNext(wrapper)
    expect(wrapper.get('[data-testid="step-title"]').text()).toBe('需求內容')

    // 必填缺(只填電話)→ 擋在需求內容
    await wrapper.get('[data-testid="field-phone"]').setValue('0912345678')
    await clickNext(wrapper)
    expect(wrapper.get('[data-testid="step-title"]').text()).toBe('需求內容')
    const errors = wrapper.findAll('.field-error')
    expect(errors.some((item) => item.text().includes('寄件人姓名'))).toBe(true)
    expect(errors.some((item) => item.text().includes('商品名稱'))).toBe(true)

    // 填齊必填 → 確認付款 → 送出成功
    await wrapper.get('[data-testid="field-sender_name"]').setValue('林小圓')
    await wrapper.get('[data-testid="field-receiver_name"]').setValue('王大明')
    await wrapper.get('[data-testid="field-item_name"]').setValue('保溫瓶')
    await clickNext(wrapper)

    expect(wrapper.get('[data-testid="step-title"]').text()).toBe('確認付款')
    expect(wrapper.get('[data-testid="quote-payable"]').text()).toContain('60')

    await wrapper.get('[data-testid="wizard-submit"]').trigger('click')
    await flushPromises()

    const orderId = wrapper.get('[data-testid="order-id"]').text()
    expect(orderId).toMatch(/^order-/)

    // stub 裡真的成立一筆 commerce order
    const response = await fetch('/api/v1/platform/commerce-orders')
    const body = (await response.json()) as { data: Array<{ id: string; items: Array<{ offeringId: string }> }> }
    expect(body.data).toHaveLength(1)
    expect(body.data[0]!.items[0]!.offeringId).toBe('off-711-c2c-standard')
  })

  it('resumes a draft from ?draft= with the entered values restored', async () => {
    stubCatalogFetch()
    const first = await mountApp(
      '/user/booking?provider=vendor-prince-electric&offering=off-prince-electric-repair',
    )
    await flushPromises()

    await reachDetailsStep(first.wrapper, 'loc-prince-electric-01')
    await first.wrapper.get('[data-testid="field-problem"]').setValue('廚房排水管阻塞')
    await first.wrapper.get('[data-testid="field-address"]').setValue('臺北市信義區示範路 1 號')
    await first.wrapper.get('[data-testid="field-phone"]').setValue('0912345678')
    await clickNext(first.wrapper) // 持久化需求內容並前往確認

    const draftId = first.router.currentRoute.value.query.draft
    expect(typeof draftId).toBe('string')
    first.wrapper.unmount()

    // 重新掛載,以 ?draft= 續填(同一個 stub 狀態)
    const second = await mountApp(`/user/booking?draft=${String(draftId)}`)
    await flushPromises()

    expect(second.wrapper.get('[data-testid="step-title"]').text()).toBe('確認送出')
    // 回到需求內容,欄位值已恢復
    await second.wrapper.get('[data-testid="wizard-back"]').trigger('click')
    await flushPromises()
    expect(
      (second.wrapper.get('[data-testid="field-problem"]').element as HTMLTextAreaElement).value,
    ).toBe('廚房排水管阻塞')
    expect(
      (second.wrapper.get('[data-testid="field-phone"]').element as HTMLInputElement).value,
    ).toBe('0912345678')
  })
})
