<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { DEMO_HOUSEHOLD_ID, type DemoCommunityAnswer } from '@/domain/communityDemo'
import { useCommunityDemoStore } from '@/stores/communityDemo'
import { useSessionStore } from '@/stores/session'

const demo = useCommunityDemoStore()
const session = useSessionStore()
const dashboard = computed(() => demo.residentDashboard)
const householdId = computed(() => session.accountId ?? DEMO_HOUSEHOLD_ID)

const query = ref('')
const answer = ref<DemoCommunityAnswer | null>(null)
const askState = ref<'idle' | 'thinking' | 'answered'>('idle')
const askFeedback = ref('')
const serviceNoteOpen = ref(false)
const fatherDayDismissed = ref(false)

const money = (value: number) => `NT$ ${value.toLocaleString('zh-TW')}`
const dateLabel = (value: string) => {
  const date = new Date(value.includes('T') ? value : `${value}T12:00:00+08:00`)
  if (Number.isNaN(date.getTime())) return value
  const weekday = ['日', '一', '二', '三', '四', '五', '六'][date.getDay()]
  return `${date.getMonth() + 1}/${date.getDate()}（週${weekday}）`
}
const progressWidth = (current: number, threshold: number) => `${Math.min(100, Math.round((current / threshold) * 100))}%`

async function askCommunity(value = query.value) {
  const clean = value.trim()
  if (!clean || askState.value === 'thinking') return
  query.value = clean
  answer.value = null
  askFeedback.value = ''
  askState.value = 'thinking'
  await new Promise((resolve) => window.setTimeout(resolve, 240))
  answer.value = demo.askCommunity(clean, householdId.value)
  askState.value = 'answered'
}

function askRelated(value: string) {
  query.value = value
  void askCommunity(value)
}

function reportAnswer() {
  if (!answer.value || answer.value.matched) return
  demo.reportUnanswered(answer.value.query, householdId.value)
  askFeedback.value = '已送入管委會未回答問題清單，謝謝你的提醒。'
}

function dismissFatherDay() {
  fatherDayDismissed.value = true
}

onMounted(() => {
  demo.loadResident(householdId.value)
})
</script>

