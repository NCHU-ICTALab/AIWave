import { vi } from 'vitest'

import type { ServiceCatalogClient } from '@/api/serviceCatalogClient'
import type { ServiceAnswers, ServiceQuote } from '@/domain/serviceIntake'

import {
  catalogForms,
  catalogServices,
  insightAccounts,
  insightRecommendations,
  insightSummary,
  insightTrail,
  todayBriefing,
} from './catalog.generated'

/**
 * 後端試算規則的測試替身。真正的規則在 `core/services/pricing.py`，並由後端測試把關；
 * 這裡只模擬前端測試會用到的情境，讓元件測試不必真的起後端。
 */
export function fakeQuote(serviceId: string, answers: ServiceAnswers = {}): ServiceQuote {
  const base: Record<string, number> = {
    'service-washer': 1600, 'service-aircon': 1800, 'service-cleaning': 1200,
    'service-housework': 900, 'service-repair': 600, 'service-shipping': 130,
    'service-restaurant': 0, 'service-delivery': 199, 'service-shopping': 699,
  }
  const quantity = Math.max(1, Number(answers.quantity) || 1)
  let baseAmount = base[serviceId] ?? 0
  if (serviceId === 'service-washer' || serviceId === 'service-aircon') baseAmount *= quantity
  if (serviceId === 'service-cleaning') baseAmount += ({ medium: 500, large: 1100 } as Record<string, number>)[String(answers.homeSize)] ?? 0
  if (serviceId === 'service-housework') baseAmount = ({ '2': 900, '3': 1200, '4': 1500 } as Record<string, number>)[String(answers.hours)] ?? 900
  if (serviceId === 'service-shipping') baseAmount = (({ small: 130, medium: 170, large: 210 } as Record<string, number>)[String(answers.parcelSize)] ?? 130) + (answers.speed === 'chilled' ? 80 : 0)
  if (serviceId === 'service-delivery') baseAmount = ({ light: 199, warm: 259, family: 499 } as Record<string, number>)[String(answers.meal)] ?? 199
  if (serviceId === 'service-shopping') baseAmount = ({ restock: 699, coffee: 240, snacks: 399 } as Record<string, number>)[String(answers.bundle)] ?? 699

  const empty = { baseAmount, couponDiscount: 0, pointDiscount: 0, paymentDiscount: 0, finalAmount: Math.max(0, baseAmount), ruleSummary: [] as string[] }
  if (serviceId !== 'service-shopping') return empty

  const bundle = String(answers.bundle)
  const ruleSummary: string[] = []
  const couponDiscount = answers.coupon === 'apply' ? ({ restock: 50, coffee: 30, snacks: 40 } as Record<string, number>)[bundle] ?? 50 : 0
  if (couponDiscount) ruleSummary.push(`${({ restock: '日用品補貨券', coffee: '咖啡券組合優惠', snacks: '零食分享券' } as Record<string, string>)[bundle] ?? '補貨券'} −NT$ ${couponDiscount}`)
  const pointDiscount = Math.min(answers.points === '50' ? 50 : 0, Math.max(0, baseAmount - couponDiscount))
  if (pointDiscount) ruleSummary.push(`OPENPOINT 折抵 ${pointDiscount} 點`)
  const paymentDiscount = answers.payment === 'icash-pay' ? 20 : 0
  if (paymentDiscount) ruleSummary.push(`icash Pay 加碼 −NT$ ${paymentDiscount}`)

  return {
    baseAmount, couponDiscount, pointDiscount, paymentDiscount,
    finalAmount: Math.max(0, baseAmount - couponDiscount - pointDiscount - paymentDiscount),
    ruleSummary,
  }
}

/** 可注入 store 的假 client（node 環境測試用）。 */
export function createFakeCatalogClient(): ServiceCatalogClient {
  return {
    listServices: async () => catalogServices,
    getServiceForm: async (serviceId) => {
      const form = catalogForms[serviceId]
      if (!form) throw new Error(`no fixture for ${serviceId}`)
      return form
    },
    quote: async (serviceId, answers) => fakeQuote(serviceId, answers),
  }
}

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

/**
 * 為掛載元件的測試安裝 fetch 契約（涵蓋服務目錄／題組／試算／諮詢單）。
 * `extra` 可補上該測試專屬的路由。
 */
export function stubCatalogFetch(extra?: (url: string, init?: RequestInit) => Response | undefined) {
  const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const custom = extra?.(url, init)
    if (custom) return custom

    if (url.endsWith('/api/v1/services')) return json({ data: catalogServices })

    const formMatch = url.match(/\/api\/v1\/services\/([^/]+)\/form$/)
    if (formMatch) {
      const form = catalogForms[formMatch[1]!]
      return form ? json({ data: form }) : new Response('{}', { status: 404 })
    }

    const quoteMatch = url.match(/\/api\/v1\/services\/([^/]+)\/quote$/)
    if (quoteMatch) {
      const answers = init?.body ? (JSON.parse(String(init.body)) as { answers?: ServiceAnswers }).answers ?? {} : {}
      return json({ data: fakeQuote(quoteMatch[1]!, answers) })
    }

    if (url.endsWith('/api/v1/inquiries')) return json({ data: [] })
    // 廠商工作台預設為空；需要內容的測試自行以 extra 覆寫
    if (url.endsWith('/api/v1/vendor/workload')) {
      return json({ data: { pendingQuote: [], awaitingResident: [], scheduled: [] } })
    }

    // 今日摘要（首頁「我現在該做什麼」）
    if (url.includes('/api/v1/today/')) {
      return json({ data: url.includes('/today/none') ? [] : todayBriefing })
    }

    // 個人洞察（今日生活中心的數字與推薦）
    if (url.includes('/api/v1/insights/')) {
      if (url.endsWith('/accounts')) return json({ data: insightAccounts })
      if (url.includes('/summary')) return json({ data: insightSummary })
      if (url.includes('/recommendations')) return json({ data: insightRecommendations })
      if (url.includes('/trail')) return json({ data: insightTrail })
    }

    return new Response('{}', { status: 404 })
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

export { catalogForms, catalogServices }
