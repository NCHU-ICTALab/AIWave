<script setup lang="ts">
import { computed, ref } from 'vue'

import { GROUP_BUY_CATALOG } from '@/data/groupBuyCatalog'

interface TickerItem {
  id: string
  label: string
  title: string
  detail: string
  to: string
}

/** 社區公告是前端 Demo 內容，不是後端公告 API 的投影。 */
const ANNOUNCEMENTS: TickerItem[] = [
  {
    id: 'ticker-elevator',
    label: '社區公告',
    title: '8/4（一）B 棟電梯保養',
    detail: '09:00–17:00 分時施工，請預留通行時間。',
    to: '/user/community',
  },
  {
    id: 'ticker-water',
    label: '社區公告',
    title: '8/6（三）09:00–12:00 蓄水池清洗停水',
    detail: '請提前儲水，當日管理室提供備用飲用水。',
    to: '/user/community',
  },
  {
    id: 'ticker-pickup',
    label: '生活圈',
    title: '步行 10 分鐘有 7-ELEVEN 與交貨便',
    detail: '門市取貨、寄件與康是美都在生活圈範圍內。',
    to: '/user/life-circle',
  },
  {
    id: 'ticker-father-day',
    label: 'AI 推薦',
    title: '父親節（8/8）服務整理',
    detail: '清潔、餐廳與禮盒團購一次看，先確認再安排。',
    to: '/user/assistant',
  },
]

const money = (value: number) => `NT$ ${value.toLocaleString('zh-TW')}`
const dateLabel = (value: string) => value.slice(5, 10).replace('-', '/')

/**
 * 熱銷團購推播直接從團購目錄算出來，而不是另外寫一份文案。
 * 手寫文案會跟商品頁的價格與成團進度漂移，跑馬燈就會說出頁面上不成立的話。
 */
const promotions = computed<TickerItem[]>(() => GROUP_BUY_CATALOG
  .filter((item) => item.status === 'open' && item.progressUnits !== undefined)
  .sort((a, b) => (b.progressUnits ?? 0) / b.thresholdUnits - (a.progressUnits ?? 0) / a.thresholdUnits)
  .slice(0, 2)
  .map((item) => {
    const remaining = Math.max(0, item.thresholdUnits - (item.progressUnits ?? 0))
    return {
      id: `ticker-${item.id}`,
      label: '熱銷團購',
      title: `${item.name}・社區價 ${money(item.communityPrice)}`,
      detail: remaining
        ? `差 ${remaining} 件成團，${dateLabel(item.expectedArrival)} 到貨後於${item.pickupLocation}取貨。`
        : `已達成團門檻，${dateLabel(item.expectedArrival)} 到貨後於${item.pickupLocation}取貨。`,
      to: '/user/community/group-buys',
    }
  }))

/** 公告與團購交錯排列，跑馬燈才不會連續播兩則同類型。 */
const items = computed<TickerItem[]>(() => {
  const merged: TickerItem[] = []
  const longest = Math.max(ANNOUNCEMENTS.length, promotions.value.length)
  for (let index = 0; index < longest; index += 1) {
    if (ANNOUNCEMENTS[index]) merged.push(ANNOUNCEMENTS[index])
    if (promotions.value[index]) merged.push(promotions.value[index])
  }
  return merged
})

const paused = ref(false)
</script>

<template>
  <section class="community-ticker" data-testid="community-ticker" aria-labelledby="community-ticker-title">
    <div class="community-ticker-label">
      <span class="community-ticker-mark" aria-hidden="true">↗</span>
      <div>
        <p class="eyebrow">COMMUNITY NOW</p>
        <h2 id="community-ticker-title">社區快訊</h2>
      </div>
    </div>
    <div class="community-ticker-viewport">
      <div class="community-ticker-track" :class="{ paused }">
        <div class="community-ticker-sequence">
          <RouterLink v-for="item in items" :key="item.id" class="community-ticker-item" :to="item.to">
            <span class="community-ticker-item-label">{{ item.label }}</span>
            <strong>{{ item.title }}</strong>
            <span>{{ item.detail }}</span>
          </RouterLink>
        </div>
        <div class="community-ticker-sequence community-ticker-sequence-copy" aria-hidden="true">
          <span v-for="item in items" :key="`copy-${item.id}`" class="community-ticker-item">
            <span class="community-ticker-item-label">{{ item.label }}</span>
            <strong>{{ item.title }}</strong>
            <span>{{ item.detail }}</span>
          </span>
        </div>
      </div>
    </div>
    <button
      class="community-ticker-toggle"
      type="button"
      :aria-pressed="paused"
      :aria-label="paused ? '繼續播放社區快訊' : '暫停播放社區快訊'"
      @click="paused = !paused"
    >
      {{ paused ? '播放' : '暫停' }}
    </button>
  </section>
</template>

<style scoped>
.community-ticker {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: .8rem;
  align-items: center;
  padding: .7rem .85rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md, 18px);
  background: var(--yellow, #fde68a);
  box-shadow: 3px 3px 0 var(--ink);
}
.community-ticker-label {
  display: flex;
  gap: .45rem;
  align-items: center;
  min-width: 8rem;
}
.community-ticker-label p,
.community-ticker-label h2 {
  margin: 0;
}
.community-ticker-label h2 {
  font-size: 1rem;
}
.community-ticker-mark {
  display: grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  border: 2px solid var(--ink);
  border-radius: 50%;
  background: var(--surface);
  font-size: 1.2rem;
  font-weight: 900;
}
.community-ticker-viewport {
  min-width: 0;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--ink) 35%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--surface) 72%, transparent);
}
.community-ticker-track {
  display: flex;
  width: max-content;
  animation: community-ticker-scroll 34s linear infinite;
}
.community-ticker-track.paused {
  animation-play-state: paused;
}
.community-ticker-sequence {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
}
.community-ticker-item {
  display: inline-flex;
  align-items: center;
  gap: .45rem;
  min-height: 2.6rem;
  padding: .35rem 1rem;
  color: var(--ink);
  font-size: .78rem;
  text-decoration: none;
  white-space: nowrap;
}
.community-ticker-item:hover,
.community-ticker-item:focus-visible {
  background: var(--surface);
  text-decoration: underline;
}
.community-ticker-item-label {
  padding: .14rem .35rem;
  border: 1px solid var(--ink);
  border-radius: 999px;
  background: var(--mint);
  font-size: .65rem;
  font-weight: 900;
}
.community-ticker-item > span:last-child {
  color: var(--muted);
}
.community-ticker-sequence-copy {
  border-left: 1px dashed var(--ink);
}
.community-ticker-toggle {
  min-height: 2.4rem;
  padding: .25rem .65rem;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--surface);
  color: var(--ink);
  font: inherit;
  font-size: .75rem;
  font-weight: 900;
}
.community-ticker-toggle:hover,
.community-ticker-toggle:focus-visible {
  background: var(--mint);
}
@keyframes community-ticker-scroll {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}
@media (prefers-reduced-motion: reduce) {
  .community-ticker-track { animation: none; }
}
@media (max-width: 720px) {
  .community-ticker {
    grid-template-columns: 1fr auto;
  }
  .community-ticker-label { min-width: 0; }
  .community-ticker-viewport { grid-column: 1 / -1; grid-row: 2; }
}
</style>
