export interface LifeTaskOption {
  value: string
  label: string
  description?: string
}
export interface LifeTaskRequirement {
  id: 'scheduledDate' | 'address' | 'scope'
  label: string
  required: boolean
  value: string | null
  options: LifeTaskOption[]
}

export interface LifeTaskVendor {
  vendorId: string
  vendorName: string
  intro: string
  rating: number
  reviewCount: number
  basePrice: number
  score: number
  reasons: Array<{ code: string; label: string; points: number }>
  concerns: string[]
  connectorMode: string
  degradedReason?: string | null
}

export interface VendorQuote {
  id: string
  vendorId: string
  total: number
  currency: string
  status: string
  validUntil: string
  items: Array<{ name: string; quantity: number; unitPrice: number; amount: number }>
}

export interface LifeTaskItem {
  id: string
  serviceId: string
  title: string
  needSummary: string
  vendorId: string | null
  vendorName: string | null
  basePrice: number | null
  slot: string | null
  candidates: LifeTaskVendor[]
  externalInquiryId: string | null
  externalOrderId: string | null
  status: string
  quotes?: VendorQuote[]
  vendorInquiry?: Record<string, unknown> | null
  vendorOrder?: Record<string, unknown> | null
  syncError?: string
}

export interface LifeTask {
  id: string
  accountId: string
  displayName: string
  utterance: string
  status: string
  statusLabel: string
  scheduledDate: string | null
  address: Record<string, string> | null
  scope: string | null
  version: number
  lastError: string | null
  items: LifeTaskItem[]
  requirements: LifeTaskRequirement[]
  missingFields: string[]
  readyForConfirmation: boolean
  points?: {
    balance: number
    baseAmount: number
    pointsApplied: number
    finalAmount: number
    rule: string
    dataSource: string
    computedBy: string
  } | null
  estimate?: {
    baseAmount: number
    pointsApplied: number
    finalAmount: number
    savedAmount: number
    source: string
  }
  dataUse: string[]
}

interface Identity {
  accountId: string
}

interface ClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

export interface LifeTaskClient {
  configure(task: LifeTask, values: {
    scheduledDate: string
    addressChoice: 'home' | 'custom'
    scope: 'personal' | 'family' | 'community'
    selectedVendors?: Record<string, string>
    customAddress?: Record<string, string>
  }, identity: Identity): Promise<LifeTask>
  confirm(task: LifeTask, identity: Identity): Promise<LifeTask>
  acceptQuotes(task: LifeTask, identity: Identity, selectedQuotes?: Record<string, string>): Promise<LifeTask>
  get(taskId: string, identity: Identity): Promise<LifeTask>
  list(identity: Identity): Promise<LifeTask[]>
}

export class LifeTaskApiError extends Error {}

export function createLifeTaskClient(options: ClientOptions = {}): LifeTaskClient {
  const baseUrl = options.baseUrl ?? '/api/v1/life-tasks'
  const fetcher = options.fetcher ?? globalThis.fetch

  async function request<T>(path: string, identity: Identity, init: RequestInit = {}): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-Account-Id': identity.accountId,
        'X-Role': 'user',
        ...(init.headers ?? {}),
      },
    })
    const payload = await response.json().catch(() => ({})) as { data?: T; detail?: unknown }
    if (!response.ok || payload.data === undefined) {
      const detail = typeof payload.detail === 'string'
        ? payload.detail
        : ((payload.detail as { message?: string } | undefined)?.message ?? `服務回應異常（${response.status}）`)
      throw new LifeTaskApiError(detail)
    }
    return payload.data
  }

  return {
    configure: (task, values, identity) => request<LifeTask>(`/${encodeURIComponent(task.id)}/configuration`, identity, {
      method: 'PUT',
      body: JSON.stringify({
        expected_version: task.version,
        scheduled_date: values.scheduledDate,
        address_choice: values.addressChoice,
        scope: values.scope,
        selected_vendors: values.selectedVendors ?? {},
        custom_address: values.customAddress ?? null,
      }),
    }),
    confirm: (task, identity) => request<LifeTask>(`/${encodeURIComponent(task.id)}/confirm`, identity, {
      method: 'POST', body: JSON.stringify({ expected_version: task.version }),
    }),
    acceptQuotes: (task, identity, selectedQuotes = {}) => request<LifeTask>(
      `/${encodeURIComponent(task.id)}/accept-quotes`, identity,
      { method: 'POST', body: JSON.stringify({ expected_version: task.version, selected_quotes: selectedQuotes }) },
    ),
    get: (taskId, identity) => request<LifeTask>(`/${encodeURIComponent(taskId)}`, identity),
    list: (identity) => request<LifeTask[]>('', identity),
  }
}
