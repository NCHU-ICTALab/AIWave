<script setup lang="ts">
// 行事曆：訂單／提醒／手動事件的同一份 projection，以月曆為主並可前後翻月。
// 訂單來源的事件不在這裡改期——改期屬於訂單詳情的廠商流程,這裡只連過去。
import { computed, onMounted, ref } from 'vue'

import { ApiError, backendAnswered } from '@/api/http'
import { createCalendarEvent, listCalendarEvents, type CalendarEvent } from '@/api/platformClient'
import { MEMBER_CALENDAR_HOLIDAYS, MEMBER_CALENDAR_ITEMS } from '@/data/memberDemoContent'

const SOURCE_LABELS: Record<string, string> = {
  booking: '訂單', manual: '手動', reminder: '提醒', community: '社區',
}
const SOURCE_TYPES = Object.keys(SOURCE_LABELS)
const DEMO_TODAY = '2026-08-02'
const DEMO_HOLIDAYS = MEMBER_CALENDAR_HOLIDAYS

const events = ref<CalendarEvent[]>([])
/** 失敗會退到 Demo 行事曆並在通知裡說明原因,所以沒有「整頁不可用」這個狀態。 */
const status = ref<'loading' | 'ready'>('loading')
/**
 * 為什麼顯示固定 Demo 行事曆——三種原因必須分開講,不能都說成「後端未啟動」:
 * `''` = 用的是後端實際事件;`empty` = 後端有回應但這個帳號還沒有任何事件;
 * `failed` = 後端回了錯誤;`offline` = 真的連不上(ApiError.status === 0)。
 */
const demoReason = ref<'' | 'empty' | 'failed' | 'offline'>('')
const demoDetail = ref('')
const error = ref('')
const selectedTypes = ref<string[]>([...SOURCE_TYPES])
let offlineEventSequence = 0

const sourceType = (event: CalendarEvent) => event.source?.type ?? 'manual'

const visibleEvents = computed(() => events.value
  .filter((event) => selectedTypes.value.includes(sourceType(event)) || !(sourceType(event) in SOURCE_LABELS))
  .slice()
  .sort((a, b) => a.startsAt.localeCompare(b.startsAt)))

function demoCalendarEvents(): CalendarEvent[] {
  return MEMBER_CALENDAR_ITEMS.map((item) => {
    const start = item.title.includes('烤肉') ? '16:00' : item.title.includes('清潔') ? '14:00' : '09:00'
    const end = item.title.includes('烤肉') ? '20:00' : item.title.includes('清潔') ? '16:00' : '11:00'
    return {
      id: item.id,
      title: item.title,
      startsAt: `${item.date}T${start}:00+08:00`,
      endsAt: `${item.date}T${end}:00+08:00`,
      allDay: item.kind === 'reminder',
      note: item.detail,
      status: 'demo',
      source: { type: item.kind, id: null },
      recurrence: null,
    }
  })
}

async function load() {
  status.value = 'loading'
  demoReason.value = ''
  demoDetail.value = ''
  error.value = ''
  try {
    // 「回了空陣列」是後端有正常回應,不是後端沒起來——兩者的說法必須不一樣。
    const loaded = await listCalendarEvents()
    if (Array.isArray(loaded) && loaded.length) {
      events.value = loaded
    } else {
      events.value = demoCalendarEvents()
      demoReason.value = 'empty'
    }
    const first = events.value[0]?.startsAt.slice(0, 10)
    if (first) {
      const [year, month] = first.split('-').map(Number)
      if (year && month) {
        focusYear.value = year
        focusMonth.value = month - 1
      }
    }
    status.value = 'ready'
  } catch (reason) {
    events.value = demoCalendarEvents()
    demoReason.value = backendAnswered(reason) ? 'failed' : 'offline'
    demoDetail.value = backendAnswered(reason) && reason instanceof ApiError ? reason.message : ''
    status.value = 'ready'
  }
}

// ── 月檢視：月份由使用者控制，不會因事件列表更新而跳回去 ──
const focusYear = ref(Number(DEMO_TODAY.slice(0, 4)))
const focusMonth = ref(Number(DEMO_TODAY.slice(5, 7)) - 1)
const monthLabel = computed(() => `${focusYear.value} 年 ${focusMonth.value + 1} 月`)

function changeMonth(delta: number) {
  const next = new Date(focusYear.value, focusMonth.value + delta, 1)
  focusYear.value = next.getFullYear()
  focusMonth.value = next.getMonth()
}

