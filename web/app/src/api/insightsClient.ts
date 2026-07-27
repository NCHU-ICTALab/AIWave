/**
 * 個人洞察 API：行為軌跡、消費摘要、可解釋推薦。
 *
 * 這些數字全部由後端依官方 `mms_order_record` 算出，前端不自帶任何統計。
 */

export interface ServiceUsage {
  serviceId: string | null
  serviceName: string
  count: number
  lastUsedOn: string | null
  daysSinceLast: number | null
  totalAmount: number
}

export interface BehaviorSummary {
  accountId: string
  totalOrders: number
  completedOrders: number
  openOrders: number
  cancelledOrders: number
  distinctServices: number
  totalSpend: number
  earnedPoints: number
  firstActivity: string | null
  lastActivity: string | null
  services: ServiceUsage[]
  /** 資料來源標記，供介面標示「來自官方訂單」。 */
  source: string
}

export interface RecommendationEvidence {
  recordId: number
  orderNo: string
  serviceName: string
  occurredOn: string | null
  detail: string
}

export interface Recommendation {
  id: string
  kind: 'resume_open' | 'revisit' | 'frequent' | 'vendor_cross_sell'
  title: string
  serviceId: string | null
  serviceName: string
  reasonCodes: string[]
  reasonText: string
  evidence: RecommendationEvidence[]
  score: number
  /** 'rules' 表示由確定性規則算出，非 LLM 生成。 */
  computedBy: string
}

export interface TrailEvent {
  occurredOn: string | null
  serviceName: string
  serviceId: string | null
  orderNo: string
  recordId: number
  status: string
  amount: number
  itemName: string
  outcome: 'completed' | 'open' | 'cancelled'
}

/** 口語需求判讀結果；`null` 表示判讀不出，介面應退回服務目錄。 */
export interface IntentMatch {
  serviceId: string
  serviceName: string
  confidence: 'high' | 'low'
  reason: string
}

/**
 * 判讀結果必須區分三種情況——把「連線失敗」講成「我聽不懂」是在說謊，
 * 使用者會以為是自己表達有問題。
 */
export type IntentOutcome =
  | { status: 'matched'; match: IntentMatch }
  | { status: 'unmatched' }
  | { status: 'error'; message: string }

export async function matchIntent(
  need: string,
  fetcher: typeof fetch = globalThis.fetch,
): Promise<IntentOutcome> {
  try {
    const response = await fetcher('/api/v1/intent/match', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ need }),
    })
    if (!response.ok) {
      return { status: 'error', message: `服務回應異常（${response.status}）` }
    }
    const match = ((await response.json()) as { data: IntentMatch | null }).data
    return match ? { status: 'matched', match } : { status: 'unmatched' }
  } catch {
    return { status: 'error', message: '無法連線到服務，請確認後端已啟動。' }
  }
}

export class InsightsApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
    this.name = 'InsightsApiError'
  }
}

interface InsightsClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

/**
 * 今日摘要的一則。
 *
 * `source` 與 `evidence` 一定有值——每一則都指得出對應的真實事物
 * （諮詢單編號、團購活動、官方訂單）。`computedBy: 'rules'` 表示非 LLM 生成。
 */
export interface BriefingItem {
  id: string
  kind: 'needs_your_decision' | 'closing_soon' | 'in_progress' | 'waiting_on_vendor' | 'suggestion'
  title: string
  detail: string
  actionLabel: string | null
  actionRoute: string | null
  source: string
  score: number
  evidence: Array<Record<string, unknown>>
  computedBy: string
}

export interface InsightsClient {
  summary(accountId?: string): Promise<BehaviorSummary>
  recommendations(accountId?: string, limit?: number): Promise<Recommendation[]>
  trail(accountId?: string): Promise<TrailEvent[]>
  today(accountId: string, limit?: number): Promise<BriefingItem[]>
}

export function createInsightsClient(options: InsightsClientOptions = {}): InsightsClient {
  const baseUrl = options.baseUrl ?? '/api/v1'

  async function request<T>(path: string): Promise<T> {
    const fetcher = options.fetcher ?? globalThis.fetch
    const response = await fetcher(`${baseUrl}${path}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) throw new InsightsApiError(response.status, `洞察資料請求失敗（${response.status}）`)
    const payload = (await response.json()) as { data: T }
    return payload.data
  }

  return {
    summary: (accountId = 'me') => request<BehaviorSummary>(`/insights/${accountId}/summary`),
    recommendations: (accountId = 'me', limit = 3) =>
      request<Recommendation[]>(`/insights/${accountId}/recommendations?limit=${limit}`),
    trail: (accountId = 'me') => request<TrailEvent[]>(`/insights/${accountId}/trail`),
    today: (accountId: string, limit = 5) => request<BriefingItem[]>(`/today/${accountId}?limit=${limit}`),
  }
}
