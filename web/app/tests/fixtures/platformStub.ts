/**
 * M4 Platform API 的測試替身(有狀態的 in-memory 假後端)。
 *
 * 真正的規則在 `api/platform_core.py` 與 `core/catalog/`,由後端測試
 * (tests/test_m4_scenarios.py)把關;這裡只鏡射前端頁面會用到的契約形狀,
 * 讓元件測試不必真的起後端。目錄內容對齊 `fake_upstreams/partner_seed.py`
 * (partner-demo-v5)的品牌與 offering id。
 */

const SCENE_PROVIDERS = [
  {
    id: 'vendor-prince-electric', name: '王子水電', scene: 'home',
    summary: '居家水電修繕與到府檢測。', rating: 4.8, reviewCount: 516, placeholder: false,
  },
  {
    id: 'vendor-duskin', name: 'DUSKIN 樂清', scene: 'home',
    summary: '居家與家電清潔、計時家事。', rating: 4.8, reviewCount: 1240, placeholder: false,
  },
  {
    id: 'vendor-21plus', name: '21PLUS', scene: 'food',
    summary: '休閒餐廳線上訂位。', rating: 4.5, reviewCount: 1860, placeholder: false,
  },
  {
    id: 'vendor-smile', name: '速邁樂加油站 Smile', scene: 'move',
    summary: '精緻洗車線上預約。', rating: 4.4, reviewCount: 980, placeholder: false,
  },
  {
    id: 'vendor-blackcat', name: '黑貓宅急便', scene: 'move',
    summary: '宅配到府收件。', rating: 4.7, reviewCount: 5210, placeholder: false,
  },
  {
    id: 'vendor-cosmed', name: '康是美', scene: 'med',
    summary: '處方箋辨識與門市領藥。', rating: 4.6, reviewCount: 4380, placeholder: false,
  },
  {
    id: 'vendor-711-shop', name: '7-ELEVEN 線上購物中心', scene: 'pre',
    summary: 'i 預購與門市取貨。', rating: 4.5, reviewCount: 6120, placeholder: false,
  },
  {
    id: 'vendor-uni-resort', name: '統一渡假村 Uni Resort', scene: 'fun',
    summary: '馬武督/谷關線上訂房。', rating: 4.6, reviewCount: 2140, placeholder: false,
  },
  {
    id: 'vendor-foodomo', name: 'foodomo', scene: 'food',
    summary: '餐飲與生活用品外送。', rating: 4.4, reviewCount: 4180, placeholder: false,
  },
  {
    id: 'vendor-711-c2c', name: '7-ELEVEN 交貨便', scene: 'move',
    summary: '店到店寄件。', rating: 4.5, reviewCount: 3140, placeholder: false,
  },
  {
    id: 'vendor-iopenmall', name: 'iOPEN Mall', scene: 'pre',
    summary: '網路開店平台商城。', rating: 4.5, reviewCount: 3560, placeholder: false,
  },
  {
    id: 'vendor-ibon-ticket', name: 'ibon 售票', scene: 'fun',
    summary: '非劃位票券購買。', rating: 4.4, reviewCount: 5120, placeholder: false,
  },
] as const

/** tier-2 陳列替身:鏡射 core/catalog/listing.py 的形狀,只取前端測試需要的樣本。 */
const LISTINGS = [
  { id: 'listing-starbucks', name: '星巴克', scene: 'food', company: '悠旅生活事業', url: '', note: '', tags: [] as string[] },
  { id: 'listing-mister-donut', name: 'Mister Donut', scene: 'food', company: '統一多拿滋', url: '', note: '', tags: [] as string[] },
  { id: 'listing-ibon-taxi', name: 'ibon 叫車(合作車隊)', scene: 'move', company: '統一超商', url: '', note: '官方流程為 ibon 機台操作,未提供線上叫車', tags: ['叫車'] },
  { id: 'listing-books', name: '博客來', scene: 'pre', company: '博客來數位科技', url: '', note: '', tags: [] as string[] },
  { id: 'listing-dream-mall', name: '統一夢時代購物中心', scene: 'fun', company: '統一夢時代', url: '', note: '', tags: [] as string[] },
  { id: 'listing-uni-pharma', name: '統一藥品(我的美麗日記)', scene: 'med', company: '統一藥品', url: '', note: '', tags: [] as string[] },
  { id: 'listing-muji', name: '台灣無印良品 MUJI', scene: 'home', company: '台灣無印良品', url: '', note: '', tags: [] as string[] },
].map((item) => ({ ...item, transactable: false as const, source: '廠商and表單.md(統一集團官方名單)' }))

