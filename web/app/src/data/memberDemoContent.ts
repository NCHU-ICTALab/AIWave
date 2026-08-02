export type MemberCalendarKind = 'booking' | 'community' | 'reminder'

export interface MemberCalendarItem {
  id: string
  date: string
  title: string
  detail: string
  kind: MemberCalendarKind
}

/**
 * Shared resident calendar projection used by the Wang demo and the regular
 * member calendar.  These are fixed 2026 presentation records, not a claim
 * about a signed-in member's live appointments.
 */
export const MEMBER_CALENDAR_ITEMS: MemberCalendarItem[] = [
  {
    id: 'demo-calendar-repair',
    date: '2026-08-03',
    title: '水電到府檢測',
    detail: '地下室滲水・上午 09:00–11:00',
    kind: 'booking',
  },
  {
    id: 'demo-calendar-father',
    date: '2026-08-08',
    title: '父親節・主動提醒',
    detail: '準備晚餐或傳訊息給爸爸',
    kind: 'reminder',
  },
  {
    id: 'demo-calendar-reservation',
    date: '2026-08-12',
    title: '烤肉區預約',
    detail: '16:00–20:00・A 棟 10F-1 黃先生',
    kind: 'community',
  },
  {
    id: 'demo-calendar-guide',
    date: '2026-08-15',
    title: '中元普渡準備提醒',
    detail: 'Demo 生活指南・先確認家庭需求',
    kind: 'reminder',
  },
  {
    id: 'demo-calendar-cleaning',
    date: '2026-07-25',
    title: '冷氣清洗完成',
    detail: '社區優惠服務・已完成',
    kind: 'booking',
  },
  {
    id: 'demo-calendar-elevator',
    date: '2026-09-04',
    title: 'B 棟電梯保養',
    detail: '09:00–17:00・社區公告',
    kind: 'community',
  },
]

export const MEMBER_CALENDAR_HOLIDAYS: Record<string, string> = {
  '2026-02-28': '和平紀念日',
  '2026-04-04': '兒童節',
  '2026-05-01': '勞動節',
  '2026-08-08': '父親節',
  '2026-10-10': '國慶日',
  '2026-12-25': '行憲紀念日',
}

export interface FatherDayRecommendation {
  id: string
  category: 'service' | 'purchase'
  label: string
  title: string
  detail: string
  priceLabel: string
  to: string
  actionLabel: string
}

/**
 * The proactive Father’s Day message is intentionally concrete: two services
 * and one purchase path.  It gives the resident useful next actions without
 * pretending that an order has already been placed.
 */
export const FATHER_DAY_RECOMMENDATIONS: FatherDayRecommendation[] = [
  {
    id: 'father-day-dining',
    category: 'service',
    label: '服務推薦',
    title: '家庭餐廳／晚餐訂位',
    detail: '想帶爸爸吃飯，可以先比較四人餐廳與可預約時段。',
    priceLabel: '先看方案，再由你確認',
    to: '/user/services/restaurant',
    actionLabel: '看餐廳服務',
  },
  {
    id: 'father-day-cleaning',
    category: 'service',
    label: '服務推薦',
    title: '到府清潔與整理',
    detail: '如果家人要來住，先安排清潔，回家後不用再趕著整理。',
    priceLabel: '社區優惠・可交給 AI 安排',
    to: '/user/services/cleaning',
    actionLabel: '看清潔服務',
  },
  {
    id: 'father-day-gift',
    category: 'purchase',
    label: '可以買什麼',
    title: '水果／點心社區團購',
    detail: '不想臨時找禮物，可以先看管理室取貨的水果或點心團購。',
    priceLabel: '社區價・管理室取貨',
    to: '/user/community#group-buys',
    actionLabel: '看社區團購',
  },
]

export interface LifeCircleServiceCard {
  id: string
  providerId: string
  category: string
  title: string
  detail: string
  priceLabel: string
  to: string
}

/** Services displayed when their provider has a location in the selected area. */
export const LIFE_CIRCLE_SERVICES: LifeCircleServiceCard[] = [
  {
    id: 'life-circle-repair',
    providerId: 'vendor-prince-electric',
    category: '修繕',
    title: '水電修繕・到府檢測',
    detail: '燈具、插座與居家小修繕，可先看可預約時段。',
    priceLabel: 'NT$ 1,200／次起',
    to: '/user/services/repair',
  },
  {
    id: 'life-circle-cleaning',
    providerId: 'vendor-duskin',
    category: '居家清潔',
    title: '冷氣清洗・社區優惠',
    detail: '由生活圈內的清潔服務提供，到府時間需先確認。',
    priceLabel: '社區價 NT$ 3,500 起',
    to: '/user/services/cleaning',
  },
]
