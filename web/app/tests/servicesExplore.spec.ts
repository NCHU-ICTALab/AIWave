// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('services explore (M4 six life scenes)', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
  })

  it('groups partner brands by the six scenes in a fixed order', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/services')
    await flushPromises()

    const groups = wrapper.findAll('[data-testid="scene-group"]')
    expect(groups.map((group) => group.attributes('data-scene'))).toEqual([
      'food', 'med', 'home', 'move', 'pre', 'fun',
    ])

    // 全部 8 個合作品牌都在,含評分展示標示與品牌 icon
    expect(wrapper.findAll('[data-testid="provider-card"]')).toHaveLength(12)
    expect(wrapper.text()).toContain('partner-demo-v5')

    const duskin = wrapper.get('[data-provider-id="vendor-duskin"]')
    expect(duskin.get('img').attributes('alt')).toBe('')
    expect(duskin.text()).toContain('展示資料')

    // 無 icon 的品牌以字首圓形徽章呈現
    const prince = wrapper.get('[data-provider-id="vendor-prince-electric"]')
    expect(prince.find('img').exists()).toBe(false)
    expect(prince.get('.brand-badge').text()).toBe('王')

    // 2026-07-31:legacy 服務目錄已移除,頁面不應再出現舊 service-card
    expect(wrapper.findAll('[data-testid="service-card"]')).toHaveLength(0)
  })

  it('routes the 預約 CTA to the booking wizard with provider and first offering', async () => {
    stubCatalogFetch()
    const { wrapper, router } = await mountApp('/user/services')
    await flushPromises()

    await wrapper
      .get('[data-provider-id="vendor-prince-electric"] [data-testid="provider-book"]')
      .trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('booking-wizard'))

    expect(router.currentRoute.value.query.provider).toBe('vendor-prince-electric')
    expect(router.currentRoute.value.query.offering).toBe('off-prince-electric-repair')
  })

  it('routes the 查看詳情 CTA to the provider detail page', async () => {
    stubCatalogFetch()
    const { wrapper, router } = await mountApp('/user/services')
    await flushPromises()

    await wrapper
      .get('[data-provider-id="vendor-prince-electric"] [data-testid="provider-detail-cta"]')
      .trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('provider-detail'))
    expect(router.currentRoute.value.params.providerId).toBe('vendor-prince-electric')
  })

  it('shows the tier-2 listing shelf honestly: no booking, notes and companies visible', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/services')
    await flushPromises()

    // 每個有 tier-2 品牌的場景都有 collapsible 陳列區
    const sections = wrapper.findAll('[data-testid="listing-section"]')
    expect(sections.length).toBeGreaterThan(0)
    expect(sections[0]!.get('summary').text()).toContain('更多統一體系品牌')

    // 品牌卡:名稱/公司/不可下單標示
    const starbucks = wrapper.get('[data-listing-id="listing-starbucks"]')
    expect(starbucks.text()).toContain('星巴克')
    expect(starbucks.text()).toContain('悠旅生活事業')
    expect(starbucks.text()).toContain('未開放線上交易')

    // ibon 叫車的機台流程 note 要誠實顯示
    const ibonTaxi = wrapper.get('[data-listing-id="listing-ibon-taxi"]')
    expect(ibonTaxi.get('[data-testid="listing-note"]').text()).toContain('ibon 機台操作')

    // 陳列區內不得有任何可點的預約按鈕
    for (const section of sections) {
      expect(section.findAll('button')).toHaveLength(0)
      expect(section.text()).not.toContain('預約')
    }
  })
})
