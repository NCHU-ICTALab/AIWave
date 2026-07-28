// @vitest-environment happy-dom

/**
 * 生活管家的規劃模式（ADR-0017：LLM 規劃、規則執行）。
 *
 * 這裡守住三件事：
 * 1. **一句話多件事都要接住**——這是規劃器取代單一意圖比對的理由。
 * 2. **寫入動作要先問**——沒按確認就不能送出任何會改資料的請求（ADR-0008）。
 * 3. **失敗要說實話**——連線失敗不能講成「我聽不懂」，那會讓使用者以為是自己的問題。
 */

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function plan(body: Partial<{ understanding: string; steps: unknown[]; rejectedReason: string | null }>) {
  return {
    understanding: '',
    steps: [],
    rejectedReason: null,
    needsConfirmation: [],
    ...body,
  }
}

const MATCH_RESULT = {
  serviceId: 'service-repair',
  region: { county_name: '台北市', district_name: '大同區' },
  criteria: { budget: 2000, slot: null, urgent: true },
  vendors: [
    {
      vendorId: 'vendor-fastfix',
      vendorName: '速修水電',
      intro: '24 小時叫修。',
      rating: 4.4,
      reviewCount: 903,
      supportsUrgent: true,
      basePrice: 1200,
      slots: ['weekend'],
      slotLabels: ['假日'],
      score: 78,
      reasons: [{ code: 'urgent', label: '可加急，當日／隔日到場', points: 25 }],
      concerns: [],
      computedBy: 'rules',
      dataSource: 'competition_seed',
    },
    {
      vendorId: 'vendor-guanjia',
      vendorName: '冠家水電工程行',
      intro: '重視施工品質。',
      rating: 4.7,
      reviewCount: 248,
      supportsUrgent: false,
      basePrice: 950,
      slots: ['weekday_morning'],
      slotLabels: ['平日上午'],
      score: 40,
      reasons: [{ code: 'budget', label: '參考價 NT$950 在預算內', points: 25 }],
      concerns: ['不提供加急，需照常排程'],
      computedBy: 'rules',
      dataSource: 'competition_seed',
    },
  ],
}

/** 攔截規劃 API，並記錄送出的請求，用來驗證「沒確認就不該送」。 */
function stubPlanner(
  response: unknown,
  executeResponse?: unknown,
  extra?: (url: string, init?: RequestInit) => Response | undefined,
) {
  const posted: Array<{ url: string; body: unknown }> = []
  stubCatalogFetch((url, init) => {
    if (url.includes('/api/v1/assistant/plan/execute')) {
      posted.push({ url, body: JSON.parse(String(init?.body)) })
      return json({ data: executeResponse ?? response })
    }
    if (url.includes('/api/v1/assistant/plan')) {
      posted.push({ url, body: JSON.parse(String(init?.body)) })
      return json({ data: response })
    }
    return extra?.(url, init)
  })
  return posted
}

