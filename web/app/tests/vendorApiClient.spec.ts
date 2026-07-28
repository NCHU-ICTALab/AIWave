import { describe, expect, it, vi } from 'vitest'

import { createVendorApiClient } from '@/api/vendorApiClient'

const json = (data: unknown) => new Response(JSON.stringify({ data, meta: { dataSource: 'fake_vendor' } }), {
  status: 200, headers: { 'Content-Type': 'application/json' },
})

describe('vendor api client', () => {
  it('only exposes cross-service tasks assigned to the selected vendor', async () => {
    const calls: Array<[RequestInfo | URL, RequestInit | undefined]> = []
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push([input, init])
      return json([
        { id: 'vinq-task', externalReference: 'TASK-1:ITEM-1' },
        { id: 'vinq-seed', externalReference: 'seed-legacy' },
      ])
    })
    const client = createVendorApiClient({ fetcher: fetcher as typeof fetch, accountId: 'vendor-prince-electric' })

    const rows = await client.listInquiries('vendor-prince-electric')

    expect(rows.map((row) => row.id)).toEqual(['vinq-task'])
    expect(String(calls[0]?.[0])).toContain('vendor_id=vendor-prince-electric')
    expect(new Headers(calls[0]?.[1]?.headers).get('X-Account-Id')).toBe('vendor-prince-electric')
  })

  it('uses a stable payload-bound idempotency key for quote retries', async () => {
    const keys: string[] = []
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      keys.push(new Headers(init?.headers).get('Idempotency-Key') ?? '')
      return json({ id: 'vqt-1' })
    })
    const client = createVendorApiClient({ fetcher: fetcher as typeof fetch })

    await client.createQuote('vinq-1', 'vendor-prince-electric', '浴室燈修繕', 1200)
    await client.createQuote('vinq-1', 'vendor-prince-electric', '浴室燈修繕', 1200)

    expect(keys[0]).toBe(keys[1])
    expect(keys[0]).toContain('quote:1200')
  })
})
