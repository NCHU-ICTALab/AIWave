// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('points redemption', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
    stubCatalogFetch()
  })

  it('shows the member wallet, deterministic saving plan, and an executable next step', async () => {
    const { wrapper, router } = await mountApp('/user/points')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/user/points')
    expect(wrapper.get('h1').text()).toBe('點數兌換')
    expect(wrapper.get('[data-testid="points-balance"]').text()).toContain('180')
    expect(wrapper.get('[data-testid="best-offer"]').text()).toContain('省下 NT$ 120')
    // 2026-07-31 版面比照 design-system/aiwave/pages/points.html:原型移除「競賽展示錢包」
    // page-status chip,改為 lead 與 demo-note 直接標示 Demo points ledger(非真實 OPENPOINT)。
    expect(wrapper.text()).toContain('Demo points ledger')
    // 原型新增「點數明細」帳本表格,資料來自 /platform/points 的 entries。
    expect(wrapper.text()).toContain('點數明細')
    expect(wrapper.text()).toContain('Demo 初始點數')

    await wrapper.get('[data-testid="use-best-offer"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/user/services/shopping'))
  })

  it('does not leak the seeded persona wallet into a newly created account', async () => {
    const { wrapper } = await mountApp('/user/points', {
      identity: { role: 'user', accountId: 'demo-new-member', displayName: '新使用者', accessToken: 'aiwave-new' },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="empty-points-wallet"]').text()).toContain('尚無消費與點數紀錄')
    expect(wrapper.find('[data-testid="points-balance"]').exists()).toBe(false)
  })
})
