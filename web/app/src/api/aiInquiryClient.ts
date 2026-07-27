export interface AiTraceStep {
  stage: 'ai' | 'tool' | 'rule' | 'guard' | 'write'
  tool: string
  status: 'completed' | 'waiting' | 'needs_retry' | 'rejected'
  topic_id?: number
  result_id?: string
}

export interface AiOperation {
  type: 'inquiry.created'
  id: string
  status: 'pending_quote'
}

export interface AiQuestionOption {
  value: string
  label: string
  optionId?: number
}

/** 當前題目的可渲染形式——讓介面把選項畫成按鈕，使用者不必打字。 */
export interface AiQuestion {
  id: string
  topicId?: number
  label: string
  type: number
  required?: boolean
  hint?: string
  options?: AiQuestionOption[]
  min?: number
  max?: number
  minDate?: string
  maxDate?: string
}

export interface AiChatResponse {
  session_id?: string
  service_id?: string
  service_name?: string
  reply: string
  question?: AiQuestion | null
  done: boolean
  awaiting_confirmation?: boolean
  progress: { answered: number; total: number }
  trace: AiTraceStep[]
  extracted?: { topic_id: number; action: string; value: unknown; note: string }
  operation?: AiOperation
}

export interface PersistedInquiry {
  id: string
  form_id: number
  status: 'pending_quote'
  created_at: string
  events: Array<{ type: string; occurred_at: string }>
}

export class AiInquiryApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
    this.name = 'AiInquiryApiError'
  }
}

interface AiInquiryClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

interface AiStreamHandlers {
  onStatus?: (label: string) => void
  onDelta?: (text: string) => void
}

type AiStreamEvent =
  | { type: 'status'; label: string }
  | { type: 'delta'; text: string }
  | { type: 'complete'; data: AiChatResponse }

export function createAiInquiryClient(options: AiInquiryClientOptions = {}) {
  const baseUrl = options.baseUrl ?? '/api'

  async function post(path: string, body: object): Promise<AiChatResponse> {
    const fetcher = options.fetcher ?? globalThis.fetch
    const response = await fetcher(`${baseUrl}${path}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new AiInquiryApiError(response.status, payload.detail ?? 'AI 服務暫時無法使用')
    }
    return response.json() as Promise<AiChatResponse>
  }

  async function listInquiries(): Promise<PersistedInquiry[]> {
    const fetcher = options.fetcher ?? globalThis.fetch
    const response = await fetcher(`${baseUrl}/v1/inquiries`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!response.ok) throw new AiInquiryApiError(response.status, '無法同步後端諮詢紀錄')
    const payload = await response.json() as { data: PersistedInquiry[] }
    return payload.data
  }

  async function messageStream(
    sessionId: string,
    message: string,
    accountId: string | null | undefined,
    handlers: AiStreamHandlers = {},
  ): Promise<AiChatResponse> {
    const fetcher = options.fetcher ?? globalThis.fetch
    const response = await fetcher(`${baseUrl}/chat/message/stream`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/x-ndjson', 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message, account_id: accountId ?? null }),
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new AiInquiryApiError(response.status, payload.detail ?? 'AI 服務暫時無法使用')
    }
    if (!response.body) throw new AiInquiryApiError(502, 'AI 串流回應不完整')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let completed: AiChatResponse | null = null

    function consume(line: string) {
      if (!line.trim()) return
      const event = JSON.parse(line) as AiStreamEvent
      if (event.type === 'status') handlers.onStatus?.(event.label)
      else if (event.type === 'delta') handlers.onDelta?.(event.text)
      else if (event.type === 'complete') completed = event.data
    }

    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) consume(line)
      if (done) break
    }
    consume(buffer)
    if (!completed) throw new AiInquiryApiError(502, 'AI 串流在完成前中斷')
    return completed
  }

  return {
    /** 以服務目錄的 service_id 開始對話——與網頁表單同一份題組定義。 */
    start: async (serviceId: string) => {
      const response = await post('/chat/start', { service_id: serviceId })
      if (!response.session_id) throw new AiInquiryApiError(502, 'AI 工作階段回應不完整')
      return response as AiChatResponse & { session_id: string }
    },
    /**
     * `accountId` 是委託的歸屬。不帶的話送出的諮詢單不屬於任何人，
     * 住戶就在「我的委託」裡看不到自己剛送出的單。
     */
    message: (sessionId: string, message: string, accountId?: string | null) =>
      post('/chat/message', { session_id: sessionId, message, account_id: accountId ?? null }),
    messageStream,
    listInquiries,
  }
}
