import type {
  CommunityProfile,
  DemoAnnouncement,
  DemoCommunityAnswer,
  DemoFacilityReservation,
  DemoGroupBuy,
  DemoMaintenance,
  DemoPackage,
  DemoRepair,
  DemoServiceOffer,
  DemoSubscriptionSummary,
  DemoUnansweredQuestion,
  DemoWikiEntry,
} from '@/domain/communityDemo'

export interface CommunityDemoSeed {
  community: CommunityProfile
  announcements: DemoAnnouncement[]
  packages: DemoPackage[]
  repairs: DemoRepair[]
  maintenance: DemoMaintenance[]
  reservations: DemoFacilityReservation[]
  serviceOffers: DemoServiceOffer[]
  groupBuys: DemoGroupBuy[]
  wiki: DemoWikiEntry[]
  queryCounts: Record<string, number>
  latestQueries: string[]
  unanswered: DemoUnansweredQuestion[]
  subscription: DemoSubscriptionSummary
}

export const DEMO_NOW = '2026-08-02T10:00:00+08:00'

const community: CommunityProfile = {
  id: 'community-sunlight-forest',
  name: '日光森林社區',
  address: '新北市板橋區文化路二段 168 號',
  builtYear: 2016,
  buildings: 'A、B 兩棟',
  floors: '地上 15 層、地下 2 層',
  households: 112,
  parking: '平面 78 席、機械 24 席',
  evChargers: 4,
  facilities: ['交誼廳', '健身房', '閱覽室', '中庭花園', '頂樓曬衣場', '烤肉區'],
  propertyManager: '安宏物業管理股份有限公司',
  managementHours: '07:00–22:00',
}

const announcements: DemoAnnouncement[] = [
  {
    id: 'announcement-elevator-july',
    title: '電梯保養通知｜8/4 A 棟、8/5 B 棟',
    body: '電梯將分棟輪流保養，施工期間請改搭另一部電梯，造成不便敬請見諒。',
    publishedAt: '2026-07-30',
    category: 'maintenance',
  },
  {
    id: 'announcement-group-buy-arrival',
    title: '團購到貨通知｜台農 17 號鳳梨',
    body: '本週團購商品已送達管理室，請於管理室服務時間內完成取貨。',
    publishedAt: '2026-07-24',
    category: 'group-buy',
  },
  {
    id: 'announcement-package-overdue',
    title: '包裹逾期未領提醒',
    body: '管理室仍有逾期包裹，請住戶於本週五前完成領取，以免退回寄件人。',
    publishedAt: '2026-07-17',
    category: 'notice',
  },
  {
    id: 'announcement-typhoon',
    title: '颱風注意事項',
    body: '請收妥陽台物品、關閉門窗；公共區域若有積水或掉落物，請立即通知管理室。',
    publishedAt: '2026-07-10',
    category: 'notice',
  },
  {
    id: 'announcement-mechanical-parking',
    title: '機械車位維修公告｜B2-18 至 B2-24',
    body: '機械車位設備將於 6/30 09:00–17:00 維修，請相關車位住戶提前移車。',
    publishedAt: '2026-06-29',
    category: 'maintenance',
  },
  {
    id: 'announcement-bulky-waste',
    title: '大型家具不得棄置於回收區',
    body: '大型家具請先向管理室登記清運，勿直接放置在 B1 回收區或垃圾集中區。',
    publishedAt: '2026-06-12',
    category: 'notice',
  },
  {
    id: 'announcement-owner-meeting',
    title: '區分所有權人會議通知',
    body: '年度區分所有權人會議預定於 6/6 19:00 在一樓交誼廳召開，請準時出席。',
    publishedAt: '2026-05-28',
    category: 'meeting',
  },
  {
    id: 'announcement-roof-waterproof',
    title: '頂樓防水施工提醒',
    body: '頂樓防水工程進入收尾階段，請勿進入施工範圍，曬衣場將暫停使用。',
    publishedAt: '2026-05-16',
    category: 'maintenance',
  },
]

