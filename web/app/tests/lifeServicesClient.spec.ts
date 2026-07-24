import { describe, expect, it, vi } from 'vitest'

import { createLifeServicesClient } from '@/api/lifeServicesClient'

describe('life-services API client', () => {
  it('lists operable services through the unified v1 contract', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: [{ id: 'service-aircon', name: '冷氣清洗', category: 'home', integrationDepth: 'deep' }],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    const client = createLifeServicesClient({ fetcher })

    const services = await client.listServices()

    expect(services).toEqual([
      { id: 'service-aircon', name: '冷氣清洗', category: 'home', integrationDepth: 'deep' },
    ])
    expect(fetcher).toHaveBeenCalledWith(
      '/api/v1/services',
      expect.objectContaining({
        credentials: 'same-origin',
        headers: expect.not.objectContaining({ 'X-Api-Key': expect.anything(), 'X-Role': expect.anything() }),
      }),
    )
  })

  it('creates an order only through the unified order endpoint', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({ data: { id: 'OP-0724-001', serviceName: '商城購物', status: 'confirmed' } }),
        { status: 201, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    const client = createLifeServicesClient({ fetcher })

    const order = await client.createOrder({
      serviceId: 'service-shopping',
      offerId: 'offer-seven-eleven-restock',
      finalAmount: 124,
    })

    expect(order).toEqual({ id: 'OP-0724-001', serviceName: '商城購物', status: 'confirmed' })
    expect(fetcher).toHaveBeenCalledWith(
      '/api/v1/orders',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          serviceId: 'service-shopping',
          offerId: 'offer-seven-eleven-restock',
          finalAmount: 124,
        }),
      }),
    )
  })
})
