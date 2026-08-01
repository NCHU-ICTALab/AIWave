// @vitest-environment happy-dom

/**
 * M8 Agent 端到端流程（取代舊 planner 規劃模式）。
 *
 * 這裡守住三件事：
 * 1. **完整閉環**——訊息→選方案→補欄位（可切手動，同一份草稿）→授權→送單，
 *    每一步都是真動作，最後訂單確實寫進 Platform（stub state 可查）。
 * 2. **交易必須明確核准**——授權卡沒按「核准並執行」就不得建立任何訂單；
 *    「先不要」要真的撤回。
 * 3. **失敗要說實話**——agent 端點掛掉時顯示誠實錯誤，不得假裝成功。
 */

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

async function settle() {
  await flushPromises()
  await flushPromises() // 串流讀取逐 microtask 進行，多沖一輪
}

async function say(wrapper: Awaited<ReturnType<typeof mountApp>>['wrapper'], text: string) {
  await wrapper.get('#agent-input').setValue(text)
  await wrapper.get('[data-testid="assistant-composer"] form').trigger('submit')
  await settle()
}

async function listBookings(): Promise<unknown[]> {
  const response = await fetch('/api/v1/platform/bookings')
  const payload = (await response.json()) as { data: unknown[] }
  return payload.data
}

/** 走到授權卡出現為止（訊息→選方案→補欄位）。 */
async function reachGrantCard(wrapper: Awaited<ReturnType<typeof mountApp>>['wrapper']) {
  await say(wrapper, '浴室的燈不亮了')
  await wrapper.get('[data-testid="proposal-select"]').trigger('click')
  await settle()
  await say(wrapper, '浴室天花板的燈不亮，可能是燈具或線路問題')
  return wrapper.get('[data-testid="grant-card"]')
}

describe('agent end-to-end flow', () => {
  it('runs message → proposal → missing fields (with manual handoff) → grant → order, and really persists the booking', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/assistant')

    // 1) 一句話 → 方案卡
    await say(wrapper, '浴室的燈不亮了')
    const card = wrapper.get('[data-testid="proposal-card"]')
    expect(card.text()).toContain('王子水電')

    // 2) 選方案 → 缺欄位提示 + 「切到手動填寫」連結(同一份草稿)
    await wrapper.get('[data-testid="proposal-select"]').trigger('click')
    await settle()
    const composer = wrapper.get('[data-testid="assistant-composer"]')
    expect(composer.text()).toContain('問題描述')
    expect(composer.text()).toContain('服務地址')
    const handoff = wrapper.get('[data-testid="handoff-manual"]')
    expect(handoff.text()).toContain('切到手動填寫')
    expect(handoff.attributes('href')).toMatch(/^\/user\/booking\?draft=draft-stub-\d+$/)
    expect(await listBookings()).toHaveLength(0) // 這一步還不能有任何訂單

    // 3) 直接在 composer 回覆補資料 → 授權卡(內容含預算上限)
    await say(wrapper, '浴室天花板的燈不亮，可能是燈具或線路問題')
    const grantCard = wrapper.get('[data-testid="grant-card"]')
    expect(grantCard.text()).toContain('預算上限')
    expect(grantCard.text()).toContain('1,200')
    expect(grantCard.find('[data-testid="grant-approve"]').exists()).toBe(true)
    expect(await listBookings()).toHaveLength(0) // 沒核准前仍不得建單

    // 4) 核准 → 結果卡含訂單編號與訂單連結
    await wrapper.get('[data-testid="grant-approve"]').trigger('click')
    await settle()
    const result = wrapper.get('[data-testid="agent-result"]')
    expect(result.text()).toMatch(/booking-stub-\d+/)
    const orderLink = result.get('[data-testid="order-link"]')
    expect(orderLink.attributes('href')).toMatch(/^\/user\/orders\/booking-stub-\d+$/)

    // 5) 訂單真的寫進 Platform(stub state),不是前端自己畫的
    const bookings = await listBookings()
    expect(bookings).toHaveLength(1)
    expect(bookings[0]).toMatchObject({ providerId: 'vendor-prince-electric', status: 'pending_provider' })
  })

  it('revokes the grant on 「先不要」 and creates no order', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/assistant')

    await reachGrantCard(wrapper)
    await wrapper.get('[data-testid="grant-revoke"]').trigger('click')
    await settle()

    expect(wrapper.get('[aria-label="對話內容"]').text()).toContain('已撤回授權')
    expect(wrapper.find('[data-testid="grant-card"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="agent-result"]').exists()).toBe(false)
    expect(await listBookings()).toHaveLength(0)
  })

  it('reports an honest error when the agent endpoint fails, without faking progress', async () => {
    stubCatalogFetch((url) => {
      if (url.includes('/api/v1/platform/agent/messages')) {
        return new Response(JSON.stringify({ detail: 'AI 管家服務暫時無法使用' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/assistant')

    await say(wrapper, '浴室的燈不亮了')

    const alert = wrapper.get('[role="alert"]')
    expect(alert.text()).toContain('目前無法繼續')
    expect(alert.text()).toContain('AI 管家服務暫時無法使用')
    // 不得假成功:沒有方案卡、沒有結果卡
    expect(wrapper.find('[data-testid="proposal-card"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="agent-result"]').exists()).toBe(false)
  })
})
