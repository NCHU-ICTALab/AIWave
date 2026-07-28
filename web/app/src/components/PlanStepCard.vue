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
import { computed, ref } from 'vue'

import { asMatchResult, type PlanStep } from '@/api/assistantClient'
import VendorComparison from './VendorComparison.vue'

const props = defineProps<{ step: PlanStep; busy?: boolean }>()
const emit = defineEmits<{
  approve: []
  choose: [vendorId: string]
  openForm: [serviceId: string]
  feedback: [recommendationId: string, action: 'dismiss' | 'undo']
  reminder: []
  watch: [productId: string, storeId: string]
  support: [subjectId: string, issueText: string, diagnosisToken: string]
}>()

const matchResult = computed(() => (props.step.tool === 'match_vendors' ? asMatchResult(props.step.result) : null))

/** 各能力的人話標題——不要把工具代號直接丟給使用者看。 */
const TOOL_LABELS: Record<string, string> = {
  list_services: '查看服務目錄',
  search_services: '找到相關服務',
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
  get_restock_plan: '試算補貨與優惠',
  record_recommendation_feedback: '調整這則推薦',
  create_restock_reminder: '建立補貨提醒',
  list_reminders: '查看補貨提醒',
  search_store_inventory: '查詢門市與庫存',
  join_stock_waitlist: '加入到貨候補',
  list_stock_watches: '查看到貨候補',
  list_vendor_workload: '查詢待處理案件',
  submit_quote: '送出報價',
  complete_inquiry: '回報完工',
  diagnose_order_issue: '診斷訂單問題',
  create_support_ticket: '建立客服工單',
  list_my_support_tickets: '查看客服進度',
  list_support_queue: '查看客服佇列',
  start_support_ticket: '開始處理工單',
  resolve_support_ticket: '完成客服工單',
}

const label = computed(() => TOOL_LABELS[props.step.tool] ?? props.step.tool)
const serviceId = computed(() => String(props.step.arguments.service_id ?? ''))

const rows = computed<Array<Record<string, unknown>>>(() =>
  Array.isArray(props.step.result) ? (props.step.result as Array<Record<string, unknown>>) : [],
)
const objectResult = computed<Record<string, any>>(() =>
  props.step.result && !Array.isArray(props.step.result)
    ? (props.step.result as Record<string, any>)
    : {},
)
const serviceRows = computed<Array<Record<string, unknown>>>(() => {
  if (props.step.tool === 'search_services') return objectResult.value.matches ?? []
  return rows.value
})
const restock = computed(() => props.step.tool === 'get_restock_plan' ? objectResult.value : null)
const retail = computed(() => props.step.tool === 'search_store_inventory' ? objectResult.value : null)
const supportDiagnosis = computed(() => props.step.tool === 'diagnose_order_issue' ? objectResult.value : null)
const pendingAction = ref<{
  kind: 'reminder' | 'watch' | 'support'
  productId?: string
  storeId?: string
  subjectId?: string
  issueText?: string
  diagnosisToken?: string
} | null>(null)

