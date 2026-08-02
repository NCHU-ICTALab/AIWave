<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { backendAnswered } from '@/api/http'
import { createInsightsClient, type BehaviorSummary, type BriefingItem } from '@/api/insightsClient'
import { createLifeTaskClient, type LifeTask } from '@/api/lifeTaskClient'
import { createLifestyleClient } from '@/api/lifestyleClient'
import CommunityTicker from '@/components/CommunityTicker.vue'
import FatherDayPushCard from '@/components/FatherDayPushCard.vue'
import SubscriptionLock from '@/components/SubscriptionLock.vue'
import {
  listCalendarEvents, listNotifications, markNotificationRead,
  type CalendarEvent, type NotificationRecord,
} from '@/api/platformClient'
import { createPointsClient, type PointsWallet } from '@/api/pointsClient'
import { useAgentSessionStore } from '@/stores/agentSession'
import { useDemoStore } from '@/stores/demo'
import { useSessionStore } from '@/stores/session'

const store = useDemoStore()
const session = useSessionStore()
const agentSession = useAgentSessionStore()
const router = useRouter()
const lifestyle = createLifestyleClient()
const lifeTasksClient = createLifeTaskClient()
const pointsClient = createPointsClient()

const summary = ref<BehaviorSummary | null>(null)
const briefing = ref<BriefingItem[]>([])
const lifeTasks = ref<LifeTask[]>([])
const wallet = ref<PointsWallet | null>(null)
const status = ref<'idle' | 'loading' | 'ready' | 'unavailable'>('idle')
/** 為什麼取不到資料：後端回了錯 / 形狀不對 / 真的連不上，三者不可以講成同一句話。 */
const unavailableReason = ref<'' | 'failed' | 'malformed' | 'offline'>('')
const need = ref('')
const feedbackStatus = ref('')
const matching = ref(false)

