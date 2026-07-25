// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { EXISTING_USER, mountApp } from './fixtures/mountApp'

const MANAGER = { role: 'manager' as const, accountId: null, displayName: '社區管理者' }

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

const CAMPAIGN = {
  id: 1,
  title: '七月社區團購',
  itemName: '愛文芒果 5 斤',
  unitPrice: 350,
  unit: '份',
  minQuantity: 10,
  closeTime: null,
  pickup: '社區管理室',
  status: 'open' as const,
  statusLabel: '收單中',
  householdCount: 2,
  totalQuantity: 5,
  totalAmount: 1750,
  reachedMinimum: false,
  joins: [
    { account_id: 'a', display_name: 'A 戶', quantity: 2, joined_at: '2026-07-25T00:00:00Z' },
    { account_id: 'b', display_name: 'B 戶', quantity: 3, joined_at: '2026-07-25T00:00:00Z' },
  ],
}

/** 社區是住戶共享的範圍，不是一種身分——所以住戶端本身就看得到。 */
function stubCommunity(extra?: (url: string, init?: RequestInit) => Response | undefined) {
  return stubCatalogFetch((url, init) => {
    const custom = extra?.(url, init)
    if (custom) return custom
    if (url.includes('/community/campaigns') && !init?.method) return json({ data: [CAMPAIGN] })
    if (url.includes('/community/my-participation')) return json({ data: [] })
    return undefined
  })
}

describe('community group buy', () => {
  it('lets a resident see the community group buy from their own app', async () => {
    stubCommunity()
    const { wrapper } = await mountApp('/user/community')

    expect(wrapper.get('h1').text()).toBe('社區團購')
    expect(wrapper.text()).toContain('愛文芒果 5 斤')
    expect(wrapper.text()).toContain('2 戶')
    expect(wrapper.text()).toContain('還差 5 份')
  })

  it('has 社區 in the resident navigation, not as a separate login', async () => {
    stubCommunity()
    const { wrapper } = await mountApp('/user')
    expect(wrapper.find('a[href="/user/community"]').exists()).toBe(true)
  })

  it('sends the resident’s own account id when joining', async () => {
    const posted: Array<Record<string, unknown>> = []
    stubCommunity((url, init) => {
      if (url.includes('/join') && init?.method === 'POST') {
        posted.push(JSON.parse(String(init.body)))
        return json({ data: { ...CAMPAIGN, totalQuantity: 7, householdCount: 3 } })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/community')

    await wrapper.get('[data-quantity-for="1"]').setValue(2)
    await wrapper.get('[data-testid="join-1"]').trigger('click')
    await flushPromises()

    expect(posted[0]).toMatchObject({ account_id: EXISTING_USER.accountId, quantity: 2 })
  })

  it('tells a brand-new account why it cannot join yet', async () => {
    stubCommunity()
    const { wrapper } = await mountApp('/user/community', {
      identity: { role: 'user', accountId: null, displayName: '新使用者' },
    })

    await wrapper.get('[data-testid="join-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('新帳號')
  })

  it('shows the manager who joined and how much', async () => {
    stubCommunity()
    const { wrapper } = await mountApp('/community', { identity: MANAGER })

    expect(wrapper.get('h1').text()).toBe('團購管理')
    const joins = wrapper.get('[data-joins-for="1"]').text()
    expect(joins).toContain('A 戶')
    expect(joins).toContain('B 戶')
  })

  it('produces a purchase order for the vendor when the manager closes it', async () => {
    stubCommunity((url, init) => {
      if (url.includes('/close') && init?.method === 'POST') {
        return json({
          data: {
            campaign: { ...CAMPAIGN, status: 'closed', statusLabel: '已結單' },
            purchaseOrder: {
              campaignId: 1, itemName: '愛文芒果 5 斤', unitPrice: 350,
              totalQuantity: 5, totalAmount: 1750, householdCount: 2,
              households: [{ name: 'A 戶', quantity: 2 }, { name: 'B 戶', quantity: 3 }],
            },
          },
        })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/community', { identity: MANAGER })

    await wrapper.get('[data-testid="close-1"]').trigger('click')
    await flushPromises()

    const order = wrapper.get('[data-testid="purchase-order"]').text()
    expect(order).toContain('NT$ 1,750')
    expect(order).toContain('A 戶 × 2')
  })

  it('sends the campaign the manager typed', async () => {
    const posted: Array<Record<string, unknown>> = []
    stubCommunity((url, init) => {
      if (url.endsWith('/community/campaigns') && init?.method === 'POST') {
        posted.push(JSON.parse(String(init.body)))
        return json({ data: CAMPAIGN })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/community', { identity: MANAGER })

    await wrapper.get('[data-testid="campaign-title"]').setValue('八月團購')
    await wrapper.get('[data-testid="campaign-item"]').setValue('文旦 10 斤')
    await wrapper.get('[data-testid="campaign-price"]').setValue(400)
    await wrapper.get('[data-testid="create-campaign"]').trigger('click')
    await flushPromises()

    expect(posted[0]).toMatchObject({ title: '八月團購', item_name: '文旦 10 斤', unit_price: 400 })
  })
})
