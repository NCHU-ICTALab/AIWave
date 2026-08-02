// @vitest-environment happy-dom

/**
 * M8 Agent 對話（換腦不換臉）：AI 頁掛 AgentConversation，對話走
 * `/api/v1/platform/agent/*`（platformStub 的確定性腳本）。
 *
 * 這裡守住互動殼的基本盤：composer 固定存在、訊息區可被螢幕閱讀器接住、
 * Enter/Shift+Enter 行為、可驗證階段（不是思考鏈）、以及釐清選項是
 * 結構化動作而不是再丟一句話給 LLM。
 */

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

/** 攔截並記錄送往 agent 端點的請求；回 undefined 讓 platformStub 照常處理。 */
function recordAgentPosts() {
  const posted: Array<{ message: string | null; action: { type: string } | null }> = []
  stubCatalogFetch((url, init) => {
    if (url.includes('/api/v1/platform/agent/messages') && init?.body) {
      posted.push(JSON.parse(String(init.body)))
    }
    return undefined
  })
  return posted
}

async function say(wrapper: Awaited<ReturnType<typeof mountApp>>['wrapper'], text: string) {
  await wrapper.get('#agent-input').setValue(text)
  await wrapper.get('[data-testid="assistant-composer"] form').trigger('submit')
  await flushPromises()
  await flushPromises() // 串流讀取是逐 microtask 進行，多沖一輪
}

describe('agent conversation shell', () => {
  it('keeps a fixed composer and a live-labelled message area, and answers a repair need with proposal cards', async () => {
    recordAgentPosts()
    const { wrapper } = await mountApp('/user/assistant')

    // 殼:單一 h1、composer 固定存在、訊息區可捲動且有 aria-live
    expect(wrapper.get('h1').text()).toBe('AI 管家')
    const messageArea = wrapper.get('[aria-label="對話內容"]')
    expect(messageArea.attributes('aria-live')).toBe('polite')
    const composer = wrapper.get('[data-testid="assistant-composer"]')
    expect(composer.find('#agent-input').exists()).toBe(true)
    expect(wrapper.get('#agent-input').attributes('data-autogrow')).toBe('true')
    expect(wrapper.find('[data-testid="agent-session-history"]').exists()).toBe(true)
    expect(wrapper.find('.assistant-session-column').exists()).toBe(true)
    expect(wrapper.find('.assistant-chat-column').exists()).toBe(true)
    expect(wrapper.get('[data-testid="natural-language-hint"]').text()).toContain('不用先選服務分類')

    await say(wrapper, '浴室的燈不亮了')

    // assistant 的拆解訊息 + 方案卡(為何推薦 reasons + 價格 + 時段)
    expect(messageArea.text()).toContain('我把需求拆成')
    const card = wrapper.get('[data-testid="proposal-card"]')
    expect(card.text()).toContain('王子水電')
    expect(card.text()).toContain('水電修繕・到府檢測')
    expect(card.text()).toContain('NT$ 1,200')
    expect(card.text()).toContain('評分 4.8')
    expect(card.find('[data-testid="proposal-select"]').exists()).toBe(true)
    // 方案在輸入框上方(同一個 composer 區,選項先於表單)
    const zone = composer.get('.agent-proposals')
    expect(
      zone.element.compareDocumentPosition(composer.get('form').element) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('understands a whole life situation and keeps multiple needs in one conversation', async () => {
    recordAgentPosts()
    const { wrapper } = await mountApp('/user/assistant')

    await say(wrapper, '爸媽週末要來，幫我安排家裡清潔和家庭晚餐')

    const messages = wrapper.get('[aria-label="對話內容"]')
    expect(messages.text()).toContain('我懂了：爸媽週末要來')
    expect(wrapper.findAll('[data-testid="proposal-card"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('DUSKIN 樂清')
    expect(wrapper.text()).toContain('21PLUS')
  })

  it('clarifies an ambiguous need with option buttons that send structured actions, not another LLM guess', async () => {
    const posted = recordAgentPosts()
    const { wrapper } = await mountApp('/user/assistant')

    await say(wrapper, '洗衣服')

    expect(wrapper.get('[aria-label="對話內容"]').text()).toContain('到府做家事')
    const options = wrapper.findAll('[data-testid="clarify-option"]')
    expect(options).toHaveLength(2)
    expect(options.map((option) => option.text())).toEqual(['到府家事服務(含洗衣)', '洗衣機清洗'])

    await options[0]!.trigger('click')
    await flushPromises()
    await flushPromises()

    // 點選項送的是結構化 clarify_option 動作,不是一句話
    expect(posted.at(-1)!.action).toMatchObject({ type: 'clarify_option', label: '到府家事服務(含洗衣)' })
    expect(posted.at(-1)!.message).toBeNull()
    expect(wrapper.get('[data-testid="proposal-card"]').text()).toContain('DUSKIN 樂清')
  })

  it('submits on Enter and keeps Shift+Enter for a new line', async () => {
    const posted = recordAgentPosts()
    const { wrapper } = await mountApp('/user/assistant')

    const input = wrapper.get('#agent-input')
    await input.setValue('浴室的燈不亮了')
    await input.trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(posted).toHaveLength(0) // Shift+Enter 只是換行

    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    await flushPromises()
    expect(posted.map((call) => call.message)).toEqual(['浴室的燈不亮了'])
    expect(wrapper.get('.message.from-user').text()).toContain('浴室的燈不亮了')
  })

  it('shows the verifiable work stages from the stream and keeps them as static text afterwards', async () => {
    recordAgentPosts()
    const { wrapper } = await mountApp('/user/assistant')

    await say(wrapper, '浴室的燈不亮了')

    // 串流階段來自後端(stub 的 stream 回應),完成後保留靜態文字;不顯示思考鏈
    const stages = wrapper.get('[data-testid="agent-stages"]')
    expect(stages.text()).toContain('理解需求')
    expect(stages.text()).toContain('查詢可用方案與時段')
    expect(stages.text()).toContain('整理方案')
    // 完成後不再是 busy 的 status 動畫,只是靜態紀錄
    expect(stages.attributes('role')).toBeUndefined()
  })

  it('renders ToolResult facts, audit references, citations, and update dates', async () => {
    recordAgentPosts()
    const { wrapper } = await mountApp('/user/assistant')

    await say(wrapper, 'OPENPOINT 怎麼折抵')

    const evidence = wrapper.get('[aria-label="權威資料卡"]')
    expect(evidence.text()).toContain('已驗證結果・succeeded')
    expect(evidence.text()).toContain('來源：published-wiki')
    expect(evidence.text()).toContain('稽核參照：wiki:product-help')
    expect(evidence.text()).toContain('OPENPOINT 折抵與兌換・折抵規則・更新 2026-07-31')
  })

  it('treats starter chips as real messages instead of navigation', async () => {
    const posted = recordAgentPosts()
    const { wrapper, router } = await mountApp('/user/assistant')

    const chips = wrapper.findAll('[data-testid="starter-chip"]')
    expect(chips.map((chip) => chip.text())).toEqual([
      '爸媽週末要來，幫我安排清潔和晚餐',
      '浴室的燈不亮了，想找人明天來修',
      '我想先看看社區有哪些服務',
    ])

    await chips[0]!.trigger('click')
    await flushPromises()
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('assistant') // 沒有導頁
    expect(posted.map((call) => call.message)).toEqual(['爸媽週末要來，幫我安排清潔和晚餐'])
    expect(wrapper.find('[data-testid="proposal-card"]').exists()).toBe(true)
  })
})