const packages: DemoPackage[] = [
  {
    id: 'package-blackcat-8842', carrier: '黑貓宅急便', arrivedAt: '2026-08-01 14:20',
    trackingLast4: '8842', pickupCode: 'A7K9', status: 'waiting',
  },
  {
    id: 'package-711-3217', carrier: '7-ELEVEN 交貨便', arrivedAt: '2026-08-02 08:45',
    trackingLast4: '3217', pickupCode: 'Q2M4', status: 'waiting',
  },
]

const repairs: DemoRepair[] = [
  {
    id: 'repair-001', subject: 'A 棟 3F 走廊燈不亮', location: 'A 棟 3F', reportedAt: '2026-07-29',
    status: 'received', statusLabel: '已受理', note: '管理室已登錄，等待物業安排現場確認。',
  },
  {
    id: 'repair-002', subject: '地下室滲水', location: 'B2 停車區 12 號柱', reportedAt: '2026-07-27',
    status: 'assigned', statusLabel: '已派工', note: '已安排水電廠商於 8/3 上午到場。',
  },
  {
    id: 'repair-003', subject: 'B 棟大門磁扣感應不良', location: 'B 棟 1F', reportedAt: '2026-07-25',
    status: 'in_progress', statusLabel: '處理中', note: '已更換感應器，正在測試夜間門禁。',
  },
  {
    id: 'repair-004', subject: '中庭水管漏水', location: '中庭花園東側', reportedAt: '2026-07-18',
    status: 'completed', statusLabel: '已完成', note: '已於 7/19 完成接管並清理現場。',
  },
]

const maintenance: DemoMaintenance[] = [
  { id: 'maintenance-elevator', name: '電梯', lastServicedAt: '2026-07-05', nextDueAt: '2026-08-04', status: 'on_track', statusLabel: '即將保養' },
  { id: 'maintenance-fire', name: '消防設備', lastServicedAt: '2026-06-20', nextDueAt: '2026-09-20', status: 'on_track', statusLabel: '正常' },
  { id: 'maintenance-water-tank', name: '水塔', lastServicedAt: '2026-07-12', nextDueAt: '2026-10-12', status: 'on_track', statusLabel: '正常' },
  { id: 'maintenance-generator', name: '發電機', lastServicedAt: '2026-05-15', nextDueAt: '2026-08-15', status: 'on_track', statusLabel: '正常' },
  { id: 'maintenance-roof', name: '屋頂防水', lastServicedAt: '2026-01-31', nextDueAt: '2026-07-31', status: 'overdue', statusLabel: '已逾期，請安排檢查' },
]

const reservations: DemoFacilityReservation[] = [
  { id: 'reservation-001', facility: '交誼廳', date: '2026-08-04', time: '19:00–21:00', resident: 'A 棟 6F-2 林小姐' },
  { id: 'reservation-002', facility: '健身房', date: '2026-08-08', time: '10:00–12:00', resident: 'B 棟 3F-1 陳先生' },
  { id: 'reservation-003', facility: '烤肉區', date: '2026-08-12', time: '16:00–20:00', resident: 'A 棟 10F-1 黃先生' },
]

const serviceOffers: DemoServiceOffer[] = [
  {
    id: 'service-aircon-cleaning', name: '冷氣清洗', marketPrice: 3800, communityPrice: 3500,
    note: '社區訂閱回饋價，每戶都能直接看到價差來源。',
  },
]

const fruitGroup: DemoGroupBuy = {
  id: 'group-fruit-2026-07',
  name: '台農 17 號鳳梨',
  description: '夏日當季水果，管理室集中取貨。',
  marketPrice: 520,
  variants: [{ id: 'pineapple-box', label: '一箱', price: 450 }],
  thresholdUnits: 10,
  seededProgressUnits: 0,
  progressUnits: 7,
  pickupLocation: '社區管理室',
  expectedArrival: '2026-08-05',
  closeAt: '2026-08-03T21:00:00+08:00',
  supplierType: 'group',
  supplierName: '統一集團食品',
  supplierFeeRate: 0,
  status: 'open',
  statusLabel: '進行中',
  published: true,
  publishedAt: '2026-07-28',
  joins: [
    { householdId: 'household-demo-a', displayName: '王先生', householdLabel: 'A 棟 8F-2', variantId: 'pineapple-box', variantLabel: '一箱', quantity: 2, amount: 900, joinedAt: '2026-07-29' },
    { householdId: 'household-demo-b', displayName: '陳小姐', householdLabel: 'B 棟 3F-1', variantId: 'pineapple-box', variantLabel: '一箱', quantity: 3, amount: 1350, joinedAt: '2026-07-30' },
    { householdId: 'household-demo-c', displayName: '林先生', householdLabel: 'A 棟 10F-1', variantId: 'pineapple-box', variantLabel: '一箱', quantity: 2, amount: 900, joinedAt: '2026-07-31' },
  ],
}

