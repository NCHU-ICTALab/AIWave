// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

function ndjson(body: unknown) {
  const payload = body as { reply?: string }
  const events = [
    { type: 'status', label: '正在理解你的回答' },
    { type: 'delta', text: payload.reply ?? '' },
    { type: 'complete', data: body },
  ]
  return new Response(events.map((event) => JSON.stringify(event)).join('\n') + '\n', {
    status: 200, headers: { 'Content-Type': 'application/x-ndjson' },
  })
}

const REPAIR_QUESTION = {
  id: 'repairType',
  topicId: 1,
  label: '修繕項目',
  type: 3,
  required: true,
  options: [
    { value: 'plumbing', label: '水管／馬桶', optionId: 1070 },
    { value: 'lighting', label: '燈具／開關', optionId: 1071 },
  ],
}

const START = {
  session_id: 's1',
  service_id: 'service-repair',
  service_name: '水電修繕',
  reply: '好的，我幫您安排「水電修繕」。\n請問修繕項目？',
  question: REPAIR_QUESTION,
  done: false,
  awaiting_confirmation: false,
  progress: { answered: 0, total: 2 },
  trace: [{ stage: 'tool', tool: 'get_service_form', status: 'completed' }],
}

/** 依網址路由的對話 stub，並記錄送出的訊息。 */
function stubConversation(replies: unknown[]) {
  const sent: string[] = []
  stubCatalogFetch((url, init) => {
    if (url.endsWith('/api/chat/start')) return json(START)
    if (url.endsWith('/api/chat/message/stream')) {
      sent.push((JSON.parse(String(init?.body)) as { message: string }).message)
      return ndjson(replies.shift() ?? { reply: '（結束）', done: true, progress: { answered: 2, total: 2 }, trace: [] })
    }
    return undefined
  })
  return sent
}

