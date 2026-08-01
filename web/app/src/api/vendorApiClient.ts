export interface VendorApiInquiry {
  id: string
  accountId: string
  serviceId: string
  vendorId: string | null
  consumer: { name: string; phone: string; email?: string }
  location: { countyName: string; districtName: string; address: string }
  preferredSlots: string[]
  budget: number | null
  urgency: string
  answers: Record<string, unknown>
  summary: string
  status: string
  version: number
  externalReference: string | null
  createdAt: string
}

export interface VendorApiOrder {
  id: string
  inquiryId: string
  quoteId: string
  vendorId: string
  accountId: string
  status: string
  version: number
  externalReference: string | null
  events: Array<{ id: string; type: string; status: string; note?: string; occurredAt: string }>
}

interface VendorApiClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
  accountId?: string | null
}

export interface VendorApiClient {
  listInquiries(vendorId: string): Promise<VendorApiInquiry[]>
  createQuote(inquiryId: string, vendorId: string, title: string, amount: number): Promise<Record<string, unknown>>
  listOrders(vendorId: string): Promise<VendorApiOrder[]>
  appendOrderEvent(orderId: string, status: 'in_service' | 'completed', note: string): Promise<VendorApiOrder>
}

export function createVendorApiClient(options: VendorApiClientOptions = {}): VendorApiClient {
  const fetcher = options.fetcher ?? globalThis.fetch
  const baseUrl = options.baseUrl ?? '/api/v1/vendor-api'
  const key = (resource: string, action: string) => `web:${resource}:${action}`

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json', 'Content-Type': 'application/json',
        ...currentAuthorizationHeaders(), ...(init.headers ?? {}),
      },
    })
    const payload = await response.json().catch(() => ({})) as { data?: T; detail?: string }
    if (!response.ok || payload.data === undefined) throw new Error(payload.detail ?? `廠商 API 回應異常（${response.status}）`)
    return payload.data
  }

  return {
    async listInquiries(vendorId) {
      const rows = await request<VendorApiInquiry[]>(`/inquiries?vendor_id=${encodeURIComponent(vendorId)}`)
      return rows.filter((item) => item.externalReference?.startsWith('TASK-'))
    },
    createQuote: (inquiryId, vendorId, title, amount) => request<Record<string, unknown>>(
      `/inquiries/${encodeURIComponent(inquiryId)}/quotes`, {
        method: 'POST', headers: { 'Idempotency-Key': key(inquiryId, `quote:${amount}`) },
        body: JSON.stringify({
          vendorId, validUntil: '2026-08-05',
          items: [{ name: title, quantity: 1, unitPrice: amount }],
        }),
      },
    ),
    async listOrders(vendorId) {
      const rows = await request<VendorApiOrder[]>(`/orders?vendor_id=${encodeURIComponent(vendorId)}`)
      return rows.filter((item) => item.externalReference?.startsWith('TASK-'))
    },
    appendOrderEvent: (orderId, status, note) => request<VendorApiOrder>(
      `/orders/${encodeURIComponent(orderId)}/events`, {
        method: 'POST', headers: { 'Idempotency-Key': key(orderId, status) },
        body: JSON.stringify({ type: status, status, note }),
      },
    ),
  }
}
import { currentAuthorizationHeaders } from '@/stores/session'