function confirmPending() {
  if (pendingAction.value?.kind === 'reminder') emit('reminder')
  if (pendingAction.value?.kind === 'watch') {
    emit('watch', pendingAction.value.productId ?? '', pendingAction.value.storeId ?? '')
  }
  if (pendingAction.value?.kind === 'support') {
    emit(
      'support',
      pendingAction.value.subjectId ?? '',
      pendingAction.value.issueText ?? '',
      pendingAction.value.diagnosisToken ?? '',
    )
  }
  pendingAction.value = null
}
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

    <!-- 服務目錄：AI 結果一定要有下一步，不能只丟一串不能按的文字 -->
    <ul v-else-if="['list_services', 'search_services'].includes(step.tool) && serviceRows.length" class="service-result-grid">
      <li v-for="row in serviceRows" :key="text(row.id)">
        <button
          class="service-result-action"
          type="button"
          data-testid="plan-service-action"
          @click="emit('openForm', text(row.id))"
        >
          <span><strong>{{ text(row.name) }}</strong><small>{{ text(row.summary) }}</small></span>
          <span class="service-result-next" aria-hidden="true">選擇</span>
        </button>
      </li>
    </ul>

    <!-- 個人化補貨：證據、確定性金額與下一步都在同一卡片，不是死建議。 -->
    <section v-else-if="restock" class="result-stack" data-testid="restock-result">
      <div class="result-highlight">
        <div>
          <strong>{{ text(restock.recommendation?.title) }}</strong>
          <p>{{ text(restock.recommendation?.reasonText) }}</p>
        </div>
        <div class="saving"><span>最佳組合</span><strong>{{ currency(restock.bestOffer?.finalAmount) }}</strong><small>省下 {{ currency(restock.bestOffer?.savedAmount) }}</small></div>
      </div>
      <details v-if="restock.evidence?.length" class="reason-details">
        <summary>查看推薦依據與計算方式</summary>
        <p>依據 {{ restock.evidence.length }} 筆服務紀錄；金額由確定性規則計算。</p>
        <ul><li v-for="rule in restock.bestOffer?.applied" :key="text(rule)">{{ text(rule) }}</li></ul>
      </details>
      <p class="source-note muted">行為來源：官方訂單；點數與優惠券為競賽建置帳本。</p>
      <div class="button-row">
        <button class="button primary" type="button" data-testid="restock-open-shopping" @click="emit('openForm', 'service-shopping')">前往補貨</button>
        <button class="button" type="button" data-testid="restock-reminder" @click="pendingAction = { kind: 'reminder' }">建立 30 天提醒</button>
        <button class="text-button" type="button" data-testid="restock-dismiss" @click="emit('feedback', text(restock.recommendation?.id), restock.recommendation?.suppressed ? 'undo' : 'dismiss')">
          {{ restock.recommendation?.suppressed ? '復原推薦' : '不感興趣' }}
        </button>
      </div>
      <div v-if="pendingAction?.kind === 'reminder'" class="inline-confirm" role="group" aria-label="確認補貨提醒">
        <p>將建立「衛生紙」每 30 天提醒，下次為 2026-08-24。</p>
        <div class="button-row"><button class="button primary" type="button" @click="confirmPending">確認建立</button><button class="button" type="button" @click="pendingAction = null">取消</button></div>
      </div>
    </section>

    <!-- 異常處理：先顯示可追溯診斷，再由使用者確認建立正式工單。 -->
    <section v-else-if="supportDiagnosis" class="result-stack" data-testid="support-diagnosis">
      <div class="result-highlight">
        <div>
          <strong>{{ text(supportDiagnosis.categoryLabel) }}</strong>
          <p>{{ text(supportDiagnosis.issueText) }}</p>
        </div>
        <div class="saving">
          <span>{{ supportDiagnosis.priority === 'high' ? '高優先' : supportDiagnosis.priority === 'medium' ? '中優先' : '一般' }}</span>
          <strong>{{ text(supportDiagnosis.slaHours) }} 小時</strong>
          <small>內開始處理</small>
        </div>
      </div>
      <details v-if="supportDiagnosis.evidence?.length" class="reason-details">
        <summary>查看判斷依據</summary>
        <ul><li v-for="item in supportDiagnosis.evidence" :key="text(item)">{{ text(item) }}</li></ul>
      </details>
      <p class="source-note muted">分類與 SLA 由可重算規則產生，不由語言模型決定。</p>
      <p v-if="supportDiagnosis.createdTicket" class="recommendation-feedback" role="status">
        客服工單 {{ text(supportDiagnosis.createdTicket.id) }} 已建立；可到訂單頁持續查看進度。
      </p>
      <button
        v-else
        class="button primary"
        type="button"
        data-testid="support-create-action"
        @click="pendingAction = { kind: 'support', subjectId: text(supportDiagnosis.subject?.id), issueText: text(supportDiagnosis.issueText), diagnosisToken: text(supportDiagnosis.diagnosisToken) }"
      >建立客服工單</button>
      <div v-if="pendingAction?.kind === 'support'" class="inline-confirm" role="group" aria-label="確認建立客服工單">
        <p>確認要為 {{ pendingAction.subjectId }} 建立可追蹤的客服工單？</p>
        <div class="button-row">
          <button class="button primary" type="button" data-testid="support-create-confirm" @click="confirmPending">確認建立</button>
          <button class="button" type="button" @click="pendingAction = null">取消</button>
        </div>
      </div>
    </section>

    <!-- 門市查詢：缺貨不是終點，同卡提供替代門市與候補。 -->
    <section v-else-if="retail" class="result-stack" data-testid="retail-result">
      <p v-if="!retail.exactMatches?.length" class="result-notice">指定區域目前沒有符合條件且有庫存的門市。</p>
      <div v-for="store in retail.exactMatches" :key="store.storeId" class="store-result">
        <div><strong>{{ store.storeName }}</strong><p>{{ store.district }}・距離約 {{ store.distanceMeters }} 公尺</p></div>
        <span class="stock-badge">庫存 {{ store.stock }}</span>
      </div>
      <div v-for="store in retail.alternatives" :key="store.storeId" class="store-result">
        <div><strong>{{ store.storeName }}</strong><p>{{ store.district }}・距離約 {{ store.distanceMeters }} 公尺</p></div>
        <span class="stock-badge">庫存 {{ store.stock }}</span>
      </div>
      <div v-for="store in retail.unavailableNearby" :key="store.storeId" class="store-result sold-out">
        <div><strong>{{ store.storeName }}</strong><p>目前缺貨</p></div>
        <button class="button" type="button" data-testid="stock-watch-action" @click="pendingAction = { kind: 'watch', productId: text(retail.product?.id), storeId: text(store.storeId) }">加入到貨候補</button>
      </div>
      <div v-if="pendingAction?.kind === 'watch'" class="inline-confirm" role="group" aria-label="確認到貨候補">
        <p>確認追蹤「{{ text(retail.product?.name) }}」在這間缺貨門市的到貨狀態？</p>
        <div class="button-row"><button class="button primary" type="button" @click="confirmPending">確認加入</button><button class="button" type="button" @click="pendingAction = null">取消</button></div>
      </div>
      <p class="source-note muted">庫存截至 {{ text(retail.asOf) }}，來源：競賽建置資料，非正式即時門市 API。</p>
    </section>
  </li>
</template>
