<script setup lang="ts">
// M4 行事曆:訂單/提醒/手動事件的同一份 projection,列表檢視 + 來源篩選 + 手動新增。
// 訂單來源的事件不在這裡改期——改期屬於訂單詳情的廠商流程,這裡只連過去。
import { computed, onMounted, ref } from 'vue'

import { ApiError } from '@/api/http'
import { createCalendarEvent, listCalendarEvents, type CalendarEvent } from '@/api/platformClient'

const SOURCE_LABELS: Record<string, string> = {
  booking: '訂單', manual: '手動', reminder: '提醒', community: '社區',
}
const SOURCE_TYPES = Object.keys(SOURCE_LABELS)

const events = ref<CalendarEvent[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const error = ref('')
const selectedTypes = ref<string[]>([...SOURCE_TYPES])

const timeOfDay = (value: string | null | undefined) => (value ?? '').slice(11, 16)
const sourceType = (event: CalendarEvent) => event.source?.type ?? 'manual'
const sourceLabel = (event: CalendarEvent) => SOURCE_LABELS[sourceType(event)] ?? sourceType(event)

const visibleEvents = computed(() => events.value
  .filter((event) => selectedTypes.value.includes(sourceType(event)) || !(sourceType(event) in SOURCE_LABELS))
  .slice()
  .sort((a, b) => a.startsAt.localeCompare(b.startsAt)))

/** 依日期分組,組內已按開始時間排序。 */
const grouped = computed(() => {
  const groups: Array<{ date: string; items: CalendarEvent[] }> = []
  for (const event of visibleEvents.value) {
    const date = event.startsAt.slice(0, 10)
    const group = groups.at(-1)
    if (group && group.date === date) group.items.push(event)
    else groups.push({ date, items: [event] })
  }
  return groups
})

async function load() {
  status.value = 'loading'
  try {
    const loaded = await listCalendarEvents()
    events.value = Array.isArray(loaded) ? loaded : []
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
  }
}

// ── 月/週檢視(方向 A 原型:月/週/列表切換;列表為預設) ──
const viewMode = ref<'list' | 'month' | 'week'>('list')

/** 聚焦月份:最早一筆可見事件所在月;沒有事件時用今天。 */
const focusMonth = computed(() => {
  const first = visibleEvents.value[0]?.startsAt
  const base = first ? new Date(`${first.slice(0, 10)}T00:00:00`) : new Date()
  return { year: base.getFullYear(), month: base.getMonth() }
})

const monthLabel = computed(() => `${focusMonth.value.year} 年 ${focusMonth.value.month + 1} 月`)

interface MonthCell {
  key: string
  day: number | null
  date: string | null
  events: CalendarEvent[]
}

const monthCells = computed<MonthCell[]>(() => {
  const { year, month } = focusMonth.value
  const firstDay = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const leading = firstDay.getDay() // 週日開頭,與原型一致
  const byDate = new Map<string, CalendarEvent[]>()
  for (const event of visibleEvents.value) {
    const date = event.startsAt.slice(0, 10)
    byDate.set(date, [...(byDate.get(date) ?? []), event])
  }
  const cells: MonthCell[] = []
  for (let index = 0; index < leading; index += 1) {
    cells.push({ key: `lead-${index}`, day: null, date: null, events: [] })
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    cells.push({ key: date, day, date, events: byDate.get(date) ?? [] })
  }
  while (cells.length % 7 !== 0) {
    cells.push({ key: `tail-${cells.length}`, day: null, date: null, events: [] })
  }
  return cells
})

// ── 週檢視:聚焦週 = 最早可見事件所在週(週日開頭),沒有事件時用今天 ──
interface WeekCell {
  key: string
  weekday: string
  date: string
  label: string
  events: CalendarEvent[]
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'] as const

const weekCells = computed<WeekCell[]>(() => {
  const first = visibleEvents.value[0]?.startsAt
  const base = first ? new Date(`${first.slice(0, 10)}T00:00:00`) : new Date()
  const sunday = new Date(base)
  sunday.setDate(base.getDate() - base.getDay()) // 週日開頭,與月檢視一致
  const byDate = new Map<string, CalendarEvent[]>()
  for (const event of visibleEvents.value) {
    const date = event.startsAt.slice(0, 10)
    byDate.set(date, [...(byDate.get(date) ?? []), event])
  }
  return WEEKDAYS.map((weekday, index) => {
    const day = new Date(sunday)
    day.setDate(sunday.getDate() + index)
    const date = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`
    return {
      key: date,
      weekday,
      date,
      label: `${day.getMonth() + 1}/${day.getDate()}`,
      events: byDate.get(date) ?? [],
    }
  })
})

const weekLabel = computed(() => {
  const cells = weekCells.value
  return cells.length ? `${cells[0]!.label}(日)– ${cells.at(-1)!.label}(六)` : ''
})

// ── 手動新增事件 ──
const draftTitle = ref('')
const draftStart = ref('')
const draftEnd = ref('')
const creating = ref(false)
const createNotice = ref('')

async function submitEvent() {
  const title = draftTitle.value.trim()
  if (!title || !draftStart.value || !draftEnd.value || creating.value) return
  creating.value = true
  error.value = ''
  createNotice.value = ''
  try {
    const created = await createCalendarEvent({
      title, startsAt: draftStart.value, endsAt: draftEnd.value,
    })
    events.value = [...events.value, created]
    createNotice.value = `已新增「${created.title}」。`
    draftTitle.value = ''
    draftStart.value = ''
    draftEnd.value = ''
  } catch (reason) {
    error.value = reason instanceof ApiError ? reason.message : '事件未能新增,請稍後再試。'
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>

<template>
  <header class="page-heading">
    <div>
      <p class="eyebrow">CALENDAR</p>
      <h1>行事曆</h1>
      <p class="muted">訂單行程與自己的事件放在同一份時間軸上。</p>
    </div>
    <span class="page-status">
      {{ status === 'ready' ? `${visibleEvents.length} 筆` : status === 'loading' ? '載入中…' : '離線' }}
    </span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>

  <section class="panel" aria-labelledby="calendar-list-title">
    <div class="section-title-row">
      <h2 id="calendar-list-title">行程列表</h2>
    </div>

    <fieldset class="filter-fieldset">
      <legend>來源篩選</legend>
      <label v-for="type in SOURCE_TYPES" :key="type" class="filter-option">
        <input v-model="selectedTypes" type="checkbox" :value="type" :data-testid="`filter-${type}`" />
        {{ SOURCE_LABELS[type] }}
      </label>
    </fieldset>

    <div class="view-toggle" role="group" aria-label="檢視方式">
      <button
        class="button" type="button" data-testid="view-list"
        :aria-pressed="viewMode === 'list'" @click="viewMode = 'list'"
      >列表</button>
      <button
        class="button" type="button" data-testid="view-month"
        :aria-pressed="viewMode === 'month'" @click="viewMode = 'month'"
      >月</button>
      <button
        class="button" type="button" data-testid="view-week"
        :aria-pressed="viewMode === 'week'" @click="viewMode = 'week'"
      >週</button>
    </div>

    <p v-if="status === 'loading'" role="status">正在載入行事曆…</p>
    <p v-else-if="status === 'unavailable'" class="muted" role="status">
      目前無法取得行事曆,請確認後端服務是否啟動。
    </p>
    <section v-else-if="viewMode === 'month'" :aria-label="`${monthLabel}月曆`">
      <h3 class="eyebrow">{{ monthLabel }}</h3>
      <div class="month-grid">
        <span v-for="weekday in ['日', '一', '二', '三', '四', '五', '六']" :key="weekday" class="month-head">{{ weekday }}</span>
        <div v-for="cell in monthCells" :key="cell.key" class="month-cell" :class="{ out: cell.day === null }">
          <span v-if="cell.day" class="month-day">{{ cell.day }}</span>
          <template v-for="event in cell.events" :key="event.id">
            <RouterLink
              v-if="sourceType(event) === 'booking' && event.source?.id"
              class="month-event" :data-source="sourceType(event)"
              :to="`/user/orders/${event.source.id}`"
            >{{ event.title }}</RouterLink>
            <span v-else class="month-event" :data-source="sourceType(event)">{{ event.title }}</span>
          </template>
        </div>
      </div>
      <p v-if="!visibleEvents.length" class="muted">目前沒有符合的行程。</p>
    </section>
    <section v-else-if="viewMode === 'week'" :aria-label="`本週 ${weekLabel}`" data-testid="week-view">
      <h3 class="eyebrow">本週 {{ weekLabel }}</h3>
      <div class="month-grid week-grid">
        <div v-for="cell in weekCells" :key="cell.key" class="month-cell week-cell" data-testid="week-column">
          <span class="month-head">{{ cell.weekday }} {{ cell.label }}</span>
          <template v-for="event in cell.events" :key="event.id">
            <RouterLink
              v-if="sourceType(event) === 'booking' && event.source?.id"
              class="month-event" :data-source="sourceType(event)"
              :to="`/user/orders/${event.source.id}`"
              data-testid="week-order-link"
            >{{ event.title }}</RouterLink>
            <span v-else class="month-event" :data-source="sourceType(event)">{{ event.title }}</span>
          </template>
        </div>
      </div>
      <p v-if="!visibleEvents.length" class="muted">目前沒有符合的行程。</p>
    </section>
    <template v-else>
      <section v-for="group in grouped" :key="group.date" :aria-label="group.date">
        <h3 class="eyebrow">{{ group.date }}</h3>
        <ul class="plain-list">
          <li v-for="event in group.items" :key="event.id" class="order-row" data-testid="calendar-event">
            <div>
              <strong>{{ event.title }}</strong>
              <span class="row-meta">
                {{ event.allDay ? '全天' : `${timeOfDay(event.startsAt)} – ${timeOfDay(event.endsAt)}` }}
                <template v-if="event.note">・{{ event.note }}</template>
              </span>
            </div>
            <span class="status" :data-status="sourceType(event)">{{ sourceLabel(event) }}</span>
            <RouterLink
              v-if="sourceType(event) === 'booking' && event.source?.id"
              class="text-link"
              :to="`/user/orders/${event.source.id}`"
              data-testid="calendar-order-link"
            >查看訂單</RouterLink>
          </li>
        </ul>
      </section>
      <div v-if="!grouped.length" class="empty-state compact">
        <h3>目前沒有符合的行程</h3>
        <p>建立預約後,行程會自動出現;也可以在下方新增自己的事件。</p>
      </div>
    </template>
  </section>

  <section class="panel" aria-labelledby="calendar-create-title">
    <h2 id="calendar-create-title">新增事件</h2>
    <form class="need-form calendar-form" @submit.prevent="submitEvent">
      <label for="calendar-title">標題</label>
      <input id="calendar-title" v-model="draftTitle" data-testid="calendar-title" type="text" required />
      <label for="calendar-start">開始</label>
      <input id="calendar-start" v-model="draftStart" data-testid="calendar-start" type="datetime-local" required />
      <label for="calendar-end">結束</label>
      <input id="calendar-end" v-model="draftEnd" data-testid="calendar-end" type="datetime-local" required />
      <button class="button primary" type="submit" data-testid="calendar-create"
        :disabled="creating || !draftTitle.trim() || !draftStart || !draftEnd">
        {{ creating ? '新增中…' : '新增事件' }}
      </button>
    </form>
    <p v-if="createNotice" class="feedback-inline" role="status">{{ createNotice }}</p>
    <p class="source-note muted">行事曆是訂單與事件的 projection;廠商預約改期請至訂單詳情申請。</p>
  </section>
</template>

<style scoped>
.view-toggle {
  display: flex;
  gap: var(--space-2);
  margin-block: var(--space-3);
}
.view-toggle .button[aria-pressed='true'] {
  background: var(--mint);
  box-shadow: inset 0 0 0 2px var(--ink);
}
.month-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 2px;
  border: var(--border-chunky) solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--ink);
  overflow: hidden;
}
.month-head {
  background: var(--lilac, #e6e6fa);
  text-align: center;
  font-weight: 800;
  font-size: var(--text-sm);
  padding: .3rem 0;
}
.month-cell {
  background: var(--surface);
  min-height: 4.5rem;
  padding: .25rem .35rem;
  display: grid;
  align-content: start;
  gap: .2rem;
}
.month-cell.out {
  background: var(--bg);
}
/* 週檢視:沿用 .month-* 樣式,單列 7 欄,每欄自帶「星期+日期」表頭 */
.week-cell {
  min-height: 7rem;
}
.week-cell .month-head {
  margin: -0.25rem -0.35rem 0.15rem;
  padding-inline: 0.2rem;
  white-space: nowrap;
}
.month-day {
  font-weight: 800;
  font-size: var(--text-sm);
}
.month-event {
  display: block;
  border: 2px solid var(--ink);
  border-radius: 8px;
  background: var(--mint);
  color: var(--ink);
  font-size: .68rem;
  font-weight: 700;
  padding: 0 .3rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-decoration: none;
}
.month-event[data-source='manual'] {
  background: var(--lilac, #e6e6fa);
}
.month-event[data-source='reminder'] {
  background: var(--blue);
}
.month-event[data-source='community'] {
  background: var(--peach);
}
@media (max-width: 650px) {
  .month-cell {
    min-height: 3.2rem;
    padding: .15rem .2rem;
  }
  .month-event {
    font-size: .58rem;
  }
}

/* .need-form 是水平搜尋列樣式;新增事件表單改直向堆疊,390px 不得水平溢出 */
.calendar-form {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-2);
  max-width: 28rem;
}
.calendar-form label {
  font-weight: 700;
}
.calendar-form .button {
  justify-self: start;
}
</style>
