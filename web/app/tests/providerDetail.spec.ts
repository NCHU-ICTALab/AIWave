// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('provider detail page', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
  })

  it('shows locations, offering pricing and the status timeline preview', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/services/provider/vendor-prince-electric')
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('王子水電')
    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.text()).toContain('展示資料')

    // 據點清單:名稱/地址/電話
    const locations = wrapper.get('[data-testid="provider-locations"]')
    expect(locations.text()).toContain('王子水電 信義服務點')
    expect(locations.text()).toContain('110臺北市信義區示範路 1 號')
    expect(locations.text()).toContain('02-2726-1000')

    // 方案價目:名稱/domain 顯示名/價格/取消規則
    const offerings = wrapper.get('[data-testid="provider-offerings"]')
    expect(offerings.text()).toContain('水電修繕・到府檢測')
    expect(offerings.text()).toContain('水電修繕')
    expect(offerings.text()).toContain('NT$ 1,200／次')
    expect(offerings.text()).toContain('開始前 24 小時可免費取消')

    // 進度預覽:依第一個 offering(home_repair,booking)的時間軸
    const preview = wrapper.get('[data-testid="status-preview"]')
    expect(preview.text()).toContain('需求送出')
    expect(preview.text()).toContain('已預約')
    expect(preview.text()).toContain('服務中')
    expect(preview.text()).toContain('已完成')
  })

  it('routes the CTA to the booking wizard with provider and offering query', async () => {
    stubCatalogFetch()
    const { wrapper, router } = await mountApp('/user/services/provider/vendor-prince-electric')
    await flushPromises()

    await wrapper.get('[data-testid="provider-start"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('booking-wizard'))
    expect(router.currentRoute.value.query.provider).toBe('vendor-prince-electric')
    expect(router.currentRoute.value.query.offering).toBe('off-prince-electric-repair')
  })

  it('shows a commerce timeline and 購買 CTA for commerce providers', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/services/provider/vendor-711-c2c')
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('7-ELEVEN 交貨便')
    expect(wrapper.get('[data-testid="provider-start"]').text()).toBe('開始購買')
    const preview = wrapper.get('[data-testid="status-preview"]')
    expect(preview.text()).toContain('寄件單成立')
    expect(preview.text()).toContain('已到店')
  })

  it('shows an honest 404 with a way back when the provider does not exist', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/services/provider/vendor-nope')
    await flushPromises()

    const alert = wrapper.get('[data-testid="provider-not-found"]')
    expect(alert.text()).toContain('找不到這個服務品牌')
    expect(alert.get('a[href="/user/services"]').text()).toContain('回服務探索')
    expect(wrapper.find('[data-testid="provider-start"]').exists()).toBe(false)
  })
})
