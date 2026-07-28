<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { createInsightsClient, type BehaviorSummary, type BriefingItem } from '@/api/insightsClient'
import { createLifestyleClient } from '@/api/lifestyleClient'
import { useDemoStore } from '@/stores/demo'
import { useSessionStore } from '@/stores/session'

const store = useDemoStore()
const session = useSessionStore()
const router = useRouter()
const lifestyle = createLifestyleClient()

const summary = ref<BehaviorSummary | null>(null)
const briefing = ref<BriefingItem[]>([])
const status = ref<'idle' | 'loading' | 'ready' | 'unavailable'>('idle')
const need = ref('')
const feedbackStatus = ref('')
const matching = ref(false)

const starters = ['浴室的燈不亮了', '想找人來打掃', '週末想訂餐廳']
const hasHistory = computed(() => (summary.value?.totalOrders ?? 0) > 0)
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`

const KIND_LABELS: Record<BriefingItem['kind'], string> = {
  needs_your_decision: '等你決定',
  closing_soon: '即將截止',
  in_progress: '進行中',
  waiting_on_vendor: '等廠商回覆',
  suggestion: '建議',
}

const visibleBriefing = computed(() =>
  briefing.value.filter((item) => !store.dismissedRecommendationIds.includes(item.id)),
)
const pendingBriefing = computed(() => visibleBriefing.value.filter((item) => item.kind !== 'suggestion'))
const suggestedBriefing = computed(() => visibleBriefing.value.filter((item) => item.kind === 'suggestion'))
const lastDismissedRecommendation = computed(() =>
  briefing.value.find((item) => item.id === store.lastDismissedRecommendationId) ?? null,
)

function dismissRecommendation(item: BriefingItem) {
  store.dismissRecommendation(item.id)
  feedbackStatus.value = ''
  if (session.accountId) {
    void lifestyle.feedback(session.accountId, item.source, 'dismiss').catch(() => {
      feedbackStatus.value = '建議已在本次畫面收起，但偏好目前無法同步，請稍後再試。'
    })
  }
}

function undoRecommendation(item: BriefingItem) {
  store.undoDismissRecommendation(item.id)
  feedbackStatus.value = ''
  if (session.accountId) {
    void lifestyle.feedback(session.accountId, item.source, 'undo').catch(() => {
      feedbackStatus.value = '畫面已復原，但偏好目前無法同步，請稍後再試。'
    })
  }
}

function describeEvidence(record: Record<string, unknown>): string {
  if (record.type === 'inquiry') return `委託 ${record.id}`
  if (record.type === 'campaign') return `群組活動 #${record.id}`
  return [
    String(record.serviceName ?? ''),
    record.occurredOn ? String(record.occurredOn) : '',
    record.orderNo ? `訂單 ${record.orderNo}` : '',
    record.detail ? `（${record.detail}）` : '',
  ].filter(Boolean).join('・')
}

function isSummary(value: unknown): value is BehaviorSummary {
  const candidate = value as BehaviorSummary | null
  return Boolean(candidate) && typeof candidate?.totalSpend === 'number' && Array.isArray(candidate?.services)
}

async function load() {
  if (!session.accountId) {
    summary.value = null
    briefing.value = []
    status.value = 'ready'
    return
  }
  status.value = 'loading'
  const client = createInsightsClient()
  try {
    const [loadedSummary, loadedBriefing] = await Promise.all([
      client.summary(session.accountId),
      client.today(session.accountId),
    ])
    if (!isSummary(loadedSummary)) {
      status.value = 'unavailable'
      return
    }
    summary.value = loadedSummary
    briefing.value = Array.isArray(loadedBriefing) ? loadedBriefing : []
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
  }
}

onMounted(load)
watch(() => session.accountId, load)

async function submitNeed(text: string) {
  const description = text.trim()
  if (!description || matching.value) return
  matching.value = true
  try {
    await router.push({ name: 'assistant', query: { need: description } })
  } finally {
    matching.value = false
  }
}
</script>

