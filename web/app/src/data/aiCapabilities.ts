export interface AICapability {
  id: string
  title: string
  summary: string
  examples: string
  to: string
}

/** Plain-language capability vocabulary shared by the AI page and Wiki copy. */
export const AI_CAPABILITIES: AICapability[] = [
  {
    id: 'community-wiki',
    title: '回答社區問題',
    summary: '查公告、生活公約、垃圾與回收、裝修、包裹及團購取貨規則。',
    examples: '例如：「垃圾車幾點來？」、「週日可以裝修嗎？」',
    to: '/user/community',
  },
  {
    id: 'home-services',
    title: '安排居家服務',
    summary: '整理清潔、修繕、餐廳與到府服務的需求，補齊必要資訊後交你確認。',
    examples: '例如：「爸媽週六要來，先幫我安排清潔和晚餐。」',
    to: '/user/services',
  },
  {
    id: 'community-shopping',
    title: '推薦商品與開團',
    summary: '比較社區價、團購門檻與管理室取貨；任何住戶都可以開團。',
    examples: '例如：「父親節買什麼？茶飲和水果哪個適合一起買？」',
    to: '/user/community/group-buys',
  },
  {
    id: 'life-circle',
    title: '整理生活圈',
    summary: '在虛擬生活圈地圖中找 7-ELEVEN 門市與交貨便、康是美、餐飲外送與到府服務。',
    examples: '例如：「走路 10 分鐘內可以取貨或寄件嗎？」',
    to: '/user/life-circle',
  },
  {
    id: 'calendar',
    title: '安排提醒與行程',
    summary: '把服務、社區活動、民俗節日與國定假日整理進行事曆。',
    examples: '例如：「把父親節晚餐和電梯保養提醒放進行事曆。」',
    to: '/user/calendar',
  },
]