const chocolateGroup: DemoGroupBuy = {
  id: 'group-dubai-chocolate-2026-08',
  name: '杜拜巧克力',
  description: '主委備妥的示範團購，發布後固定從 7/10 開始累積。',
  marketPrice: 149,
  variants: [
    { id: 'dubai-single', label: '單入', price: 135 },
    { id: 'dubai-six', label: '六入', price: 780 },
  ],
  thresholdUnits: 10,
  seededProgressUnits: 7,
  progressUnits: 7,
  pickupLocation: '社區管理室',
  expectedArrival: '2026-08-07',
  closeAt: '2026-08-06T21:00:00+08:00',
  supplierType: 'external',
  supplierName: '可可日常食品',
  supplierFeeRate: 0.03,
  status: 'draft',
  statusLabel: '待發布',
  published: false,
  publishedAt: null,
  joins: [],
}

const groupHistory: DemoGroupBuy[] = [
  fruitGroup,
  {
    id: 'group-water-2026-06', name: '天然水家庭箱', description: '已達成門檻。', marketPrice: 250,
    variants: [{ id: 'water-case', label: '12 瓶／箱', price: 220 }], thresholdUnits: 10, seededProgressUnits: 12, progressUnits: 12,
    pickupLocation: '社區管理室', expectedArrival: '2026-06-22', closeAt: '2026-06-18T21:00:00+08:00', supplierType: 'group', supplierName: '統一集團食品', supplierFeeRate: 0,
    status: 'achieved', statusLabel: '已成團', published: true, publishedAt: '2026-06-10', joins: [],
  },
  {
    id: 'group-rice-2026-05', name: '池上米 10 斤', description: '已到貨，等待住戶取貨。', marketPrice: 680,
    variants: [{ id: 'rice-bag', label: '10 斤／袋', price: 620 }], thresholdUnits: 8, seededProgressUnits: 9, progressUnits: 9,
    pickupLocation: '社區管理室', expectedArrival: '2026-05-24', closeAt: '2026-05-20T21:00:00+08:00', supplierType: 'external', supplierName: '米鄉農產', supplierFeeRate: 0.03,
    status: 'pickup', statusLabel: '可取貨', published: true, publishedAt: '2026-05-12', joins: [],
  },
  {
    id: 'group-cleaner-2026-04', name: '居家清潔組', description: '團購已完成。', marketPrice: 399,
    variants: [{ id: 'cleaner-set', label: '清潔組', price: 349 }], thresholdUnits: 10, seededProgressUnits: 15, progressUnits: 15,
    pickupLocation: '社區管理室', expectedArrival: '2026-04-20', closeAt: '2026-04-15T21:00:00+08:00', supplierType: 'group', supplierName: '統一集團生活', supplierFeeRate: 0,
    status: 'completed', statusLabel: '已完成', published: true, publishedAt: '2026-04-05', joins: [],
  },
  {
    id: 'group-strawberry-2026-03', name: '草莓禮盒', description: '未達最低成團單位。', marketPrice: 980,
    variants: [{ id: 'strawberry-box', label: '一盒', price: 880 }], thresholdUnits: 10, seededProgressUnits: 6, progressUnits: 6,
    pickupLocation: '社區管理室', expectedArrival: '2026-03-18', closeAt: '2026-03-15T21:00:00+08:00', supplierType: 'external', supplierName: '莓好農場', supplierFeeRate: 0.03,
    status: 'failed', statusLabel: '未達門檻', published: true, publishedAt: '2026-03-05', joins: [],
  },
]

