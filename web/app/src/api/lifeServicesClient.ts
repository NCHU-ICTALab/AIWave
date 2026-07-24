export type WorkspaceRole = 'resident' | 'community' | 'vendor' | 'platform'

export interface ServiceSummary {
  id: string
  name: string
  category: 'home' | 'daily'
  integrationDepth: 'standard' | 'deep'
}

export interface CreateOrderInput {
  serviceId: string
  offerId: string
  finalAmount: number
}

export interface OrderSummary {
  id: string
  serviceName: string
  status: 'pending' | 'confirmed' | 'in_progress' | 'completed'
}

interface ApiEnvelope<T> {
  data: T
}

interface LifeServicesClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
}

export class LifeServicesApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'LifeServicesApiError'
    this.status = status
  }
}

export function createLifeServicesClient({
  fetcher = fetch,
  baseUrl = '/api/v1',
}: LifeServicesClientOptions = {}) {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...init.headers,
      },
    })

    if (!response.ok) {
      throw new LifeServicesApiError(response.status, `Life services request failed (${response.status})`)
    }

    const payload = (await response.json()) as ApiEnvelope<T>
    return payload.data
  }

  return {
    listServices: () => request<ServiceSummary[]>('/services'),
    createOrder: (input: CreateOrderInput) =>
      request<OrderSummary>('/orders', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
  }
}
