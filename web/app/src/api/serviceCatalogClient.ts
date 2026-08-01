import type { ServiceFormDefinition, ServiceAnswers, ServiceQuote } from '@/domain/serviceIntake'
import { currentAuthorizationHeaders } from '@/stores/session'

/** 服務目錄項目；由後端 `/api/v1/services` 提供，前端不再自帶定義。 */
export interface CatalogService {
  id: string
  name: string
  category: string
  summary: string
  partner: string
  glyph: string
  keywords: string[]
}

export class ServiceCatalogApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
    this.name = 'ServiceCatalogApiError'
  }
}

interface ServiceCatalogClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

export interface ServiceCatalogClient {
  listServices(): Promise<CatalogService[]>
  getServiceForm(serviceId: string): Promise<ServiceFormDefinition>
  quote(serviceId: string, answers: ServiceAnswers): Promise<ServiceQuote>
  submit(serviceId: string, answers: ServiceAnswers): Promise<ServiceSubmission>
}

export interface ServiceSubmission {
  kind: 'order' | 'service_request'
  resource: { id: string; idempotentReplay?: boolean; [key: string]: unknown }
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`
  if (value && typeof value === 'object') {
    return `{${Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableStringify(item)}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function payloadHash(value: unknown): string {
  let hash = 2166136261
  for (const character of stableStringify(value)) {
    hash ^= character.charCodeAt(0)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

export function createServiceCatalogClient(options: ServiceCatalogClientOptions = {}): ServiceCatalogClient {
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
    if (!response.ok) throw new ServiceCatalogApiError(response.status, `服務目錄請求失敗（${response.status}）`)
    const payload = (await response.json()) as { data: T }
    return payload.data
  }

  return {
    listServices: () => request<CatalogService[]>('/services'),
    getServiceForm: (serviceId) => request<ServiceFormDefinition>(`/services/${serviceId}/form`),
    quote: (serviceId, answers) =>
      request<ServiceQuote>(`/services/${serviceId}/quote`, { method: 'POST', body: JSON.stringify({ answers }) }),
    submit: (serviceId, answers) => request<ServiceSubmission>(`/services/${serviceId}/submissions`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `web:service:${serviceId}:${payloadHash(answers)}` },
      body: JSON.stringify({ answers }),
    }),
  }
}
