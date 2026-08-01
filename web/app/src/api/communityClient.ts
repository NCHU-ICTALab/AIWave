/**
 * 社區團購：住戶與管委會呼叫同一組資料，只是可做的動作不同（ADR-0003）。
 */

export interface CampaignJoin {
  account_id: string
  display_name: string
  quantity: number
  joined_at: string
}

export interface Campaign {
  id: number
  title: string
  itemName: string
  unitPrice: number
  unit: string
  minQuantity: number
  closeTime: string | null
  pickup: string | null
  status: 'open' | 'closed' | 'fulfilled'
  statusLabel: string
  householdCount: number
  totalQuantity: number
  totalAmount: number
  reachedMinimum: boolean
  joins: CampaignJoin[]
  /** 只有「我跟過的團」清單會帶。 */
  myQuantity?: number
}

export interface PurchaseOrder {
  campaignId: number
  itemName: string
  unitPrice: number
  totalQuantity: number
  totalAmount: number
  householdCount: number
  households: Array<{ name: string; quantity: number }>
}

export class CommunityApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
    this.name = 'CommunityApiError'
  }
}

interface ClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

export function createCommunityClient(options: ClientOptions = {}) {
  const baseUrl = options.baseUrl ?? '/api/v1'

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const fetcher = options.fetcher ?? globalThis.fetch
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json', 'Content-Type': 'application/json',
        ...currentAuthorizationHeaders(), ...init.headers,
      },
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new CommunityApiError(response.status, payload.detail ?? '操作未完成，請稍後再試。')
    }
    return ((await response.json()) as { data: T }).data
  }

  return {
    listOpen: () => request<Campaign[]>('/community/campaigns?only_open=true'),
    listAll: () => request<Campaign[]>('/community/campaigns'),
    myParticipation: (accountId: string) =>
      request<Campaign[]>(`/community/my-participation?account_id=${encodeURIComponent(accountId)}`),
    join: (campaignId: number, accountId: string, displayName: string, quantity: number) =>
      request<Campaign>(`/community/campaigns/${campaignId}/join`, {
        method: 'POST',
        body: JSON.stringify({ account_id: accountId, display_name: displayName, quantity }),
      }),
    create: (payload: {
      title: string; item_name: string; unit_price: number; min_quantity: number; pickup?: string
    }) => request<Campaign>('/community/campaigns', { method: 'POST', body: JSON.stringify(payload) }),
    close: (campaignId: number) =>
      request<{ campaign: Campaign; purchaseOrder: PurchaseOrder }>(
        `/community/campaigns/${campaignId}/close`, { method: 'POST' },
      ),
  }
}
import { currentAuthorizationHeaders } from '@/stores/session'
