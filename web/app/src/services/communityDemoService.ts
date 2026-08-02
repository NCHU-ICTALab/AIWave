import { COMMUNITY_DEMO_SEED, DEMO_NOW, type CommunityDemoSeed } from '@/data/communityDemoSeed'
import {
  DEMO_HOUSEHOLD_ID,
  type DemoCommunityAnswer,
  type DemoCommitteeDashboard,
  type DemoGroupBuy,
  type DemoGroupBuyJoin,
  type DemoOrder,
  type DemoResidentDashboard,
  type DemoSubscriptionSummary,
  type DemoUnansweredQuestion,
  type JoinGroupBuyInput,
  type PublishDemoGroupBuyInput,
  type UpdateDemoGroupBuyInput,
} from '@/domain/communityDemo'

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function normalize(value: string): string {
  return value.trim().replace(/[？?！!。．，,、\s]+$/g, '')
}

function sortNewest<T extends { publishedAt?: string; askedAt?: string }>(rows: T[]): T[] {
  return rows.slice().sort((a, b) => (b.publishedAt ?? b.askedAt ?? '').localeCompare(a.publishedAt ?? a.askedAt ?? ''))
}

export interface CommunityDemoServiceApi {
  listAnnouncements(): ReturnType<CommunityDemoService['listAnnouncements']>
  getResidentDashboard(householdId: string): ReturnType<CommunityDemoService['getResidentDashboard']>
  askCommunity(query: string, householdId: string): ReturnType<CommunityDemoService['askCommunity']>
  reportUnanswered(query: string, householdId: string): ReturnType<CommunityDemoService['reportUnanswered']>
  listGroupBuys(): ReturnType<CommunityDemoService['listGroupBuys']>
  getGroupBuy(id: string): ReturnType<CommunityDemoService['getGroupBuy']>
  openResidentGroupBuy(input?: PublishDemoGroupBuyInput): ReturnType<CommunityDemoService['openResidentGroupBuy']>
  publishDemoGroupBuy(input?: PublishDemoGroupBuyInput): ReturnType<CommunityDemoService['publishDemoGroupBuy']>
  updateGroupBuy(groupBuyId: string, input: UpdateDemoGroupBuyInput): ReturnType<CommunityDemoService['updateGroupBuy']>
  closeGroupBuy(groupBuyId: string): ReturnType<CommunityDemoService['closeGroupBuy']>
  reopenGroupBuy(groupBuyId: string): ReturnType<CommunityDemoService['reopenGroupBuy']>
  joinGroupBuy(input: JoinGroupBuyInput): ReturnType<CommunityDemoService['joinGroupBuy']>
  cancelGroupBuy(groupBuyId: string, householdId: string): ReturnType<CommunityDemoService['cancelGroupBuy']>
  listMyOrders(householdId: string): ReturnType<CommunityDemoService['listMyOrders']>
  getCommitteeDashboard(): ReturnType<CommunityDemoService['getCommitteeDashboard']>
  getSubscriptionSummary(): ReturnType<CommunityDemoService['getSubscriptionSummary']>
  markUnansweredForWiki(id: string): ReturnType<CommunityDemoService['markUnansweredForWiki']>
  resetDemo(): void
}

export class CommunityDemoService implements CommunityDemoServiceApi {
  private state: CommunityDemoSeed = clone(COMMUNITY_DEMO_SEED)

  listAnnouncements() {
    return clone(sortNewest(this.state.announcements))
  }

  getResidentDashboard(householdId = DEMO_HOUSEHOLD_ID): DemoResidentDashboard {
    const groupBuyHistory = this.state.groupBuys
      .filter((group) => group.published)
      .map((group) => this.withProgress(group))

    return clone({
      community: this.state.community,
      resident: {
        householdId,
        displayName: '王小明',
        householdLabel: 'A 棟 12F-3',
        householdMembers: '夫妻＋幼兒，共 3 人',
        residenceType: '自住',
        pastGroupBuys: 6,
      },
      announcements: sortNewest(this.state.announcements),
      packages: this.state.packages,
      repairs: this.state.repairs,
      maintenance: this.state.maintenance,
      reservations: this.state.reservations,
      activeGroupBuys: groupBuyHistory.filter((group) => group.status === 'open'),
      groupBuyHistory,
      serviceOffers: this.state.serviceOffers,
    })
  }

