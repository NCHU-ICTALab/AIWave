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

  it('shows a first-time visitor the public homepage, never someone else’s dashboard', async () => {
    // spec 15 §9.1(方向 A 核准):公開首頁先講產品價值,右上角才是登入入口
    const { wrapper, router } = await mountApp('/', { identity: null })

    expect(router.currentRoute.value.name).toBe('home-public')
    expect(wrapper.text()).toContain('六大生活場景')
    expect(wrapper.find('[data-testid="public-sign-in"]').exists()).toBe(true)
    // 未登入時不該出現任何個人數字
    expect(wrapper.find('[data-testid="metric-spend"]').exists()).toBe(false)
  })

  it('protects resident pages from unauthenticated access', async () => {
    const { router } = await mountApp('/user/orders', { identity: null })
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('uses /login as the unified entry for the community Demo', async () => {
    const resident = await mountApp('/login', { identity: null })

    await resident.wrapper.get('[data-testid="enter-community-demo-resident"]').trigger('click')
    await vi.waitFor(() => expect(resident.router.currentRoute.value.path).toBe('/demo/resident'))
    expect(resident.session.identity?.displayName).toBe('王小明')
    expect(resident.wrapper.text()).toContain('日光森林社區')

    const manager = await mountApp('/login', { identity: null })
    await manager.wrapper.get('[data-testid="enter-community-demo-manager"]').trigger('click')
    await vi.waitFor(() => expect(manager.router.currentRoute.value.path).toBe('/demo/committee'))
    expect(manager.session.identity?.displayName).toBe('主委陳建華')
    expect(manager.wrapper.text()).toContain('社區營運工作台')
  })

  it('starts a new account with no records at all', async () => {
    const { wrapper, router, session } = await mountApp('/login', { identity: null })

    await wrapper.get('[data-testid="start-new-user"]').trigger('click')
    // 路由採 lazy import，須等元件載入完成
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/user'))
    await flushPromises()

    expect(session.accountId).toBe('demo-new-member')
    expect(session.accessToken).toBe('aiwave-new')
    expect(session.isNewUser).toBe(true)
    expect(wrapper.find('[data-testid="onboarding-steps"]').exists()).toBe(true)
  })

  /**
   * 登入清單是三位有名字的展示住戶，不是 10 個通路帳號。
   *
   * 官方樣本 7/10 帳號只用過單一服務——那是通路切分，不是 10 個真實的人。
   * 後端先以官方雜湊做行為指紋解析，再組成完整生活樣貌的住戶。
   */
  it('offers a few named households rather than one entry per channel account', async () => {
    const { wrapper } = await mountApp('/login', { identity: null })
    const options = wrapper.findAll('[data-account-id]')

    expect(options.length).toBeLessThanOrEqual(4)
    expect(options[0]!.text()).toMatch(/\d+ 筆紀錄/)
    expect(options[0]!.text()).toMatch(/\d 種服務/)
    for (const option of options) {
      expect(option.text()).not.toMatch(/^使用者 \d/)   // 有名字，不是「使用者 1」
    }
  })

  it('signs the resident in under the household name', async () => {
    const { wrapper, session } = await mountApp('/login', { identity: null })
    const first = wrapper.findAll('[data-account-id]')[0]!
    const name = first.find('strong').text()

    await first.trigger('click')

    expect(session.identity?.displayName).toBe(name)
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
