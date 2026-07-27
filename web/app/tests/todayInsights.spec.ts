// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { insightRecommendations, insightSummary } from './fixtures/catalog.generated'
import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp, NEW_USER } from './fixtures/mountApp'

describe('resident home', () => {
  beforeEach(() => stubCatalogFetch())

  it('makes describing a need the primary action', async () => {
    const { wrapper } = await mountApp('/user')

    expect(wrapper.get('h1').text()).toBe('今天需要什麼？')
    expect(wrapper.find('[data-testid="need-input"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="need-starter"]').length).toBeGreaterThan(0)
  })

  it('teaches a brand-new user what happens next instead of showing empty panels', async () => {
    const { wrapper } = await mountApp('/user', { identity: NEW_USER })

    expect(wrapper.get('[data-testid="onboarding-steps"]').text()).toContain('描述需求')
    // 新帳號不該看到任何別人的數字
    expect(wrapper.find('[data-testid="metric-spend"]').exists()).toBe(false)
  })

  it('shows spend and open-order counts computed from the signed-in account', async () => {
    const { wrapper } = await mountApp('/user')

    expect(wrapper.get('[data-testid="metric-spend"]').text())
      .toBe(`NT$ ${insightSummary.totalSpend.toLocaleString('zh-TW')}`)
    expect(wrapper.get('[data-testid="metric-open"]').text()).toBe(String(insightSummary.openOrders))
  })

  it('renders the top rule-computed recommendation with its evidence', async () => {
    const { wrapper } = await mountApp('/user')
    const top = insightRecommendations[0]!

    expect(wrapper.get('[data-testid="recommendation-title"]').text()).toBe(top.title)
    expect(wrapper.text()).toContain(top.reasonText)

    await wrapper.get('.reason-details summary').trigger('click')
    const evidence = wrapper.get('[data-testid="recommendation-evidence"]').text()
    expect(evidence).toContain(top.evidence[0]!.serviceName)
    expect(wrapper.text()).toContain('非語言模型生成')
  })

  /**
   * 需求交給規劃器（ADR-0017），首頁不再自己做意圖判讀。
   *
   * 原因：意圖比對只挑得出一項服務，「冷氣不冷，順便看團購」的後半句會被默默丟掉；
   * 而且判讀依據應該攤開給使用者看，不該在首頁默默決定完就跳走。
   * 判讀失敗與無法對應的處理都移到生活管家頁，見 assistantPlanning.spec.ts。
   */
  it('hands the need to the assistant instead of deciding the service on the home page', async () => {
    const { wrapper, router } = await mountApp('/user')

    await wrapper.get('[data-testid="need-input"]').setValue('冷氣不冷，順便看看社區團購')
    await wrapper.get('[data-testid="need-submit"]').trigger('submit')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('assistant'))

    expect(router.currentRoute.value.query.need).toBe('冷氣不冷，順便看看社區團購')
    // 首頁不預先決定服務——那是規劃器的工作，而且可能不只一項
    expect(router.currentRoute.value.query.service).toBeUndefined()
  })

  it('carries a starter through the same path as a typed need', async () => {
    const { wrapper, router } = await mountApp('/user')

    const starter = wrapper.findAll('[data-testid="need-starter"]')[0]!
    const label = starter.text()
    await starter.trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('assistant'))

    expect(router.currentRoute.value.query.need).toBe(label)
  })

  it('degrades to a status message instead of crashing on a malformed payload', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ data: [] }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })))
    const { wrapper } = await mountApp('/user')

    expect(wrapper.text()).toContain('無法取得你的使用紀錄')
    expect(wrapper.find('[data-testid="metric-spend"]').exists()).toBe(false)
  })
})
