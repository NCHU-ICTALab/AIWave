// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp, NEW_USER } from './fixtures/mountApp'

describe('community group-buy catalog', () => {
  it('browses products and carries a selected product into the editable opening flow', async () => {
    stubCatalogFetch()
    const { wrapper, router, session } = await mountApp('/user/community/group-buys', { identity: NEW_USER })
    await flushPromises()

    expect(wrapper.get('[data-testid="group-buy-catalog"]').text()).toContain('商品列表')
    expect(wrapper.findAll('[data-testid="open-group-from-list"]').length).toBeGreaterThan(3)

    await wrapper.find('[data-testid="open-group-from-list"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('community-group-buy-open'))
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('community-group-buy-open')
    expect(wrapper.get('[data-testid="group-buy-open-page"]').text()).toContain('可編輯')
    const selectedName = (wrapper.get('[data-testid="open-group-name"]').element as HTMLInputElement).value

    await wrapper.get('form.group-buy-open-form').trigger('submit')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('community-group-buy'))
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('community-group-buy')
    expect(session.role).toBe('user')
    expect(wrapper.get('h1').text()).toContain(selectedName)
    expect(wrapper.find('[data-testid="join-group-buy"]').exists()).toBe(true)
  })
})
