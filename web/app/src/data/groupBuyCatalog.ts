import type { DemoGroupBuy, DemoGroupBuyVariant } from '@/domain/communityDemo'

export const GROUP_BUY_CATEGORIES = ['全部', '生鮮食材', '方便料理', '日用百貨', '居家清潔', '節慶送禮'] as const

export type GroupBuyCatalogCategory = (typeof GROUP_BUY_CATEGORIES)[number]

export interface GroupBuyCatalogItem {
  id: string
  name: string
  category: Exclude<GroupBuyCatalogCategory, '全部'>
  badge: string
  description: string
  visual: string
  marketPrice: number
  communityPrice: number
  variants: DemoGroupBuyVariant[]
  thresholdUnits: number
  pickupLocation: string
  expectedArrival: string
  closeAt: string
  supplierType: 'external' | 'group'
  supplierName: string
  sourceGroupBuyId?: string
  progressUnits?: number
  status?: string
  statusLabel?: string
}

/**
 * Catalog cards are frontend-only Demo inventory.  The first rows mirror the
 * community seed; the remaining rows make the browse page feel like a real
 * seasonal shelf without pretending that an external store is connected.
 */
export const GROUP_BUY_CATALOG: GroupBuyCatalogItem[] = [
  {
    id: 'catalog-fresh-pineapple',
    name: '台農 17 號鳳梨',
    category: '生鮮食材',
    badge: '本週熱選',
    description: '夏日當季水果，管理室集中取貨。',
    visual: '🍍',
    marketPrice: 520,
    communityPrice: 450,
    variants: [{ id: 'pineapple-box', label: '一箱', price: 450 }],
    thresholdUnits: 10,
    pickupLocation: '社區管理室',
    expectedArrival: '2026-08-05',
    closeAt: '2026-08-03T21:00',
    supplierType: 'group',
    supplierName: '統一集團食品',
    sourceGroupBuyId: 'group-fruit-2026-07',
    progressUnits: 7,
    status: 'open',
    statusLabel: '進行中',
  },
  {
    id: 'catalog-dubai-chocolate',
    name: '杜拜巧克力',
    category: '節慶送禮',
    badge: '住戶許願',
    description: '主委備妥的示範商品，想買的人可以直接發起開團。',
    visual: '🍫',
    marketPrice: 149,
    communityPrice: 135,
    variants: [
      { id: 'dubai-single', label: '單入', price: 135 },
      { id: 'dubai-six', label: '六入', price: 780 },
    ],
    thresholdUnits: 10,
    pickupLocation: '社區管理室',
    expectedArrival: '2026-08-07',
    closeAt: '2026-08-06T21:00',
    supplierType: 'external',
    supplierName: '可可日常食品',
    sourceGroupBuyId: 'group-dubai-chocolate-2026-08',
    progressUnits: 7,
    status: 'draft',
    statusLabel: '可發起',
  },
  {
    id: 'catalog-fathers-fruit-box',
    name: '父親節鮮果禮盒',
    category: '節慶送禮',
    badge: '父親節推薦',
    description: '給爸爸的當季水果組合，預計週末前送到管理室。',
    visual: '🍎',
    marketPrice: 899,
    communityPrice: 699,
    variants: [{ id: 'fathers-fruit-box', label: '經典禮盒', price: 699 }],
    thresholdUnits: 8,
    pickupLocation: '社區管理室',
    expectedArrival: '2026-08-07',
    closeAt: '2026-08-04T20:00',
    supplierType: 'external',
    supplierName: '好日子鮮果',
  },
  {
    id: 'catalog-family-water',
    name: '天然水家庭箱',
    category: '日用百貨',
    badge: '家庭常備',
    description: '上次社區團購達標商品，想再買可重新發起。',
    visual: '💧',
    marketPrice: 250,
    communityPrice: 220,
    variants: [{ id: 'water-case', label: '12 瓶／箱', price: 220 }],
    thresholdUnits: 10,
    pickupLocation: '社區管理室',
    expectedArrival: '2026-08-14',
    closeAt: '2026-08-10T21:00',
    supplierType: 'group',
    supplierName: '統一集團食品',
    sourceGroupBuyId: 'group-water-2026-06',
    progressUnits: 12,
    status: 'achieved',
    statusLabel: '可再次開團',
  },
  {
    id: 'catalog-cleaning-set',
    name: '日光森林居家清潔組',
    category: '居家清潔',
    badge: '社區回饋價',
    description: '洗衣、廚房與浴室常用清潔用品一次補齊。',
    visual: '🧼',
    marketPrice: 399,
    communityPrice: 349,
    variants: [{ id: 'cleaner-set', label: '清潔組', price: 349 }],
    thresholdUnits: 10,
    pickupLocation: '社區管理室',
    expectedArrival: '2026-08-12',
    closeAt: '2026-08-08T21:00',
    supplierType: 'group',
    supplierName: '統一集團生活',
    sourceGroupBuyId: 'group-cleaner-2026-04',
    progressUnits: 15,
    status: 'completed',
    statusLabel: '可再次開團',
  },
  {
    id: 'catalog-eggs',
    name: '友善飼養洗選蛋',
    category: '生鮮食材',
    badge: '早餐補給',
    description: '家庭早餐常備，一盒 30 顆，社區取貨不用等宅配。',
    visual: '🥚',
    marketPrice: 245,
    communityPrice: 199,
    variants: [{ id: 'eggs-tray', label: '30 顆／盒', price: 199 }],
    thresholdUnits: 12,
    pickupLocation: '社區管理室',
    expectedArrival: '2026-08-15',
    closeAt: '2026-08-11T21:00',
    supplierType: 'external',
    supplierName: '日常好食農場',
  },
  {
    id: 'catalog-dishwasher-tabs',
    name: '洗碗機清潔錠補充包',
    category: '方便料理',
    badge: '免搬大包裝',
    description: '家庭用量友善的補充包，達標後由管理室統一收貨。',
    visual: '🫧',
    marketPrice: 420,
    communityPrice: 360,
    variants: [{ id: 'dishwasher-tabs', label: '60 顆／包', price: 360 }],
    thresholdUnits: 8,
    pickupLocation: '社區管理室',
    expectedArrival: '2026-08-18',
    closeAt: '2026-08-13T21:00',
    supplierType: 'external',
    supplierName: '好日子居家',
  },
]

export function catalogItemFromGroup(group: DemoGroupBuy): GroupBuyCatalogItem {
  return {
    id: `catalog-${group.id}`,
    name: group.name,
    category: group.name.includes('清潔') ? '居家清潔' : group.name.includes('水') ? '日用百貨' : '生鮮食材',
    badge: group.status === 'open' ? '正在收單' : '歷史團購',
    description: group.description,
    visual: group.name.includes('巧克力') ? '🍫' : group.name.includes('水') ? '💧' : '📦',
    marketPrice: group.marketPrice,
    communityPrice: group.variants[0]?.price ?? group.marketPrice,
    variants: group.variants,
    thresholdUnits: group.thresholdUnits,
    pickupLocation: group.pickupLocation,
    expectedArrival: group.expectedArrival,
    closeAt: group.closeAt.slice(0, 16),
    supplierType: group.supplierType,
    supplierName: group.supplierName,
    sourceGroupBuyId: group.id,
    progressUnits: group.progressUnits,
    status: group.status,
    statusLabel: group.statusLabel,
  }
}
