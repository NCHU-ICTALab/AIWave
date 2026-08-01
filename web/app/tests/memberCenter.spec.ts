// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DEMO_RESIDENT_IDENTITY } from '@/stores/session'

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
    expect(wrapper.get('[data-testid="member-community-link"]').attributes('href')).toBe('/user/community')
    expect(wrapper.text()).toContain('模擬 uniopen 身分')
  })

  it('lets the unified Demo profile open the community page', async () => {
    const { wrapper, router } = await mountApp('/demo/member', { identity: DEMO_RESIDENT_IDENTITY, attach: true })

    expect(wrapper.get('h1').text()).toBe('會員中心')
    await wrapper.get('[data-testid="member-community-link"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/demo/community'))

    expect(router.currentRoute.value.path).toBe('/demo/community')
    expect(wrapper.text()).toContain('日光森林社區')
    expect(wrapper.find('[data-testid="resident-group-buys"]').exists()).toBe(true)
  })

  it('requires a deliberate confirmation before restoring the demo', async () => {
    let resets = 0
    stubCatalogFetch((url, init) => {
      if (url.endsWith('/api/v1/platform/demo/reset') && init?.method === 'POST') {
        resets += 1
        return new Response(JSON.stringify({ data: { status: 'ready', resetAt: '2026-07-29T10:00:00+08:00' } }), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/member')

    await wrapper.get('[data-testid="open-demo-reset"]').trigger('click')
    expect(resets).toBe(0)
    expect(wrapper.get('[role="dialog"]').text()).toContain('所有展示操作紀錄')

    await wrapper.get('[data-testid="confirm-demo-reset"]').trigger('click')
    await flushPromises()

    expect(resets).toBe(1)
    expect(wrapper.text()).toContain('已還原成 Demo 初始資料')
  })
})
