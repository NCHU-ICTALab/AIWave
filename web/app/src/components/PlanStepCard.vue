<script setup lang="ts">
/**
 * 計畫中的一步：做了什麼、為什麼、結果是什麼。
 *
 * 這是「Agent 感受不到」那項回饋的正面答案——把規劃過程攤開來，
 * 使用者看得到系統理解了什麼、動用了哪項能力、依據是什麼，而不是一個黑箱結論。
 *
 * 寫入類步驟一定停在確認狀態（ADR-0008），確認鍵由這裡發出事件，
 * 實際執行仍由後端重新驗證。
 */
import { computed } from 'vue'

import { asMatchResult, type PlanStep } from '@/api/assistantClient'
import VendorComparison from './VendorComparison.vue'

const props = defineProps<{ step: PlanStep; busy?: boolean }>()
const emit = defineEmits<{ approve: []; choose: [vendorId: string]; openForm: [serviceId: string] }>()

const matchResult = computed(() => (props.step.tool === 'match_vendors' ? asMatchResult(props.step.result) : null))

/** 各能力的人話標題——不要把工具代號直接丟給使用者看。 */
const TOOL_LABELS: Record<string, string> = {
  list_services: '查看服務目錄',
  get_service_form: '準備諮詢單',
  estimate_price: '試算參考價格',
  match_vendors: '媒合合適廠商',
  list_my_inquiries: '查詢你的委託',
  get_inquiry: '查詢委託詳情',
  confirm_quote: '同意廠商報價',
  list_group_buys: '查看社區團購',
  join_group_buy: '跟團',
  open_group_buy: '開團',
  close_group_buy: '團購結單',
  get_behavior_summary: '整理你的使用紀錄',
  get_activity_trail: '查詢使用軌跡',
  get_recommendations: '整理值得提醒你的事',
  list_vendor_workload: '查詢待處理案件',
  submit_quote: '送出報價',
  complete_inquiry: '回報完工',
}

const label = computed(() => TOOL_LABELS[props.step.tool] ?? props.step.tool)
const serviceId = computed(() => String(props.step.arguments.service_id ?? ''))

const rows = computed<Array<Record<string, unknown>>>(() =>
  Array.isArray(props.step.result) ? (props.step.result as Array<Record<string, unknown>>) : [],
)
const text = (value: unknown) => (value == null ? '' : String(value))
const currency = (value: unknown) => `NT$ ${Number(value ?? 0).toLocaleString('zh-TW')}`
</script>

<template>
  <li class="plan-step" :class="step.status" data-testid="plan-step">
    <header class="plan-step-head">
      <span class="plan-step-mark" aria-hidden="true">
        {{ step.status === 'done' ? '✓' : step.status === 'failed' ? '✕' : step.writes ? '!' : '·' }}
      </span>
      <div>
        <h3>{{ label }}</h3>
        <p v-if="step.why" class="muted">{{ step.why }}</p>
      </div>
      <!-- 狀態不只用顏色表達，文字也讀得到 -->
      <span class="plan-step-status" :data-status="step.status">
        {{ step.status === 'done' ? '已完成' : step.status === 'failed' ? '未完成' : step.status === 'needs_confirmation' ? '待確認' : '準備中' }}
      </span>
    </header>

    <p v-if="step.error" class="plan-step-error" role="alert">{{ step.error }}</p>

    <!-- 需要確認才會動到資料 -->
    <div v-if="step.status === 'needs_confirmation'" class="plan-step-confirm">
      <p>這一步會變更資料，確認後才會執行。</p>
      <button class="button primary" type="button" :disabled="busy" data-testid="plan-approve" @click="emit('approve')">
        {{ busy ? '執行中…' : '確認執行' }}
      </button>
    </div>

    <!-- 媒合：可比較、可改選 -->
    <VendorComparison v-else-if="matchResult" :result="matchResult" @choose="emit('choose', $event)" />

    <!-- 題組：接續既有的引導填答流程 -->
    <div v-else-if="step.tool === 'get_service_form' && step.status === 'done'" class="plan-step-cta">
      <p>接下來只要回答幾個問題就能送出委託。</p>
      <button class="button primary" type="button" data-testid="plan-open-form" @click="emit('openForm', serviceId)">
        開始填寫
      </button>
    </div>

    <!-- 團購 -->
    <ul v-else-if="step.tool === 'list_group_buys' && rows.length" class="plain-list">
      <li v-for="row in rows" :key="text(row.id)">
        <strong>{{ text(row.title) }}</strong>・{{ text(row.itemName) }}
        <span class="muted">{{ currency(row.unitPrice) }}／{{ text(row.unit) }}・{{ text(row.householdCount) }} 戶跟團・{{ text(row.statusLabel) }}</span>
      </li>
    </ul>

    <!-- 行為軌跡 -->
    <ul v-else-if="step.tool === 'get_activity_trail' && rows.length" class="plain-list">
      <li v-for="row in rows" :key="text(row.recordId)">
        <strong>{{ text(row.serviceName) }}</strong>
        <span class="muted">{{ text(row.occurredOn) }}・{{ currency(row.amount) }}</span>
      </li>
    </ul>

    <!-- 可解釋推薦 -->
    <ul v-else-if="step.tool === 'get_recommendations' && rows.length" class="plain-list">
      <li v-for="row in rows" :key="text(row.id)">
        <strong>{{ text(row.title) }}</strong>
        <span class="muted">{{ text(row.reasonText) }}</span>
      </li>
    </ul>

    <!-- 我的委託 -->
    <ul v-else-if="step.tool === 'list_my_inquiries'" class="plain-list">
      <li v-for="row in rows" :key="text(row.id)">
        <strong>{{ text(row.id) }}</strong>
        <span class="muted">{{ text(row.status_label) }}</span>
      </li>
      <li v-if="!rows.length" class="muted">目前沒有任何委託。</li>
    </ul>

    <!-- 服務目錄 -->
    <ul v-else-if="step.tool === 'list_services' && rows.length" class="plain-list">
      <li v-for="row in rows.slice(0, 5)" :key="text(row.id)">
        <strong>{{ text(row.name) }}</strong><span class="muted">{{ text(row.summary) }}</span>
      </li>
    </ul>
  </li>
</template>
