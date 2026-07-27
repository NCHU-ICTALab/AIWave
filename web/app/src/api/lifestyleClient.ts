/** 個人化補貨與超商候補 API；所有寫入都由明確按鈕觸發。 */

interface LifestyleClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

export function createLifestyleClient(options: LifestyleClientOptions = {}) {
  const fetcher = options.fetcher ?? globalThis.fetch
  const baseUrl = options.baseUrl ?? '/api/v1'

  async function post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!response.ok) throw new Error(`操作失敗（${response.status}）`)
    return ((await response.json()) as { data: T }).data
  }

  return {
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
