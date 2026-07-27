/**
 * 諮詢單生命週期：住戶送出 → 廠商報價 → 住戶確認 → 廠商完工。
 *
 * 三個角色看到的是同一批真實資料，不是各自的展示樣本。
 */

export interface InquirySummaryLine {
  label: string
  value: string
}

export interface InquiryQuoteItem {
  name: string
  amount: number
}

export interface InquiryQuote {
  items: InquiryQuoteItem[]
  amount: number
  vendorName: string
  quotedAt: string | null
}

export type InquiryStatus = 'pending_quote' | 'quoted' | 'confirmed' | 'completed' | 'cancelled'

export interface Inquiry {
  id: string
  form_id: number
  service_id: string | null
  status: InquiryStatus
  status_label: string
  official_status: string | null
  summary: InquirySummaryLine[]
  quote: InquiryQuote | null
  created_at: string
  events: Array<{ type: string; occurred_at: string; detail?: string | null }>
}

export interface VendorWorkload {
  pendingQuote: Inquiry[]
  awaitingResident: Inquiry[]
  scheduled: Inquiry[]
}

export interface PlatformOrder {
  id: string
  accountId: string
  serviceId: string
  status: string
  statusLabel: string
  amount: number
  pricingSource: string
  createdAt: string
  events: Array<{ type: string; occurred_at: string; detail?: string | null }>
}

export class InquiryApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
    this.name = 'InquiryApiError'
  }
}

interface ClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

export function createInquiryLifecycleClient(options: ClientOptions = {}) {
  const baseUrl = options.baseUrl ?? '/api/v1'

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const fetcher = options.fetcher ?? globalThis.fetch
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init.headers },
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new InquiryApiError(response.status, payload.detail ?? '操作未完成，請稍後再試。')
    }
    return ((await response.json()) as { data: T }).data
  }

  return {
    listMine: () => request<Inquiry[]>('/inquiries'),
    listOrders: (accountId: string) => request<PlatformOrder[]>(`/orders?account_id=${encodeURIComponent(accountId)}`),
    vendorWorkload: () => request<VendorWorkload>('/vendor/workload'),
    quote: (inquiryId: string, items: InquiryQuoteItem[], vendorName: string) =>
      request<Inquiry>(`/inquiries/${inquiryId}/quote`, {
        method: 'POST',
        body: JSON.stringify({ items, vendor_name: vendorName }),
      }),
    confirm: (inquiryId: string) =>
      request<Inquiry>(`/inquiries/${inquiryId}/confirm`, { method: 'POST' }),
    /** 議價或想換一家出價——案件退回待報價，附上住戶的說明。 */
    requestRevision: (inquiryId: string, note: string) =>
      request<Inquiry>(`/inquiries/${inquiryId}/revise`, { method: 'POST', body: JSON.stringify({ note }) }),
    cancel: (inquiryId: string, reason?: string) =>
      request<Inquiry>(`/inquiries/${inquiryId}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason: reason ?? null }),
      }),
    complete: (inquiryId: string, note?: string) =>
      request<Inquiry>(`/inquiries/${inquiryId}/complete`, {
        method: 'POST',
        body: JSON.stringify({ note: note ?? null }),
      }),
  }
}
