// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAgentSessionStore } from '@/stores/agentSession'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

/**
 * M8「桌面主工作區+Agent 側欄」(spec 15 §4.1)。
 *
 * 側欄與 /user/assistant 全頁共用同一個 agent-session store,
 * 所以斷言都落在 store 與側欄殼上,不依賴 AgentConversation 的內部標記
 * ——那個元件正在被另一條工作線重寫,測試必須在重寫落地後仍然成立。
 */
describe('agent drawer', () => {
  beforeEach(() => stubCatalogFetch())

  it('opens the shared conversation from a member route and closes with Escape', async () => {
    const { wrapper } = await mountApp('/user', { attach: true })

    const toggle = wrapper.get('[data-testid="agent-drawer-toggle"]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[data-testid="agent-drawer"]').exists()).toBe(false)

    await toggle.trigger('click')
    await flushPromises()
    expect(toggle.attributes('aria-expanded')).toBe('true')
    const drawer = wrapper.get('[data-testid="agent-drawer"]')
    expect(drawer.attributes('aria-label')).toBe('AI 管家側欄')
    // 側欄裡掛的是與 AI 頁同一個對話元件
    expect(wrapper.findComponent({ name: 'AgentConversation' }).exists()).toBe(true)
    // 開啟時焦點移入側欄;側欄不是 dialog(主工作區+側欄並存,不做焦點陷阱)
    expect(drawer.element.contains(document.activeElement)).toBe(true)
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    // 側欄提供回完整 AI 頁的入口
    expect(wrapper.get('[data-testid="agent-drawer-full-page"]').attributes('href')).toBe('/user/assistant')

    await drawer.trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(wrapper.find('[data-testid="agent-drawer"]').exists()).toBe(false)
    expect(toggle.attributes('aria-expanded')).toBe('false')
    // 關閉後焦點回到開關鈕
    expect(document.activeElement).toBe(toggle.element)

    wrapper.unmount()
  })

  it('keeps the same conversation when moving from the drawer to the full AI page', async () => {
    const { wrapper, router } = await mountApp('/user')
    await wrapper.get('[data-testid="agent-drawer-toggle"]').trigger('click')
    await flushPromises()

    // 透過共用 store 送訊息(側欄與 AI 頁讀寫同一份;不綁 composer 的內部標記)
    const agent = useAgentSessionStore()
    await agent.send({ message: '浴室的燈不亮了' })
    expect(agent.error).toBe('')
    expect(agent.messages.map((message) => message.content)).toContain('浴室的燈不亮了')

    await router.push('/user/assistant')
    await flushPromises()

    // 完整 AI 頁不再疊側欄(它本身就是同一段對話),對話因同一個 store 而保留
    expect(wrapper.find('[data-testid="agent-drawer-toggle"]').exists()).toBe(false)
    expect(agent.messages.map((message) => message.content)).toContain('浴室的燈不亮了')
  })

  it('does not render the toggle for non-member roles', async () => {
    const { wrapper } = await mountApp('/partner', {
      identity: { role: 'partner', accountId: 'vendor-prince-electric', displayName: '王子水電' },
    })

    expect(wrapper.find('[data-testid="agent-drawer-toggle"]').exists()).toBe(false)
  })

  it('queues a home-page need into the shared store and hands off to the AI page', async () => {
    const { wrapper, router } = await mountApp('/user')
    const agent = useAgentSessionStore()

    await wrapper.get('[data-testid="need-input"]').setValue('冷氣不冷，順便看看社區團購')
    await wrapper.get('[data-testid="need-submit"]').trigger('submit')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('assistant'))

    // AI 頁掛載後會 flushPending 自動送出;在那之前訊息保持排隊。
    // 兩種最終狀態(排隊中/已送出)都代表首頁與 AI 頁共享同一段對話。
    await vi.waitFor(() => expect(
      agent.pendingMessage === '冷氣不冷，順便看看社區團購'
        || agent.messages.some((message) => message.content === '冷氣不冷，順便看看社區團購'),
    ).toBe(true))
  })
})
