// @vitest-environment happy-dom

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import App from '@/App.vue'
import { createAppRouter } from '@/router'

describe('order backend projection', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('restores a persisted AI inquiry after a fresh page load', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ data: [{ id: 'INQ-20260725-009', form_id: 901, status: 'pending_quote', created_at: '2026-07-25T00:00:00Z', events: [{ type: 'inquiry.created', occurred_at: '2026-07-25T00:00:00Z' }] }] }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    const router = createAppRouter(createMemoryHistory())
    await router.push('/app/orders')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [createPinia(), router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('INQ-20260725-009')
    expect(wrapper.text()).toContain('已同步後端諮詢紀錄')
  })
})
