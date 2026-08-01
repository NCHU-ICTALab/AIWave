import { currentAuthorizationHeaders } from '@/stores/session'

export interface PointsEntry {
  id: string
  type: 'earn' | 'redeem' | 'refund' | 'reverse' | 'expire'
  amount: number
  description: string
  referenceType: string
  referenceId: string
  expiresAt: string | null
  reversesEntryId: string | null
  createdAt: string
}

export interface PointsWallet {
  label: string
  balance: number
  entries: PointsEntry[]
}

interface PointsClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

/** Read the Demo OPENPOINT balance from the M2 ledger—the only wallet source of truth. */
export function createPointsClient(options: PointsClientOptions = {}) {
  const fetcher = options.fetcher ?? globalThis.fetch
  const baseUrl = options.baseUrl ?? '/api/v1/platform'

  return {
    async wallet(): Promise<PointsWallet> {
      const response = await fetcher(`${baseUrl}/points`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json', ...currentAuthorizationHeaders() },
      })
      const payload = await response.json().catch(() => ({})) as { data?: PointsWallet; detail?: unknown }
      if (!response.ok || !payload.data) throw new Error(`點數帳本讀取失敗（${response.status}）`)
      return payload.data
    },
  }
}
