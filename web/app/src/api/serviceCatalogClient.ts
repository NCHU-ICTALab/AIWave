import type { ServiceFormDefinition, ServiceAnswers, ServiceQuote } from '@/domain/serviceIntake'

/** 服務目錄項目；由後端 `/api/v1/services` 提供，前端不再自帶定義。 */
export interface CatalogService {
  id: string
  name: string
  category: string
  summary: string
  partner: string
  glyph: string
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
}

export function createServiceCatalogClient(options: ServiceCatalogClientOptions = {}): ServiceCatalogClient {
  const baseUrl = options.baseUrl ?? '/api/v1'

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const fetcher = options.fetcher ?? globalThis.fetch
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init.headers },
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
  }
}