const OFFERINGS: Record<string, {
  id: string; providerId: string; name: string; domainType: string;
  fulfillmentKind: string; basePrice: number; currency: string;
  pricingUnit: string; cancelPolicyHours: number; description: string;
}> = Object.fromEntries([
  { id: 'off-prince-electric-repair', providerId: 'vendor-prince-electric', name: '水電修繕・到府檢測', domainType: 'home_repair', fulfillmentKind: 'booking', basePrice: 1200, pricingUnit: '次', cancelPolicyHours: 24 },
  { id: 'off-duskin-cleaning', providerId: 'vendor-duskin', name: '全室清潔', domainType: 'home_cleaning', fulfillmentKind: 'booking', basePrice: 3200, pricingUnit: '次', cancelPolicyHours: 24 },
  { id: 'off-21plus-dinner', providerId: 'vendor-21plus', name: '21PLUS 晚餐訂位', domainType: 'dining_reservation', fulfillmentKind: 'booking', basePrice: 0, pricingUnit: '位', cancelPolicyHours: 2 },
  { id: 'off-smile-wash-sedan', providerId: 'vendor-smile', name: '精緻洗車(轎車)', domainType: 'car_wash', fulfillmentKind: 'booking', basePrice: 450, pricingUnit: '次', cancelPolicyHours: 2 },
  { id: 'off-blackcat-pickup', providerId: 'vendor-blackcat', name: '宅配到府收件(常溫)', domainType: 'shipping_pickup', fulfillmentKind: 'booking', basePrice: 130, pricingUnit: '件', cancelPolicyHours: 2 },
  { id: 'off-cosmed-rx-pickup', providerId: 'vendor-cosmed', name: '處方箋門市領藥預約', domainType: 'pharmacy_pickup', fulfillmentKind: 'booking', basePrice: 0, pricingUnit: '次', cancelPolicyHours: 2 },
  { id: 'off-711-shop-preorder-coffee', providerId: 'vendor-711-shop', name: 'i 預購・咖啡寄杯 10 杯組', domainType: 'ec_preorder', fulfillmentKind: 'commerce', basePrice: 450, pricingUnit: '組', cancelPolicyHours: 0 },
  { id: 'off-uniresort-stay', providerId: 'vendor-uni-resort', name: '渡假村住宿(一晚)', domainType: 'resort_booking', fulfillmentKind: 'booking', basePrice: 4200, pricingUnit: '晚', cancelPolicyHours: 72 },
  { id: 'off-foodomo-meal', providerId: 'vendor-foodomo', name: 'foodomo・熱食外送', domainType: 'food_delivery', fulfillmentKind: 'commerce', basePrice: 259, pricingUnit: '餐', cancelPolicyHours: 0 },
  { id: 'off-711-c2c-standard', providerId: 'vendor-711-c2c', name: '交貨便・店到店(常溫)', domainType: 'c2c_shipping', fulfillmentKind: 'commerce', basePrice: 60, pricingUnit: '件', cancelPolicyHours: 0 },
  { id: 'off-iopenmall-home', providerId: 'vendor-iopenmall', name: 'iOPEN Mall・居家小物組', domainType: 'ec_preorder', fulfillmentKind: 'commerce', basePrice: 690, pricingUnit: '組', cancelPolicyHours: 0 },
  { id: 'off-ibon-attraction', providerId: 'vendor-ibon-ticket', name: '景點門票・傳藝中心全票', domainType: 'ticket_purchase', fulfillmentKind: 'commerce', basePrice: 150, pricingUnit: '張', cancelPolicyHours: 0 },
].map((item) => [item.id, { currency: 'TWD', description: `${item.name}(展示資料)`, ...item }]))

function stubProposal(providerId: string, offeringId: string) {
  const offering = OFFERINGS[offeringId]!
  const provider = SCENE_PROVIDERS.find((item) => item.id === providerId)!
  const slot = slotsFor(providerId, offeringId)[0]!
  return {
    id: `option-${providerId.replace('vendor-', '')}`,
    providerId, providerName: provider.name,
    offeringId, offeringName: offering.name,
    fulfillmentKind: offering.fulfillmentKind, basePrice: offering.basePrice,
    slot, reasons: [`評分 ${provider.rating}(展示資料)`, `NT$${offering.basePrice}/次`, '最早可約 08-01 09:00'],
    rating: provider.rating,
  }
}

function slotsFor(providerId: string, offeringId: string) {
  return [1, 2, 3].map((day) => ({
    id: `slot-${providerId.replace('vendor-', '')}-${day}`,
    providerId,
    offeringId,
    locationId: `loc-${providerId.replace('vendor-', '')}-01`,
    resourceId: `resource-${providerId.replace('vendor-', '')}-a`,
    startsAt: `2026-08-0${day}T09:00:00+08:00`,
    endsAt: `2026-08-0${day}T11:00:00+08:00`,
    status: 'available',
    capacity: 1,
  }))
}

function providerDetail(providerId: string) {
  const provider = SCENE_PROVIDERS.find((item) => item.id === providerId)
  if (!provider) return null
  return {
    ...provider,
    seedVersion: 'partner-demo-v5',
    syncedAt: '2026-07-30T00:00:00+08:00',
    locations: [{
      id: `loc-${providerId.replace('vendor-', '')}-01`, providerId,
      name: `${provider.name} 信義服務點`, countyName: '臺北市', districtName: '信義區',
      address: '110臺北市信義區示範路 1 號', phone: '02-2726-1000',
    }],
    offerings: Object.values(OFFERINGS).filter((item) => item.providerId === providerId),
    resources: [{
      id: `resource-${providerId.replace('vendor-', '')}-a`, providerId,
      name: '示範服務資源', kind: 'service_team',
    }],
  }
}

