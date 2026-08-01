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
