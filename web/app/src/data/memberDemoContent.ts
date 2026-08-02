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
  '2026-01-01': '元旦・國定假日',
  '2026-02-14': '春節假期',
  '2026-02-16': '除夕・國定假日',
  '2026-02-17': '農曆初一・春節',
  '2026-02-18': '春節假期',
  '2026-02-27': '和平紀念日補假',
  '2026-02-28': '和平紀念日',
  '2026-03-03': '元宵節・民俗節日',
  '2026-04-03': '兒童節補假',
  '2026-04-04': '兒童節',
  '2026-04-05': '清明節',
  '2026-04-06': '清明節補假',
  '2026-05-01': '勞動節',
  '2026-05-10': '母親節・民俗節日',
  '2026-06-19': '端午節',
  '2026-08-08': '父親節',
  '2026-08-19': '七夕・民俗節日',
  '2026-08-27': '中元節・民俗節日',
  '2026-09-25': '中秋節',
  '2026-09-28': '孔子誕辰／教師節',
  '2026-10-09': '國慶日補假',
  '2026-10-10': '國慶日',
  '2026-10-18': '重陽節・民俗節日',
  '2026-10-26': '臺灣光復暨金門古寧頭大捷紀念日',
  '2026-12-22': '冬至・民俗節日',
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

/**
 * Services displayed when their provider has a location in the selected area.
 *
 * `providerId` 必須是目錄投影（`fake_upstreams/partner_seed.py`）真的有的 Provider，
 * 否則卡片永遠不會出現；`to` 也必須是 `router/index.ts` 存在的路由。
 */
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
    id: 'life-circle-711-pickup',
    providerId: 'vendor-711-shop',
    category: '便利服務',
    title: '7-ELEVEN 線上購物中心・門市取貨',
    detail: '走幾分鐘就到的門市，i 預購與日常補給都可以指定這裡取貨。',
    priceLabel: 'i 預購 NT$ 320 起・門市取貨',
    to: '/user/services/provider/vendor-711-shop',
  },
  {
    id: 'life-circle-711-c2c',
    providerId: 'vendor-711-c2c',
    category: '便利服務',
    title: '7-ELEVEN 交貨便・店到店寄件',
    detail: '把東西寄給家人或收社區團購包裹，選同一間門市就好。',
    priceLabel: 'NT$ 60／件起',
    to: '/user/services/provider/vendor-711-c2c',
  },
  {
    id: 'life-circle-cosmed',
    providerId: 'vendor-cosmed',
    category: '健康藥妝',
    title: '康是美・處方箋門市領藥',
    detail: '先上傳處方箋預約，藥局備好再走過去領，不用現場等。',
    priceLabel: '預約免費・藥費依處方',
    to: '/user/services/provider/vendor-cosmed',
  },
  {
    id: 'life-circle-cleaning',
    providerId: 'vendor-duskin',
    category: '居家清潔',
    title: 'DUSKIN 樂清・居家與家電清潔',
    detail: '由生活圈內的清潔服務提供，到府時間需先確認。',
    priceLabel: 'NT$ 3,200／次起',
    to: '/user/services/cleaning',
  },
  {
    id: 'life-circle-foodomo',
    providerId: 'vendor-foodomo',
    category: '餐飲外送',
    title: 'foodomo 社區外送',
    detail: '附近餐飲外送合作點，父親節或家庭聚餐可以交給 AI 先整理。',
    priceLabel: 'NT$ 259／餐起',
    to: '/user/services/restaurant',
  },
  {
    id: 'life-circle-21plus',
    providerId: 'vendor-21plus',
    category: '餐廳訂位',
    title: '21PLUS・家庭聚餐訂位',
    detail: '機車幾分鐘可到的休閒餐廳，可以先看有沒有適合的時段。',
    priceLabel: '訂位免費・餐費現場結',
    to: '/user/services/provider/vendor-21plus',
  },
  {
    id: 'life-circle-blackcat',
    providerId: 'vendor-blackcat',
    category: '宅配寄件',
    title: '黑貓宅急便・到府收件',
    detail: '大件或不方便自己拿去門市的包裹，約時間讓司機來收。',
    priceLabel: 'NT$ 130／件起',
    to: '/user/services/provider/vendor-blackcat',
  },
  {
    id: 'life-circle-smile',
    providerId: 'vendor-smile',
    category: '洗車保養',
    title: '速邁樂 Smile・精緻洗車預約',
    detail: '假日出門前先把車洗好，站點就在生活圈外圈。',
    priceLabel: 'NT$ 450／次起',
    to: '/user/services/provider/vendor-smile',
  },
  {
    id: 'life-circle-iopenmall',
    providerId: 'vendor-iopenmall',
    category: '商城購物',
    title: 'iOPEN Mall・居家小物',
    detail: '社區常買的居家小物，也可以整理成團購一起開團。',
    priceLabel: 'NT$ 690／組起',
    to: '/user/community/group-buys',
  },
  {
    id: 'life-circle-ibon-ticket',
    providerId: 'vendor-ibon-ticket',
    category: '票券',
    title: 'ibon 售票・景點門票',
    detail: '安排週末行程時，可以順手把非劃位票券一起買好。',
    priceLabel: 'NT$ 150／張起',
    to: '/user/services/provider/vendor-ibon-ticket',
  },
]
