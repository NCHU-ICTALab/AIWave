/** 個人化補貨與超商候補 API；所有寫入都由明確按鈕觸發。 */

interface LifestyleClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

export interface RestockPlan {
  recommendation: {
    id: string
    title: string
    serviceId: string
    reasonText: string
    suppressed: boolean
  }
  wallet: {
    openpointBalance: number
    coupon: { id: string; label: string; amount: number } | null
    payment: string | null
    dataSource: string
  }
  bestOffer: {
    baseAmount: number
    finalAmount: number
    savedAmount: number
    applied: string[]
    computedBy: string
  }
  evidence: unknown[]
  source: string
}

export function createLifestyleClient(options: LifestyleClientOptions = {}) {
  const fetcher = options.fetcher ?? globalThis.fetch
  const baseUrl = options.baseUrl ?? '/api/v1'

  async function post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json', 'Content-Type': 'application/json',
        ...currentAuthorizationHeaders(),
      },
      body: JSON.stringify(body),
    })
    if (!response.ok) throw new Error(`操作失敗（${response.status}）`)
    return ((await response.json()) as { data: T }).data
  }

  async function get<T>(path: string): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', ...currentAuthorizationHeaders() },
    })
    if (!response.ok) throw new Error(`讀取失敗（${response.status}）`)
    return ((await response.json()) as { data: T }).data
  }

  return {
    restockPlan(accountId: string) {
      return get<RestockPlan>(`/personalization/${encodeURIComponent(accountId)}/restock-plan`)
    },
    feedback(accountId: string, recommendationId: string, action: 'dismiss' | 'undo') {
      return post<{ active: boolean }>(`/personalization/${accountId}/feedback`, {
        recommendation_id: recommendationId,
        action,
      })
    },
    createReminder(accountId: string) {
      return post<{ id: number; nextDueOn: string }>(`/personalization/${accountId}/reminders`, {
        item_name: '衛生紙',
        cadence_days: 30,
        next_due_on: '2026-08-24',
      })
    },
    joinStockWatch(accountId: string, productId: string, storeId: string) {
      return post<{ id: number; status: string }>('/retail/stock-watches', {
        account_id: accountId,
        product_id: productId,
        store_id: storeId,
      })
    },
  }
}
import { currentAuthorizationHeaders } from '@/stores/session'