<template>
  <section class="member-page home-page">
    <section class="home-overview" data-home-section="overview" aria-labelledby="home-title">
      <header class="page-heading">
        <div>
          <p class="eyebrow">YOUR DAY</p>
          <h1 id="home-title">生活總覽</h1>
          <p class="muted">先看資源與待辦，再把接下來的事交給 AI。</p>
        </div>
        <span class="page-status">{{ hasHistory ? '資料已更新' : '從第一件事開始' }}</span>
      </header>

      <div v-if="status === 'ready' && summary" class="panel overview-panel">
        <div class="metric-row home-metrics">
          <div class="metric"><span>資料期間消費</span><strong data-testid="metric-spend">{{ currency(summary.totalSpend) }}</strong></div>
          <div class="metric"><span>累積點數</span><strong>{{ summary.earnedPoints.toLocaleString('zh-TW') }}</strong></div>
          <div class="metric"><span>進行中</span><strong data-testid="metric-open">{{ summary.openOrders }}</strong></div>
          <div class="metric"><span>使用服務</span><strong>{{ summary.distinctServices }}</strong></div>
        </div>
        <div class="overview-footer">
          <p class="source-note">來源：競賽提供的服務紀錄；「資料期間消費」不假稱為即時月帳單。</p>
          <RouterLink class="text-link" to="/user/points">查看點數與優惠方案 →</RouterLink>
        </div>
        <details v-if="summary.services.length" class="usage-disclosure">
          <summary>查看常用服務紀錄</summary>
          <ul class="plain-list" data-testid="service-usage-list">
            <li v-for="usage in summary.services" :key="usage.serviceName">
              <strong>{{ usage.serviceName }}</strong> {{ usage.count }} 次
              <span v-if="usage.daysSinceLast !== null" class="muted">・{{ usage.daysSinceLast }} 天前</span>
            </li>
          </ul>
        </details>
      </div>
      <div v-else-if="status === 'ready'" class="panel empty-overview">
        <strong>尚無消費與點數紀錄</strong>
        <p class="muted">新會員不會看到其他人的展示數字；完成第一件服務後才開始累積。</p>
      </div>
      <p v-else-if="status === 'unavailable'" class="panel muted" role="status">目前無法取得你的使用紀錄，請確認後端服務是否啟動。</p>
      <div v-else class="panel" role="status">正在整理你的生活資訊…</div>
    </section>

    <section class="panel briefing" data-home-section="pending" data-testid="today-pending" aria-labelledby="pending-title">
      <div class="section-title-row">
        <div>
          <p class="eyebrow">NEXT ACTION</p>
          <h2 id="pending-title">待處理事項</h2>
        </div>
        <RouterLink class="text-link" to="/user/orders">查看全部訂單</RouterLink>
      </div>
      <p v-if="!pendingBriefing.length" class="muted">目前沒有等你處理的案件。</p>
      <ul v-else class="briefing-list">
        <li v-for="item in pendingBriefing" :key="item.id" class="briefing-item" :class="item.kind" data-testid="briefing-item">
          <div class="briefing-body">
            <span class="briefing-tag" :data-kind="item.kind">{{ KIND_LABELS[item.kind] }}</span>
            <strong>{{ item.title }}</strong>
            <p class="muted">{{ item.detail }}</p>
            <details v-if="item.evidence.length" class="reason-details">
              <summary>為什麼提這件事？</summary>
              <ul :data-testid="`briefing-evidence-${item.id}`">
                <li v-for="(record, index) in item.evidence" :key="index">{{ describeEvidence(record) }}</li>
              </ul>
            </details>
          </div>
          <RouterLink v-if="item.actionRoute" class="button inline" :to="item.actionRoute">{{ item.actionLabel }}</RouterLink>
        </li>
      </ul>
      <p class="source-note">依你的委託與案件狀態以規則整理，非語言模型生成。</p>
    </section>

    <section class="need-hero home-ai" data-home-section="ai" aria-labelledby="need-title">
      <p class="eyebrow">AI LIFE ASSISTANT</p>
      <h2 id="need-title">接下來想處理什麼？</h2>
      <p class="need-lede">直接說生活目標，AI 會拆成可確認的步驟，不會只丟一串服務名稱。</p>
      <form class="need-form" @submit.prevent="submitNeed(need)">
        <label class="visually-hidden" for="need-input">描述你的需求</label>
        <input id="need-input" v-model="need" data-testid="need-input" type="text" placeholder="例如：爸媽週六要來，幫我安排清潔和修繕" autocomplete="off" />
        <button class="button primary" type="submit" data-testid="need-submit" :disabled="matching">{{ matching ? '準備中…' : '交給 AI' }}</button>
      </form>
      <div class="need-starters">
        <span class="muted">試試看：</span>
        <button v-for="starter in starters" :key="starter" class="starter-chip" type="button" data-testid="need-starter" @click="submitNeed(starter)">{{ starter }}</button>
      </div>
      <ol v-if="status === 'ready' && !hasHistory" class="onboarding-steps compact" data-testid="onboarding-steps">
        <li><strong>描述需求</strong><span>用日常說法即可。</span></li>
        <li><strong>預覽方案</strong><span>AI 補齊必要資訊。</span></li>
        <li><strong>確認才執行</strong><span>交易與送單不會偷跑。</span></li>
      </ol>
    </section>

    <section class="panel briefing" data-home-section="recommendations" aria-labelledby="recommendation-title">
      <div class="section-title-row">
        <div>
          <p class="eyebrow">FOR YOU</p>
          <h2 id="recommendation-title">為你整理的建議</h2>
        </div>
      </div>
      <p v-if="!suggestedBriefing.length" class="muted">使用服務後，這裡會出現有依據、可單獨調整的建議。</p>
      <ul v-else class="briefing-list">
        <li v-for="item in suggestedBriefing" :key="item.id" class="briefing-item suggestion" data-testid="briefing-item">
          <div class="briefing-body">
            <span class="briefing-tag" data-kind="suggestion">建議</span>
            <strong>{{ item.title }}</strong>
            <p class="muted">{{ item.detail }}</p>
            <details v-if="item.evidence.length" class="reason-details">
              <summary>為什麼提這件事？</summary>
              <ul :data-testid="`briefing-evidence-${item.id}`">
                <li v-for="(record, index) in item.evidence" :key="index">{{ describeEvidence(record) }}</li>
              </ul>
            </details>
          </div>
          <div class="briefing-actions">
            <RouterLink v-if="item.actionRoute" class="button inline" :to="item.actionRoute">{{ item.actionLabel }}</RouterLink>
            <button class="text-button" type="button" data-testid="briefing-dismiss" :aria-label="`不顯示「${item.title}」這則建議`" @click="dismissRecommendation(item)">不感興趣</button>
          </div>
        </li>
      </ul>
      <p v-if="lastDismissedRecommendation" class="recommendation-feedback" role="status" data-testid="briefing-dismissed">
        已收起「{{ lastDismissedRecommendation.title }}」，其他建議不受影響。
        <button class="text-button" type="button" @click="undoRecommendation(lastDismissedRecommendation)">復原</button>
      </p>
      <p v-if="feedbackStatus" class="need-error" role="alert">{{ feedbackStatus }}</p>
      <p class="source-note">依你的使用紀錄以規則整理，非語言模型生成。</p>
    </section>

    <section class="home-section" data-home-section="shortcuts" aria-labelledby="shortcuts-title">
      <div class="section-title-row"><h2 id="shortcuts-title">常用功能</h2></div>
      <div class="shortcut-grid">
        <RouterLink class="panel shortcut-card" to="/user/orders"><strong>追蹤訂單</strong><span>報價、進度與異常處理</span></RouterLink>
        <RouterLink class="panel shortcut-card" to="/user/services"><strong>瀏覽服務</strong><span>清潔、修繕、訂位與購物</span></RouterLink>
        <RouterLink class="panel shortcut-card" to="/user/community"><strong>群組共享</strong><span>家庭、朋友與社區任務</span></RouterLink>
      </div>
    </section>

    <section class="panel promotion-card" data-home-section="promotions" aria-labelledby="promotion-title">
      <div>
        <p class="eyebrow">SMART SAVING</p>
        <h2 id="promotion-title">不要只看點數，讓 AI 一起算優惠</h2>
        <p class="muted">整合展示點數、優惠券與支付方式，先試算再決定是否使用。</p>
      </div>
      <RouterLink class="button primary" to="/user/points">查看節省方案</RouterLink>
    </section>
  </section>
</template>
