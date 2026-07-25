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
})
