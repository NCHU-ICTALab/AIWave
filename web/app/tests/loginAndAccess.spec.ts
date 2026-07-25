// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('entry points and identity', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
    stubCatalogFetch()
  })

  it('sends a first-time visitor to the sign-in page instead of someone else’s dashboard', async () => {
    const { wrapper, router } = await mountApp('/', { identity: null })

    expect(router.currentRoute.value.name).toBe('login')
    expect(wrapper.text()).toContain('說一句話，生活的事就有人接手')
    // 未登入時不該出現任何個人數字
    expect(wrapper.find('[data-testid="metric-spend"]').exists()).toBe(false)
  })

  it('protects resident pages from unauthenticated access', async () => {
    const { router } = await mountApp('/user/orders', { identity: null })
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('starts a new account with no records at all', async () => {
    const { wrapper, router, session } = await mountApp('/login', { identity: null })

    await wrapper.get('[data-testid="start-new-user"]').trigger('click')
    // 路由採 lazy import，須等元件載入完成
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/user'))
    await flushPromises()

    expect(session.accountId).toBeNull()
    expect(session.isNewUser).toBe(true)
    expect(wrapper.find('[data-testid="onboarding-steps"]').exists()).toBe(true)
  })

  it('offers existing accounts described by their actual behaviour', async () => {
    const { wrapper } = await mountApp('/login', { identity: null })
    const options = wrapper.findAll('[data-account-id]')

    expect(options.length).toBeGreaterThan(0)
    expect(options[0]!.text()).toMatch(/\d+ 筆紀錄/)
  })

  it('signs in as an existing account and shows that account’s data', async () => {
    const { wrapper, router, session } = await mountApp('/login', { identity: null })

    await wrapper.findAll('[data-account-id]')[0]!.trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/user'))
    await flushPromises()

    expect(session.accountId).not.toBeNull()
    expect(wrapper.find('[data-testid="metric-spend"]').exists()).toBe(true)
  })

  it('keeps staff workspaces separate from the resident app', async () => {
    const { wrapper, router } = await mountApp('/login', { identity: null })

    await wrapper.get('[data-testid="enter-manager"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/community'))

    // 管理者不能直接進住戶頁——會被導回自己的工作台
    await router.push('/user/orders')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/community'))
  })

  it('has no workspace switcher or reset control in the shell', async () => {
    const { wrapper } = await mountApp('/user')

    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('重設')
  })

  it('signs out back to the sign-in page', async () => {
    const { wrapper, router, session } = await mountApp('/user')

    await wrapper.get('[data-testid="sign-out"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('login'))
    expect(session.isSignedIn).toBe(false)
  })
})
