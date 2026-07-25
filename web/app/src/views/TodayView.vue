<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  createInsightsClient,
  type BehaviorSummary,
  type Recommendation,
} from '@/api/insightsClient'
import { useDemoStore } from '@/stores/demo'

const store = useDemoStore()
const summary = ref<BehaviorSummary | null>(null)
const recommendations = ref<Recommendation[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const openEvidence = ref<string | null>(null)

const topRecommendation = computed(() => recommendations.value[0] ?? null)
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`

/** 回應形狀不如預期時寧可顯示「無法取得」，也不要讓整頁崩潰。 */
function isSummary(value: unknown): value is BehaviorSummary {
  const candidate = value as BehaviorSummary | null
  return Boolean(candidate) && typeof candidate?.totalSpend === 'number' && Array.isArray(candidate?.services)
}

onMounted(async () => {
  const client = createInsightsClient()
  try {
    const [loadedSummary, loadedRecommendations] = await Promise.all([
      client.summary(),
      client.recommendations(),
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
})

function toggleEvidence(id: string) {
  openEvidence.value = openEvidence.value === id ? null : id
}
</script>

<template>
  <header class="page-heading">
    <div><p class="eyebrow">Individual workspace</p><h1>今日生活中心</h1></div>
    <span class="page-status">
      {{ status === 'ready' && summary ? `${summary.distinctServices} 種服務・${summary.totalOrders} 筆紀錄` : '載入中…' }}
    </span>
  </header>

  <div class="grid">
    <section class="panel hero">
      <p class="eyebrow">Today's plan</p>
      <h2>把生活中的零散需求，整理成今天做得到的事。</h2>
      <p v-if="summary">
        依你在官方訂單紀錄中的
        {{ summary.totalOrders }} 筆行為、跨 {{ summary.distinctServices }} 種服務整理。
      </p>
      <div class="button-row">
        <RouterLink class="button primary inline" to="/app/services">找一項服務</RouterLink>
        <RouterLink class="button" to="/app/orders">查看訂單</RouterLink>
      </div>
    </section>

    <aside class="panel aside" aria-labelledby="month-overview">
      <h2 id="month-overview">消費概況</h2>
      <p v-if="status === 'loading'" class="muted" role="status">計算中…</p>
      <p v-else-if="status === 'unavailable'" class="muted" role="status">無法取得洞察資料，請確認後端是否啟動。</p>
      <template v-else-if="summary">
        <div class="metric-row">
          <div class="metric"><span>已完成消費</span><strong data-testid="metric-spend">{{ currency(summary.totalSpend) }}</strong></div>
          <div class="metric"><span>累積點數</span><strong>{{ summary.earnedPoints.toLocaleString('zh-TW') }}</strong></div>
          <div class="metric"><span>進行中</span><strong data-testid="metric-open">{{ summary.openOrders }}</strong></div>
          <div class="metric"><span>使用服務</span><strong>{{ summary.distinctServices }}</strong></div>
        </div>
        <p class="muted source-note">
          來源：官方訂單紀錄
          <span v-if="summary.lastActivity">・最近活動 {{ summary.lastActivity }}</span>
        </p>
      </template>
    </aside>

    <section class="panel span-7" aria-labelledby="recommendation-title">
      <template v-if="!store.recommendationDismissed && topRecommendation">
        <p class="eyebrow">Personalized</p>
        <h2 id="recommendation-title" data-testid="recommendation-title">{{ topRecommendation.title }}</h2>
        <p class="muted">{{ topRecommendation.reasonText }}</p>

        <details class="reason-details" :open="openEvidence === topRecommendation.id">
          <summary @click.prevent="toggleEvidence(topRecommendation.id)">為什麼推薦？</summary>
          <ul data-testid="recommendation-evidence">
            <li v-for="item in topRecommendation.evidence" :key="`${item.recordId}-${item.detail}`">
              {{ item.serviceName }}<span v-if="item.occurredOn">・{{ item.occurredOn }}</span>
              <span v-if="item.orderNo">・訂單 {{ item.orderNo }}</span>
              <span class="muted">（{{ item.detail }}）</span>
            </li>
          </ul>
          <p class="muted">
            此推薦由規則依官方訂單紀錄算出（{{ topRecommendation.reasonCodes.join('、') }}），非語言模型生成。
          </p>
        </details>

        <div class="button-row">
          <RouterLink
            v-if="topRecommendation.serviceId"
            class="button primary inline"
            :to="`/app/services/${topRecommendation.serviceId.replace('service-', '')}`"
          >前往安排</RouterLink>
          <button class="button" type="button" @click="store.dismissRecommendation">不感興趣</button>
        </div>
      </template>
      <div v-else-if="store.recommendationDismissed" class="feedback-state" role="status">
        <h2>已調整你的偏好</h2>
        <p>之後會減少這類推薦；這不會永久封鎖相關服務。</p>
        <button class="text-button" type="button" @click="store.undoDismissRecommendation">復原</button>
      </div>
      <div v-else-if="status === 'ready'" class="empty-state compact">
        <h2>目前沒有需要提醒的事</h2>
        <p>沒有未完成的訂單，也還沒到回訪週期。</p>
      </div>
    </section>

    <section class="panel span-5" aria-labelledby="service-usage">
      <p class="eyebrow">Behaviour trail</p>
      <h2 id="service-usage">你的服務使用</h2>
      <ul v-if="summary?.services.length" class="plain-list" data-testid="service-usage-list">
        <li v-for="usage in summary.services" :key="usage.serviceName">
          <strong>{{ usage.serviceName }}</strong>
          {{ usage.count }} 次
          <span v-if="usage.daysSinceLast !== null" class="muted">・{{ usage.daysSinceLast }} 天前</span>
        </li>
      </ul>
      <p v-else class="muted">尚無服務使用紀錄。</p>
    </section>
  </div>
</template>
