<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  MEMBER_CALENDAR_HOLIDAYS,
  MEMBER_CALENDAR_ITEMS,
  type MemberCalendarItem,
} from '@/data/memberDemoContent'

const DEMO_TODAY = '2026-08-02'
const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']
const HOLIDAYS = MEMBER_CALENDAR_HOLIDAYS
const ITEMS: MemberCalendarItem[] = MEMBER_CALENDAR_ITEMS

const focusYear = ref(2026)
const focusMonth = ref(7)
const monthLabel = computed(() => `${focusYear.value} 年 ${focusMonth.value + 1} 月`)

function changeMonth(delta: number) {
  const next = new Date(focusYear.value, focusMonth.value + delta, 1)
  focusYear.value = next.getFullYear()
  focusMonth.value = next.getMonth()
}

function backToToday() {
  focusYear.value = 2026
  focusMonth.value = 7
}

interface MonthCell {
  key: string
  date: string | null
  day: number | null
  holiday: string | null
  items: MemberCalendarItem[]
}

const monthCells = computed<MonthCell[]>(() => {
  const first = new Date(focusYear.value, focusMonth.value, 1)
  const days = new Date(focusYear.value, focusMonth.value + 1, 0).getDate()
  const cells: MonthCell[] = []
  for (let index = 0; index < first.getDay(); index += 1) {
    cells.push({ key: `lead-${index}`, date: null, day: null, holiday: null, items: [] })
  }
  for (let day = 1; day <= days; day += 1) {
    const date = `${focusYear.value}-${String(focusMonth.value + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    cells.push({
      key: date,
      date,
      day,
      holiday: HOLIDAYS[date] ?? null,
      items: ITEMS.filter((item) => item.date === date),
    })
  }
  while (cells.length % 7 !== 0) cells.push({ key: `tail-${cells.length}`, date: null, day: null, holiday: null, items: [] })
  return cells
})
</script>

<template>
  <section class="demo-page demo-calendar-page" data-testid="demo-calendar">
    <div class="demo-back-row"><RouterLink class="demo-text-button" to="/demo/member">← 回個人檔案</RouterLink><span class="demo-kicker">WANG XIAOMING・CALENDAR</span></div>
    <header class="demo-hero demo-hero-resident">
      <div>
        <p class="eyebrow">王小明的生活檔案</p>
        <h1>月行事曆</h1>
        <p class="demo-hero-lede">訂單、社區活動與主動提醒放在同一個月視圖，回頭看也知道自己最近忙了什麼。</p>
      </div>
      <div class="demo-hero-side"><span class="demo-kicker">固定 Demo 資料</span><strong>最近 3 個月都有生活紀錄</strong><span>不代表正式帳戶的即時行程</span></div>
    </header>

    <section class="panel demo-panel" aria-labelledby="demo-calendar-title">
      <div class="demo-section-heading">
        <div><p class="eyebrow">MONTH VIEW</p><h2 id="demo-calendar-title">{{ monthLabel }}</h2></div>
        <div class="demo-calendar-actions" role="group" aria-label="切換月份">
          <button class="button" type="button" data-testid="demo-calendar-prev" aria-label="上一個月" @click="changeMonth(-1)">←</button>
          <button class="button" type="button" data-testid="demo-calendar-next" aria-label="下一個月" @click="changeMonth(1)">→</button>
          <button class="button" type="button" data-testid="demo-calendar-today" @click="backToToday">回到本月</button>
        </div>
      </div>
      <div class="demo-calendar-grid" aria-label="Demo 月行事曆">
        <span v-for="weekday in WEEKDAYS" :key="weekday" class="demo-calendar-head">{{ weekday }}</span>
        <div v-for="cell in monthCells" :key="cell.key" class="demo-calendar-cell" :class="{ out: !cell.date, today: cell.date === DEMO_TODAY }" :data-date="cell.date ?? undefined">
          <span v-if="cell.day" class="demo-calendar-day">{{ cell.day }}</span>
          <span v-if="cell.holiday" class="demo-calendar-holiday" data-testid="demo-calendar-holiday">{{ cell.holiday }}</span>
          <div v-for="item in cell.items" :key="item.id" class="demo-calendar-item" :data-kind="item.kind" data-testid="demo-calendar-item">
            <strong>{{ item.title }}</strong><small>{{ item.detail }}</small>
          </div>
        </div>
      </div>
      <div class="demo-calendar-legend"><span><i data-kind="booking" />服務／訂單</span><span><i data-kind="community" />社區</span><span><i data-kind="reminder" />提醒</span></div>
      <p class="demo-note">父親節與節日是競賽 Demo 固定提醒；正式產品會以會員確認過的行事曆資料為準。</p>
    </section>

    <section class="demo-three-column">
      <article class="panel demo-panel"><p class="eyebrow">RECENT ACTIVITY</p><h2>最近活動</h2><ul class="demo-list demo-compact-list"><li><div><strong>完成冷氣清洗</strong><span class="demo-meta">7/25・社區優惠服務</span></div><span class="status">已完成</span></li><li><div><strong>參加台農鳳梨團購</strong><span class="demo-meta">7/29・管理室取貨</span></div><span class="status">已取貨</span></li></ul></article>
      <article class="panel demo-panel"><p class="eyebrow">UPCOMING</p><h2>接下來</h2><ul class="demo-list demo-compact-list"><li><div><strong>水電到府檢測</strong><span class="demo-meta">8/3 上午・地下室</span></div><span class="status">已安排</span></li><li><div><strong>父親節</strong><span class="demo-meta">8/8・主動提醒</span></div><span class="status">提醒</span></li></ul></article>
      <article class="panel demo-panel"><p class="eyebrow">NEXT STEP</p><h2>還要做什麼？</h2><p class="demo-note">可以回社區頁跟團，或打開 AI 管家把「爸媽週末要來」整理成任務包。</p><div class="button-row"><RouterLink class="button" to="/demo/community">看社區</RouterLink><RouterLink class="button primary" to="/user/assistant">問 AI 管家</RouterLink></div></article>
    </section>
  </section>
</template>

<style scoped>
.demo-calendar-actions { display: flex; gap: .45rem; flex-wrap: wrap; justify-content: flex-end; }
.demo-calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 2px; margin-top: 1rem; border: 2px solid var(--ink); border-radius: 14px; overflow: hidden; background: var(--ink); }
.demo-calendar-head { padding: .45rem; text-align: center; font-weight: 900; background: var(--lilac); }
.demo-calendar-cell { min-height: 7rem; padding: .4rem; display: grid; align-content: start; gap: .3rem; background: var(--surface); }
.demo-calendar-cell.out { background: var(--surface-2); }
.demo-calendar-cell.today { box-shadow: inset 0 0 0 3px var(--accent); }
.demo-calendar-day { font-weight: 900; }
.demo-calendar-holiday { color: var(--danger, #a13d32); font-size: .72rem; font-weight: 900; }
.demo-calendar-item { display: grid; gap: .12rem; padding: .32rem; border: 2px solid var(--ink); border-radius: 8px; background: var(--mint); font-size: .7rem; }
.demo-calendar-item[data-kind='community'] { background: var(--peach); }
.demo-calendar-item[data-kind='reminder'] { background: var(--yellow, #fde68a); }
.demo-calendar-item strong, .demo-calendar-item small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.demo-calendar-legend { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: .75rem; font-size: .8rem; font-weight: 800; }
.demo-calendar-legend span { display: inline-flex; align-items: center; gap: .35rem; }
.demo-calendar-legend i { width: .75rem; height: .75rem; display: inline-block; border: 2px solid var(--ink); border-radius: 50%; background: var(--mint); }
.demo-calendar-legend i[data-kind='community'] { background: var(--peach); }
.demo-calendar-legend i[data-kind='reminder'] { background: var(--yellow, #fde68a); }
@media (max-width: 700px) {
  .demo-calendar-cell { min-height: 4.4rem; padding: .22rem; }
  .demo-calendar-item { padding: .2rem; font-size: .6rem; }
  .demo-calendar-item small { display: none; }
}
</style>
