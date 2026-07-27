<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  createInsightsClient,
  type BehaviorSummary,
  type BriefingItem,
  type Recommendation,
} from '@/api/insightsClient'
import { useDemoStore } from '@/stores/demo'
import { useSessionStore } from '@/stores/session'

const store = useDemoStore()
const session = useSessionStore()
const router = useRouter()

const summary = ref<BehaviorSummary | null>(null)
const recommendations = ref<Recommendation[]>([])
const briefing = ref<BriefingItem[]>([])
const status = ref<'idle' | 'loading' | 'ready' | 'unavailable'>('idle')
const need = ref('')

/** 起手式用真實說法，不是功能名稱——它同時負責教學（ADR-0016）。 */
const starters = [
  '浴室的燈不亮了',
  '想找人來打掃',
  '週末想訂餐廳',
]

const hasHistory = computed(() => (summary.value?.totalOrders ?? 0) > 0)
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`

const KIND_LABELS: Record<BriefingItem['kind'], string> = {
  needs_your_decision: '等你決定',
  closing_soon: '即將截止',
  in_progress: '進行中',
  waiting_on_vendor: '等廠商回覆',
  suggestion: '建議',
}

/** 說「不感興趣」之後只收起建議；真正的待辦不是偏好問題，不該被關掉。 */
const visibleBriefing = computed(() =>
  store.recommendationDismissed
    ? briefing.value.filter((item) => item.kind !== 'suggestion')
    : briefing.value,
)

/**
 * 把證據講成人話。
 *
 * 不同種類的摘要帶的證據形狀不同（諮詢單／團購活動／官方訂單），
 * 但共同的承諾是一樣的：**每一則都指得出一件真實存在的東西**。
 */
function describeEvidence(record: Record<string, unknown>): string {
  if (record.type === 'inquiry') return `委託 ${record.id}`
  if (record.type === 'campaign') return `社區團購活動 #${record.id}`
  const parts = [
    String(record.serviceName ?? ''),
    record.occurredOn ? String(record.occurredOn) : '',
    record.orderNo ? `訂單 ${record.orderNo}` : '',
    record.detail ? `（${record.detail}）` : '',
  ].filter(Boolean)
  return parts.join('・')
}

function isSummary(value: unknown): value is BehaviorSummary {
  const candidate = value as BehaviorSummary | null
  return Boolean(candidate) && typeof candidate?.totalSpend === 'number' && Array.isArray(candidate?.services)
}

async function load() {
  // 新使用者沒有帳號，因此不會有任何紀錄——不需要也不應該去查
  if (!session.accountId) {
    summary.value = null
    recommendations.value = []
    briefing.value = []
    status.value = 'ready'
    return
  }
  status.value = 'loading'
  const client = createInsightsClient()
  try {
    const [loadedSummary, loadedRecommendations, loadedBriefing] = await Promise.all([
      client.summary(session.accountId),
      client.recommendations(session.accountId),
      client.today(session.accountId),
    ])
    if (!isSummary(loadedSummary)) {
      status.value = 'unavailable'
      return
    }
    summary.value = loadedSummary
    recommendations.value = Array.isArray(loadedRecommendations) ? loadedRecommendations : []
    briefing.value = Array.isArray(loadedBriefing) ? loadedBriefing : []
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
  }
}

onMounted(load)
watch(() => session.accountId, load)

const matching = ref(false)
const needError = ref('')

/**
 * 需求交給**規劃器**處理，而不是單一意圖比對（ADR-0017）。
 *
 * 差別在使用者說「冷氣不冷，順便看看團購」時：意圖比對只會挑到一項服務、
 * 默默丟掉後半句；規劃器會把兩件事都排進計畫。像「我上次什麼時候叫過清潔」
 * 這種問題也不必被硬塞進某張表單才能得到答案。
 *
 * 這裡不做判讀，直接把話帶到生活管家頁——判讀結果與依據要在那裡攤開給使用者看，
 * 而不是在首頁默默決定完就跳走。
 */
async function submitNeed(text: string) {
  const description = text.trim()
  if (!description || matching.value) return
  matching.value = true
  needError.value = ''
  try {
    await router.push({ name: 'assistant', query: { need: description } })
  } finally {
    matching.value = false
  }
}
</script>