  askCommunity(query: string, householdId = DEMO_HOUSEHOLD_ID): DemoCommunityAnswer {
    const cleanQuery = normalize(query)
    const entry = this.state.wiki.find((item) =>
      item.keywords.some((keyword) => cleanQuery.includes(keyword)),
    )

    if (cleanQuery) {
      this.state.queryCounts[cleanQuery] = (this.state.queryCounts[cleanQuery] ?? 0) + 1
      this.state.latestQueries = [cleanQuery, ...this.state.latestQueries.filter((item) => item !== cleanQuery)].slice(0, 5)
    }

    if (!entry) {
      return {
        query: cleanQuery,
        matched: false,
        shortAnswer: '這題我還不會，已轉知管委會',
        fullRule: '目前 Wiki 尚未收錄這個問題，你可以把它送進未回答問題清單，請管委會補充。',
        source: null,
        updatedAt: null,
        relatedQuestions: ['管理室服務時間？', '如何提交社區建議？', '團購商品可以取消嗎？'],
        wikiEntryId: null,
      }
    }

    // Keep householdId in the boundary even though this local Demo does not persist per-user transcripts yet.
    void householdId
    return {
      query: cleanQuery,
      matched: true,
      shortAnswer: entry.shortAnswer,
      fullRule: entry.fullRule,
      source: entry.source,
      updatedAt: entry.updatedAt,
      relatedQuestions: entry.relatedQuestions,
      wikiEntryId: entry.id,
    }
  }

  reportUnanswered(query: string, householdId = DEMO_HOUSEHOLD_ID): DemoUnansweredQuestion {
    const cleanQuery = normalize(query)
    const existing = this.state.unanswered.find((item) => item.query === cleanQuery && item.status === 'new')
    if (existing) return clone(existing)

    const created: DemoUnansweredQuestion = {
      id: `unanswered-${String(this.state.unanswered.length + 1).padStart(3, '0')}`,
      query: cleanQuery,
      householdId,
      askedAt: DEMO_NOW.slice(0, 10),
      status: 'new',
    }
    this.state.unanswered.unshift(created)
    return clone(created)
  }

  listGroupBuys(): DemoGroupBuy[] {
    return clone(this.state.groupBuys
      .filter((group) => group.published && group.status === 'open')
      .map((group) => this.withProgress(group)))
  }

  getGroupBuy(id: string): DemoGroupBuy | null {
    const group = this.state.groupBuys.find((item) => item.id === id && item.published)
    return group ? clone(this.withProgress(group)) : null
  }

  /**
   * Any signed-in resident can start a group buy. The committee dashboard
   * remains useful for later community-wide management, but it is not a
   * publishing gate for the resident flow.
   */
  openResidentGroupBuy(input: PublishDemoGroupBuyInput = {}): DemoGroupBuy {
    const residentGroupCount = this.state.groupBuys.filter((group) => group.id.startsWith('group-resident-')).length + 1
    const marketPrice = Number.isFinite(input.marketPrice) && (input.marketPrice ?? 0) > 0 ? input.marketPrice as number : 399
    const variants = input.variants?.filter((variant) => (
      variant.id.trim() && variant.label.trim() && Number.isFinite(variant.price) && variant.price > 0
    ))
    const supplierType = input.supplierType ?? 'external'
    const group: DemoGroupBuy = {
      id: `group-resident-${DEMO_NOW.slice(0, 10).replaceAll('-', '')}-${String(residentGroupCount).padStart(3, '0')}`,
      name: input.name?.trim() || '新的社區團購',
      description: input.description?.trim() || '由社區住戶發起，達標後集中送至管理室。',
      marketPrice,
      variants: clone(variants?.length ? variants : [{ id: 'resident-default', label: '標準規格', price: Math.max(1, Math.round(marketPrice * .9)) }]),
      thresholdUnits: Number.isInteger(input.thresholdUnits) && (input.thresholdUnits ?? 0) > 0 ? input.thresholdUnits as number : 10,
      seededProgressUnits: 0,
      progressUnits: 0,
      pickupLocation: input.pickupLocation?.trim() || '社區管理室',
      expectedArrival: input.expectedArrival?.trim() || '2026-08-15',
      closeAt: input.closeAt?.trim() || '2026-08-10T21:00:00+08:00',
      supplierType,
      supplierName: input.supplierName?.trim() || '住戶推薦廠商',
      supplierFeeRate: supplierType === 'external' ? 0.03 : 0,
      status: 'open',
      statusLabel: '進行中',
      published: true,
      publishedAt: DEMO_NOW.slice(0, 10),
      joins: [],
    }
    this.state.groupBuys.unshift(group)
    return clone(this.withProgress(group))
  }