<template>
  <section v-if="dashboard" class="demo-page demo-resident-page">
    <header class="demo-hero demo-hero-resident">
      <div>
        <p class="eyebrow">AI 智慧社區・住戶首頁</p>
        <h1>{{ dashboard.community.name }}</h1>
        <p class="demo-hero-lede">把公告、社區規約與團購放在同一個入口，住戶不用再翻群組訊息。</p>
        <div class="demo-chip-row">
          <span class="demo-chip demo-chip-mint">{{ dashboard.resident.displayName }}・{{ dashboard.resident.householdLabel }}</span>
          <span class="demo-chip">{{ dashboard.community.address }}</span>
        </div>
      </div>
      <div class="demo-hero-side">
        <span class="demo-kicker">本次 Demo 入口</span>
        <strong>住戶先看懂，管委會再放大</strong>
        <span>訂閱服務 → 社區優惠 → 團購成交</span>
      </div>
    </header>

    <section class="demo-kpi-grid" aria-label="住戶首頁摘要">
      <article class="demo-kpi-card demo-kpi-peach" data-testid="resident-package-kpi">
        <span class="demo-kpi-icon" aria-hidden="true">📦</span>
        <div><strong>{{ dashboard.packages.length }}</strong><span>件待領包裹</span></div>
        <small>管理室 07:00–22:00</small>
      </article>
      <article class="demo-kpi-card demo-kpi-blue" data-testid="resident-announcement-kpi">
        <span class="demo-kpi-icon" aria-hidden="true">📣</span>
        <div><strong>{{ dashboard.announcements[0]?.title.includes('電梯') ? '1' : '—' }}</strong><span>則近期電梯保養</span></div>
        <small>{{ dateLabel(dashboard.announcements[0]?.publishedAt ?? '') }}</small>
      </article>
      <article class="demo-kpi-card demo-kpi-lilac" data-testid="resident-repair-kpi">
        <span class="demo-kpi-icon" aria-hidden="true">🛠</span>
        <div><strong>{{ dashboard.repairs.filter((item) => item.status !== 'completed').length }}</strong><span>筆報修進行中</span></div>
        <small>{{ dashboard.repairs[0]?.statusLabel }}・{{ dashboard.repairs[0]?.subject }}</small>
      </article>
      <article class="demo-kpi-card demo-kpi-mint" data-testid="resident-group-buy-kpi">
        <span class="demo-kpi-icon" aria-hidden="true">🛒</span>
        <div><strong>{{ dashboard.activeGroupBuys.length }}</strong><span>檔進行中團購</span></div>
        <small>最低成團單位清楚可見</small>
      </article>
    </section>

    <section v-if="!fatherDayDismissed" class="panel demo-panel demo-care-push" data-testid="father-day-push" aria-labelledby="father-day-push-title">
      <div class="demo-care-push-icon" aria-hidden="true">💌</div>
      <div class="demo-care-push-copy"><p class="eyebrow">AI 主動提醒・8/8</p><h2 id="father-day-push-title">父親節快到了，王小明要不要先安排一下？</h2><p>這是根據你已授權的 Demo 行事曆提醒；可以先看看月曆，再決定要不要準備晚餐或傳訊息給爸爸。</p><span class="demo-meta">資料來源：競賽 Demo 固定事件・不背景追蹤位置</span></div>
      <div class="button-row demo-care-push-actions"><RouterLink class="button primary" data-testid="father-day-calendar-link" to="/demo/calendar">看月曆</RouterLink><button class="button" type="button" data-testid="father-day-snooze" @click="dismissFatherDay">稍後提醒</button></div>
    </section>

    <div class="demo-two-column">
      <section class="panel demo-panel" data-testid="resident-announcements" aria-labelledby="resident-announcements-title">
        <div class="demo-section-heading">
          <div><p class="eyebrow">COMMUNITY NEWS</p><h2 id="resident-announcements-title">社區公告</h2></div>
          <span class="demo-count-badge">{{ dashboard.announcements.length }} 則</span>
        </div>
        <ul class="demo-list demo-announcement-list">
          <li v-for="item in dashboard.announcements.slice(0, 4)" :key="item.id">
            <div>
              <strong>{{ item.title }}</strong>
              <span class="demo-meta">{{ dateLabel(item.publishedAt) }}</span>
            </div>
            <details><summary>查看內容</summary><p>{{ item.body }}</p></details>
          </li>
        </ul>
      </section>

      <section class="panel demo-panel" aria-labelledby="community-summary-title">
        <div class="demo-section-heading">
          <div><p class="eyebrow">ABOUT THIS COMMUNITY</p><h2 id="community-summary-title">日光森林社區</h2></div>
          <span class="demo-count-badge">{{ dashboard.community.households }} 戶</span>
        </div>
        <dl class="demo-definition-list">
          <div><dt>規模</dt><dd>{{ dashboard.community.buildings }}・{{ dashboard.community.floors }}</dd></div>
          <div><dt>車位</dt><dd>{{ dashboard.community.parking }}</dd></div>
          <div><dt>公設</dt><dd>{{ dashboard.community.facilities.slice(0, 4).join('、') }}</dd></div>
          <div><dt>物業</dt><dd>{{ dashboard.community.propertyManager }}</dd></div>
        </dl>
        <p class="demo-note">{{ dashboard.resident.householdMembers }}・{{ dashboard.resident.residenceType }}・過去參加 {{ dashboard.resident.pastGroupBuys }} 次團購</p>
      </section>
    </div>

    <section class="panel demo-panel demo-ask-panel" data-testid="ask-community-panel" aria-labelledby="ask-community-title">
      <div class="demo-section-heading">
        <div><p class="eyebrow">COMMUNITY AI WIKI</p><h2 id="ask-community-title">問社區</h2></div>
        <span class="demo-ai-badge">不呼叫外部 LLM・Demo Wiki</span>
      </div>
      <p class="demo-panel-lede">公告找不到、規約看不懂？用平常說話的方式問，我會標出答案來源。</p>
      <form class="demo-ask-form" @submit.prevent="askCommunity()">
        <label class="visually-hidden" for="community-query">想問社區什麼事？</label>
        <input id="community-query" v-model="query" data-testid="community-query" type="text" placeholder="例如：垃圾車幾點來" />
        <button class="button primary" data-testid="ask-community" type="submit" :disabled="askState === 'thinking'">
          {{ askState === 'thinking' ? '整理規約中…' : '送出問題' }}
        </button>
      </form>
      <div class="demo-quick-questions" aria-label="常見問題">
        <span>試試看：</span>
        <button type="button" data-testid="quick-garbage" @click="askRelated('垃圾車幾點來')">垃圾車幾點來</button>
        <button type="button" data-testid="quick-renovation" @click="askRelated('裝修可以假日施工嗎')">假日可以裝修嗎</button>
      </div>

      <div v-if="askState === 'thinking'" class="demo-thinking" data-testid="community-thinking" role="status" aria-live="polite">
        <span class="demo-thinking-dots" aria-hidden="true"><i /><i /><i /></span>
        正在比對社區生活公約…
      </div>

      <article v-if="answer && askState === 'answered'" class="demo-answer" :class="{ 'is-unmatched': !answer.matched }" data-testid="community-answer" aria-live="polite">
        <div class="demo-answer-label"><span>{{ answer.matched ? 'AI 回答' : '需要管委會補充' }}</span><span>{{ answer.query }}</span></div>
        <p class="demo-answer-short">{{ answer.shortAnswer }}</p>
        <details open class="demo-answer-details">
          <summary>完整內容</summary>
          <p>{{ answer.fullRule }}</p>
        </details>
        <div v-if="answer.matched" class="demo-source-row">
          <span>來源：{{ answer.source }}</span>
          <span>更新於 {{ answer.updatedAt }}</span>
        </div>
        <div v-else class="demo-unanswered-action">
          <button class="button" type="button" data-testid="report-unanswered" @click="reportAnswer">送入未回答問題清單</button>
          <span v-if="askFeedback" role="status">{{ askFeedback }}</span>
        </div>
        <div class="demo-related-questions">
          <span>相關問題</span>
          <button v-for="related in answer.relatedQuestions" :key="related" type="button" @click="askRelated(related)">{{ related }}</button>
        </div>
      </article>
    </section>

    <div class="demo-two-column demo-service-row">
      <section class="panel demo-panel demo-offer-card" data-testid="community-service-offer" aria-labelledby="service-offer-title">
        <div class="demo-section-heading">
          <div><p class="eyebrow">COMMUNITY BENEFIT</p><h2 id="service-offer-title">社區優惠服務</h2></div>
          <span class="demo-price-tag">訂閱回饋</span>
        </div>
        <div class="demo-offer-copy">
          <div><span class="demo-offer-icon" aria-hidden="true">❄️</span><strong>{{ dashboard.serviceOffers[0]?.name }}</strong></div>
          <div class="demo-price-pair"><del>市價 {{ money(dashboard.serviceOffers[0]?.marketPrice ?? 0) }}</del><strong>社區價 {{ money(dashboard.serviceOffers[0]?.communityPrice ?? 0) }}</strong></div>
        </div>
        <p>{{ dashboard.serviceOffers[0]?.note }}</p>
        <button class="demo-question-button" type="button" data-testid="offer-price-question" :aria-expanded="serviceNoteOpen" @click="serviceNoteOpen = !serviceNoteOpen">？為什麼有價差</button>
        <p v-if="serviceNoteOpen" class="demo-explanation" data-testid="offer-price-explanation">日光森林社區已訂閱 AI 智慧社區服務，價差由社區訂閱費回饋，非廠商補貼。</p>
      </section>

      <section class="panel demo-panel" aria-labelledby="packages-title">
        <div class="demo-section-heading"><div><p class="eyebrow">PICKUP</p><h2 id="packages-title">我的包裹</h2></div><span class="demo-count-badge">{{ dashboard.packages.length }} 件待領</span></div>
        <ul class="demo-list demo-compact-list">
          <li v-for="item in dashboard.packages" :key="item.id"><div><strong>{{ item.carrier }}</strong><span class="demo-meta">抵達 {{ item.arrivedAt }}</span></div><span class="demo-code">末四碼 {{ item.trackingLast4 }}・取件碼 {{ item.pickupCode }}</span></li>
        </ul>
      </section>
    </div>

    <section id="group-buys" class="panel demo-panel" data-testid="resident-group-buys" aria-labelledby="group-buy-title">
      <div class="demo-section-heading">
        <div><p class="eyebrow">COMMUNITY GROUP BUY</p><h2 id="group-buy-title">社區團購</h2></div>
        <span class="demo-count-badge">{{ dashboard.activeGroupBuys.length }} 檔收單中</span>
      </div>
      <p class="demo-panel-lede">社區優惠價與跟團進度透明，取貨地點固定在管理室。</p>
      <div class="demo-group-grid">
        <article v-for="group in dashboard.activeGroupBuys" :key="group.id" class="demo-group-card" :data-testid="`group-buy-card-${group.id}`">
          <div class="demo-group-card-head"><div><span class="demo-kicker">{{ group.supplierType === 'external' ? '外部廠商・抽成 3%' : '統一集團商品・免抽成' }}</span><h3>{{ group.name }}</h3></div><span class="status">{{ group.statusLabel }}</span></div>
          <p>{{ group.description }}</p>
          <div class="demo-group-metrics"><span>進度 <strong>{{ group.progressUnits }}/{{ group.thresholdUnits }}</strong></span><span>預計到貨 <strong>{{ dateLabel(group.expectedArrival) }}</strong></span></div>
          <div class="demo-progress" role="progressbar" :aria-valuenow="group.progressUnits" :aria-valuemin="0" :aria-valuemax="group.thresholdUnits" :aria-label="`${group.name} 成團進度`"><span :style="{ width: progressWidth(group.progressUnits, group.thresholdUnits) }" /></div>
          <div class="demo-group-card-foot"><span>社區價 {{ money(group.variants[0]?.price ?? 0) }} 起</span><RouterLink class="button primary" :to="{ name: 'demo-group-buy', params: { groupBuyId: group.id } }">查看團購</RouterLink></div>
        </article>
      </div>
      <p v-if="!dashboard.activeGroupBuys.length" class="demo-empty">目前沒有進行中的團購，請稍後再回來看看。</p>
    </section>

    <div class="demo-three-column">
      <section class="panel demo-panel" aria-labelledby="repair-title">
        <div class="demo-section-heading"><div><p class="eyebrow">REPAIR TRACKING</p><h2 id="repair-title">報修進度</h2></div><span class="demo-count-badge">{{ dashboard.repairs.length }} 筆</span></div>
        <ul class="demo-timeline"><li v-for="item in dashboard.repairs" :key="item.id" :class="{ completed: item.status === 'completed' }"><span class="demo-timeline-dot" /><div><strong>{{ item.subject }}</strong><span class="demo-meta">{{ item.statusLabel }}・{{ item.note }}</span></div></li></ul>
      </section>
      <section class="panel demo-panel" aria-labelledby="maintenance-title">
        <div class="demo-section-heading"><div><p class="eyebrow">CARE SCHEDULE</p><h2 id="maintenance-title">設備保養</h2></div><span class="demo-count-badge">{{ dashboard.maintenance.length }} 項</span></div>
        <ul class="demo-status-list"><li v-for="item in dashboard.maintenance" :key="item.id"><div><strong>{{ item.name }}</strong><span class="demo-meta">下次 {{ item.nextDueAt }}</span></div><span class="status" :class="{ warn: item.status === 'overdue' }">{{ item.statusLabel }}</span></li></ul>
      </section>
      <section class="panel demo-panel" aria-labelledby="facility-title">
        <div class="demo-section-heading"><div><p class="eyebrow">NEXT TWO WEEKS</p><h2 id="facility-title">公設預約</h2></div><span class="demo-count-badge">{{ dashboard.reservations.length }} 筆</span></div>
        <ul class="demo-list demo-compact-list"><li v-for="item in dashboard.reservations" :key="item.id"><div><strong>{{ item.facility }}</strong><span class="demo-meta">{{ dateLabel(item.date) }}・{{ item.time }}</span></div><span class="demo-meta">{{ item.resident }}</span></li></ul>
      </section>
    </div>

    <details class="panel demo-panel demo-history" data-testid="group-buy-history">
      <summary><span><span class="eyebrow">GROUP BUY HISTORY</span><strong>團購歷史（{{ dashboard.groupBuyHistory.length }} 檔）</strong></span><span class="demo-summary-hint">展開查看不同狀態</span></summary>
      <div class="demo-history-grid"><div v-for="group in dashboard.groupBuyHistory" :key="group.id"><strong>{{ group.name }}</strong><span class="status" :data-status="group.status">{{ group.statusLabel }}</span><small>{{ group.progressUnits }}/{{ group.thresholdUnits }} 單位</small></div></div>
    </details>
  </section>
  <div v-else class="panel demo-loading" role="status">正在整理日光森林社區資料…</div>
</template>

<style scoped>
.demo-care-push {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: center;
  border-color: var(--ink);
  background: var(--yellow, #fde68a);
}
.demo-care-push-icon { font-size: 2.25rem; }
.demo-care-push-copy { min-width: 0; }
.demo-care-push-copy h2 { margin: 0 0 .35rem; }
.demo-care-push-copy p { margin: .2rem 0 .45rem; }
.demo-care-push-actions { justify-content: flex-end; }
@media (max-width: 720px) {
  .demo-care-push { grid-template-columns: auto minmax(0, 1fr); }
  .demo-care-push-actions { grid-column: 1 / -1; justify-content: flex-start; }
}
</style>
