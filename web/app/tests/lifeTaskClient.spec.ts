// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createLifeTaskClient, type LifeTask } from '@/api/lifeTaskClient'

const TASK = {
  id: 'TASK-20260725-001', version: 2, status: 'ready', statusLabel: '等待一次確認',
} as LifeTask

function response(data: unknown) {
  return new Response(JSON.stringify({ data }), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

describe('life task client', () => {
  beforeEach(() => {
    globalThis.localStorage?.setItem('life-ai.identity', JSON.stringify({
      role: 'user', accountId: '019a52d3-7f6b-7da3-b48d-9c9e2522d616',
      displayName: '小圓', accessToken: 'aiwave',
    }))
  })

  it('keeps authenticated identity in Bearer and version-binds the one-confirm request', async () => {
    const fetcher = vi.fn(async () => response({ ...TASK, status: 'submitted', version: 4 }))
    const client = createLifeTaskClient({ fetcher, baseUrl: 'https://example.test/api/v1/life-tasks' })

    await client.confirm(TASK, { accountId: 'member-001' })

    expect(fetcher).toHaveBeenCalledWith(
      'https://example.test/api/v1/life-tasks/TASK-20260725-001/confirm',
      expect.objectContaining({
        method: 'POST', credentials: 'same-origin',
        headers: expect.objectContaining({ Authorization: 'Bearer aiwave' }),
        body: JSON.stringify({ expected_version: 2 }),
      }),
    )
  })

  it('sends only explicit configuration and selected vendor choices', async () => {
    const calls: Array<[RequestInfo | URL, RequestInit | undefined]> = []
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push([input, init])
      return response(TASK)
    })
    const client = createLifeTaskClient({ fetcher, baseUrl: '/api/v1/life-tasks' })

    await client.configure(TASK, {
      scheduledDate: '2026-08-01', addressChoice: 'home', scope: 'family',
      selectedVendors: { 'TASK-20260725-001-ITEM-1': 'vendor-prince-electric' },
    }, { accountId: 'member-001' })

    const init = calls[0]![1]!
    expect(JSON.parse(String(init.body))).toEqual({
      expected_version: 2, scheduled_date: '2026-08-01', address_choice: 'home', scope: 'family',
      selected_vendors: { 'TASK-20260725-001-ITEM-1': 'vendor-prince-electric' }, custom_address: null,
    })
  })
})