describe('assistant planning', () => {
  beforeEach(() => stubCatalogFetch())

  it('shows what it understood so the user can tell whether it listened', async () => {
    stubPlanner(plan({
      understanding: '申請冷氣清洗並查詢社區團購',
      steps: [{ tool: 'list_group_buys', arguments: {}, why: '查詢團購', writes: false, status: 'done', result: [], error: null }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('冷氣不冷，順便看團購'))

    expect(wrapper.get('h1').text()).toBe('申請冷氣清洗並查詢社區團購')
    expect(wrapper.text()).toContain('冷氣不冷，順便看團購')
  })

  it('handles two intents in one sentence rather than dropping the second', async () => {
    stubPlanner(plan({
      understanding: '冷氣清洗與團購',
      steps: [
        { tool: 'get_service_form', arguments: { service_id: 'service-aircon' }, why: '準備題目', writes: false, status: 'done', result: {}, error: null },
        { tool: 'list_group_buys', arguments: {}, why: '查詢團購', writes: false, status: 'done', result: [{ id: 1, title: '中秋文旦', itemName: '文旦', unitPrice: 300, unit: '份', householdCount: 2, statusLabel: '收單中' }], error: null },
      ],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('冷氣不冷，順便看團購'))

    expect(wrapper.findAll('[data-testid="plan-step"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('中秋文旦')
  })

  it('names each step in plain language rather than showing tool identifiers', async () => {
    stubPlanner(plan({
      understanding: '找廠商',
      steps: [{ tool: 'match_vendors', arguments: { service_id: 'service-repair' }, why: '媒合', writes: false, status: 'done', result: MATCH_RESULT, error: null }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('水管漏水'))

    expect(wrapper.text()).toContain('媒合合適廠商')
    expect(wrapper.text()).not.toContain('match_vendors')
  })

  // ---- 媒合（FR-S-04）：列 2–3 家比較可改選 ----

  it('lists vendors to compare with the reasons behind the ranking', async () => {
    stubPlanner(plan({
      understanding: '找水電',
      steps: [{ tool: 'match_vendors', arguments: { service_id: 'service-repair' }, why: '媒合', writes: false, status: 'done', result: MATCH_RESULT, error: null }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('水管漏水很急'))

    expect(wrapper.findAll('[data-testid="vendor-card"]')).toHaveLength(2)
    expect(wrapper.get('[data-testid="vendor-recommended"]').text()).toBe('建議')
    expect(wrapper.get('[data-testid="vendor-reason"]').text()).toContain('可加急')
  })

  it('states each vendor’s drawbacks instead of hiding them', async () => {
    stubPlanner(plan({
      understanding: '找水電',
      steps: [{ tool: 'match_vendors', arguments: { service_id: 'service-repair' }, why: '媒合', writes: false, status: 'done', result: MATCH_RESULT, error: null }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('水管漏水很急'))

    expect(wrapper.get('[data-testid="vendor-concern"]').text()).toContain('不提供加急')
  })

  it('labels the seed pricing so nobody reads it as a real quote', async () => {
    stubPlanner(plan({
      understanding: '找水電',
      steps: [{ tool: 'match_vendors', arguments: { service_id: 'service-repair' }, why: '媒合', writes: false, status: 'done', result: MATCH_RESULT, error: null }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('水管漏水'))

    expect(wrapper.get('[data-testid="vendor-comparison"]').text()).toContain('競賽建置資料')
  })

  it('lets the user pick a vendor other than the recommended one', async () => {
    stubPlanner(plan({
      understanding: '找水電',
      steps: [{ tool: 'match_vendors', arguments: { service_id: 'service-repair' }, why: '媒合', writes: false, status: 'done', result: MATCH_RESULT, error: null }],
    }))
    const { wrapper, router } = await mountApp('/user/assistant?need=' + encodeURIComponent('水管漏水'))

    await wrapper.findAll('[data-testid="vendor-choose"]')[1]!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query.vendor).toBe('vendor-guanjia')
    expect(router.currentRoute.value.query.service).toBe('service-repair')
  })

  // ---- 寫入動作一律先問（ADR-0008） ----

  it('does not run a write step until the user confirms it', async () => {
    const posted = stubPlanner(plan({
      understanding: '跟團兩份',
      steps: [{ tool: 'join_group_buy', arguments: { campaign_id: 1, quantity: 2 }, why: '跟團', writes: true, status: 'needs_confirmation', result: null, error: null }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('幫我跟團兩份'))

    expect(wrapper.find('[data-testid="plan-approve"]').exists()).toBe(true)
    expect(posted.some((call) => call.url.includes('/execute'))).toBe(false)
  })

  it('executes only the approved step when confirmed', async () => {
    const posted = stubPlanner(
      plan({
        understanding: '跟團兩份',
        steps: [{ tool: 'join_group_buy', arguments: { campaign_id: 1, quantity: 2 }, why: '跟團', writes: true, status: 'needs_confirmation', result: null, error: null }],
      }),
      plan({
        understanding: '跟團兩份',
        steps: [{ tool: 'join_group_buy', arguments: { campaign_id: 1, quantity: 2 }, why: '跟團', writes: true, status: 'done', result: { totalQuantity: 2 }, error: null }],
      }),
    )
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('幫我跟團兩份'))

    await wrapper.get('[data-testid="plan-approve"]').trigger('click')
    await flushPromises()

    const execute = posted.find((call) => call.url.includes('/execute'))
    expect((execute!.body as { approved: number[] }).approved).toEqual([0])
    expect(wrapper.text()).toContain('已完成')
  })

  // ---- 接續填答 ----

  it('hands off to the guided form when the plan prepared one', async () => {
    stubPlanner(plan({
      understanding: '冷氣清洗',
      steps: [{ tool: 'get_service_form', arguments: { service_id: 'service-aircon' }, why: '準備題目', writes: false, status: 'done', result: {}, error: null }],
    }))
    const { wrapper, router } = await mountApp('/user/assistant?need=' + encodeURIComponent('冷氣不冷'))

    await wrapper.get('[data-testid="plan-open-form"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query.service).toBe('service-aircon')
  })

  it('turns a service catalog result into actions instead of a dead list', async () => {
    stubPlanner(plan({
      understanding: '找人打掃環境',
      steps: [{
        tool: 'list_services', arguments: {}, why: '確認打掃對應的服務', writes: false, status: 'done', error: null,
        result: [
          { id: 'service-cleaning', name: '專業清潔', summary: '居家空間重點清潔' },
          { id: 'service-housework', name: '計時家事', summary: '小時計時家事協助' },
        ],
      }],
    }))
    const { wrapper, router } = await mountApp('/user/assistant?need=' + encodeURIComponent('想找人來打掃'))

    const actions = wrapper.findAll('[data-testid="plan-service-action"]')
    expect(actions).toHaveLength(2)
    expect(actions[0]!.text()).toContain('專業清潔')

    await actions[0]!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.service).toBe('service-cleaning')
  })

  it('renders grounded service-search matches as choices instead of the whole catalog', async () => {
    stubPlanner(plan({
      understanding: '找打掃服務',
      steps: [{
        tool: 'search_services', arguments: { query: '想找人打掃' }, why: '搜尋相關服務', writes: false, status: 'done', error: null,
        result: { confidence: 'high', matches: [
          { id: 'service-cleaning', name: '專業清潔', summary: '居家空間重點清潔', matchedTerms: ['打掃'] },
          { id: 'service-housework', name: '計時家事', summary: '兩小時計時家事協助', matchedTerms: ['打掃'] },
        ] },
      }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('想找人打掃'))

    expect(wrapper.findAll('[data-testid="plan-service-action"]')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('寄件服務')
    expect(wrapper.text()).not.toContain('美食外送')
  })

  it('shows the restock evidence and deterministic savings with usable actions', async () => {
    stubPlanner(plan({
      understanding: '月初補貨',
      steps: [{ tool: 'get_restock_plan', arguments: {}, why: '計算優惠', writes: false, status: 'done', error: null, result: {
        recommendation: { id: 'restock-monthly', title: '月初日用品補貨', serviceId: 'service-shopping', reasonText: '近三個月都在月初購買。', suppressed: false },
        wallet: { openpointBalance: 180, dataSource: 'competition_seed_wallet' },
        bestOffer: { baseAmount: 699, finalAmount: 579, savedAmount: 120, applied: ['優惠券折抵 NT$70'], computedBy: 'deterministic_rules' },
        evidence: [{ orderNo: '2601', occurredOn: '2026-07-01' }], source: 'official_orders+competition_seed_wallet',
      } }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('月初幫我補貨'))

    expect(wrapper.get('[data-testid="restock-result"]').text()).toContain('省下 NT$ 120')
    expect(wrapper.find('[data-testid="restock-open-shopping"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="restock-dismiss"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="restock-reminder"]').exists()).toBe(true)
  })

  it('shows an in-stock alternative and an actionable waitlist for the nearby sold-out store', async () => {
    stubPlanner(plan({
      understanding: '找限定杯',
      steps: [{ tool: 'search_store_inventory', arguments: { query: '吉伊卡哇限定杯', district: '大同區', capability: '列印' }, why: '查庫存', writes: false, status: 'done', error: null, result: {
        product: { id: 'limited-cup', name: '吉伊卡哇限定杯' }, exactMatches: [],
        alternatives: [{ storeId: 'zhongxing', storeName: '7-ELEVEN 中興門市', district: '中山區', stock: 12, distanceMeters: 920, capabilities: ['列印'] }],
        unavailableNearby: [{ storeId: 'qingchuan', storeName: '7-ELEVEN 晴川門市', stock: 0 }],
        dataSource: 'competition_seed', asOf: '2026-07-25T09:00:00+08:00',
      } }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('哪裡有吉伊卡哇限定杯'))

    expect(wrapper.get('[data-testid="retail-result"]').text()).toContain('中興門市')
    expect(wrapper.get('[data-testid="retail-result"]').text()).toContain('庫存 12')
    expect(wrapper.get('[data-testid="stock-watch-action"]').text()).toContain('加入到貨候補')
    expect(wrapper.text()).toContain('競賽建置資料')
  })

  it('shows exact in-district stores when the requested product is in stock', async () => {
    stubPlanner(plan({
      understanding: '找衛生紙',
      steps: [{ tool: 'search_store_inventory', arguments: { query: '衛生紙', district: '中山區' }, why: '查庫存', writes: false, status: 'done', error: null, result: {
        product: { id: 'tissue-pack', name: '舒潔衛生紙' },
        exactMatches: [{ storeId: 'zhongxing', storeName: '7-ELEVEN 中興門市', district: '中山區', stock: 8, distanceMeters: 420, capabilities: ['取貨'] }],
        alternatives: [], unavailableNearby: [], dataSource: 'competition_seed', asOf: '2026-07-25T09:00:00+08:00',
      } }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('中山區哪裡有衛生紙'))

    expect(wrapper.get('[data-testid="retail-result"]').text()).toContain('中興門市')
    expect(wrapper.get('[data-testid="retail-result"]').text()).toContain('庫存 8')
  })

  it('tells the user when live upstream failed and offline data is being used', async () => {
    stubPlanner(plan({
      understanding: '用離線資料找限定杯',
      steps: [{ tool: 'search_store_inventory', arguments: { query: '吉伊卡哇限定杯' }, why: '查庫存', writes: false, status: 'done', error: null, result: {
        product: { id: 'limited-cup', name: '吉伊卡哇限定杯' }, exactMatches: [],
        alternatives: [{ storeId: 'zhongxing', storeName: '7-ELEVEN 中興門市', district: '中山區', stock: 12, distanceMeters: 920 }],
        unavailableNearby: [], dataSource: 'competition_seed_offline_fallback', connectorMode: 'offline_fallback',
        degradedReason: '品牌庫存服務維護中', asOf: '2026-07-25T09:00:00+08:00',
      } }],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('哪裡有吉伊卡哇限定杯'))

    const result = wrapper.get('[data-testid="retail-result"]')
    expect(result.get('[role="status"]').text()).toContain('即時庫存暫時無法連線')
    expect(result.get('[role="status"]').text()).toContain('品牌庫存服務維護中')
    expect(result.text()).toContain('離線備援資料')
  })

  it('turns an issue diagnosis into a confirmed, trackable support ticket', async () => {
    let created = 0
    stubPlanner(plan({
      understanding: '查明委託延遲並協助處理',
      steps: [{
        tool: 'diagnose_order_issue',
        arguments: { subject_id: 'INQ-20260728-001', issue_text: '約定時間已過但師傅還沒到' },
        why: '確認目前狀態與處理時限',
        writes: false,
        status: 'done',
        error: null,
        result: {
          subject: { type: 'inquiry', id: 'INQ-20260728-001', status: 'quoted', statusLabel: '待確認報價' },
          issueText: '約定時間已過但師傅還沒到',
          category: 'delay', categoryLabel: '到場或處理延遲', priority: 'high', slaHours: 4,
          dueAt: '2026-07-28T13:00:00+00:00', recommendedRoute: 'service_coordination',
          evidence: ['目前狀態：待確認報價', '最近事件：廠商已報價'], computedBy: 'deterministic_rules',
          diagnosisToken: 'diagnosis-123', previewExpiresInSeconds: 300,
        },
      }],
    }), undefined, (url, init) => {
      if (!url.includes('/api/v1/support/tickets')) return undefined
      created += 1
      expect(JSON.parse(String(init?.body))).toEqual({
        subject_id: 'INQ-20260728-001',
        issue_text: '約定時間已過但師傅還沒到',
        diagnosis_token: 'diagnosis-123',
      })
      expect(new Headers(init?.headers).get('X-Account-Id')).toBe('019a52d3-7f6b-7da3-b48d-9c9e2522d616')
      return json({ data: {
        id: 'SUP-20260728-001', accountId: '019a52d3-7f6b-7da3-b48d-9c9e2522d616', subjectType: 'inquiry',
        subjectId: 'INQ-20260728-001', category: 'delay', categoryLabel: '到場或處理延遲',
        issueText: '約定時間已過但師傅還沒到', status: 'open', statusLabel: '待處理',
        priority: 'high', slaHours: 4, dueAt: '2026-07-28T13:00:00+00:00', events: [],
      } })
    })
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('INQ-20260728-001 師傅還沒到'))

    const diagnosis = wrapper.get('[data-testid="support-diagnosis"]')
    expect(diagnosis.text()).toContain('到場或處理延遲')
    expect(diagnosis.text()).toContain('4 小時內開始處理')
    expect(diagnosis.text()).toContain('目前狀態：待確認報價')

    await wrapper.get('[data-testid="support-create-action"]').trigger('click')
    expect(created).toBe(0)
    expect(wrapper.get('[aria-label="確認建立客服工單"]').text()).toContain('INQ-20260728-001')

    await wrapper.get('[data-testid="support-create-confirm"]').trigger('click')
    await flushPromises()

    expect(created).toBe(1)
    expect(wrapper.get('[role="status"]').text()).toContain('SUP-20260728-001')
    expect(wrapper.find('[data-testid="support-create-action"]').exists()).toBe(false)
  })

  // ---- 誠實 ----

  it('explains that it cannot help and offers the catalog, without pretending', async () => {
    stubPlanner(plan({ understanding: '使用者要求退費', rejectedReason: '沒有可執行的步驟' }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('我要退費'))

    const rejected = wrapper.get('[data-testid="plan-rejected"]')
    expect(rejected.text()).toContain('這件事我還幫不上忙')
    expect(wrapper.find('a[href="/user/services"]').exists()).toBe(true)
  })

  it('says the connection failed rather than blaming how the user phrased it', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('浴室的燈不亮了'))

    const alert = wrapper.get('[role="alert"]')
    expect(alert.text()).toContain('無法連線')
    expect(wrapper.text()).not.toContain('我還無法對應')
    expect(wrapper.text()).not.toContain('幫不上忙')
  })

  it('reports a server error as a service problem, not a comprehension problem', async () => {
    stubCatalogFetch((url) => (url.includes('/api/v1/assistant/plan') ? json({}, 500) : undefined))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('浴室的燈不亮了'))

    expect(wrapper.get('[role="alert"]').text()).toContain('異常')
  })

  it('surfaces a failed step without discarding the ones that worked', async () => {
    stubPlanner(plan({
      understanding: '查團購與委託',
      steps: [
        { tool: 'list_group_buys', arguments: {}, why: '看團購', writes: false, status: 'done', result: [], error: null },
        { tool: 'get_inquiry', arguments: { inquiry_id: 'INQ-X' }, why: '查單', writes: false, status: 'failed', result: null, error: '查無諮詢單 INQ-X' },
      ],
    }))
    const { wrapper } = await mountApp('/user/assistant?need=' + encodeURIComponent('看看團購和我的單'))

    expect(wrapper.findAll('[data-testid="plan-step"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('查無諮詢單 INQ-X')
    expect(wrapper.text()).toContain('已完成')
  })
})
