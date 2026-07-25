// @vitest-environment happy-dom

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import App from '@/App.vue'
import { createAppRouter } from '@/router'

import { insightRecommendations, insightSummary } from './fixtures/catalog.generated'
import { stubCatalogFetch } from './fixtures/catalogClient'

async function mountToday() {
  const router = createAppRouter(createMemoryHistory())
  await router.push('/app/today')
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [createPinia(), router] } })
  await flushPromises()
  return wrapper
}

describe('today insights from official order data', () => {
  beforeEach(() => stubCatalogFetch())

  it('shows spend and open-order counts computed from the official records', async () => {
    const wrapper = await mountToday()

    expect(wrapper.get('[data-testid="metric-spend"]').text())
      .toBe(`NT$ ${insightSummary.totalSpend.toLocaleString('zh-TW')}`)
    expect(wrapper.get('[data-testid="metric-open"]').text())
      .toBe(String(insightSummary.openOrders))
    expect(wrapper.text()).toContain('來源：官方訂單紀錄')
  })

  it('lists the cross-service behaviour trail', async () => {
    const wrapper = await mountToday()
    const usage = wrapper.get('[data-testid="service-usage-list"]').text()
    for (const service of insightSummary.services) {
      expect(usage).toContain(service.serviceName)
    }
  })

  it('renders the top rule-computed recommendation with its reason', async () => {
    const wrapper = await mountToday()
    const top = insightRecommendations[0]!

    expect(wrapper.get('[data-testid="recommendation-title"]').text()).toBe(top.title)
    expect(wrapper.text()).toContain(top.reasonText)
  })

  it('can show the official order evidence behind a recommendation', async () => {
    const wrapper = await mountToday()
    const top = insightRecommendations[0]!

    await wrapper.get('.reason-details summary').trigger('click')
    const evidence = wrapper.get('[data-testid="recommendation-evidence"]').text()
    expect(evidence).toContain(top.evidence[0]!.serviceName)
    expect(evidence).toContain(top.evidence[0]!.detail)
    expect(wrapper.text()).toContain('非語言模型生成')
  })

  it('degrades to a status message instead of crashing on a malformed payload', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ data: [] }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })))
    const wrapper = await mountToday()

    expect(wrapper.text()).toContain('無法取得洞察資料')
    expect(wrapper.find('[data-testid="metric-spend"]').exists()).toBe(false)
  })
})
