// @vitest-environment happy-dom

import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import App from '@/App.vue'
import { createAppRouter } from '@/router'

async function confirmDialog() {
  const button = document.querySelector<HTMLButtonElement>('[data-testid="confirm-action"]')
  expect(button).not.toBeNull()
  if (button) await new DOMWrapper(button).trigger('click')
  await flushPromises()
}

describe('community to vendor workflow', () => {
  it('publishes a request, returns a quote, and assigns the vendor through confirmations', async () => {
    const router = createAppRouter(createMemoryHistory())
    await router.push('/app/community')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [createPinia(), router] }, attachTo: document.body })

    await wrapper.get('[data-testid="publish-campaign"]').trigger('click')
    expect(document.body.textContent).toContain('確認發送聯合服務需求')
    await confirmDialog()

    await router.push('/app/vendor')
    await flushPromises()
    await wrapper.get('[data-testid="submit-quote"]').trigger('click')
    expect(document.body.textContent).toContain('確認送出 18 戶清潔報價')
    await confirmDialog()

    await router.push('/app/community')
    await flushPromises()
    await wrapper.get('[data-testid="assign-vendor"]').trigger('click')
    await confirmDialog()

    expect(wrapper.text()).toContain('已安排履約')
    expect(wrapper.text()).toContain('7/27 開始履約')
  })
})