function goToDemoToday() {
  focusYear.value = Number(DEMO_TODAY.slice(0, 4))
  focusMonth.value = Number(DEMO_TODAY.slice(5, 7)) - 1
}

interface MonthCell {
  key: string
  day: number | null
  date: string | null
  events: CalendarEvent[]
  holiday: string | null
}

const monthCells = computed<MonthCell[]>(() => {
  const year = focusYear.value
  const month = focusMonth.value
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
    cells.push({ key: `lead-${index}`, day: null, date: null, events: [], holiday: null })
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    cells.push({ key: date, day, date, events: byDate.get(date) ?? [], holiday: DEMO_HOLIDAYS[date] ?? null })
  }
  while (cells.length % 7 !== 0) {
    cells.push({ key: `tail-${cells.length}`, day: null, date: null, events: [], holiday: null })
  }
  return cells
})
const monthEventCount = computed(() => monthCells.value.reduce((count, cell) => count + cell.events.length, 0))

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
    // 只有「真的連不上」才在本機補一筆離線事件。後端有回應卻失敗(400/500…)時
    // 假裝新增成功,等於騙使用者事件已經存進去了。
    if (!backendAnswered(reason)) {
      offlineEventSequence += 1
      const created: CalendarEvent = {
        id: `offline-calendar-${offlineEventSequence}`,
        title,
        startsAt: draftStart.value,
        endsAt: draftEnd.value,
        allDay: false,
        note: '連不上後端時的本機事件,尚未寫入後端',
        status: 'demo',
        source: { type: 'manual', id: null },
        recurrence: null,
      }
      events.value = [...events.value, created]
      createNotice.value = `已在本機新增「${created.title}」;目前連不上後端,這筆還沒存到後端。`
      draftTitle.value = ''
      draftStart.value = ''
      draftEnd.value = ''
    } else {
      error.value = reason instanceof ApiError ? reason.message : '事件未能新增,請稍後再試。'
    }
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
      {{ status === 'ready' ? `${visibleEvents.length} 筆${demoReason ? '・Demo' : ''}` : '載入中…' }}
    </span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>

  <section class="panel calendar-month-panel" aria-labelledby="calendar-month-title">
    <div class="section-title-row calendar-month-heading">
      <div>
        <p class="eyebrow">MONTH VIEW</p>
        <h2 id="calendar-month-title">月行事曆</h2>
      </div>
      <div class="calendar-month-actions" role="group" aria-label="切換月份">
        <button class="button" type="button" data-testid="calendar-prev-month" aria-label="上一個月" @click="changeMonth(-1)">←</button>
        <strong data-testid="calendar-month-label">{{ monthLabel }}</strong>
        <button class="button" type="button" data-testid="calendar-next-month" aria-label="下一個月" @click="changeMonth(1)">→</button>
        <button class="button" type="button" data-testid="calendar-today" @click="goToDemoToday">回到 Demo 本月</button>
      </div>
    </div>

    <fieldset class="filter-fieldset">
      <legend>來源篩選</legend>
      <label v-for="type in SOURCE_TYPES" :key="type" class="filter-option">
        <input v-model="selectedTypes" type="checkbox" :value="type" :data-testid="`filter-${type}`" />
        {{ SOURCE_LABELS[type] }}
      </label>
    </fieldset>

    <p v-if="status === 'loading'" role="status">正在載入行事曆…</p>
    <section v-else :aria-label="`${monthLabel}月曆`">
      <p v-if="demoReason" class="calendar-demo-notice" :data-reason="demoReason" data-testid="calendar-offline-demo" role="status">
        <template v-if="demoReason === 'empty'">
          後端行事曆目前沒有任何會員事件，因此顯示王小明的固定 Demo 行事曆；建立訂單或新增事件後就會換成實際資料。
        </template>
        <template v-else-if="demoReason === 'failed'">
          後端有回應但取不到行事曆{{ demoDetail ? `（${demoDetail}）` : '' }}，先顯示王小明的固定 Demo 行事曆。
        </template>
        <template v-else>
          目前連不上後端行事曆 API，先顯示王小明的固定 Demo 行事曆；連線恢復後會切換成實際資料。
        </template>
      </p>
      <div class="month-grid">
        <span v-for="weekday in ['日', '一', '二', '三', '四', '五', '六']" :key="weekday" class="month-head">{{ weekday }}</span>
        <div v-for="cell in monthCells" :key="cell.key" class="month-cell" :class="{ out: cell.day === null, today: cell.date === DEMO_TODAY }" :data-date="cell.date ?? undefined">
          <span v-if="cell.day" class="month-day">{{ cell.day }}</span>
          <span v-if="cell.holiday" class="month-holiday" data-testid="calendar-holiday">{{ cell.holiday }}</span>
          <template v-for="event in cell.events" :key="event.id">
            <RouterLink
              v-if="sourceType(event) === 'booking' && event.source?.id"
              class="month-event" :data-source="sourceType(event)" data-testid="calendar-order-link"
              :to="`/user/orders/${event.source.id}`"
            ><span data-testid="calendar-event">{{ event.title }}</span></RouterLink>
            <span v-else class="month-event" :data-source="sourceType(event)" data-testid="calendar-event">{{ event.title }}</span>
          </template>
        </div>
      </div>
      <p v-if="!monthEventCount && !monthCells.some((cell) => cell.holiday)" class="muted">這個月目前沒有符合的行程。</p>
      <p class="calendar-note muted">行事曆已放入 2026 國定假日、民俗節日與王小明生活提醒；訂單事件仍會連回訂單詳情，這裡不直接改期。</p>
      <section class="member-calendar-activity" data-testid="member-calendar-activity" aria-labelledby="member-calendar-activity-title">
        <div class="section-title-row">
          <h3 id="member-calendar-activity-title">住戶生活提醒</h3>
          <span class="muted">與王小明 Demo 使用同一組展示事件</span>
        </div>
        <ul class="member-calendar-activity-list">
          <li v-for="item in MEMBER_CALENDAR_ITEMS.slice(0, 4)" :key="item.id" :data-kind="item.kind">
            <span class="member-calendar-activity-dot" aria-hidden="true" />
            <div><strong>{{ item.title }}</strong><span>{{ item.date.slice(5).replace('-', '/') }}・{{ item.detail }}</span></div>
          </li>
        </ul>
      </section>
    </section>
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
.calendar-month-heading {
  align-items: center;
  gap: 1rem;
}
.calendar-month-heading h2 {
  margin: 0;
}
.calendar-month-actions {
  display: flex;
  align-items: center;
  gap: .45rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.calendar-month-actions strong {
  min-width: 8rem;
  text-align: center;
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
.month-cell.today {
  box-shadow: inset 0 0 0 3px var(--accent);
}
.month-holiday {
  display: block;
  color: var(--danger, #a13d32);
  font-size: .65rem;
  font-weight: 900;
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
.calendar-note {
  margin: .75rem 0 0;
}
.calendar-demo-notice {
  margin: 0 0 .8rem;
  padding: .7rem .8rem;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--yellow, #fde68a);
  color: var(--accent-ink);
  font-size: .82rem;
  font-weight: 800;
}
.member-calendar-activity {
  display: grid;
  gap: .65rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 2px dashed var(--ink);
}
.member-calendar-activity h3 {
  margin: 0;
  font-size: 1rem;
}
.member-calendar-activity-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: .6rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.member-calendar-activity-list li {
  display: flex;
  gap: .5rem;
  align-items: flex-start;
  padding: .65rem;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface-2);
}
.member-calendar-activity-list li[data-kind='community'] { background: var(--peach); }
.member-calendar-activity-list li[data-kind='reminder'] { background: var(--yellow); }
.member-calendar-activity-dot {
  flex: 0 0 .7rem;
  width: .7rem;
  height: .7rem;
  margin-top: .25rem;
  border: 2px solid var(--ink);
  border-radius: 50%;
  background: var(--mint);
}
.member-calendar-activity-list div {
  display: grid;
  gap: .15rem;
  min-width: 0;
}
.member-calendar-activity-list span:not(.member-calendar-activity-dot) {
  color: var(--muted);
  font-size: .78rem;
}
@media (max-width: 650px) {
  .month-cell {
    min-height: 3.2rem;
    padding: .15rem .2rem;
  }
  .month-event {
    font-size: .58rem;
  }
  .calendar-month-heading {
    align-items: flex-start;
    display: grid;
  }
  .calendar-month-actions {
    justify-content: flex-start;
  }
  .member-calendar-activity-list {
    grid-template-columns: 1fr;
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