<template>
  <!-- 主動作：說出需求（ADR-0016） -->
  <section class="need-hero" aria-labelledby="need-title">
    <p class="eyebrow">{{ hasHistory ? '今日生活中心' : '歡迎使用' }}</p>
    <h1 id="need-title">今天需要什麼？</h1>
    <p class="need-lede">用你自己的話描述就好，我會判斷該用哪項服務並幫你把資料填齊。</p>

    <form class="need-form" @submit.prevent="submitNeed(need)">
      <label class="visually-hidden" for="need-input">描述你的需求</label>
      <input
        id="need-input"
        v-model="need"
        data-testid="need-input"
        type="text"
        placeholder="例如：浴室的燈不亮了"
        autocomplete="off"
      />
      <button class="button primary" type="submit" data-testid="need-submit" :disabled="matching">
        {{ matching ? '判讀中…' : '開始' }}
      </button>
    </form>

    <p v-if="needError" class="need-error" role="alert" data-testid="need-error">{{ needError }}</p>

    <div class="need-starters">
      <span class="muted">試試看：</span>
      <button
        v-for="starter in starters"
        :key="starter"
        class="starter-chip"
        type="button"
        data-testid="need-starter"
        @click="submitNeed(starter)"
      >{{ starter }}</button>
    </div>

    <p class="muted need-alt">
      已經知道要什麼？<RouterLink to="/user/services">直接瀏覽所有服務</RouterLink>
    </p>
  </section>

  <!--
    今日摘要：先回答「我現在該做什麼」，再談其他。
    排序依據是「誰在等誰」——卡在使用者身上的事排最前面（見 core/insights/today.py）。
  -->
  <!--
    收起最後一則建議之後區塊仍要留著——否則整個面板連同確認訊息一起消失，
    使用者按下「不感興趣」後得不到任何回饋，會以為是壞掉了。
  -->
  <section
    v-if="visibleBriefing.length || store.recommendationDismissed"
    class="panel briefing"
    aria-labelledby="briefing-title"
    data-testid="today-briefing"
  >
    <h2 id="briefing-title">今天該處理的事</h2>
    <p v-if="!visibleBriefing.length" class="muted">目前沒有需要處理的事。</p>
    <ul v-else class="briefing-list">
      <li v-for="item in visibleBriefing" :key="item.id" class="briefing-item" :class="item.kind" data-testid="briefing-item">
        <div class="briefing-body">
          <!-- 種類不倚賴顏色傳達，文字本身讀得出輕重（WCAG 1.4.1） -->
          <span class="briefing-tag" :data-kind="item.kind">{{ KIND_LABELS[item.kind] }}</span>
          <strong>{{ item.title }}</strong>
          <p class="muted">{{ item.detail }}</p>

          <!-- 可解釋性：這一則憑什麼出現在你的畫面上（ADR-0011） -->
          <details v-if="item.evidence.length" class="reason-details">
            <summary>為什麼提這件事？</summary>
            <ul :data-testid="`briefing-evidence-${item.id}`">
              <li v-for="(record, index) in item.evidence" :key="index">{{ describeEvidence(record) }}</li>
            </ul>
          </details>
        </div>
        <div class="briefing-actions">
          <RouterLink v-if="item.actionRoute" class="button inline" :to="item.actionRoute">
            {{ item.actionLabel }}
          </RouterLink>
          <!-- 只有建議可以說不感興趣；待辦不是偏好問題，不該被「關掉」 -->
          <button
            v-if="item.kind === 'suggestion'"
            class="text-button"
            type="button"
            data-testid="briefing-dismiss"
            @click="store.dismissRecommendation"
          >不感興趣</button>
        </div>
      </li>
    </ul>
    <p v-if="store.recommendationDismissed" class="muted" role="status" data-testid="briefing-dismissed">
      已調整你的偏好，之後會減少這類建議；這不會永久封鎖相關服務。
      <button class="text-button" type="button" @click="store.undoDismissRecommendation">復原</button>
    </p>
    <p class="muted source-note">依你的委託、社區活動與使用紀錄以規則整理，非語言模型生成。</p>
  </section>

  <!-- 零狀態：新使用者沒有紀錄，這裡負責說明接下來會發生什麼 -->
  <section v-if="status === 'ready' && !hasHistory" class="panel onboarding" aria-labelledby="onboarding-title">
    <h2 id="onboarding-title">接下來會這樣進行</h2>
    <ol class="onboarding-steps" data-testid="onboarding-steps">
      <li><strong>描述需求</strong><span>用日常說法就好，不必知道服務名稱。</span></li>
      <li><strong>補齊必要資訊</strong><span>只問這項服務真正需要的欄位，其餘自動略過。</span></li>
      <li><strong>確認後才送出</strong><span>金額與內容先讓你確認，確認前不會建立任何委託。</span></li>
    </ol>
    <p class="muted">完成第一件事之後，這裡會顯示進度與值得提醒你的事。</p>
  </section>

  <!-- 有紀錄時：使用概況（「該做什麼」已由上方今日摘要負責） -->
  <div v-else-if="status === 'ready'" class="grid">
    <aside class="panel span-12" aria-labelledby="month-overview">
      <h2 id="month-overview">你的使用概況</h2>
      <div v-if="summary" class="metric-row">
        <div class="metric"><span>已完成消費</span><strong data-testid="metric-spend">{{ currency(summary.totalSpend) }}</strong></div>
        <div class="metric"><span>進行中</span><strong data-testid="metric-open">{{ summary.openOrders }}</strong></div>
        <div class="metric"><span>使用服務</span><strong>{{ summary.distinctServices }}</strong></div>
        <div class="metric"><span>累積點數</span><strong>{{ summary.earnedPoints.toLocaleString('zh-TW') }}</strong></div>
      </div>
      <ul v-if="summary?.services.length" class="plain-list" data-testid="service-usage-list">
        <li v-for="usage in summary.services" :key="usage.serviceName">
          <strong>{{ usage.serviceName }}</strong> {{ usage.count }} 次
          <span v-if="usage.daysSinceLast !== null" class="muted">・{{ usage.daysSinceLast }} 天前</span>
        </li>
      </ul>
      <p class="muted source-note">來源：你的服務紀錄</p>
    </aside>
  </div>

  <p v-else-if="status === 'unavailable'" class="panel muted" role="status">
    目前無法取得你的使用紀錄，請確認後端服務是否啟動。
  </p>
</template>
