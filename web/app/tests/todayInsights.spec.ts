// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { insightRecommendations, insightSummary, todayBriefing } from './fixtures/catalog.generated'
import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp, NEW_USER } from './fixtures/mountApp'

describe('resident home', () => {
  beforeEach(() => stubCatalogFetch())

  it('leads with a life overview while keeping AI available as the lightweight action', async () => {
    const { wrapper } = await mountApp('/user')

    expect(wrapper.get('h1').text()).toBe('生活總覽')
    expect(wrapper.find('[data-testid="need-input"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="need-starter"]').length).toBeGreaterThan(0)
  })

  it('renders the six approved home sections in product reading order', async () => {
    const { wrapper } = await mountApp('/user')

    expect(wrapper.findAll('[data-home-section]').map((section) => section.attributes('data-home-section'))).toEqual([
      'overview',
      'pending',
      'ai',
      'recommendations',
      'shortcuts',
      'promotions',
    ])
  })

  /**
   * 首頁要先回答「我現在該做什麼」（spec 08 產品原則第一條）。
   * 摘要由規則從真實待辦算出，每一則都指得出來源——這條測試守住的是後者。
   */
  it('answers “what should I do now” with items that point at something real', async () => {
    const { wrapper } = await mountApp('/user')

    const items = wrapper.findAll('[data-testid="briefing-item"]')
    expect(items.length).toBeGreaterThan(0)
    expect(wrapper.get('[data-testid="today-pending"]').text()).toContain('待處理事項')
    expect(wrapper.text()).toContain('非語言模型生成')
  })

  it('shows nothing to do rather than filler for a brand-new user', async () => {
    const { wrapper } = await mountApp('/user', { identity: NEW_USER })

    expect(wrapper.get('[data-testid="today-pending"]').text()).toContain('目前沒有等你處理的案件')
    expect(wrapper.findAll('[data-testid="briefing-item"]')).toHaveLength(0)
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

  /**
   * 推薦已併入今日摘要——先前它自成一個「值得先處理」面板，
   * 導致同一則建議在畫面上出現兩次（實際開瀏覽器才看到）。
   * 併入後可解釋性不能打折：每一則仍要攤得出證據。
   */
  it('shows the evidence behind each briefing item', async () => {
    const { wrapper } = await mountApp('/user')
    const withEvidence = todayBriefing.find((item) => item.evidence.length > 0)!

    await wrapper.get('.briefing .reason-details summary').trigger('click')
    const evidence = wrapper.get(`[data-testid="briefing-evidence-${withEvidence.id}"]`).text()

    expect(evidence.length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('非語言模型生成')
  })

  it('does not repeat the same recommendation in a second panel', async () => {
    const { wrapper } = await mountApp('/user')
    const title = insightRecommendations[0]!.title

    const occurrences = wrapper.text().split(title).length - 1
    expect(occurrences).toBe(1)
  })

  it('dismisses only the selected suggestion and lets the user undo that item', async () => {
    const { wrapper } = await mountApp('/user')

    // 待辦不是偏好問題，不該提供「不感興趣」
    const dismissable = wrapper.findAll('[data-testid="briefing-dismiss"]')
    const suggestions = todayBriefing.filter((item) => item.kind === 'suggestion')
    expect(dismissable).toHaveLength(suggestions.length)

    if (dismissable.length) {
      const dismissedTitle = suggestions[0]!.title
      const remainingTitle = suggestions[1]!.title
      await dismissable[0]!.trigger('click')
      expect(wrapper.find('[data-testid="briefing-dismissed"]').exists()).toBe(true)
      const visibleItems = wrapper.findAll('[data-testid="briefing-item"]').map((item) => item.text()).join('\n')
      expect(visibleItems).not.toContain(dismissedTitle)
      expect(visibleItems).toContain(remainingTitle)
      expect(wrapper.findAll('[data-testid="briefing-dismiss"]')).toHaveLength(suggestions.length - 1)

      await wrapper.get('[data-testid="briefing-dismissed"] button').trigger('click')
      expect(wrapper.text()).toContain(dismissedTitle)
    }
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
