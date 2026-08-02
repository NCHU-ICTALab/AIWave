// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('unified regular resident experience', () => {
  it('gives a regular resident the same community page and Father’s Day recommendations', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/community')
    await flushPromises()

    const nav = wrapper.get('nav[aria-label="主要導覽"]')
    expect(nav.text()).toContain('社區')
    expect(nav.text()).not.toContain('點數兌換')
    expect(wrapper.get('[data-testid="community-hub"]').text()).toContain('日光森林社區')
    expect(wrapper.findAll('[data-testid="father-day-recommendation"]')).toHaveLength(3)
    expect(wrapper.get('[data-testid="father-day-push"]').text()).toContain('可以買什麼')
  })

  it('opens the same community page from a regular member profile', async () => {
    stubCatalogFetch()
    const { wrapper, router } = await mountApp('/user/member')

    await wrapper.get('[data-testid="member-community-link"]').trigger('click')
    await router.isReady()
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/user/community')
    expect(wrapper.get('[data-testid="community-hub"]').text()).toContain('住戶首頁')
  })
})