const wiki: DemoWikiEntry[] = [
  {
    id: 'wiki-garbage', category: '垃圾與回收', title: '垃圾車與垃圾集中區', keywords: ['垃圾車', '垃圾', '回收', '丟垃圾'],
    shortAnswer: '週一至週六 19:30–20:00，地點在 B1 垃圾集中區；週日不收。',
    fullRule: '一般垃圾請配合垃圾車時間集中至 B1 垃圾集中區；週一至週六 19:30–20:00 收運，週日不收。大型家具需先向管理室登記清運。',
    source: '社區生活公約第 8 條', updatedAt: '2026-07-15', relatedQuestions: ['回收物要怎麼分類？', '大型家具要丟哪裡？', '垃圾車下雨天還會來嗎？'],
  },
  {
    id: 'wiki-renovation', category: '裝修', title: '裝修施工時間', keywords: ['裝修', '施工', '假日', '週末'],
    shortAnswer: '週六僅限 09:00–12:00；週日及國定假日禁止施工。',
    fullRule: '週一至週五 09:00–12:00、14:00–17:00；週六 09:00–12:00；週日及國定假日禁止施工。施工前請向管理室登記。',
    source: '社區裝修管理辦法第 4 條', updatedAt: '2026-06-20', relatedQuestions: ['裝修需要申請嗎？', '可以使用電梯載材料嗎？', '施工噪音怎麼反映？'],
  },
  {
    id: 'wiki-visitor-parking', category: '訪客停車', title: '訪客臨停', keywords: ['訪客', '停車', '臨停'],
    shortAnswer: '訪客車輛請先至管理室登記，臨停以 4 小時為限。', fullRule: '訪客車輛請由住戶陪同或事先通知管理室登記，停放於訪客車位，單次以 4 小時為限。', source: '社區停車管理辦法第 6 條', updatedAt: '2026-06-08', relatedQuestions: ['訪客車位在哪裡？', '過夜停車要登記嗎？', '機械車位可以停訪客車嗎？'],
  },
  {
    id: 'wiki-keycard', category: '磁扣', title: '磁扣遺失與申請', keywords: ['磁扣', '門禁', '感應'],
    shortAnswer: '磁扣遺失請立即通知管理室停用，補發每枚工本費 NT$200。', fullRule: '磁扣遺失、損壞或感應異常，請於管理室服務時間辦理停用與補發；補發每枚 NT$200。', source: '門禁設備使用須知', updatedAt: '2026-05-30', relatedQuestions: ['磁扣可以借人嗎？', '大門感應失效怎麼辦？', '如何申請訪客磁扣？'],
  },
  {
    id: 'wiki-package', category: '包裹', title: '包裹領取', keywords: ['包裹', '取件', '管理室'],
    shortAnswer: '請於管理室 07:00–22:00 取件，逾期包裹會通知住戶領回。', fullRule: '包裹到達後由管理室代收，住戶請於 07:00–22:00 持取件碼領取；冷藏與逾期包裹會另行通知。', source: '社區包裹代收辦法', updatedAt: '2026-07-01', relatedQuestions: ['包裹可以請家人代領嗎？', '取件碼在哪裡看？', '冷藏包裹如何處理？'],
  },
  {
    id: 'wiki-pets', category: '寵物', title: '寵物公共區域規範', keywords: ['寵物', '狗', '貓'],
    shortAnswer: '寵物進出公共區域請使用牽繩或提籠，並由飼主清理排泄物。', fullRule: '寵物可搭乘電梯但須使用牽繩或提籠；飼主應避開兒童遊戲區並即時清理排泄物。', source: '社區生活公約第 12 條', updatedAt: '2026-05-20', relatedQuestions: ['寵物可以進健身房嗎？', '公共區域需要戴嘴套嗎？', '寵物吠叫怎麼反映？'],
  },
  {
    id: 'wiki-fee', category: '管理費', title: '管理費繳費', keywords: ['管理費', '繳費', '帳單'],
    shortAnswer: '管理費每月 10 日前繳交，可透過管理室或指定繳費方式辦理。', fullRule: '管理費帳單於每月初放入信箱，請於每月 10 日前完成繳費；逾期將依規約計收滯納金。', source: '社區規約第 18 條', updatedAt: '2026-04-30', relatedQuestions: ['管理費可以刷卡嗎？', '忘記繳管理費怎麼辦？', '管理費包含哪些服務？'],
  },
  {
    id: 'wiki-facility', category: '公設', title: '公設預約', keywords: ['公設', '預約', '交誼廳', '健身房'],
    shortAnswer: '公設請於住戶 App 預約，使用後恢復場地整潔。', fullRule: '交誼廳、烤肉區等公設須事前預約；健身房與閱覽室依現場規範使用，離場前請關閉設備。', source: '公共設施使用規則', updatedAt: '2026-06-05', relatedQuestions: ['烤肉區怎麼預約？', '公設可以帶訪客嗎？', '預約後臨時取消怎麼辦？'],
  },
  {
    id: 'wiki-charger', category: '充電樁', title: '電動車充電樁', keywords: ['充電樁', '電動車', '充電'],
    shortAnswer: '社區共有 4 席充電樁，使用前請在管理室登記車位與時段。', fullRule: '充電樁位於 B2，住戶使用前請登記車號與預計時段，充電完成後請於 30 分鐘內移車。', source: '電動車充電設備使用辦法', updatedAt: '2026-05-12', relatedQuestions: ['充電樁如何計費？', '訪客可以使用充電樁嗎？', '充電完成忘記移車怎麼辦？'],
  },
  {
    id: 'wiki-emergency', category: '緊急聯絡', title: '緊急聯絡方式', keywords: ['緊急', '聯絡', '管理室', '電話'],
    shortAnswer: '管理室服務時間為 07:00–22:00，緊急狀況請先撥 119 或 110。', fullRule: '管理室 07:00–22:00 可協助社區事件；火災、急病、治安等緊急狀況請先撥 119 或 110，再通知管理室。', source: '社區緊急應變卡', updatedAt: '2026-07-05', relatedQuestions: ['管理室電話是多少？', '停電要通知誰？', '瓦斯異味怎麼辦？'],
  },
  {
    id: 'wiki-elevator-trapped', category: '電梯受困', title: '電梯受困處理', keywords: ['電梯', '受困', '故障'],
    shortAnswer: '請按緊急通話鈕並保持冷靜，不要自行撬門；管理室會立即通報。', fullRule: '電梯受困時請按緊急通話鈕、說明所在電梯與人數，等待專業人員處理，切勿自行撬門或攀爬。', source: '電梯安全使用須知', updatedAt: '2026-07-08', relatedQuestions: ['電梯停在樓層中間怎麼辦？', '停電時電梯會怎樣？', '如何回報電梯異音？'],
  },
  {
    id: 'wiki-group-pickup', category: '團購取貨', title: '團購取貨', keywords: ['團購', '取貨', '到貨'],
    shortAnswer: '團購到貨後會公告，請於管理室服務時間 07:00–22:00 取貨。', fullRule: '團購商品統一送至管理室，住戶可在團購頁查看到貨公告與取貨期限；逾期請先聯繫管理室。', source: '社區團購取貨須知', updatedAt: '2026-07-22', relatedQuestions: ['團購可以請人代領嗎？', '團購商品會冷藏嗎？', '跟團後可以取消嗎？'],
  },
]