describe('assistant conversation', () => {
  beforeEach(() => stubConversation([]))

  it('runs as a full page rather than a cramped drawer', async () => {
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')
    const workspace = wrapper.get('[data-testid="assistant-workspace"]')

    expect(wrapper.get('h1').text()).toBe('水電修繕')
    expect(wrapper.text()).toContain('請問修繕項目？')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(workspace.find('.message-list').exists()).toBe(true)
    expect(workspace.find('[data-testid="assistant-composer"]').exists()).toBe(true)
  })

  /**
   * 泡泡的角色 class 不可與版面容器撞名。
   *
   * 先前直接用 role 當 class，「assistant」正好命中頁面容器的 `.assistant`
   * （`min-height: calc(100vh - 9rem)`），每顆管家泡泡下方因此空出一整個視窗高，
   * 內容被擠到要往上滑才看得到。單元測試看不出來，但使用者一眼就看到。
   */
  it('namespaces message role classes so they cannot collide with layout classes', async () => {
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')
    const bubble = wrapper.get('.message')

    expect(bubble.classes()).toContain('from-assistant')
    expect(bubble.classes()).not.toContain('assistant')
  })

  it('places question options above the always-available bottom composer', async () => {
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')
    const composer = wrapper.get('[data-testid="assistant-composer"]')
    const menu = composer.get('[data-testid="answer-choices"]')
    const choices = menu.findAll('[data-choice]')

    expect(choices.map((choice) => choice.text())).toEqual(['水管／馬桶', '燈具／開關'])
    expect(composer.find('#assistant-input').exists()).toBe(true)
    expect(menu.element.compareDocumentPosition(composer.get('form').element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('sends the chosen option label when a button is clicked', async () => {
    const sent = stubConversation([
      { reply: '請問緊急程度？', question: null, done: false, progress: { answered: 1, total: 2 }, trace: [] },
    ])
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')

    await wrapper.get('[data-choice="lighting"]').trigger('click')
    await flushPromises()

    expect(sent).toEqual(['燈具／開關'])
    expect(wrapper.text()).toContain('請問緊急程度？')
  })

  it('shows safe progress immediately and renders streamed assistant text incrementally', async () => {
    const encoder = new TextEncoder()
    let streamController!: ReadableStreamDefaultController<Uint8Array>
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        streamController = controller
        controller.enqueue(encoder.encode('{"type":"status","label":"正在理解你的回答"}\n'))
      },
    })
    stubCatalogFetch((url) => {
      if (url.endsWith('/api/chat/start')) return json(START)
      if (url.endsWith('/api/chat/message/stream')) {
        return new Response(stream, { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')

    await wrapper.get('[data-choice="lighting"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="assistant-activity"]').text()).toContain('正在理解你的回答')
    expect(wrapper.get('.message.from-user').text()).toContain('燈具／開關')
    expect(wrapper.findAll('.message.from-assistant')).toHaveLength(1)

    streamController.enqueue(encoder.encode('{"type":"delta","text":"請問緊急"}\n'))
    await flushPromises()
    expect(wrapper.findAll('.message.from-assistant').at(-1)!.text()).toContain('請問緊急')

    streamController.enqueue(encoder.encode('{"type":"delta","text":"程度？"}\n'))
    streamController.enqueue(encoder.encode('{"type":"complete","data":{"reply":"請問緊急程度？","question":null,"done":false,"progress":{"answered":1,"total":2},"trace":[]}}\n'))
    streamController.close()
    await vi.waitFor(() => expect(wrapper.find('[data-testid="assistant-activity"]').exists()).toBe(false))
    expect(wrapper.findAll('.message.from-assistant').at(-1)!.text()).toContain('請問緊急程度？')
  })

  it('submits on Enter and keeps Shift+Enter for a new line', async () => {
    const sent = stubConversation([
      { reply: '收到', question: null, done: false, progress: { answered: 1, total: 2 }, trace: [] },
    ])
    // 沒有選項的題目才需要打字
    stubCatalogFetch((url, init) => {
      if (url.endsWith('/api/chat/start')) return json({ ...START, question: { ...REPAIR_QUESTION, options: undefined } })
      if (url.endsWith('/api/chat/message/stream')) {
        sent.push((JSON.parse(String(init?.body)) as { message: string }).message)
        return ndjson({ reply: '收到', question: null, done: false, progress: { answered: 1, total: 2 }, trace: [] })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')

    const input = wrapper.get('#assistant-input')
    await input.setValue('馬桶會漏水')
    await input.trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(sent).toEqual([])   // Shift+Enter 只是換行

    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(sent).toEqual(['馬桶會漏水'])
  })

  it('grows the message box with multiline input without a manual resize handle', async () => {
    stubCatalogFetch((url) => (url.endsWith('/api/chat/start')
      ? json({ ...START, question: { ...REPAIR_QUESTION, options: undefined } })
      : undefined))
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')
    const input = wrapper.get<HTMLTextAreaElement>('#assistant-input')
    Object.defineProperty(input.element, 'scrollHeight', { configurable: true, value: 92 })

    await input.setValue('浴室漏水\n而且地板很滑')

    expect(input.element.style.height).toBe('92px')
    expect(input.attributes('data-autogrow')).toBe('true')
  })

  it('offers one confirm button plus a way to say what to change', async () => {
    stubCatalogFetch((url) => (url.endsWith('/api/chat/start')
      ? json({ ...START, reply: '幫您確認以下內容…', question: null, awaiting_confirmation: true })
      : undefined))
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')

    expect(wrapper.find('[data-testid="confirm-send"]').exists()).toBe(true)
    expect(wrapper.get('#assistant-input').attributes('placeholder')).toContain('想改哪一項')
  })

  it('shows the created inquiry and a link to track it', async () => {
    stubCatalogFetch((url) => (url.endsWith('/api/chat/start')
      ? json({
          ...START,
          reply: '已建立諮詢單 INQ-20260725-001',
          question: null,
          done: true,
          operation: { type: 'inquiry.created', id: 'INQ-20260725-001', status: 'pending_quote' },
        })
      : undefined))
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')

    expect(wrapper.text()).toContain('INQ-20260725-001')
    expect(wrapper.find('a[href="/user/orders"]').exists()).toBe(true)
  })

  it('reports a connection failure honestly instead of blaming the wording', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
    const { wrapper } = await mountApp('/user/assistant?service=service-repair')

    expect(wrapper.get('[role="alert"]').text()).toContain('無法連線')
  })
})
