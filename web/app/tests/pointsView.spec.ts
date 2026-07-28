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
    expect(wrapper.text()).toContain('競賽展示錢包')

    await wrapper.get('[data-testid="use-best-offer"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/user/services/shopping'))
  })
})