export const COMMUNITY_DEMO_SEED: CommunityDemoSeed = {
  community,
  announcements,
  packages,
  repairs,
  maintenance,
  reservations,
  serviceOffers,
  groupBuys: [...groupHistory, chocolateGroup],
  wiki,
  queryCounts: {
    垃圾車幾點來: 18,
    裝修可以假日施工嗎: 12,
    團購取貨時間: 8,
    公設怎麼預約: 6,
  },
  latestQueries: ['團購取貨時間', '裝修可以假日施工嗎', '垃圾車幾點來'],
  unanswered: [
    { id: 'unanswered-001', query: '社區可以養鴿子嗎？', householdId: 'household-demo-a', askedAt: '2026-07-31', status: 'new' },
  ],
  subscription: {
    householdCount: 112,
    standardPlanLabel: '標準方案：101–200 戶',
    standardMonthlyFee: 12000,
    trialMonthlyFee: 6000,
    residentSavings: 18420,
    netBenefit: 12420,
    externalSupplierFeeRate: 0.03,
    groupSupplierFeeRate: 0,
    trialMonths: '可免費試用 3–6 個月',
    hardware: '零硬體、免施工',
  },
}

/** Used by tests and the typed service; the answer shape stays in the domain boundary. */
export type DemoAnswerSeed = DemoCommunityAnswer
