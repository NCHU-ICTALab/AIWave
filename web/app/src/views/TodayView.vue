<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  createInsightsClient,
  matchIntent,
  type BehaviorSummary,
  type Recommendation,
} from '@/api/insightsClient'
import { useDemoStore } from '@/stores/demo'
import { useSessionStore } from '@/stores/session'

const store = useDemoStore()
const session = useSessionStore()
const router = useRouter()

const summary = ref<BehaviorSummary | null>(null)
const recommendations = ref<Recommendation[]>([])
const status = ref<'idle' | 'loading' | 'ready' | 'unavailable'>('idle')
const need = ref('')

/** 起手式用真實說法，不是功能名稱——它同時負責教學（ADR-0016）。 */
const starters = [
  '浴室的燈不亮了',
  '想找人來打掃',
  '週末想訂餐廳',
]

const topRecommendation = computed(() => recommendations.value[0] ?? null)
const hasHistory = computed(() => (summary.value?.totalOrders ?? 0) > 0)
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`

function isSummary(value: unknown): value is BehaviorSummary {
  const candidate = value as BehaviorSummary | null
  return Boolean(candidate) && typeof candidate?.totalSpend === 'number' && Array.isArray(candidate?.services)
}

async function load() {
  // 新使用者沒有帳號，因此不會有任何紀錄——不需要也不應該去查
  if (!session.accountId) {
    summary.value = null
    recommendations.value = []
    status.value = 'ready'
    return
  }
  status.value = 'loading'
  const client = createInsightsClient()
  try {
    const [loadedSummary, loadedRecommendations] = await Promise.all([
      client.summary(session.accountId),
      client.recommendations(session.accountId),
    ])
    if (!isSummary(loadedSummary)) {
      status.value = 'unavailable'
      return
    }
    summary.value = loadedSummary
    recommendations.value = Array.isArray(loadedRecommendations) ? loadedRecommendations : []
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
  }
}

onMounted(load)
watch(() => session.accountId, load)

const matching = ref(false)

/** 判讀需求 → 直接進入對應服務；判讀不出就退回目錄，不硬猜（ADR-0016）。 */
async function submitNeed(text: string) {
  const description = text.trim()
  if (!description || matching.value) return
  matching.value = true
  try {
    const match = await matchIntent(description)
    if (match) {
      await router.push({
        name: 'services',
        params: { serviceSlug: match.serviceId.replace('service-', '') },
        query: { need: description, why: match.reason },
      })
    } else {
      await router.push({ name: 'services', query: { need: description, unmatched: '1' } })
    }
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

  <!-- 有紀錄時：進行中的事與可解釋推薦 -->
  <div v-else-if="status === 'ready'" class="grid">
    <section class="panel span-7" aria-labelledby="recommendation-title">
      <template v-if="!store.recommendationDismissed && topRecommendation">
        <p class="eyebrow">值得先處理</p>
        <h2 id="recommendation-title" data-testid="recommendation-title">{{ topRecommendation.title }}</h2>
        <p class="muted">{{ topRecommendation.reasonText }}</p>

        <details class="reason-details">
          <summary>為什麼推薦？</summary>
          <ul data-testid="recommendation-evidence">
            <li v-for="item in topRecommendation.evidence" :key="`${item.recordId}-${item.detail}`">
              {{ item.serviceName }}<span v-if="item.occurredOn">・{{ item.occurredOn }}</span>
              <span v-if="item.orderNo">・訂單 {{ item.orderNo }}</span>
              <span class="muted">（{{ item.detail }}）</span>
            </li>
          </ul>
          <p class="muted">依你的紀錄以規則算出（{{ topRecommendation.reasonCodes.join('、') }}），非語言模型生成。</p>
        </details>

        <div class="button-row">
          <RouterLink
            v-if="topRecommendation.serviceId"
            class="button primary inline"
            :to="`/user/services/${topRecommendation.serviceId.replace('service-', '')}`"
          >前往安排</RouterLink>
          <button class="button" type="button" @click="store.dismissRecommendation">不感興趣</button>
        </div>
      </template>
      <div v-else-if="store.recommendationDismissed" class="feedback-state" role="status">
        <h2>已調整你的偏好</h2>
        <p>之後會減少這類推薦；這不會永久封鎖相關服務。</p>
        <button class="text-button" type="button" @click="store.undoDismissRecommendation">復原</button>
      </div>
      <div v-else class="empty-state compact">
        <h2>目前沒有需要提醒的事</h2>
        <p>沒有未完成的委託，也還沒到回訪週期。</p>
      </div>
    </section>

    <aside class="panel span-5" aria-labelledby="month-overview">
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
