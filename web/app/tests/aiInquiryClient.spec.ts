import { describe, expect, it, vi } from 'vitest'

import { createAiInquiryClient } from '@/api/aiInquiryClient'

describe('AI inquiry API client', () => {
  it('starts a real backend form session and sends messages to that session', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ session_id: 's1', reply: '第一題', done: false, progress: { answered: 0, total: 6 }, trace: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ reply: '第二題', done: false, progress: { answered: 1, total: 7 }, trace: [{ tool: 'extract_form_answer', status: 'completed' }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const client = createAiInquiryClient({ fetcher })

    // 以服務目錄的 service_id 開始，與網頁表單同一份題組定義
    const started = await client.start('service-aircon')
    const replied = await client.message(started.session_id, '兩台分離式冷氣', 'A001')

    expect(started.session_id).toBe('s1')
    expect(replied.progress.answered).toBe(1)
    expect(fetcher).toHaveBeenNthCalledWith(1, '/api/chat/start', expect.objectContaining({ method: 'POST', credentials: 'same-origin', body: JSON.stringify({ service_id: 'service-aircon' }) }))
    // 帶上帳號，否則送出的諮詢單不屬於任何人，住戶在「我的委託」看不到自己的單
    expect(fetcher).toHaveBeenNthCalledWith(2, '/api/chat/message', expect.objectContaining({ body: JSON.stringify({ session_id: 's1', message: '兩台分離式冷氣', account_id: 'A001' }) }))
  })

  it('throws a safe typed error instead of reporting AI success on HTTP failure', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ detail: '工作階段不存在' }), { status: 404, headers: { 'Content-Type': 'application/json' } }))
    const client = createAiInquiryClient({ fetcher })
    await expect(client.message('missing', '確認')).rejects.toMatchObject({ status: 404, message: '工作階段不存在' })
  })

  it('consumes NDJSON progress and text deltas even when chunks split between events', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('{"type":"status","label":"正在理解你的回答"}\n{"type":"del'))
        controller.enqueue(encoder.encode('ta","text":"請問緊急"}\n{"type":"delta","text":"程度？"}\n'))
        controller.enqueue(encoder.encode('{"type":"complete","data":{"reply":"請問緊急程度？","done":false,"progress":{"answered":1,"total":2},"trace":[]}}\n'))
        controller.close()
      },
    })
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(body, {
      status: 200, headers: { 'Content-Type': 'application/x-ndjson' },
    }))
    const statuses: string[] = []
    const deltas: string[] = []

    const result = await createAiInquiryClient({ fetcher }).messageStream('s1', '燈壞了', 'A001', {
      onStatus: (label) => statuses.push(label),
      onDelta: (text) => deltas.push(text),
    })

    expect(statuses).toEqual(['正在理解你的回答'])
    expect(deltas.join('')).toBe('請問緊急程度？')
    expect(result.progress.answered).toBe(1)
    expect(fetcher).toHaveBeenCalledWith('/api/chat/message/stream', expect.objectContaining({
      method: 'POST', headers: expect.objectContaining({ Accept: 'application/x-ndjson' }),
    }))
  })

  it('reloads persisted inquiries from the backend repository', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ data: [{ id: 'INQ-20260725-001', form_id: 901, status: 'pending_quote', created_at: '2026-07-25T00:00:00Z', events: [] }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const inquiries = await createAiInquiryClient({ fetcher }).listInquiries()
    expect(inquiries[0]?.id).toBe('INQ-20260725-001')
    expect(fetcher).toHaveBeenCalledWith('/api/v1/inquiries', expect.objectContaining({ credentials: 'same-origin' }))
  })
})