const starters = ['浴室的燈不亮了', '想找人來打掃', '週末想訂餐廳']
const hasHistory = computed(() => (summary.value?.totalOrders ?? 0) > 0)
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`

// ── 問候與導語:比照原型 dashboard.html「早安,小圓」+ page-lead;數字誠實取自現有資料 ──
const now = new Date()
const greeting = computed(() => {
  const hour = now.getHours()
  if (hour < 11) return '早安'
  if (hour < 18) return '午安'
  return '晚安'
})
const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'] as const
const dateLine = computed(
  () => `今天是 ${now.getFullYear()} 年 ${now.getMonth() + 1} 月 ${now.getDate()} 日（週${WEEKDAYS[now.getDay()]}）`,
)

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
const activeLifeTasks = computed(() => lifeTasks.value.filter((task) => !['completed', 'cancelled'].includes(task.status)))
const suggestedBriefing = computed(() => visibleBriefing.value.filter((item) => item.kind === 'suggestion'))
const lastDismissedRecommendation = computed(() =>
  briefing.value.find((item) => item.id === store.lastDismissedRecommendationId) ?? null,
)
const pendingCount = computed(() => pendingBriefing.value.length + activeLifeTasks.value.length)

// 到期提示:只描述帳本裡「最近一批仍有效期的獲得點數」,不推算剩餘可用量(那需要 FIFO 沖銷)
const nextExpiringEarn = computed(() => {
  const entries = wallet.value?.entries ?? []
  const nowIso = new Date().toISOString()
  return entries
    .filter((entry) => entry.type === 'earn' && entry.expiresAt && entry.expiresAt > nowIso)
    .sort((a, b) => (a.expiresAt ?? '').localeCompare(b.expiresAt ?? ''))[0] ?? null
})
const formatShortDate = (iso: string) => {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso.slice(0, 10) : `${date.getMonth() + 1}/${date.getDate()}`
}

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
    lifeTasks.value = []
    wallet.value = null
    status.value = 'ready'
    return
  }
  status.value = 'loading'
  const client = createInsightsClient()
  try {
    const [loadedSummary, loadedBriefing, loadedLifeTasks, loadedWallet] = await Promise.all([
      client.summary(session.accountId),
      client.today(session.accountId),
      lifeTasksClient.list({ accountId: session.accountId }).catch(() => []),
      pointsClient.wallet().catch(() => null),
    ])
    if (!isSummary(loadedSummary)) {
      // 後端有回,只是內容不是預期的形狀。這不是「後端沒起來」。
      unavailableReason.value = 'malformed'
      status.value = 'unavailable'
      return
    }
    summary.value = loadedSummary
    briefing.value = Array.isArray(loadedBriefing) ? loadedBriefing : []
    lifeTasks.value = Array.isArray(loadedLifeTasks) ? loadedLifeTasks : []
    wallet.value = loadedWallet
    status.value = 'ready'
  } catch (reason) {
    // 有 HTTP 狀態碼就代表後端有回應(例如 401 憑證過期);叫使用者去啟動一個
    // 已經在跑的服務,只會讓真正的原因更難找。
    unavailableReason.value = backendAnswered(reason) ? 'failed' : 'offline'
    status.value = 'unavailable'
  }
}

// ── 近期行程與通知(M4):獨立載入,失敗只影響這張卡,不拖垮整頁 ──
const upcomingEvents = ref<CalendarEvent[]>([])
const unreadCount = ref(0)
const recentNotifications = ref<NotificationRecord[]>([])
const notificationsOpen = ref(false)
const scheduleStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')

const formatEventTime = (value: string | null | undefined) => (value ?? '').replace('T', ' ').slice(0, 16)

async function loadSchedule() {
  scheduleStatus.value = 'loading'
  try {
    const [events, inbox] = await Promise.all([listCalendarEvents(), listNotifications()])
    upcomingEvents.value = (Array.isArray(events) ? events : [])
      .slice()
      .sort((a, b) => a.startsAt.localeCompare(b.startsAt))
      .slice(0, 3)
    const inboxRecord = inbox as { unreadCount?: unknown; items?: unknown } | null
    unreadCount.value = typeof inboxRecord?.unreadCount === 'number' ? inboxRecord.unreadCount : 0
    recentNotifications.value = Array.isArray(inboxRecord?.items)
      ? (inboxRecord.items as NotificationRecord[]).slice(0, 3)
      : []
    scheduleStatus.value = 'ready'
  } catch {
    scheduleStatus.value = 'unavailable'
  }
}

async function markRead(item: NotificationRecord) {
  try {
    const updated = await markNotificationRead(item.id)
    recentNotifications.value = recentNotifications.value.map((row) => (row.id === updated.id ? updated : row))
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch {
    // 已讀狀態同步失敗不擋畫面;下次載入會回到真實狀態
  }
}

onMounted(() => {
  void load()
  void loadSchedule()
})
watch(() => session.accountId, load)

/**
 * M8(spec 15 §4.1):首頁不再用 query 帶字串,而是把需求排進共用 agent store,
 * AI 工作區掛載時 flushPending 自動送出——首頁、側欄與 AI 頁因此是同一段對話。
 */
async function submitNeed(text: string) {
  const description = text.trim()
  if (!description || matching.value) return
  matching.value = true
  try {
    agentSession.queueMessage(description)
    await router.push({ name: 'assistant' })
  } finally {
    matching.value = false
  }
}
</script>

<template>
  <section class="member-page home-page">
    <!-- 版面比照核准原型 design-system/aiwave/pages/dashboard.html:問候 h1 + page-lead,之後單欄 card 堆疊 -->
    <header class="home-heading">
      <h1 id="home-title">{{ greeting }}，{{ session.displayName }}</h1>
      <p class="page-lead">
        {{ dateLine }}。
        <template v-if="status === 'ready' && summary">
          你有 {{ pendingCount }} 件待處理事項、<strong class="lead-count" data-testid="metric-open">{{ summary.openOrders }}</strong> 筆服務進行中。
        </template>
        <template v-else-if="status === 'ready'">從第一件事開始。</template>
      </p>
    </header>

    <CommunityTicker />

    <!--
      一般住戶與王小明共用同一個主動關懷卡片：推薦服務，也說清楚可以買什麼。
      免費社區看到的是同一張卡片的霧面版本——看得到訂閱換到什麼，但點不到。
    -->
    <SubscriptionLock
      :locked="!session.isSubscriber"
      title="AI 主動關懷提醒"
      description="訂閱社區後，AI 會依節日與你的生活紀錄主動整理可以安排的服務；免費社區仍可使用社區團購。"
      :heading-level="2"
    >
      <FatherDayPushCard />
    </SubscriptionLock>

    <!-- 1. 點數與本月消費 -->
    <section class="home-card" data-home-section="overview" aria-labelledby="points-title">
      <div v-if="status === 'ready' && summary" class="panel home-panel">
        <h2 id="points-title">點數與本月消費</h2>
        <div class="kpi-grid">
          <div class="kpi">
            <strong class="kpi-value" data-testid="metric-points">{{ (wallet?.balance ?? summary.earnedPoints).toLocaleString('zh-TW') }}</strong>
            <span class="kpi-label">可用點數（Demo 帳本）</span>
            <span v-if="nextExpiringEarn" class="kpi-note">其中一批 {{ nextExpiringEarn.amount.toLocaleString('zh-TW') }} 點效期至 {{ formatShortDate(nextExpiringEarn.expiresAt!) }}</span>
          </div>
          <div class="kpi">
            <strong class="kpi-value" data-testid="metric-spend">{{ currency(summary.totalSpend) }}</strong>
            <span class="kpi-label">資料期間消費</span>
            <span class="kpi-note">{{ summary.totalOrders }} 筆官方服務紀錄</span>
          </div>
          <div class="kpi-action">
            <RouterLink class="button inline" to="/user/points">查看點數明細與兌換</RouterLink>
          </div>
        </div>
        <p class="source-note">資料來源：Demo points ledger 與競賽提供的服務紀錄；「資料期間消費」不假稱為即時月帳單。</p>
      </div>
      <div v-else-if="status === 'ready'" class="panel home-panel empty-overview">
        <h2 id="points-title">點數與本月消費</h2>
        <strong>尚無消費與點數紀錄</strong>
        <p class="muted">新會員不會看到其他人的展示數字；完成第一件服務後才開始累積。</p>
      </div>
      <p v-else-if="status === 'unavailable'" class="panel muted" role="status" :data-reason="unavailableReason">
        目前無法取得你的使用紀錄——{{ unavailableReason === 'offline'
          ? '連不上後端服務，請確認 API 是否已啟動。'
          : unavailableReason === 'malformed'
            ? '後端有回應，但資料格式不如預期。'
            : '後端有回應但拒絕了這次查詢（可能是登入憑證已失效），請重新登入再試。' }}
      </p>
      <div v-else class="panel" role="status">正在整理你的生活資訊…</div>
    </section>

    <!-- 2. 待處理事項 -->
    <section class="panel home-panel briefing" data-home-section="pending" data-testid="today-pending" aria-labelledby="pending-title">
      <div class="section-title-row">
        <h2 id="pending-title">待處理事項</h2>
        <RouterLink class="text-link" to="/user/orders">查看全部訂單</RouterLink>
      </div>
      <p v-if="!pendingBriefing.length && !activeLifeTasks.length" class="muted">
        <template v-if="summary?.openOrders">目前沒有等你確認的案件；另有 {{ summary.openOrders }} 筆官方紀錄尚未結案，可到訂單頁查看。</template>
        <template v-else>目前沒有等你處理的案件。</template>
      </p>
      <ul v-if="activeLifeTasks.length" class="briefing-list" data-testid="life-task-briefing-list">
        <li v-for="task in activeLifeTasks" :key="task.id" class="briefing-item in_progress" data-testid="life-task-briefing-item">
          <div class="briefing-body">
            <span class="briefing-tag status" data-kind="in_progress">跨服務任務</span>
            <strong>{{ task.items.map((item) => item.title).join('＋') }}</strong>
            <p class="muted">{{ task.statusLabel }}<span v-if="task.scheduledDate">・{{ task.scheduledDate }}</span></p>
          </div>
          <RouterLink
            class="button inline"
            :to="task.status === 'draft' || task.status === 'partial_failure'
              ? { name: 'assistant', query: { task: task.id } }
              : { name: 'orders', query: { task: task.id } }"
          >{{ task.status === 'draft' || task.status === 'partial_failure' ? '繼續安排' : '查看進度' }}</RouterLink>
        </li>
      </ul>
      <ul v-if="pendingBriefing.length" class="briefing-list">
        <li v-for="item in pendingBriefing" :key="item.id" class="briefing-item" :class="item.kind" data-testid="briefing-item">
          <div class="briefing-body">
            <span class="briefing-tag status" :data-kind="item.kind">{{ KIND_LABELS[item.kind] }}</span>
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
      <!-- 近期行程卡:行事曆 projection 的前三筆 + 通知未讀;非六大區塊之一,掛在待處理事項之下 -->
      <SubscriptionLock
        :locked="!session.isSubscriber"
        title="近期行程與通知"
        description="行事曆、提醒與通知整理是訂閱功能；訂閱後這裡會列出接下來要發生的事。"
        :heading-level="3"
      >
        <div class="panel schedule-card" data-testid="upcoming-schedule">
          <div class="section-title-row">
            <h3>近期行程</h3>
            <RouterLink class="text-link" to="/user/calendar">開啟行事曆</RouterLink>
          </div>
          <p v-if="scheduleStatus === 'unavailable'" class="muted" role="status">
            行程與通知暫時無法載入;其他內容不受影響。
          </p>
          <template v-else>
            <ul v-if="upcomingEvents.length" class="plain-list" data-testid="upcoming-event-list">
              <li v-for="event in upcomingEvents" :key="event.id">
                <strong>{{ event.title }}</strong>
                <span class="muted">・{{ formatEventTime(event.startsAt) }}</span>
              </li>
            </ul>
            <p v-else class="muted">近期沒有已排定的行程。</p>
            <div v-if="unreadCount > 0">
              <button class="text-button" type="button" data-testid="notification-toggle"
                :aria-expanded="notificationsOpen" @click="notificationsOpen = !notificationsOpen">
                通知 <span class="status" data-testid="notification-badge">{{ unreadCount }} 則未讀</span>
              </button>
              <ul v-if="notificationsOpen" class="plain-list" data-testid="notification-list">
                <li v-for="item in recentNotifications" :key="item.id">
                  <strong>{{ item.title }}</strong>
                  <span class="muted">・{{ item.body }}</span>
                  <button v-if="!item.readAt" class="text-button" type="button"
                    :data-testid="`notification-read-${item.id}`" @click="markRead(item)">標為已讀</button>
                </li>
              </ul>
            </div>
            <p class="source-note muted">進度、通知與行事曆來自同一份 StatusEvent(展示資料)。</p>
          </template>
        </div>
      </SubscriptionLock>
      <p class="source-note">依你的委託與案件狀態以規則整理，非語言模型生成。</p>
    </section>

    <!-- v4 生活圈入口：資料未審核時頁面會明確顯示 blocker，不顯示假範圍。 -->
    <SubscriptionLock
      :locked="!session.isSubscriber"
      title="會場生活圈"
      description="虛擬地圖、通勤圈與附近 7-ELEVEN／ibon／統一服務，訂閱後即可查看。"
      :heading-level="2"
    >
      <section class="panel home-panel" data-v4-section="life-circle" aria-labelledby="life-circle-title">
        <div class="section-title-row">
          <h2 id="life-circle-title">會場生活圈</h2>
          <RouterLink class="button inline" to="/user/life-circle">查看生活圈</RouterLink>
        </div>
        <p class="muted">從指定會場切換步行／機車與 10／15 分鐘；只在有經確認 GeoJSON 時顯示據點。</p>
      </section>
    </SubscriptionLock>

    <!-- 3. 交給 AI 管家 -->
    <SubscriptionLock
      :locked="!session.isSubscriber"
      title="AI 管家"
      description="自然語言拆解、服務推薦與確認後安排，訂閱社區後即可使用。"
      :heading-level="2"
    >
      <section class="panel home-panel home-ai" data-home-section="ai" aria-labelledby="ai-title">
        <h2 id="ai-title">交給 AI 管家</h2>
        <p class="need-lede">用一句話描述需求，AI 會拆解成可確認的任務，例如「這週末找一間信義區四人餐廳」。</p>
        <form class="need-form" @submit.prevent="submitNeed(need)">
          <label class="visually-hidden" for="need-input">描述你的需求</label>
          <input id="need-input" v-model="need" data-testid="need-input" type="text" placeholder="例如：爸媽週六要來，幫我安排清潔和修繕" autocomplete="off" />
          <button class="button primary" type="submit" data-testid="need-submit" :disabled="matching">{{ matching ? '準備中…' : '交給 AI' }}</button>
        </form>
        <div class="need-starters">
          <span class="muted">試試看：</span>
          <button v-for="starter in starters" :key="starter" class="starter-chip" type="button" data-testid="need-starter" @click="submitNeed(starter)">{{ starter }}</button>
        </div>
        <div class="button-row ai-cta-row">
          <RouterLink class="button primary" to="/user/assistant">開始對話</RouterLink>
        </div>
        <ol v-if="status === 'ready' && !hasHistory" class="onboarding-steps compact" data-testid="onboarding-steps">
          <li><strong>描述需求</strong><span>用日常說法即可。</span></li>
          <li><strong>預覽方案</strong><span>AI 補齊必要資訊。</span></li>
          <li><strong>確認才執行</strong><span>交易與送單不會偷跑。</span></li>
        </ol>
      </section>
    </SubscriptionLock>

    <!-- 4. 給你的建議 -->
    <SubscriptionLock
      :locked="!session.isSubscriber"
      title="給你的建議"
      description="個人化服務建議與優惠整理，會在訂閱後依你的社區生活資料提供。"
      :heading-level="2"
    >
      <section class="panel home-panel briefing" data-home-section="recommendations" aria-labelledby="recommendation-title">
        <div class="section-title-row">
          <h2 id="recommendation-title">給你的建議</h2>
        </div>
        <p v-if="!suggestedBriefing.length" class="muted">使用服務後，這裡會出現有依據、可單獨調整的建議。</p>
        <ul v-else class="briefing-list">
          <li v-for="item in suggestedBriefing" :key="item.id" class="briefing-item suggestion" data-testid="briefing-item">
            <div class="briefing-body">
              <span class="briefing-tag status reco-badge" data-kind="suggestion">個人化</span>
              <strong>{{ item.title }}</strong>
              <p class="muted reco-why">{{ item.detail }}</p>
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
    </SubscriptionLock>

    <!-- 5. 常用功能 -->
    <section class="panel home-panel" data-home-section="shortcuts" aria-labelledby="shortcuts-title">
      <h2 id="shortcuts-title">常用功能</h2>
      <ul class="quick-links">
        <li><RouterLink :class="{ 'locked-shortcut': !session.isSubscriber }" :aria-label="session.isSubscriber ? '預約服務' : '預約服務，訂閱解鎖'" to="/user/services">預約服務<span v-if="!session.isSubscriber" aria-hidden="true"> 🔒</span></RouterLink></li>
        <li><RouterLink to="/user/orders">我的訂單</RouterLink></li>
        <li><RouterLink :class="{ 'locked-shortcut': !session.isSubscriber }" :aria-label="session.isSubscriber ? '行事曆' : '行事曆，訂閱解鎖'" to="/user/calendar">行事曆<span v-if="!session.isSubscriber" aria-hidden="true"> 🔒</span></RouterLink></li>
        <li><RouterLink :class="{ 'locked-shortcut': !session.isSubscriber }" :aria-label="session.isSubscriber ? '生活關懷與成果' : '生活關懷與成果，訂閱解鎖'" to="/user/wellbeing">生活關懷與成果<span v-if="!session.isSubscriber" aria-hidden="true"> 🔒</span></RouterLink></li>
        <li><RouterLink to="/user/community#my-groups-title">我的群組</RouterLink></li>
        <li><RouterLink to="/user/community">我的社區</RouterLink></li>
      </ul>
    </section>

    <!-- 6. 優惠內容(原型無此區,依 MASTER 閱讀順序保留在最後,樣式改為同款 card) -->
    <section class="panel home-panel promotion-card" data-home-section="promotions" aria-labelledby="promotion-title">
      <div>
        <h2 id="promotion-title">不要只看點數，讓 AI 一起算優惠</h2>
        <p class="muted">整合展示點數、優惠券與支付方式，先試算再決定是否使用。</p>
      </div>
      <RouterLink class="button primary" to="/user/points">查看節省方案</RouterLink>
    </section>
  </section>
</template>

<style scoped>
/* 版面語彙照原型:整頁單欄 card 堆疊,每張 card 是 .panel,h2 直接是區塊標題 */
.home-page {
  width: min(100%, 72rem);
  gap: var(--space-5, 1.25rem);
}
.home-heading h1 {
  margin: 0 0 0.35rem;
}
.page-lead {
  margin: 0;
  color: var(--muted, #666);
  font-size: 1.02rem;
}
.page-lead .lead-count {
  color: inherit;
  font-weight: 700;
}
.home-panel h2 {
  margin: 0 0 0.75rem;
}
.home-card {
  display: grid;
}
.locked-shortcut {
  color: var(--muted);
}

/* 點數與本月消費:三欄 KPI(原型 .grid.cols-3 + .kpi) */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: var(--space-4, 1rem);
  align-items: start;
}
.kpi {
  display: grid;
  gap: 0.15rem;
  min-width: 0;
  border-radius: 14px;
  background: var(--surface-2, #f5f5f5);
  padding: 0.9rem;
}
.kpi-value {
  font-size: clamp(1.6rem, 4vw, 2.2rem);
  line-height: 1.15;
  overflow-wrap: anywhere;
}
.kpi-label {
  color: var(--muted, #666);
  font-size: 0.82rem;
  font-weight: 700;
}
.kpi-note {
  color: var(--muted, #666);
  font-size: 0.78rem;
  font-weight: 500;
}
.kpi-action {
  align-self: center;
  justify-self: start;
}
.home-panel > .source-note {
  margin: var(--space-3, 0.75rem) 0 0;
}
.empty-overview {
  display: grid;
  gap: 0.35rem;
}

/* 待處理事項的狀態 badge:沿用全域 .status,依 kind 上原型的色票 */
.briefing-tag.status {
  align-self: flex-start;
}
.briefing-tag.status[data-kind='needs_your_decision'] {
  background: var(--peach, #ffd9c9);
}
.briefing-tag.status[data-kind='closing_soon'] {
  background: var(--blue, #cfe3ff);
}
.briefing-tag.status[data-kind='in_progress'],
.briefing-tag.status[data-kind='waiting_on_vendor'] {
  background: var(--lilac, #e6e6fa);
}
.briefing-tag.status[data-kind='suggestion'] {
  background: var(--mint, #cdeedd);
}

/* 交給 AI 管家:一般 card,不再是多欄 grid hero */
.home-ai {
  width: 100%;
  max-width: none;
  margin: 0;
  text-align: left;
}
.home-ai .need-lede {
  margin: 0 0 1rem;
  max-width: none;
}
.home-ai .need-form {
  margin-inline: 0;
}
.ai-cta-row {
  margin-top: var(--space-3, 0.75rem);
}

/* 常用功能:原型 .quick-links grid(五格) */
.quick-links {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}
.quick-links li {
  display: contents;
}
.quick-links a {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 56px;
  padding: 8px;
  border: 2px solid var(--ink, #1a1a1a);
  border-radius: 14px;
  background: var(--surface, #fff);
  box-shadow: 3px 3px 0 var(--ink, #1a1a1a);
  color: var(--ink, #1a1a1a);
  font-weight: 800;
  text-align: center;
  text-decoration: none;
}
.quick-links a:hover {
  translate: 1px 1px;
  box-shadow: 2px 2px 0 var(--ink, #1a1a1a);
}

/* 390px 單欄:KPI 與快速連結各自縮成單欄,card 內不橫向溢出 */
@media (max-width: 480px) {
  .kpi-grid,
  .quick-links {
    grid-template-columns: 1fr;
  }
}
</style>
