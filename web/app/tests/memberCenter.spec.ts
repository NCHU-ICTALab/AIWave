// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('member center', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
    stubCatalogFetch()
  })

  it('shows the signed-in member and functional order and group destinations', async () => {
    const { wrapper, router, session } = await mountApp('/user/member')

    expect(router.currentRoute.value.path).toBe('/user/member')
    expect(wrapper.get('h1').text()).toBe('會員中心')
    expect(wrapper.get('[data-testid="member-identity"]').text()).toContain(session.displayName)
    expect(wrapper.get('a[href="/user/orders"]').text()).toContain('訂單')
    expect(wrapper.get('a[href="/user/community"]').text()).toContain('群組')
    expect(wrapper.text()).toContain('模擬 uniopen 身分')
  })
})