interface StubState {
  drafts: Map<string, any>
  bookings: Map<string, any>
  orders: Map<string, any>
  payments: Map<string, any>
  notifications: any[]
  calendar: any[]
  announcements?: any[]
  agentSession?: any
  careMessages: any[]
  taskPackages: any[]
  outcomes: any
  providerSettlement: any
  counter: number
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function ok(data: unknown): Response {
  return json({ data })
}

function bodyOf(init?: RequestInit): any {
  try {
    return init?.body ? JSON.parse(String(init.body)) : {}
  } catch {
    return {}
  }
}

/**
 * 回傳一個有狀態的 platform fetch handler;傳給 `stubCatalogFetch` 或自行安裝。
 * 每次呼叫 `createPlatformStub()` 都是乾淨狀態(對應一個測試)。
 */
export function createPlatformStub() {
  const state: StubState = {
    drafts: new Map(), bookings: new Map(), orders: new Map(),
    payments: new Map(), notifications: [], calendar: [], careMessages: [{
      id: 'care-message-stub-1', candidateId: 'care-candidate-stub-1', state: 'delivered',
      deliveredAt: '2026-08-01T10:00:00+08:00', actedAt: null, action: null,
      candidate: {
        id: 'care-candidate-stub-1', eventId: 'life-event-demo-stub', kind: 'life_preparation',
        reason: '你已授權的競賽 Demo event 可能需要提前查看準備資訊。',
        evidence: { source: 'competition_demo_event', isDemo: true, noBackgroundTracking: true, guideStatus: 'published_internal_demo' },
        status: 'delivered',
      },
    }], taskPackages: [{
      id: 'package-stub-1', source: { type: 'agent_session', id: 'agent-stub-1' },
      beneficiary: { label: 'Demo' }, serviceLocation: {}, status: 'awaiting_confirmation', grantId: 'grant-stub-1', version: 1,
      totalAmount: 1200, totalPoints: 0, providerIds: ['vendor-prince-electric'], selectedItemIds: ['package-stub-1-item-1'], taskDraftRefs: ['draft-stub-1'],
      items: [{ id: 'package-stub-1-item-1', position: 1, taskDraftId: 'draft-stub-1', sourceSubtaskId: 'task-stub-1', providerId: 'vendor-prince-electric', providerName: '王子水電', offeringId: 'off-prince-electric-repair', offeringName: '水電修繕・到府檢測', amount: 1200, points: 0, startsAt: '2026-08-08T09:00:00+08:00', endsAt: '2026-08-08T11:00:00+08:00', status: 'selected', details: { proposalOptions: [] }, lastError: null, version: 1 }],
    }], outcomes: {
      outcomes: [{ id: 'outcome-stub-1', packageId: null, subjectType: 'booking', subjectId: 'booking-stub-1', providerId: 'vendor-prince-electric', amount: 0, status: 'completed', summary: 'booking booking-stub-1 狀態：completed', eventId: 'event-stub-1', createdAt: '2026-08-01T10:00:00+08:00' }],
      achievements: [{ key: 'first_life_outcome', title: '完成一項生活任務', outcomeId: 'outcome-stub-1', unlockedAt: '2026-08-01T10:00:00+08:00' }],
      rewards: [{ id: 'reward-stub-1', campaignId: 'demo-completion-reward-2026', subjectType: 'booking', subjectId: 'booking-stub-1', kind: 'grant', amount: 20, pointsEntryId: 'points-stub-1', reversesEntryId: null, createdAt: '2026-08-01T10:00:00+08:00' }],
      note: '會員端只顯示自己的成果、成就與 Demo 回饋；Provider success fee 不在此顯示。',
    }, providerSettlement: {
      providerId: 'vendor-prince-electric',
      fees: [{
        id: 'fee-stub-1', subjectType: 'booking', subjectId: 'booking-stub-1',
        kind: 'charge', amount: 60, rateBps: 500, eventId: 'event-stub-1',
        reversalOf: null, createdAt: '2026-08-01T10:00:00+08:00',
      }],
      netAmount: 60, rateBps: 500, dataSource: 'competition_demo_fee_projection', officialRate: false,
    }, counter: 0,
  }

  function nextId(prefix: string): string {
    state.counter += 1
    return `${prefix}-stub-${state.counter}`
  }

  function pushEvent(subject: any, type: string, from: string | null, to: string, actorRole: string, note: string | null = null) {
    subject.events.push({
      id: nextId('event'), type, fromStatus: from, toStatus: to,
      actorRole, note, occurredAt: '2026-07-30T10:00:00+08:00',
    })
  }

  function notify(title: string, body: string, deepLink: string | null) {
    state.notifications.unshift({
      id: nextId('ntf'), category: 'booking_status', title, body,
      deepLink, readAt: null, createdAt: '2026-07-30T10:00:00+08:00',
    })
  }

  return function platformStub(url: string, init?: RequestInit): Response | undefined {
    const method = (init?.method ?? 'GET').toUpperCase()
    const path = url.replace(/^https?:\/\/[^/]+/, '').split('?')[0] ?? ''
    const query = new URLSearchParams(url.split('?')[1] ?? '')
    if (!path.startsWith('/api/v1/platform/') && !path.startsWith('/api/v1/admin/')) return undefined

    // ── 目錄 ──
    if (path === '/api/v1/platform/catalog/providers') {
      const scene = query.get('scene')
      const rows = SCENE_PROVIDERS
        .filter((item) => !scene || item.scene === scene)
        .map((item) => ({ ...item, seedVersion: 'partner-demo-v5', syncedAt: '2026-07-30T00:00:00+08:00' }))
      return ok(rows)
    }
    const providerMatch = path.match(/^\/api\/v1\/platform\/catalog\/providers\/([^/]+)$/)
    if (providerMatch) {
      const detail = providerDetail(providerMatch[1]!)
      return detail ? ok(detail) : json({ detail: '目錄中查無 Provider' }, 404)
    }
    if (path === '/api/v1/platform/catalog/availability') {
      const providerId = query.get('providerId') ?? ''
      const offeringId = query.get('offeringId')
        ?? Object.values(OFFERINGS).find((item) => item.providerId === providerId)?.id ?? ''
      return ok(slotsFor(providerId, offeringId))
    }
    if (path === '/api/v1/platform/catalog/listings') {
      const scene = query.get('scene')
      return ok(LISTINGS.filter((item) => !scene || item.scene === scene))
    }
    if (path === '/api/v1/platform/catalog/health') {
      return ok(SCENE_PROVIDERS.map((item) => ({
        providerId: item.id, seedVersion: 'partner-demo-v5',
        syncedAt: '2026-07-30T00:00:00+08:00', offerings: 1, availableSlots: 3,
      })))
    }
    if (path === '/api/v1/platform/catalog/sync') {
      return ok({ status: 'ok', providers: SCENE_PROVIDERS.map((item) => ({ providerId: item.id, status: 'synced' })) })
    }

    // ── 試算 ──
    if (path === '/api/v1/platform/quotes') {
      const body = bodyOf(init)
      const offering = OFFERINGS[body.offering_id]
      if (!offering) return json({ detail: '目錄中查無服務方案' }, 404)
      const quantity = Math.max(1, Number(body.quantity) || 1)
      const subtotal = offering.basePrice * quantity
      const balance = 180
      const maxRedeemable = Math.min(balance, subtotal)
      const points = Math.min(Number(body.points_to_redeem) || 0, maxRedeemable)
      if ((Number(body.points_to_redeem) || 0) > maxRedeemable) return json({ detail: '點數折抵超過上限' }, 422)
      return ok({
        offeringId: offering.id, offeringName: offering.name, currency: 'TWD',
        unitPrice: offering.basePrice, quantity, subtotal,
        pointsBalance: balance, maxRedeemablePoints: maxRedeemable,
        pointsToRedeem: points, pointsDiscount: points, payable: subtotal - points,
        ruleSummary: 'Demo 規則:1 點折抵 NT$1。',
      })
    }

    // ── TaskDraft ──
    if (path === '/api/v1/platform/task-drafts' && method === 'POST') {
      const body = bodyOf(init)
      const draft = {
        id: nextId('draft'), domainType: body.domain_type, status: 'drafting',
        values: body.values ?? {}, provenance: {}, version: 1,
        resultSubjectType: null, resultSubjectId: null, updatedAt: '2026-07-30T10:00:00+08:00',
      }
      state.drafts.set(draft.id, draft)
      return ok(draft)
    }
    if (path === '/api/v1/platform/task-drafts' && method === 'GET') {
      return ok([...state.drafts.values()])
    }
    const draftMatch = path.match(/^\/api\/v1\/platform\/task-drafts\/([^/]+)(\/.*)?$/)
    if (draftMatch) {
      const draft = state.drafts.get(draftMatch[1]!)
      if (!draft) return json({ detail: '查無草稿' }, 404)
      const action = draftMatch[2] ?? ''
      const body = bodyOf(init)
      if (!action && method === 'GET') return ok(draft)
      if (body.expected_version !== undefined && body.expected_version !== draft.version) {
        return json({ detail: '草稿版本已更新，請重新載入' }, 409)
      }
      if (!action && method === 'PATCH') {
        Object.assign(draft.values, body.values ?? {})
        draft.version += 1
        return ok({ ...draft, ignoredFields: [] })
      }
      if (action === '/transition') {
        draft.status = body.status
        draft.version += 1
        return ok(draft)
      }
      if (action === '/submit') {
        if (draft.resultSubjectId) {
          return ok({ draft, subjectType: draft.resultSubjectType, subjectId: draft.resultSubjectId, idempotentReplay: true })
        }
        const values = draft.values as Record<string, any>
        const offering = OFFERINGS[String(values.offering_id ?? '')]
        if (!offering) return json({ detail: '草稿缺少商品欄位:offering_id' }, 422)
        if (offering.fulfillmentKind === 'booking') {
          const booking = {
            id: nextId('booking'), providerId: offering.providerId,
            locationId: values.location_id, offeringId: offering.id,
            resourceId: values.resource_id ?? null, slotId: values.slot_id,
            startsAt: values.starts_at, endsAt: values.ends_at,
            status: 'pending_provider', version: 1, events: [] as any[],
            providerSync: { syncStatus: 'synced', lastError: null },
          }
          pushEvent(booking, 'booking_created', null, 'pending_provider', 'member')
          state.bookings.set(booking.id, booking)
          state.calendar.push({
            id: nextId('calendar'), title: offering.name, startsAt: booking.startsAt,
            endsAt: booking.endsAt, allDay: false, note: '狀態:需求送出', status: 'active',
            source: { type: 'booking', id: booking.id }, recurrence: null,
          })
          notify(`${offering.name}進度更新`, '目前狀態:需求送出', `/orders/${booking.id}`)
          draft.status = 'confirmed'
          draft.resultSubjectType = 'booking'
          draft.resultSubjectId = booking.id
          draft.version += 1
          return ok({ draft, subjectType: 'booking', subjectId: booking.id, booking })
        }
        const quantity = Math.max(1, Number(values.quantity) || 1)
        const order = {
          id: nextId('order'), providerId: offering.providerId,
          items: [{ offeringId: offering.id, name: offering.name, quantity, unitPrice: offering.basePrice, amount: offering.basePrice * quantity }],
          subtotal: offering.basePrice * quantity, discount: 0, total: offering.basePrice * quantity,
          status: 'placed', version: 1, events: [] as any[],
        }
        pushEvent(order, 'order_placed', null, 'placed', 'member')
        state.orders.set(order.id, order)
        notify(`${offering.name}訂單已建立`, `訂單金額 NT$${order.total}`, `/orders/${order.id}`)
        draft.status = 'confirmed'
        draft.resultSubjectType = 'commerce_order'
        draft.resultSubjectId = order.id
        draft.version += 1
        return ok({ draft, subjectType: 'commerce_order', subjectId: order.id, order })
      }
    }

    // ── Booking ──
    if (path === '/api/v1/platform/bookings' && method === 'GET') {
      return ok([...state.bookings.values()])
    }
    const bookingMatch = path.match(/^\/api\/v1\/platform\/bookings\/([^/]+)(\/.*)?$/)
    if (bookingMatch) {
      const booking = state.bookings.get(bookingMatch[1]!)
      if (!booking) return json({ detail: '查無預約' }, 404)
      const action = bookingMatch[2] ?? ''
      const body = bodyOf(init)
      if (!action && method === 'GET') return ok(booking)
      if (action === '/provider-sync') return ok(booking)
      if (body.expected_version !== undefined && body.expected_version !== booking.version) {
        return json({ detail: '預約版本已更新，請重新載入' }, 409)
      }
      if (action === '/transition') {
        pushEvent(booking, `booking_${body.status}`, booking.status, body.status, 'partner_staff', body.note)
        booking.status = body.status
        booking.version += 1
        notify('預約進度更新', `目前狀態:${body.status}`, `/orders/${booking.id}`)
        return ok(booking)
      }
      if (action === '/cancellation') {
        if (!['pending_provider', 'confirmed'].includes(booking.status)) {
          return json({ detail: `預約狀態 ${booking.status} 不可由會員取消` }, 409)
        }
        pushEvent(booking, 'booking_cancelled', booking.status, 'cancelled', 'member', body.note)
        booking.status = 'cancelled'
        booking.version += 1
        const refunds = [...state.payments.values()]
          .filter((item) => item.subjectId === booking.id && item.status === 'succeeded')
          .map((item) => ({ ...item, status: 'refunded', refundedAmount: item.amount, refundedPoints: item.pointsRedeemed }))
        for (const refund of refunds) state.payments.set(refund.id, refund)
        for (const event of state.calendar) {
          if (event.source?.id === booking.id) event.status = 'cancelled'
        }
        notify('預約已取消', refunds.length ? '款項與點數將依原路退回' : '預約已取消', `/orders/${booking.id}`)
        return ok({ ...booking, refunds })
      }
      if (action === '/reschedule-requests') {
        return ok({ id: nextId('reschedule'), bookingId: booking.id, status: 'pending' })
      }
    }

    // ── CommerceOrder ──
    if (path === '/api/v1/platform/commerce-orders' && method === 'GET') {
      return ok([...state.orders.values()])
    }
    const orderMatch = path.match(/^\/api\/v1\/platform\/commerce-orders\/([^/]+)(\/.*)?$/)
    if (orderMatch) {
      const order = state.orders.get(orderMatch[1]!)
      if (!order) return json({ detail: '查無購物訂單' }, 404)
      const action = orderMatch[2] ?? ''
      const body = bodyOf(init)
      if (body.expected_version !== undefined && body.expected_version !== order.version) {
        return json({ detail: '訂單版本已更新，請重新載入' }, 409)
      }
      if (action === '/transition') {
        pushEvent(order, `order_${body.status}`, order.status, body.status, 'partner_staff', body.note)
        order.status = body.status
        order.version += 1
        return ok(order)
      }
      if (action === '/cancellation') {
        pushEvent(order, 'order_cancelled', order.status, 'cancelled', 'member', body.note)
        order.status = 'cancelled'
        order.version += 1
        return ok({ ...order, refunds: [] })
      }
    }

    // ── 付款 ──
    if (path === '/api/v1/platform/payments' && method === 'POST') {
      const body = bodyOf(init)
      const subject = state.bookings.get(body.subject_id) ?? state.orders.get(body.subject_id)
      if (!subject) return json({ detail: '查無交易主體' }, 404)
      const payment = {
        id: nextId('payment'), subjectType: body.subject_type, subjectId: body.subject_id,
        amount: body.amount, pointsRedeemed: body.points_redeemed ?? 0,
        refundedAmount: 0, refundedPoints: 0,
        status: body.outcome === 'success' ? 'succeeded' : body.outcome === 'failure' ? 'failed' : 'pending',
        failureCode: body.outcome === 'failure' ? 'DEMO_DECLINED' : null,
        label: 'Demo 支付（未連接真實金流）',
      }
      state.payments.set(payment.id, payment)
      return ok(payment)
    }

    // ── 通知/行事曆/點數以外的支援端點 ──
    if (path === '/api/v1/platform/notifications' && method === 'GET') {
      return ok({
        unreadCount: state.notifications.filter((item) => !item.readAt).length,
        items: state.notifications,
        quietHoursActive: false,
      })
    }
    const readMatch = path.match(/^\/api\/v1\/platform\/notifications\/([^/]+)\/read$/)
    if (readMatch) {
      const target = state.notifications.find((item) => item.id === readMatch[1])
      if (!target) return json({ detail: '查無通知' }, 404)
      target.readAt = '2026-07-30T10:05:00+08:00'
      return ok(target)
    }
    if (path === '/api/v1/platform/calendar/events' && method === 'GET') {
      return ok(state.calendar.filter((item) => item.status === 'active'))
    }
    if (path === '/api/v1/platform/calendar/events' && method === 'POST') {
      const body = bodyOf(init)
      const event = {
        id: nextId('calendar'), title: body.title, startsAt: body.starts_at, endsAt: body.ends_at,
        allDay: Boolean(body.all_day), note: body.note ?? null, status: 'active',
        source: { type: 'manual', id: null }, recurrence: body.recurrence ?? null,
      }
      state.calendar.push(event)
      return ok(event)
    }
    if (path === '/api/v1/platform/provider/snapshot') {
      return ok({ providerId: 'vendor-prince-electric', seedVersion: 'partner-demo-v5', counts: { bookings: state.bookings.size } })
    }
    if (path === '/api/v1/platform/provider/settlement') {
      return ok(state.providerSettlement)
    }
    if (path === '/api/v1/platform/provider/catalog') {
      return ok(providerDetail('vendor-prince-electric'))
    }
    // ── admin(操作台替身) ──
    if (path === '/api/v1/admin/demo-personas') {
      return ok([
        { membershipId: 'membership-member-xiaoyuan', accountId: 'acct-1', displayName: '林小圓', role: 'member', demoWorkspaceId: 'demo-default', workspace: { id: 'ws-1', kind: 'personal', ownerRef: 'acct-1', name: '林小圓的個人空間' } },
        { membershipId: 'membership-partner-prince-electric', accountId: 'acct-p', displayName: '王子水電人員', role: 'partner_staff', demoWorkspaceId: 'demo-default', workspace: { id: 'ws-p', kind: 'partner', ownerRef: 'vendor-prince-electric', name: '王子水電' } },
      ])
    }
    const personaResetMatch = path.match(/^\/api\/v1\/platform\/admin\/workspaces\/([^/]+)\/reset$/)
    if (personaResetMatch) {
      if (personaResetMatch[1]!.includes('partner')) return json({ detail: '只能重置個人 workspace' }, 422)
      return ok({ status: 'ready', scope: 'workspace' })
    }
    if (path === '/api/v1/platform/admin/upstream-health') {
      return ok({ status: 'ok', seedVersion: 'partner-demo-v5', platformSeedVersions: ['partner-demo-v5'], consistent: true })
    }
    if (path === '/api/v1/platform/admin/upstream-faults') {
      const body = bodyOf(init)
      return ok({ action: body.action, result: body.action === 'clear' ? { cleared: 1 } : { status: 'armed' } })
    }
    // ── 社區公告替身 ──
    const announcementMatch = path.match(/^\/api\/v1\/platform\/communities\/([^/]+)\/announcements$/)
    if (announcementMatch) {
      state.announcements = state.announcements ?? [
        { id: 'announcement-seed-1', communityId: announcementMatch[1], title: '公設保養通知', body: '8/2(日)公共設施保養,電梯輪流停機。', publishedBy: 'demo-community-manager', publishedAt: '2026-07-28T09:00:00+08:00' },
      ]
      if (method === 'GET') return ok(state.announcements)
      const body = bodyOf(init)
      if (!String(body.title ?? '').trim()) return json({ detail: '公告標題與內容不可空白' }, 422)
      const created = {
        id: nextId('announcement'), communityId: announcementMatch[1],
        title: body.title, body: body.body, publishedBy: 'demo-community-manager',
        publishedAt: '2026-07-31T10:00:00+08:00',
      }
      state.announcements.unshift(created)
      return ok(created)
    }
    if (path === '/api/v1/platform/provider/availability' && method === 'PUT') {
      return json({ detail: '此 Provider 不是工作台接入,availability 由廠商系統維護' }, 409)
    }
    if (path === '/api/v1/platform/provider/availability' && method === 'GET') {
      return ok(slotsFor('vendor-prince-electric', 'off-prince-electric-repair'))
    }
    // ── v4 Session lifecycle + M8 Agent 對話替身 ──
    if (path === '/api/v1/platform/agent/sessions' && method === 'GET') {
      const current = state.agentSession
      const includeArchived = query.get('include_archived') === 'true'
      if (!current || (current.status === 'archived' && !includeArchived)) return ok([])
      return ok([{
        id: current.id, title: current.title ?? '新對話', status: current.status ?? 'active',
        summary: current.summary ?? '', pendingGrantId: current.pendingGrantId ?? current.grantId ?? null,
        archivedAt: current.archivedAt ?? null, version: current.version ?? 1,
        createdAt: current.createdAt ?? '2026-07-30T10:00:00+08:00', updatedAt: current.updatedAt,
      }])
    }
    if (path === '/api/v1/platform/reachability/area') {
      const mode = query.get('travelMode') ?? 'pedestrian'
      const threshold = Number(query.get('thresholdMinutes') ?? 10)
      return ok({
        originId: query.get('originId'), travelMode: mode, thresholdMinutes: threshold,
        geometry: { type: 'Polygon', coordinates: [[[121.562, 25.031], [121.569, 25.031], [121.570, 25.037], [121.563, 25.038], [121.562, 25.031]]] },
        eligibleLocationIds: threshold === 10 ? ['loc-prince-01'] : ['loc-prince-01', 'loc-duskin-01'],
        locations: threshold === 10
          ? [{ id: 'loc-prince-01', providerId: 'vendor-prince-electric', name: '王子水電信義服務點', address: '示範路 1 號' }]
          : [
            { id: 'loc-prince-01', providerId: 'vendor-prince-electric', name: '王子水電信義服務點', address: '示範路 1 號' },
            { id: 'loc-duskin-01', providerId: 'vendor-duskin', name: 'DUSKIN 樂清信義服務點', address: '示範路 2 號' },
          ],
        source: 'reviewed-demo-fixture', calculatedAt: '2026-08-01T10:00:00+08:00',
        isDemo: true, realTime: false, navigation: false,
      })
    }
    // ── v4 主動照護／任務包／成果替身 ──
    if (path === '/api/v1/platform/care/messages' && method === 'GET') {
      const includeClosed = query.get('include_closed') === 'true'
      return ok(includeClosed ? state.careMessages : state.careMessages.filter((item) => !['closed', 'ignored'].includes(item.state)))
    }
    const careActionMatch = path.match(/^\/api\/v1\/platform\/care\/messages\/([^/]+)\/actions$/)
    if (careActionMatch && method === 'POST') {
      const message = state.careMessages.find((item) => item.id === careActionMatch[1])
      if (!message) return json({ detail: '查無照護訊息' }, 404)
      const action = bodyOf(init).action
      message.action = action
      message.actedAt = '2026-08-01T10:05:00+08:00'
      if (action === 'ignore') message.state = 'ignored'
      if (action === 'snooze') message.state = 'snoozed'
      if (action === 'close') message.state = 'closed'
      if (action === 'open_guide') message.guide = {
        status: 'published', title: '中元普渡準備・競賽 Demo 指南',
        message: '這是一份人工檢視過的競賽 Demo 指南，不是政府公告或採購清單；請依家庭與社區規範調整。',
        source: 'AIWave 競賽 Demo 編寫資料', updatedAt: '2026-08-01', reviewedBy: 'AIWave Demo Editorial',
        steps: [
          { id: 'confirm-context', title: '先確認情境', body: '確認家人是否參與、日期、地點與社區公共區域規則。' },
          { id: 'make-checklist', title: '建立可修改清單', body: '依人數、場地與保存方式建立準備清單。' },
        ],
        preparationItems: [
          { id: 'common-supplies', name: '供桌／容器與飲水', necessity: 'common-required', quantityBasis: '依家庭與場地規範', estimatedPoints: 20 },
          { id: 'optional-food', name: '水果或點心', necessity: 'optional', quantityBasis: '依參與人數與家庭習慣', estimatedPoints: 15 },
          { id: 'community-help', name: '社區代收／整理服務', necessity: 'cooperation-recommendation', cooperationLabel: '合作推薦（非必要）', estimatedPoints: 20 },
        ],
        pointsEstimate: { min: 20, max: 55, label: 'Demo 點數估算 20–55 點' },
        warnings: ['不同家庭、宗教與社區規定可能不同；不確定時先詢問家人或管理室。'],
        suggestedActions: [{ type: 'create-checklist', label: '幫我整理準備清單' }],
        commercialBoundary: '只整理類別與 Demo 點數估算，不建立訂單、不代替會員同意採購。',
      }
      return ok(message)
    }
    if (path === '/api/v1/platform/agent/task-packages' && method === 'GET') return ok(state.taskPackages)
    const packageItemMatch = path.match(/^\/api\/v1\/platform\/agent\/task-packages\/([^/]+)\/items\/([^/]+)$/)
    if (packageItemMatch && method === 'PATCH') {
      const taskPackage = state.taskPackages.find((item) => item.id === packageItemMatch[1])
      const packageItem = taskPackage?.items.find((item: any) => item.id === packageItemMatch[2])
      if (!taskPackage || !packageItem) return json({ detail: '查無任務包項目' }, 404)
      const body = bodyOf(init)
      if (Number(body.expected_version) !== taskPackage.version) return json({ detail: '任務包版本已更新，請重新載入' }, 409)
      if (body.operation === 'pause') packageItem.status = 'paused'
      if (body.operation === 'resume') packageItem.status = 'selected'
      if (body.operation === 'remove') packageItem.status = 'removed'
      taskPackage.version += 1
      taskPackage.totalAmount = taskPackage.items.filter((item: any) => !['paused', 'removed'].includes(item.status)).reduce((sum: number, item: any) => sum + item.amount, 0)
      return ok(taskPackage)
    }
    if (path === '/api/v1/platform/outcomes' && method === 'GET') return ok(state.outcomes)
    if (path === '/api/v1/platform/agent/sessions' && method === 'POST') {
      const body = bodyOf(init)
      state.agentSession = {
        id: nextId('agent'), title: String(body.title ?? '').trim() || '新對話', status: 'active',
        summary: '', messages: [], subtasks: [], awaiting: null, grantId: null,
        pendingGrantId: null, archivedAt: null, version: 1, lastTurn: null,
      }
      return ok(state.agentSession)
    }
    const archiveMatch = path.match(/^\/api\/v1\/platform\/agent\/sessions\/([^/]+)\/(archive|restore)$/)
    if (archiveMatch && method === 'POST') {
      if (!state.agentSession || state.agentSession.id !== archiveMatch[1]) return json({ detail: '查無此對話' }, 404)
      const body = bodyOf(init)
      if (Number(body.expected_version ?? 1) !== Number(state.agentSession.version ?? 1)) {
        return json({ detail: '對話版本衝突' }, 409)
      }
      state.agentSession.status = archiveMatch[2] === 'archive' ? 'archived' : 'active'
      state.agentSession.archivedAt = state.agentSession.status === 'archived' ? '2026-08-01T10:00:00+08:00' : null
      state.agentSession.version = Number(state.agentSession.version ?? 1) + 1
      return ok(state.agentSession)
    }
    if (path === '/api/v1/platform/agent/sessions/latest') {
      return ok(state.agentSession ?? null)
    }
    const agentSessionMatch = path.match(/^\/api\/v1\/platform\/agent\/sessions\/([^/]+)$/)
    if (agentSessionMatch) {
      if (state.agentSession?.id === agentSessionMatch[1]) {
        if (method === 'PATCH') {
          const body = bodyOf(init)
          if (Number(body.expected_version ?? 1) !== Number(state.agentSession.version ?? 1)) {
            return json({ detail: '對話版本衝突' }, 409)
          }
          state.agentSession.title = String(body.title ?? state.agentSession.title).trim()
          state.agentSession.version = Number(state.agentSession.version ?? 1) + 1
        }
        return ok(state.agentSession)
      }
      return json({ detail: '查無此對話,請重新開始' }, 404)
    }
    if (path === '/api/v1/platform/agent/messages' || path === '/api/v1/platform/agent/messages/stream') {
      const body = bodyOf(init)
      if (!state.agentSession) {
        state.agentSession = {
          id: nextId('agent'), title: '新對話', status: 'active', version: 1,
          messages: [], subtasks: [], awaiting: null, grantId: null, lastTurn: null,
        }
      }
      const session = state.agentSession
      const stages: string[] = []
      const action = body.action ?? null
      const text = String(body.message ?? '')

      const reply = (content: string) => session.messages.push({ role: 'assistant', content })

      if (action?.type === 'select_option') {
        const subtask = session.subtasks.find((item: any) => item.id === action.subtaskId)
        const option = subtask?.proposals.find((item: any) => item.id === action.optionId)
        if (subtask && option) {
          stages.push('預填正式表單', '等待你確認')
          const draft = {
            id: nextId('draft'), domainType: subtask.domain, status: 'drafting',
            values: {
              provider_id: option.providerId, offering_id: option.offeringId,
              location_id: option.slot?.locationId, resource_id: option.slot?.resourceId,
              slot_id: option.slot?.id, starts_at: option.slot?.startsAt, ends_at: option.slot?.endsAt,
            },
            provenance: {}, version: 1, resultSubjectType: null, resultSubjectId: null,
            updatedAt: '2026-07-31T10:00:00+08:00',
          }
          state.drafts.set(draft.id, draft)
          subtask.selected = option
          subtask.draftId = draft.id
          subtask.missingFields = ['problem', 'address', 'phone']
          subtask.status = 'fields'
          subtask.quote = { payable: option.basePrice, subtotal: option.basePrice }
          session.awaiting = 'fields'
          reply(`已選${option.providerName}・${option.offeringName},還差:問題描述、服務地址、聯絡電話。可以直接回覆,或點「切到手動填寫」;兩邊是同一份草稿。`)
        }
      } else if (action?.type === 'clarify_option') {
        const subtask = session.subtasks.find((item: any) => item.id === action.subtaskId)
        if (subtask) {
          stages.push('查詢可用方案與時段', '整理方案', '等待你確認')
          subtask.domain = action.domain
          subtask.status = 'resolved'
          subtask.clarify = null
          subtask.clarifyOptions = []
          subtask.proposals = [stubProposal('vendor-duskin', 'off-duskin-cleaning')]
          session.awaiting = 'option'
          reply(`了解,是${action.label}。以下是可選方案,請挑一個。`)
        }
      } else if (action?.type === 'approve_grant') {
        stages.push('核准授權', '建立訂單')
        for (const subtask of session.subtasks.filter((item: any) => item.status === 'ready')) {
          const booking = {
            id: nextId('booking'), providerId: subtask.selected.providerId,
            locationId: subtask.selected.slot?.locationId, offeringId: subtask.selected.offeringId,
            resourceId: null, slotId: subtask.selected.slot?.id,
            startsAt: subtask.selected.slot?.startsAt, endsAt: subtask.selected.slot?.endsAt,
            status: 'pending_provider', version: 1, events: [],
            providerSync: { syncStatus: 'synced', lastError: null },
          }
          state.bookings.set(booking.id, booking)
          subtask.status = 'submitted'
          subtask.subjectType = 'booking'
          subtask.subjectId = booking.id
        }
        session.awaiting = null
        reply('已完成:訂單已建立;進度、通知與行事曆都會同步更新,可到「我的訂單」追蹤。')
      } else if (action?.type === 'revoke_grant') {
        session.grantId = null
        session.awaiting = 'option'
        reply('已撤回授權,不會送出任何訂單。')
      } else if (text) {
        session.messages.push({ role: 'user', content: text })
        if (session.awaiting === 'fields') {
          stages.push('理解需求', '等待你確認')
          const subtask = session.subtasks.find((item: any) => item.status === 'fields')
          if (subtask) {
            const draft = state.drafts.get(subtask.draftId)
            Object.assign(draft.values, { problem: text, address: '台北市信義區', phone: '0912345678' })
            subtask.missingFields = []
            subtask.status = 'ready'
            session.awaiting = 'grant'
            session.grantId = session.grantId ?? nextId('grant')
            reply(`表單都備齊了,金額 NT$${subtask.quote.payable}。執行授權內容:服務商 ${subtask.selected.providerName};預算上限 NT$${subtask.quote.payable};30 分鐘內有效。核准後我才會實際送出。`)
          }
        } else if (text.includes('爸媽') && text.includes('清潔') && (text.includes('晚餐') || text.includes('餐廳'))) {
          stages.push('理解需求', '查詢可用方案與時段', '整理方案', '等待你確認')
          session.subtasks = [
            {
              id: nextId('task'), goal: '安排家裡清潔', domain: 'home_cleaning',
              time: { date: '2026-08-01', endDate: null, echo: '8/1(週六)' }, status: 'resolved',
              clarify: null, clarifyOptions: [],
              proposals: [stubProposal('vendor-duskin', 'off-duskin-cleaning')],
              selected: null, draftId: null, missingFields: [], subjectType: null, subjectId: null,
            },
            {
              id: nextId('task'), goal: '安排家庭晚餐', domain: 'dining_reservation',
              time: { date: '2026-08-01', endDate: null, echo: '8/1(週六)' }, status: 'resolved',
              clarify: null, clarifyOptions: [],
              proposals: [stubProposal('vendor-21plus', 'off-21plus-dinner')],
              selected: null, draftId: null, missingFields: [], subjectType: null, subjectId: null,
            },
          ]
          session.awaiting = 'option'
          reply('我懂了：爸媽週末要來，你想安排家裡清潔，也想找一個家庭晚餐方案。我先把兩件事分開列出來，你可以各自看看，不用現在決定。')
        } else if (text.includes('洗衣服')) {
          stages.push('理解需求', '等待你確認')
          session.subtasks = [{
            id: nextId('task'), goal: '洗衣服', domain: null, time: null, status: 'clarify',
            clarify: '「洗衣服」是想找人到府做家事(含洗衣),還是洗衣機本身要清洗?',
            clarifyOptions: [
              { domain: 'home_cleaning', label: '到府家事服務(含洗衣)' },
              { domain: 'home_cleaning', label: '洗衣機清洗' },
            ],
            proposals: [], selected: null, draftId: null, missingFields: [],
            subjectType: null, subjectId: null,
          }]
          session.awaiting = 'clarify'
          reply('「洗衣服」是想找人到府做家事(含洗衣),還是洗衣機本身要清洗?')
        } else if (text.includes('OPENPOINT')) {
          stages.push('理解需求', '查閱已發布說明', '整理引用', '完成回覆')
          session.awaiting = null
          session.lastTurn = {
            intent: 'product_help',
            citedKnowledge: [{
              articleId: 'points-and-redemption',
              title: 'OPENPOINT 折抵與兌換',
              section: '折抵規則',
              updatedAt: '2026-07-31',
              domain: 'product-help',
            }],
            toolResults: [{
              actionId: 'action-product-help-demo',
              status: 'succeeded',
              facts: { domain: 'product-help', source: 'published-wiki' },
              cards: [{ type: 'knowledge', domain: 'product-help', articleId: 'points-and-redemption' }],
              warnings: [], retryPolicy: 'none', auditRef: 'wiki:product-help',
            }],
            groundedResponse: {
              answer: 'OPENPOINT 是否可折抵，請依已發布說明與結帳頁實際顯示為準。',
              source: 'tool_results', warnings: [],
            },
          }
          reply('我找到已發布的 OPENPOINT 說明；折抵規則請以結帳頁實際顯示為準。')
        } else {
          stages.push('理解需求', '查詢可用方案與時段', '整理方案', '等待你確認')
          session.subtasks = [{
            id: nextId('task'), goal: '修理水電', domain: 'home_repair',
            time: { date: '2026-08-01', endDate: null, echo: '8/1(週六)' }, status: 'resolved',
            clarify: null, clarifyOptions: [],
            proposals: [stubProposal('vendor-prince-electric', 'off-prince-electric-repair')],
            selected: null, draftId: null, missingFields: [],
            subjectType: null, subjectId: null,
          }]
          session.awaiting = 'option'
          const task = session.subtasks[0]
          session.lastTurn = {
            intent: 'plan', citedKnowledge: [], groundedResponse: null,
            toolResults: task ? [{
              actionId: `action-catalog-${task.id}`,
              status: 'succeeded',
              facts: { subtaskId: task.id, domain: task.domain, proposalCount: task.proposals.length },
              cards: task.proposals.map((proposal: any) => ({
                type: 'offering', providerId: proposal.providerId, providerName: proposal.providerName,
                offeringId: proposal.offeringId, offeringName: proposal.offeringName,
                amount: proposal.basePrice, slotId: proposal.slot?.id,
              })),
              warnings: ['目前使用可重置 Demo 目錄'], retryPolicy: 'none',
              auditRef: `catalog-search:${task.id}`,
            }] : [],
          }
          reply('我把需求拆成:水電修繕(8/1(週六))。以下方案來自平台核准店家的真實資料,請選一個,最終由你決定。')
        }
      }
      const result = { session, stages }
      if (path.endsWith('/stream')) {
        const linesOut = stages.map((stage) => JSON.stringify({ stage })).join('\n')
        return new Response(`${linesOut}\n${JSON.stringify({ result: { data: result } })}\n`, {
          status: 200, headers: { 'Content-Type': 'application/x-ndjson' },
        })
      }
      return ok(result)
    }
    const grantMatch = path.match(/^\/api\/v1\/platform\/agent\/grants\/([^/]+)$/)
    if (grantMatch) {
      return ok({
        id: grantMatch[1], providerIds: ['vendor-prince-electric'],
        windowStart: '2026-08-01', windowEnd: '2026-08-01',
        budgetLimit: 1200, pointsLimit: 0, status: 'proposed',
        expiresAt: '2026-07-31T11:00:00+08:00',
        summary: '王子水電;時間 2026-08-01;預算上限 NT$1,200;30 分鐘內有效',
      })
    }
    if (path === '/api/v1/platform/demo/reset') {
      state.drafts.clear(); state.bookings.clear(); state.orders.clear()
      state.payments.clear(); state.notifications = []; state.calendar = []
      return ok({ status: 'ready', scope: 'workspace' })
    }
    return undefined
  }
}
