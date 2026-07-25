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

  it('routes a described need to the matched service', async () => {
    stubCatalogFetch((url) =>
      url.includes('/api/v1/intent/match')
        ? new Response(JSON.stringify({ data: { serviceId: 'service-repair', serviceName: '水電修繕', confidence: 'high', reason: '燈具故障' } }), { status: 200, headers: { 'Content-Type': 'application/json' } })
        : undefined,
    )
    const { wrapper, router } = await mountApp('/user')

    await wrapper.get('[data-testid="need-input"]').setValue('浴室的燈不亮了')
    await wrapper.get('[data-testid="need-submit"]').trigger('submit')
    await vi.waitFor(() => expect(router.currentRoute.value.params.serviceSlug).toBe('repair'))
    expect(router.currentRoute.value.query.need).toBe('浴室的燈不亮了')
  })

  it('falls back to the catalog when the need cannot be matched', async () => {
    stubCatalogFetch((url) =>
      url.includes('/api/v1/intent/match')
        ? new Response(JSON.stringify({ data: null }), { status: 200, headers: { 'Content-Type': 'application/json' } })
        : undefined,
    )
    const { wrapper, router } = await mountApp('/user')

    await wrapper.get('[data-testid="need-input"]').setValue('幫我養一隻貓')
    await wrapper.get('[data-testid="need-submit"]').trigger('submit')
    await vi.waitFor(() => expect(router.currentRoute.value.query.unmatched).toBe('1'))
    expect(wrapper.get('[data-testid="need-unmatched"]').text()).toContain('幫我養一隻貓')
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