  publishDemoGroupBuy(input: PublishDemoGroupBuyInput = {}): DemoGroupBuy {
    const group = this.state.groupBuys.find((item) => item.id === 'group-dubai-chocolate-2026-08')
    if (!group) throw new Error('找不到示範團購草稿')

    Object.assign(group, {
      name: input.name ?? group.name,
      marketPrice: input.marketPrice ?? group.marketPrice,
      variants: input.variants ? clone(input.variants) : group.variants,
      thresholdUnits: input.thresholdUnits ?? group.thresholdUnits,
      pickupLocation: input.pickupLocation ?? group.pickupLocation,
      expectedArrival: input.expectedArrival ?? group.expectedArrival,
      closeAt: input.closeAt ?? group.closeAt,
      supplierType: input.supplierType ?? group.supplierType,
      supplierName: input.supplierName ?? group.supplierName,
      published: true,
      publishedAt: DEMO_NOW.slice(0, 10),
      status: 'open',
      statusLabel: '進行中',
    })
    return clone(this.withProgress(group))
  }

  updateGroupBuy(groupBuyId: string, input: UpdateDemoGroupBuyInput): DemoGroupBuy {
    const group = this.state.groupBuys.find((item) => item.id === groupBuyId)
    if (!group) throw new Error('找不到這檔團購')

    const name = input.name?.trim()
    const pickupLocation = input.pickupLocation?.trim()
    if (input.name !== undefined && !name) throw new Error('團購名稱不可為空白')
    if (input.marketPrice !== undefined && (!Number.isFinite(input.marketPrice) || input.marketPrice <= 0)) {
      throw new Error('市價必須大於 0')
    }
    if (input.thresholdUnits !== undefined && (!Number.isInteger(input.thresholdUnits) || input.thresholdUnits <= 0)) {
      throw new Error('成團門檻必須是正整數')
    }
    if (input.closeAt !== undefined && !input.closeAt.trim()) throw new Error('截止時間不可為空白')
    if (input.pickupLocation !== undefined && !pickupLocation) throw new Error('取貨地點不可為空白')

    Object.assign(group, {
      ...(name ? { name } : {}),
      ...(input.marketPrice !== undefined ? { marketPrice: input.marketPrice } : {}),
      ...(input.thresholdUnits !== undefined ? { thresholdUnits: input.thresholdUnits } : {}),
      ...(pickupLocation ? { pickupLocation } : {}),
      ...(input.expectedArrival !== undefined ? { expectedArrival: input.expectedArrival } : {}),
      ...(input.closeAt !== undefined ? { closeAt: input.closeAt } : {}),
    })
    return clone(this.withProgress(group))
  }

  closeGroupBuy(groupBuyId: string): DemoGroupBuy {
    const group = this.state.groupBuys.find((item) => item.id === groupBuyId && item.published)
    if (!group) throw new Error('找不到已發布的團購')
    if (group.status !== 'open') throw new Error('這檔團購目前不是收單中')
    group.status = 'closed'
    group.statusLabel = '已結束收單'
    return clone(this.withProgress(group))
  }

  reopenGroupBuy(groupBuyId: string): DemoGroupBuy {
    const group = this.state.groupBuys.find((item) => item.id === groupBuyId && item.published)
    if (!group) throw new Error('找不到已發布的團購')
    if (group.status !== 'closed') throw new Error('只有已結束收單的團購可以重新開放')
    group.status = 'open'
    group.statusLabel = '進行中'
    return clone(this.withProgress(group))
  }

  joinGroupBuy(input: JoinGroupBuyInput): DemoGroupBuy {
    const group = this.state.groupBuys.find((item) => item.id === input.groupBuyId && item.published)
    if (!group) throw new Error('找不到這檔團購')
    if (group.status !== 'open') throw new Error('這檔團購目前不是收單中')
    if (input.quantity < 0) throw new Error('數量不可小於 0')
    const variant = group.variants.find((item) => item.id === input.variantId)
    if (!variant) throw new Error('找不到所選規格')

    const existingIndex = group.joins.findIndex((item) => item.householdId === input.householdId)
    if (input.quantity === 0) {
      if (existingIndex >= 0) group.joins.splice(existingIndex, 1)
      return clone(this.withProgress(group))
    }

    const join: DemoGroupBuyJoin = {
      householdId: input.householdId,
      displayName: input.displayName ?? '王小明',
      householdLabel: input.householdLabel ?? 'A 棟 12F-3',
      variantId: variant.id,
      variantLabel: variant.label,
      quantity: input.quantity,
      amount: variant.price * input.quantity,
      joinedAt: DEMO_NOW.slice(0, 10),
    }
    if (existingIndex >= 0) group.joins.splice(existingIndex, 1, join)
    else group.joins.push(join)

    group.statusLabel = this.withProgress(group).progressUnits >= group.thresholdUnits ? '已成團' : '進行中'
    return clone(this.withProgress(group))
  }

