// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createServiceCatalogClient } from '@/api/serviceCatalogClient'

describe('service catalog client submission', () => {
  beforeEach(() => {
    globalThis.localStorage?.setItem('life-ai.identity', JSON.stringify({
      role: 'user', accountId: 'demo-new-member', displayName: '新使用者', accessToken: 'aiwave-new',
    }))
  })

  it('uses Bearer auth and a stable payload-bound idempotency key', async () => {
    const calls: RequestInit[] = []
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls.push(init ?? {})
      return new Response(JSON.stringify({ data: {
        kind: 'order', resource: { id: 'ORD-1' },
      } }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    const client = createServiceCatalogClient({ fetcher, baseUrl: 'https://example.test/api/v1' })
    const answers = { bundle: 'restock', delivery: 'store' }

    await client.submit('service-shopping', answers)
    await client.submit('service-shopping', { delivery: 'store', bundle: 'restock' })

    const first = new Headers(calls[0]?.headers)
    const second = new Headers(calls[1]?.headers)
    expect(first.get('Authorization')).toBe('Bearer aiwave-new')
    expect(first.get('X-Account-Id')).toBeNull()
    expect(first.get('Idempotency-Key')).toBe(second.get('Idempotency-Key'))
    expect(first.get('Idempotency-Key')).toMatch(/^web:service:service-shopping:/)
  })
})
