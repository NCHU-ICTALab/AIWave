import { describe, expect, it, vi } from 'vitest'

import { createLifestyleClient } from '@/api/lifestyleClient'

describe('lifestyle client', () => {
  it('reads a member restock and points plan through the public API contract', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({
      data: {
        recommendation: { id: 'restock-monthly', title: '月初日用品補貨', serviceId: 'service-shopping', reasonText: '依近期紀錄推測。', suppressed: false },
        wallet: { openpointBalance: 180, coupon: { id: 'coupon-70', label: '日用品滿額折 NT$70', amount: 70 }, payment: 'icash Pay', dataSource: 'competition_seed_wallet' },
        bestOffer: { baseAmount: 699, finalAmount: 579, savedAmount: 120, applied: ['優惠券 −NT$70', 'OPENPOINT 50 點'], computedBy: 'deterministic_rules' },
        evidence: [],
        source: 'official_orders+competition_seed_wallet',
      },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const client = createLifestyleClient({ fetcher, baseUrl: 'https://example.test/api/v1' })

    const plan = await client.restockPlan('member-001')

    expect(fetcher).toHaveBeenCalledWith(
      'https://example.test/api/v1/personalization/member-001/restock-plan',
      expect.objectContaining({ method: 'GET', credentials: 'same-origin' }),
    )
    expect(plan.wallet.openpointBalance).toBe(180)
    expect(plan.bestOffer.savedAmount).toBe(120)
  })
})