  cancelGroupBuy(groupBuyId: string, householdId: string): DemoGroupBuy | null {
    const group = this.state.groupBuys.find((item) => item.id === groupBuyId && item.published)
    if (!group) return null
    group.joins = group.joins.filter((item) => item.householdId !== householdId)
    return clone(this.withProgress(group))
  }

  listMyOrders(householdId = DEMO_HOUSEHOLD_ID): DemoOrder[] {
    return clone(this.orders().filter((order) => order.householdId === householdId))
  }

  getCommitteeDashboard(): DemoCommitteeDashboard {
    const groupBuys = this.state.groupBuys
      .filter((group) => group.published)
      .map((group) => this.withProgress(group))
    const orders = this.orders()
    const ordersByHousehold = Array.from(new Set(orders.map((order) => order.householdId))).map((householdId) => {
      const items = orders.filter((order) => order.householdId === householdId)
      return {
        householdId,
        householdLabel: items[0]?.householdLabel ?? '',
        displayName: items[0]?.displayName ?? '',
        amount: items.reduce((sum, item) => sum + item.amount, 0),
        items,
      }
    })
    const variants = new Map<string, { variantLabel: string; quantity: number; amount: number }>()
    for (const order of orders) {
      const current = variants.get(order.variantId) ?? { variantLabel: order.variantLabel, quantity: 0, amount: 0 }
      current.quantity += order.quantity
      current.amount += order.amount
      variants.set(order.variantId, current)
    }

    return clone({
      community: this.state.community,
      manager: { displayName: '主委陳建華', householdLabel: 'A 棟 8F-1', term: '2026.07–2027.06' },
      draftGroupBuy: this.state.groupBuys.find((group) => !group.published) ?? null,
      groupBuys,
      orders,
      ordersByHousehold,
      variantSummary: Array.from(variants.values()),
      wiki: {
        queryRanking: Object.entries(this.state.queryCounts)
          .map(([query, count]) => ({ query, count }))
          .sort((a, b) => b.count - a.count),
        latestQueries: this.state.latestQueries,
        unanswered: sortNewest(this.state.unanswered),
      },
      kpis: {
        groupBuyRevenue: orders.reduce((sum, order) => sum + order.amount, 0),
        externalCommission: orders.reduce((sum, order) => {
          const group = groupBuys.find((item) => item.id === order.groupBuyId)
          return sum + (group?.supplierType === 'external' ? order.amount * (group.supplierFeeRate ?? 0) : 0)
        }, 0),
        openGroupBuys: groupBuys.filter((group) => group.status === 'open').length,
        savedForResidents: this.state.subscription.residentSavings,
      },
    })
  }

  getSubscriptionSummary(): DemoSubscriptionSummary {
    return clone(this.state.subscription)
  }

  markUnansweredForWiki(id: string): DemoUnansweredQuestion | null {
    const question = this.state.unanswered.find((item) => item.id === id)
    if (!question) return null
    question.status = 'to_supplement'
    return clone(question)
  }

  resetDemo(): void {
    this.state = clone(COMMUNITY_DEMO_SEED)
  }

  private withProgress(group: DemoGroupBuy): DemoGroupBuy {
    const progressUnits = group.seededProgressUnits + group.joins.reduce((sum, join) => sum + join.quantity, 0)
    return { ...group, progressUnits, joins: clone(group.joins) }
  }

  private orders(): DemoOrder[] {
    const groups = this.state.groupBuys.filter((group) => group.published)
    return groups.flatMap((group) => group.joins.map((join) => ({
      id: `order-${group.id}-${join.householdId}`,
      groupBuyId: group.id,
      groupBuyName: group.name,
      householdId: join.householdId,
      displayName: join.displayName,
      householdLabel: join.householdLabel,
      variantId: join.variantId,
      variantLabel: join.variantLabel,
      quantity: join.quantity,
      amount: join.amount,
      status: 'joined' as const,
      joinedAt: join.joinedAt,
    })))
  }
}

export const communityDemoService = new CommunityDemoService()
