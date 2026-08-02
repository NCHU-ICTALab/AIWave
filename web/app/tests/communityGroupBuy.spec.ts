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

const JOINT_CAMPAIGN = {
  id: 2, communityId: 'community-sunshine-demo', title: '九月冷氣聯合清洗需求調查',
  serviceId: 'service-aircon', status: 'collecting' as const, statusLabel: '需求募集',
  demand: { householdCount: 0, unitCount: 0, equipment: [], timePreferences: [], specialRequirements: [] },
  draft: { notification: '只在你明確同意後匿名彙整需求。' }, proposals: [],
  selectedProposalId: null, selectedProposal: null, events: [],
  dataNotice: '競賽建置資料', myParticipation: null,
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
  it('lets a resident create, join and manage real groups', async () => {
    const calls: Array<{ url: string; body?: Record<string, unknown> }> = []
    const group = {
      id: 'group-shared-1', name: '小圓的群組',
      inviteCode: 'HOME-7284', myRole: 'admin', myRoleLabel: '管理者',
      members: [{ accountId: EXISTING_USER.accountId, displayName: '測試使用者', role: 'admin', roleLabel: '管理者' }],
      createdAt: '2026-07-29T09:00:00+08:00',
    }
    stubCommunity((url, init) => {
      if (url.endsWith('/api/v1/groups') && !init?.method) return json({ data: [group] })
      if (url.endsWith('/api/v1/groups') && init?.method === 'POST') {
        calls.push({ url, body: JSON.parse(String(init.body)) })
        return json({ data: { ...group, id: 'group-new', name: '讀書會' } })
      }
      if (url.endsWith('/api/v1/groups/join') && init?.method === 'POST') {
        calls.push({ url, body: JSON.parse(String(init.body)) })
        return json({ data: group })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/community')

    expect(wrapper.get('[data-testid="my-groups"]').text()).toContain('小圓的群組')
    expect(wrapper.text()).toContain('HOME-7284')

    await wrapper.get('[data-testid="open-create-group"]').trigger('click')
    await wrapper.get('[data-testid="group-name"]').setValue('讀書會')
    await wrapper.get('[data-testid="create-group"]').element.closest('form')!.dispatchEvent(new Event('submit'))
    await flushPromises()

    await wrapper.get('[data-testid="open-join-group"]').trigger('click')
    await wrapper.get('[data-testid="invite-code"]').setValue('HOME-7284')
    await wrapper.get('[data-testid="join-group"]').element.closest('form')!.dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(calls.map((call) => call.body)).toEqual([
      expect.objectContaining({ name: '讀書會' }),
      expect.objectContaining({ invite_code: 'HOME-7284' }),
    ])
    expect(wrapper.find('[data-testid="group-type"]').exists()).toBe(false)
  })

  it('lets a resident see the community group buy from their own app', async () => {
    stubCommunity()
    const { wrapper } = await mountApp('/user/community')

    expect(wrapper.get('h1').text()).toBe('群組與社區')
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

  it('requires explicit consent before adding an anonymous shared-service demand', async () => {
    const posted: Array<Record<string, unknown>> = []
    stubCommunity((url, init) => {
      if (url.endsWith('/api/v1/groups/joint-services')) return json({ data: [JOINT_CAMPAIGN] })
      if (url.endsWith('/community/joint-services/2/join') && init?.method === 'POST') {
        posted.push(JSON.parse(String(init.body)))
        return json({ data: {
          ...JOINT_CAMPAIGN,
          myParticipation: {
            units: 1, equipment: '分離式冷氣', preferredSlot: '週六上午', specialRequirement: null,
            consentVersion: 'joint-demand-v1', consentedAt: '2026-07-28T09:00:00Z',
          },
        } })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/community')

    const submit = wrapper.get('[data-testid="join-joint-2"]')
    expect(submit.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('不會分享姓名、電話或門牌')
    await wrapper.get('[data-testid="joint-consent-2"]').setValue(true)
    await submit.trigger('click')
    await flushPromises()

    expect(posted).toHaveLength(1)
    expect(posted[0]).toMatchObject({ consent: true, units: 1, equipment: '分離式冷氣', preferred_slot: '週六上午' })
    expect(wrapper.text()).toContain('已於')
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

  // 商業規則:免費社區只開放團購。訂閱閘門把公告與群組收起來時,絕不能連跟團一起收掉,
  // 否則免費方案就沒有任何可用功能了。
  it('lets a free resident still see and use group buying behind the subscription gate', async () => {
    stubCommunity()
    const { wrapper } = await mountApp('/user/community', {
      identity: { role: 'user', accountId: null, displayName: '新使用者' },
    })

    expect(wrapper.find('[data-testid="community-subscription-gate"]').exists()).toBe(true)
    expect(wrapper.get('[data-campaign-id="1"]').text()).toContain('愛文芒果')
    expect(wrapper.find('[data-testid="join-1"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('我跟的團')
    // 其餘社區功能才是訂閱解鎖的部分。
    expect(wrapper.find('[data-testid="community-announcements"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="my-groups"]').exists()).toBe(false)
  })

  it('shows the manager who joined and how much', async () => {
    stubCommunity()
    const { wrapper } = await mountApp('/community', { identity: MANAGER })

    expect(wrapper.get('h1').text()).toBe('社區營運中心')
    const joins = wrapper.get('[data-joins-for="1"]').text()
    expect(joins).toContain('A 戶')
    expect(joins).toContain('B 戶')
  })

  it('keeps group-buy operations available when only the support queue fails', async () => {
    stubCommunity((url) => url.endsWith('/api/v1/support/queue')
      ? new Response(JSON.stringify({ detail: 'offline' }), { status: 503, headers: { 'Content-Type': 'application/json' } })
      : undefined)
    const { wrapper } = await mountApp('/community', { identity: MANAGER })
    await flushPromises()

    expect(wrapper.text()).toContain('愛文芒果 5 斤')
    expect(wrapper.get('[role="alert"]').text()).toContain('客服佇列暫時無法載入')
    expect(wrapper.get('[role="alert"]').text()).toContain('團購功能仍可使用')
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

  it('lets community support take ownership and resolve a resident issue with confirmation', async () => {
    const calls: string[] = []
    const openTicket = {
      id: 'SUP-20260728-001', accountId: 'A001', subjectType: 'inquiry', subjectId: 'INQ-001',
      category: 'delay', categoryLabel: '服務延遲／未到場', issueText: '師傅晚兩小時還沒來',
      status: 'open', statusLabel: '等待客服處理', priority: 'high', slaHours: 4,
      dueAt: '2026-07-28T13:00:00+00:00',
      events: [{ type: 'support.created', actor: '住戶', occurred_at: '2026-07-28T09:00:00+00:00' }],
    }
    const working = { ...openTicket, status: 'in_progress', statusLabel: '客服處理中' }
    stubCommunity((url, init) => {
      if (url.endsWith('/support/queue')) return json({ data: [openTicket] })
      if (url.endsWith('/support/tickets/SUP-20260728-001/start') && init?.method === 'POST') {
        calls.push('start')
        return json({ data: working })
      }
      if (url.endsWith('/support/tickets/SUP-20260728-001/resolve') && init?.method === 'POST') {
        calls.push(`resolve:${JSON.parse(String(init.body)).note}`)
        return json({ data: { ...working, status: 'resolved', statusLabel: '已處理完成' } })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/community', { identity: MANAGER })

    expect(wrapper.text()).toContain('服務延遲／未到場')
    expect(wrapper.text()).toContain('師傅晚兩小時還沒來')
    await wrapper.get('[data-testid="support-start-SUP-20260728-001"]').trigger('click')
    expect(calls).toEqual([])
    await wrapper.get('[data-testid="support-start-confirm-SUP-20260728-001"]').trigger('click')
    await flushPromises()
    expect(calls).toEqual(['start'])

    await wrapper.get('[data-testid="support-resolution-SUP-20260728-001"]').setValue('已重新安排 14:00 到場')
    await wrapper.get('[data-testid="support-resolve-SUP-20260728-001"]').trigger('click')
    expect(calls).toEqual(['start'])
    await wrapper.get('[data-testid="support-resolve-confirm-SUP-20260728-001"]').trigger('click')
    await flushPromises()

    expect(calls).toEqual(['start', 'resolve:已重新安排 14:00 到場'])
    expect(wrapper.text()).toContain('SUP-20260728-001 已結案')
    expect(wrapper.find('[data-testid="support-start-SUP-20260728-001"]').exists()).toBe(false)
  })
})
