// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DEMO_HOUSEHOLD_ID } from '@/domain/communityDemo'
import { communityDemoService } from '@/services/communityDemoService'
import { useCommunityDemoStore } from '@/stores/communityDemo'
import { DEMO_MANAGER_IDENTITY, DEMO_RESIDENT_IDENTITY } from '@/stores/session'

import { mountApp } from './fixtures/mountApp'

const CHOCOLATE_ID = 'group-dubai-chocolate-2026-08'

beforeEach(() => {
  globalThis.localStorage?.clear()
  communityDemoService.resetDemo()
  setActivePinia(createPinia())
})

describe('AI 智慧社區 Demo', () => {
  it('切換 Demo 住戶與主委身分並導向各自工作台', async () => {
    const { wrapper, router, session } = await mountApp('/demo/resident', { identity: DEMO_RESIDENT_IDENTITY })

    expect(wrapper.text()).toContain('王小明')
    await wrapper.get('[data-testid="demo-role-switcher"]').setValue('manager')
    await flushPromises()
    expect(session.role).toBe('manager')
    expect(session.displayName).toBe('主委陳建華')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/demo/committee'))
    expect(wrapper.text()).toContain('社區營運工作台')

    await wrapper.get('[data-testid="demo-role-switcher"]').setValue('user')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/demo/resident')
    expect(session.displayName).toBe('王小明')
  })

  it('回答垃圾車與假日裝修問題，並提供來源、完整規則與相關問題', async () => {
    const { wrapper } = await mountApp('/demo/resident', { identity: DEMO_RESIDENT_IDENTITY })

    await wrapper.get('[data-testid="community-query"]').setValue('垃圾車幾點來')
    await wrapper.get('form.demo-ask-form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.get('[data-testid="community-answer"]').text()).toContain('週一至週六 19:30–20:00'))
    expect(wrapper.get('[data-testid="community-answer"]').text()).toContain('社區生活公約第 8 條')
    expect(wrapper.get('[data-testid="community-answer"]').text()).toContain('完整內容')
    expect(wrapper.findAll('.demo-related-questions button')).toHaveLength(3)

    await wrapper.get('[data-testid="community-query"]').setValue('裝修可以假日施工嗎')
    await wrapper.get('form.demo-ask-form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.get('[data-testid="community-answer"]').text()).toContain('週六僅限 09:00–12:00'))
    expect(wrapper.get('[data-testid="community-answer"]').text()).toContain('週一至週五 09:00–12:00、14:00–17:00')
    expect(wrapper.get('[data-testid="community-answer"]').text()).toContain('週日及國定假日禁止')
  })

  it('未知問題可送入未回答清單，管委會可以標記待補充', async () => {
    const { wrapper } = await mountApp('/demo/resident', { identity: DEMO_RESIDENT_IDENTITY })

    await wrapper.get('[data-testid="community-query"]').setValue('社區可以養獨角獸嗎')
    await wrapper.get('form.demo-ask-form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.get('[data-testid="community-answer"]').text()).toContain('這題我還不會'))
    await wrapper.get('[data-testid="report-unanswered"]').trigger('click')
    expect(wrapper.text()).toContain('已送入管委會未回答問題清單')

    await wrapper.get('[data-testid="demo-role-switcher"]').setValue('manager')
    await flushPromises()
    const newQuestion = wrapper.findAll('[data-testid^="mark-wiki-"]')[0]
    expect(newQuestion).toBeDefined()
    await newQuestion!.trigger('click')
    expect(wrapper.text()).toContain('已標記為待補充')
  })

  it('主委發布杜拜巧克力後，住戶看到同一檔團購並以六入一組跟團', async () => {
    const { wrapper, router } = await mountApp('/demo/committee', { identity: DEMO_MANAGER_IDENTITY })

    await wrapper.get('[data-testid="publish-dubai-group-buy"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('杜拜巧克力已發布')

    await wrapper.get('[data-testid="demo-role-switcher"]').setValue('user')
    await flushPromises()
    expect(wrapper.text()).toContain('杜拜巧克力')
    await wrapper.get(`[data-testid="group-buy-card-${CHOCOLATE_ID}"] a`).trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('demo-group-buy'))
    await wrapper.get('[data-testid="variant-dubai-six"]').setValue(true)
    await wrapper.get('[data-testid="join-group-buy"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="group-progress"]').text()).toContain('8/10')
    expect(wrapper.get('[data-testid="join-feedback"]').text()).toContain('NT$ 780')
    expect(wrapper.get('[data-testid="my-group-order"]').text()).toContain('王小明已跟團')
  })

  it('管委會彙總會出現王小明、住址、六入與 NT$780，KPI 與分潤同步更新', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useCommunityDemoStore()
    store.resetDemo()
    store.publishDemoGroupBuy()
    store.joinGroupBuy({
      groupBuyId: CHOCOLATE_ID,
      variantId: 'dubai-six',
      quantity: 1,
      householdId: DEMO_HOUSEHOLD_ID,
      displayName: '王小明',
      householdLabel: 'A 棟 12F-3',
    })

    const dashboard = store.committeeDashboard!
    expect(dashboard.ordersByHousehold).toEqual(expect.arrayContaining([
      expect.objectContaining({ displayName: '王小明', householdLabel: 'A 棟 12F-3', amount: 780 }),
    ]))
    expect(dashboard.variantSummary).toEqual(expect.arrayContaining([
      expect.objectContaining({ variantLabel: '六入', quantity: 1, amount: 780 }),
    ]))
    expect(dashboard.kpis.groupBuyRevenue).toBeGreaterThanOrEqual(780)
    expect(dashboard.kpis.externalCommission).toBeCloseTo(23.4, 2)
  })

  it('重設 Demo 後回到未發布杜拜巧克力與初始住戶狀態', async () => {
    const { wrapper, router } = await mountApp('/demo/committee', { identity: DEMO_MANAGER_IDENTITY })
    await wrapper.get('[data-testid="publish-dubai-group-buy"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="demo-role-switcher"]').setValue('reset')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/demo/resident')
    expect(wrapper.text()).not.toContain('杜拜巧克力')
    expect(wrapper.get('[data-testid="resident-package-kpi"]').text()).toContain('2')
    expect(useCommunityDemoStore().lastAnswer).toBeNull()
  })

  it('訂閱頁區分 112 戶標準月費與試辦優惠，並計算淨效益', async () => {
    const { wrapper } = await mountApp('/demo/subscription', { identity: DEMO_MANAGER_IDENTITY })

    const pricing = wrapper.get('[data-testid="subscription-pricing"]').text()
    expect(pricing).toContain('101–200 戶')
    expect(pricing).toContain('NT$ 12,000／月')
    expect(pricing).toContain('NT$ 6,000／月')
    expect(wrapper.text()).toContain('本月住戶累計省下')
    expect(wrapper.text()).toContain('NT$ 18,420')
    expect(wrapper.text()).toContain('+NT$ 12,420')
    expect(wrapper.get('[data-testid="commission-rules"]').text()).toContain('外部廠商成交抽成')
    expect(wrapper.get('[data-testid="commission-rules"]').text()).toContain('統一集團商品抽成')
  })
})
