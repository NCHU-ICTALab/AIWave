// @vitest-environment happy-dom

import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import App from '@/App.vue'
import { createAppRouter } from '@/router'

import { stubCatalogFetch } from './fixtures/catalogClient'

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

describe('real AI Copilot flow', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('calls the backend and projects the persisted inquiry into order tracking', async () => {
    // 依網址路由，而非依呼叫順序——頁面本身也會取洞察資料
    const chatReplies = [
      json({ session_id: 's1', reply: '請問需要修繕的項目？', done: false, awaiting_confirmation: false, progress: { answered: 0, total: 6 }, trace: [{ stage: 'tool', tool: 'get_service_form', status: 'completed' }] }),
      json({ reply: '已建立諮詢單 INQ-20260725-001', done: true, awaiting_confirmation: false, progress: { answered: 6, total: 6 }, trace: [{ stage: 'write', tool: 'submit_inquiry', status: 'completed' }], operation: { type: 'inquiry.created', id: 'INQ-20260725-001', status: 'pending_quote' } }),
    ]
    stubCatalogFetch((url) => (url.includes('/api/chat/') ? chatReplies.shift() : undefined))
    const router = createAppRouter(createMemoryHistory())
    await router.push('/app/today')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [createPinia(), router] }, attachTo: document.body })

    await wrapper.get('[aria-haspopup="dialog"]').trigger('click')
    const startButton = document.querySelector<HTMLButtonElement>('[data-testid="start-ai-inquiry"]')
    expect(startButton).not.toBeNull()
    if (startButton) await new DOMWrapper(startButton).trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('get_service_form')

    const input = document.querySelector<HTMLTextAreaElement>('#copilot-input')
    expect(input).not.toBeNull()
    if (input) {
      input.value = '確認送出'
      input.dispatchEvent(new Event('input', { bubbles: true }))
    }
    const form = document.querySelector<HTMLFormElement>('.copilot-form')
    form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await flushPromises()

    expect(document.body.textContent).toContain('INQ-20260725-001')
    await router.push('/app/orders')
    await flushPromises()
    expect(wrapper.text()).toContain('INQ-20260725-001')
    expect(wrapper.text()).toContain('待確認')
  })
})
