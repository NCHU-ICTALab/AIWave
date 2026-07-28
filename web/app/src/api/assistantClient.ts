/**
 * 生活管家的規劃 API（ADR-0017：LLM 規劃、規則執行）。
 *
 * 與 `matchIntent` 的差別：意圖比對只回「這句話對應哪一項服務」，規劃器回的是
 * 「要完成這件事得做哪幾步、各自的結果是什麼」——一句話兩件事也接得住。
 *
 * 步驟的執行狀態由後端決定，前端**不自行判斷哪些可以執行**：
 * 寫入類步驟一律回 `needs_confirmation`，要使用者按下確認後才會真的動到資料。
 */

export interface PlanStep {
  tool: string
  arguments: Record<string, unknown>
  /** 給使用者看的理由，例如「媒合符合預算的水電廠商」。 */
  why: string
  writes: boolean
  status: 'ready' | 'needs_confirmation' | 'done' | 'failed'
  result: unknown
  error: string | null
}

export interface Plan {
  /** 系統複述的需求理解，用來讓使用者確認「有沒有聽懂」。 */
  understanding: string
  steps: PlanStep[]
  /** 計畫作廢的原因；有值時 `steps` 必為空。 */
  rejectedReason: string | null
  needsConfirmation: PlanStep[]
}

export interface PlanIdentity {
  accountId?: string | null
  role?: string
  displayName?: string
}

/** 三態結果——把「連線失敗」講成「我聽不懂」會讓使用者以為是自己的問題。 */
export type PlanOutcome =
  | { status: 'planned'; plan: Plan }
  | { status: 'error'; message: string }

interface AssistantClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

export interface AssistantClient {
  plan(message: string, identity?: PlanIdentity): Promise<PlanOutcome>
  execute(message: string, steps: PlanStep[], approved: number[], identity?: PlanIdentity): Promise<PlanOutcome>
  tools(role?: string): Promise<Array<{ name: string; description: string }>>
}

export function createAssistantClient(options: AssistantClientOptions = {}): AssistantClient {
  const baseUrl = options.baseUrl ?? '/api/v1/assistant'

  function identityHeaders(identity: PlanIdentity = {}) {
    return {
      'X-Account-Id': identity.accountId ?? '',
      'X-Role': identity.role ?? 'user',
    }
  }

  async function post(path: string, body: unknown, identity: PlanIdentity = {}): Promise<PlanOutcome> {
    const fetcher = options.fetcher ?? globalThis.fetch
    try {
      const response = await fetcher(`${baseUrl}${path}`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...identityHeaders(identity) },
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        return { status: 'error', message: `服務回應異常（${response.status}）` }
      }
      const payload = (await response.json()) as { data: Plan }
      return { status: 'planned', plan: payload.data }
    } catch {
      return { status: 'error', message: '無法連線到服務，請確認後端已啟動。' }
    }
  }

  return {
    plan: (message, identity) => post('/plan', { message }, identity),

    execute: (message, steps, approved, identity) =>
      post('/plan/execute', {
        message,
        // 只回傳執行需要的欄位；結果與狀態由後端重算，前端送什麼都不算數
        steps: steps.map((step) => ({ tool: step.tool, arguments: step.arguments, why: step.why })),
        approved,
      }, identity),

    async tools(role = 'user') {
      const fetcher = options.fetcher ?? globalThis.fetch
      const response = await fetcher(`${baseUrl}/tools`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json', ...identityHeaders({ role }) },
      })
      if (!response.ok) return []
      return ((await response.json()) as { data: Array<{ name: string; description: string }> }).data
    },
  }
}

// ---- 媒合（FR-S-04）-------------------------------------------------------

export interface VendorMatch {
  vendorId: string
  vendorName: string
  intro: string
  rating: number
  reviewCount: number
  supportsUrgent: boolean
  basePrice: number
  slots: string[]
  slotLabels: string[]
  score: number
  reasons: Array<{ code: string; label: string; points: number }>
  /** 不符合的條件——保留廠商但講清楚代價，使用者才有得選。 */
  concerns: string[]
  computedBy: string
  /** 'competition_seed'：報價與評分是競賽建置資料，不是品牌實價。 */
  dataSource: string
}

export interface MatchResult {
  serviceId: string
  region: { county_name: string; district_name: string } | null
  criteria: { budget: number | null; slot: string | null; urgent: boolean }
  vendors: VendorMatch[]
}

/** 把規劃器回傳的 `match_vendors` 結果轉成型別化物件；形狀不符時回 null。 */
export function asMatchResult(value: unknown): MatchResult | null {
  const candidate = value as MatchResult | null
  return candidate && Array.isArray(candidate.vendors) ? candidate : null
}
