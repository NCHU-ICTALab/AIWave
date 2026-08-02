// 共用 HTTP 層:Platform API 的 Bearer、Idempotency-Key 與錯誤正規化。
// 既有 client 逐步遷移;新 M4 client 一律走這裡。
import { currentAuthorizationHeaders } from '../stores/session'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: unknown = null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/**
 * 區分「連不上後端」與「後端有回應但這次失敗」。
 *
 * 後者包含 401／403／500——那時候後端明明是活的。畫面若一律說
 * 「請確認後端服務是否啟動」,會把人導去重開一個已經在跑的 API,
 * 真正的原因(憑證過期、伺服器錯誤)反而被蓋掉。
 *
 * 各 client 的錯誤型別都帶 `status`;`request()` 把連線失敗正規化成 status 0,
 * 沒有 `status` 的錯誤一律保守地當成連不上。
 */
export function backendAnswered(reason: unknown): boolean {
  const status = (reason as { status?: unknown } | null | undefined)?.status
  return typeof status === 'number' && status > 0
}

interface RequestOptions {
  method?: string
  body?: unknown
  idempotencyKey?: string
  query?: Record<string, string | number | boolean | null | undefined>
}

function buildQuery(query: RequestOptions['query']): string {
  if (!query) return ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined && value !== '') params.set(key, String(value))
  }
  const raw = params.toString()
  return raw ? `?${raw}` : ''
}

/** 對相同 payload 產生穩定的 Idempotency-Key(payload-bound;重試不會建第二筆)。 */
export function stableIdempotencyKey(prefix: string, payload: unknown): string {
  const raw = JSON.stringify(payload ?? {})
  let hash = 0
  for (let index = 0; index < raw.length; index += 1) {
    hash = (hash * 31 + raw.charCodeAt(index)) | 0
  }
  return `${prefix}-${(hash >>> 0).toString(16)}`
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...currentAuthorizationHeaders(),
  }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey
  let response: Response
  try {
    response = await fetch(`${path}${buildQuery(options.query)}`, {
      method: options.method ?? (options.body !== undefined ? 'POST' : 'GET'),
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })
  } catch (error) {
    throw new ApiError('無法連線到平台服務,請稍後再試', 0, error)
  }
  let payload: any = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }
  if (!response.ok) {
    const detail = payload?.detail ?? payload?.error ?? payload
    const message =
      typeof detail === 'string'
        ? detail
        : (detail?.message ?? detail?.msg ?? `平台回應 ${response.status}`)
    throw new ApiError(String(message), response.status, detail)
  }
  return (payload?.data ?? payload) as T
}
