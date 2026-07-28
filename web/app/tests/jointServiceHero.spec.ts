// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

const MANAGER = { role: 'manager' as const, accountId: null, displayName: '社區管理者' }
const PARTNER = { role: 'partner' as const, accountId: 'vendor-duskin', displayName: 'DUSKIN 樂清' }
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })

const PROPOSALS = [
  { id: 'proposal-care', vendorId: 'vendor-duskin', vendorName: 'DUSKIN 樂清', badge: '整體推薦',
    items: [{ name: '冷氣清洗 27 台', amount: 40500 }, { name: '公共區域防護與清潔', amount: 2400 }, { name: '社區分梯排程', amount: 1800 }],
    total: 44700, perUnit: 1656, availableSlots: ['8/8（六）09:00–17:00'], strengths: ['符合週末偏好'], concerns: ['高樓外機另估'], score: 92,
    source: 'competition_seed', sourceLabel: '競賽建置方案，非品牌即時報價' },
  { id: 'proposal-value', vendorId: 'vendor-prince-property', vendorName: '太子物業', badge: '價格較低',
    items: [{ name: '冷氣清洗 27 台', amount: 37800 }, { name: '耗材與室內防護', amount: 1800 }, { name: '社區統籌費', amount: 900 }],
    total: 40500, perUnit: 1500, availableSlots: ['8/12（三）09:00–17:00'], strengths: ['省 NT$4,200'], concerns: ['與週末偏好不符'], score: 78,
    source: 'competition_seed', sourceLabel: '競賽建置方案，非品牌即時報價' },
]

const CAMPAIGN = {
  id: 1, communityId: 'community-sunshine-demo', title: '八月冷氣聯合清洗', serviceId: 'service-aircon',
  status: 'proposal_review', statusLabel: '方案評選',
  demand: { householdCount: 18, unitCount: 27, privacy: '以匿名住戶雜湊去重', sourceLabel: '競賽建置需求資料',
    equipment: [{ label: '分離式冷氣', count: 23 }, { label: '窗型冷氣', count: 4 }],
    timePreferences: [{ label: '週六上午', households: 10 }], specialRequirements: ['3 戶需高樓外機評估'] },
  draft: { notification: '需求已完成匿名彙整', generatedBy: 'AI Copilot 草稿；管委會尚未確認指派', serviceContext: 'DUSKIN 公開服務情境' },
  proposals: PROPOSALS, selectedProposalId: null, selectedProposal: null,
  events: [{ type: 'joint_service.proposals_ready', actor: 'AI Copilot', detail: '完成兩案比較', occurredAt: '2026-07-28T09:00:00Z' }],
  dataNotice: '需求、時段、報價與評分為競賽建置資料，非品牌即時報價。',
}

function stubHero(extra?: (url: string, init?: RequestInit) => Response | undefined) {
  return stubCatalogFetch((url, init) => {
    const result = extra?.(url, init)
    if (result) return result
    if (url.endsWith('/community/joint-services')) return json({ data: [CAMPAIGN] })
    if (url.endsWith('/vendor/joint-services')) return json({ data: [] })
    if (url.includes('/community/campaigns')) return json({ data: [] })
    if (url.endsWith('/support/queue')) return json({ data: [] })
    if (url.endsWith('/vendor/workload')) return json({ data: { pendingQuote: [], awaitingResident: [], scheduled: [] } })
    return undefined
  })
}

describe('community and vendor joint-service hero', () => {
  it('shows demand evidence and two honest comparable proposals', async () => {
    stubHero()
    const { wrapper } = await mountApp('/community', { identity: MANAGER })
    await flushPromises()

    const hero = wrapper.get('[data-testid="joint-service-hero"]')
    expect(hero.text()).toContain('18 戶')
    expect(hero.text()).toContain('27 台')
    expect(hero.text()).toContain('DUSKIN 公開服務情境')
    expect(hero.text()).toContain('DUSKIN 樂清')
    expect(hero.text()).toContain('太子物業')
    expect(hero.text()).toContain('非品牌即時報價')
    expect(hero.text()).toContain('高樓外機另估')
  })

  it('requires a visible second confirmation before assigning', async () => {
    const calls: unknown[] = []
    stubHero((url, init) => {
      if (url.endsWith('/joint-services/1/assign') && init?.method === 'POST') {
        calls.push(JSON.parse(String(init.body)))
        return json({ data: { ...CAMPAIGN, status: 'assigned', statusLabel: '已指派', selectedProposalId: PROPOSALS[0].id, selectedProposal: PROPOSALS[0] } })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/community', { identity: MANAGER })
    await wrapper.get('[data-testid="choose-proposal-care"]').trigger('click')
    expect(calls).toHaveLength(0)
    expect(wrapper.get('[role="group"]').text()).toContain('NT$ 44,700')
    await wrapper.get('[data-testid="confirm-proposal-care"]').trigger('click')
    await flushPromises()
    expect(calls).toEqual([{ proposal_id: 'proposal-care' }])
    expect(wrapper.text()).toContain('已指派')
  })

  it('lets the partner progress the same assigned record with a required completion note', async () => {
    const assigned = { ...CAMPAIGN, status: 'assigned', statusLabel: '已指派', selectedProposalId: PROPOSALS[0].id, selectedProposal: PROPOSALS[0] }
    const calls: string[] = []
    stubHero((url, init) => {
      if (url.endsWith('/vendor/joint-services')) return json({ data: [assigned] })
      if (url.endsWith('/joint-services/1/start') && init?.method === 'POST') {
        calls.push('start'); return json({ data: { ...assigned, status: 'in_progress', statusLabel: '服務進行中' } })
      }
      if (url.endsWith('/joint-services/1/complete') && init?.method === 'POST') {
        calls.push(`complete:${JSON.parse(String(init.body)).note}`)
        return json({ data: { ...assigned, status: 'completed', statusLabel: '已完成' } })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/partner', { identity: PARTNER })
    await flushPromises()
    expect(wrapper.text()).toContain('18 戶／27 台')
    await wrapper.get('[data-testid="start-joint-1"]').trigger('click')
    await wrapper.get('[data-testid="confirm-start-joint-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="joint-note-1"]').setValue('27 台完成，已附檢查紀錄')
    await wrapper.get('[data-testid="complete-joint-1"]').trigger('click')
    await wrapper.get('[data-testid="confirm-complete-joint-1"]').trigger('click')
    await flushPromises()
    expect(calls).toEqual(['start', 'complete:27 台完成，已附檢查紀錄'])
    expect(wrapper.text()).toContain('已完成')
  })
})
