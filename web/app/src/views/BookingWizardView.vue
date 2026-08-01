<script setup lang="ts">
// M4 會員預約核心:TaskDraft 驅動的分步流程。
// booking 類:選據點 → 選方案 → 選時段 → 需求內容 → 確認送出(不預收款);
// commerce 類(ec_preorder):方案(含數量)→ 需求內容 → 確認付款。
// 草稿在第一次「下一步」時建立,之後每步以 expectedVersion 樂觀鎖更新;
// 409 表示草稿已在別處更新,重新載入後請使用者確認。
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import StepIndicator from '@/components/StepIndicator.vue'
import { ApiError } from '@/api/http'
import {
  createDraft,
  createPayment,
  createQuote,
  getDraft,
  getProvider,
  listAvailability,
  retryBookingSync,
  submitDraft,
  transitionDraft,
  updateDraft,
  type CatalogProviderDetail,
  type CatalogSlot,
  type Quote,
  type TaskDraft,
} from '@/api/platformClient'

const route = useRoute()
const router = useRouter()

// ── 需求內容欄位:與後端 core/catalog/domains.py 的 required_fields 一致 ──
interface DomainField {
  id: string
  label: string
  kind: 'text' | 'textarea' | 'number' | 'radio' | 'checkbox'
  options?: Array<{ value: string; label: string }>
  note?: string
  /** 選填欄位:不參與必填驗證,UI 標示（選填）。 */
  optional?: boolean
}

const DOMAIN_FIELDS: Record<string, DomainField[]> = {
  home_repair: [
    { id: 'problem', label: '問題描述', kind: 'textarea' },
    { id: 'address', label: '服務地址', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
    {
      id: 'category',
      label: '報修類別',
      kind: 'radio',
      optional: true,
      options: [
        { value: 'plumbing_electric', label: '水電設備' },
        { value: 'furniture', label: '傢俱' },
        { value: 'aircon', label: '冷氣機' },
        { value: 'network', label: '網路' },
        { value: 'piping', label: '管線' },
        { value: 'lock', label: '門鎖' },
      ],
    },
    { id: 'floor_info', label: '屋齡／坪數／樓層', kind: 'text', optional: true },
  ],
  home_cleaning: [
    { id: 'address', label: '服務地址', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
  ],
  dining_reservation: [
    { id: 'party_size', label: '用餐人數', kind: 'number' },
    { id: 'contact_name', label: '訂位人姓名', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
    {
      id: 'seat_preference',
      label: '座位偏好',
      kind: 'radio',
      optional: true,
      options: [
        { value: 'bar', label: '吧檯' },
        { value: 'table', label: '一般桌' },
        { value: 'private', label: '包廂' },
      ],
    },
    { id: 'special_needs', label: '特殊需求', kind: 'text', optional: true },
  ],
  car_wash: [
    { id: 'plate_number', label: '車牌號碼', kind: 'text' },
    { id: 'car_type', label: '車型', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
  ],
  pharmacy_pickup: [
    {
      id: 'rx_type',
      label: '處方箋類型',
      kind: 'radio',
      options: [
        { value: 'chronic', label: '慢箋' },
        { value: 'general', label: '一般' },
      ],
    },
    { id: 'patient_name', label: '領藥人姓名', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
    {
      id: 'pickup_in_person',
      label: '是否本人領藥',
      kind: 'radio',
      options: [
        { value: 'yes', label: '本人領取' },
        { value: 'no', label: '家人代領' },
      ],
    },
    {
      id: 'rx_confirmed',
      label: '我已逐欄確認辨識結果',
      kind: 'checkbox',
      note: '處方箋辨識僅提供辨識展示，不提供診斷或用藥建議。',
    },
  ],
  shipping_pickup: [
    { id: 'package_size', label: '包裹尺寸', kind: 'text' },
    { id: 'pickup_address', label: '收件地址（取件）', kind: 'text' },
    { id: 'receiver_address', label: '送達地址', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
  ],
  resort_booking: [
    { id: 'party_size', label: '入住人數', kind: 'number' },
    { id: 'contact_name', label: '訂房人姓名', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
  ],
  ec_preorder: [
    { id: 'receiver_name', label: '取件人姓名', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
    {
      id: 'pickup_method',
      label: '取貨方式',
      kind: 'radio',
      options: [
        { value: 'store', label: '門市取貨' },
        { value: 'home', label: '宅配' },
      ],
    },
    {
      id: 'temperature',
      label: '溫層',
      kind: 'radio',
      optional: true,
      options: [
        { value: 'ambient', label: '常溫' },
        { value: 'chilled', label: '冷藏' },
        { value: 'frozen', label: '冷凍' },
      ],
    },
    {
      id: 'invoice',
      label: '發票開立',
      kind: 'radio',
      optional: true,
      options: [
        { value: 'carrier', label: '載具' },
        { value: 'donation', label: '捐贈碼' },
        { value: 'company', label: '統編' },
      ],
    },
  ],
  food_delivery: [
    { id: 'delivery_address', label: '外送地址', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
    { id: 'note', label: '備註', kind: 'text', optional: true },
  ],
  c2c_shipping: [
    { id: 'sender_name', label: '寄件人姓名', kind: 'text' },
    { id: 'receiver_name', label: '收件人姓名', kind: 'text' },
    { id: 'item_name', label: '商品名稱', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
  ],
  ticket_purchase: [
    { id: 'use_date', label: '使用日期', kind: 'text', note: '格式範例:2026-08-09' },
    { id: 'buyer_name', label: '購票人姓名', kind: 'text' },
    { id: 'phone', label: '聯絡電話', kind: 'text' },
  ],
}

// ── 狀態 ──
const provider = ref<CatalogProviderDetail | null>(null)
const draft = ref<TaskDraft | null>(null)
const values = reactive<Record<string, unknown>>({})
const slots = ref<CatalogSlot[]>([])
const quote = ref<Quote | null>(null)
const quoteError = ref('')
const pointsToRedeem = ref(0)
const stepIndex = ref(0)
const loading = ref(true)
const loadError = ref('')
const stepError = ref('')
const conflictNotice = ref('')
const fieldErrors = ref<Record<string, string>>({})
const submitting = ref(false)
const submitError = ref('')
const retrying = ref(false)
const done = ref<null | { subjectType: 'booking' | 'commerce_order'; subjectId: string; syncFailed: boolean }>(null)

// ── 導出計算 ──
const selectedOffering = computed(() =>
  provider.value?.offerings.find((item) => item.id === values.offering_id) ?? null)

const isCommerce = computed(() => {
  if (selectedOffering.value) return selectedOffering.value.fulfillmentKind === 'commerce'
  const offerings = provider.value?.offerings ?? []
  return offerings.length > 0 && offerings.every((item) => item.fulfillmentKind === 'commerce')
})

const steps = computed(() =>
  isCommerce.value
    ? [
        { id: 'offering', label: '選方案' },
        { id: 'details', label: '需求內容' },
        { id: 'confirm', label: '確認付款' },
      ]
    : [
        { id: 'location', label: '選據點' },
        { id: 'offering', label: '選方案' },
        { id: 'slot', label: '選時段' },
        { id: 'details', label: '需求內容' },
        { id: 'confirm', label: '確認送出' },
      ])

const currentStep = computed(() => steps.value[stepIndex.value] ?? steps.value[0]!)
const stepId = computed(() => currentStep.value.id)

const visibleOfferings = computed(() =>
  (provider.value?.offerings ?? []).filter((item) =>
    isCommerce.value ? item.fulfillmentKind === 'commerce' : item.fulfillmentKind === 'booking'))

const domainType = computed(() => draft.value?.domainType ?? selectedOffering.value?.domainType ?? '')
const domainFields = computed(() => DOMAIN_FIELDS[domainType.value] ?? [])

const slotGroups = computed(() => {
  const groups = new Map<string, CatalogSlot[]>()
  for (const slot of slots.value) {
    if (slot.status !== 'available') continue
    const date = slot.startsAt.slice(0, 10)
    groups.set(date, [...(groups.get(date) ?? []), slot])
  }
  return [...groups.entries()].map(([date, list]) => ({ date, slots: list }))
})

function money(value: number) {
  return `NT$ ${value.toLocaleString('zh-TW')}`
}

function timeOf(iso: string) {
  return iso.slice(11, 16)
}

function messageOf(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback
}

function filled(value: unknown): boolean {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim() !== ''
  if (typeof value === 'boolean') return value
  return true
}

// ── 載入:draft 續填或從 provider 開新流程 ──
function inferStep(): number {
  // 只看必填欄位:選填不影響「需求內容是否完成」的推斷
  const fields = (DOMAIN_FIELDS[domainType.value] ?? []).filter((field) => !field.optional)
  const detailsDone = fields.length > 0 && fields.every((field) => filled(values[field.id]))
  if (detailsDone) return steps.value.length - 1
  if (isCommerce.value) return values.offering_id ? 1 : 0
  if (values.slot_id) return 3
  if (values.offering_id && values.location_id) return 2
  if (values.location_id) return 1
  return 0
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const draftId = typeof route.query.draft === 'string' ? route.query.draft : ''
    if (draftId) {
      const restored = await getDraft(draftId)
      draft.value = restored
      Object.assign(values, restored.values)
      const providerId = String(restored.values.provider_id ?? '')
      if (!providerId) {
        loadError.value = '草稿缺少服務提供者資訊，請從服務探索重新開始。'
        return
      }
      provider.value = await getProvider(providerId)
      stepIndex.value = inferStep()
    } else {
      const providerId = typeof route.query.provider === 'string' ? route.query.provider : ''
      if (!providerId) {
        loadError.value = '缺少服務提供者，請從服務探索選擇要預約的品牌。'
        return
      }
      provider.value = await getProvider(providerId)
      values.provider_id = providerId
      const offeringId = typeof route.query.offering === 'string' ? route.query.offering : ''
      if (offeringId && provider.value.offerings.some((item) => item.id === offeringId)) {
        values.offering_id = offeringId
      }
    }
    if (isCommerce.value && !values.quantity) values.quantity = 1
  } catch (reason) {
    loadError.value = messageOf(reason, '暫時無法載入預約資訊，請稍後再試。')
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── 草稿持久化 ──
function snapshot(): Record<string, unknown> {
  const output: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined) output[key] = value
  }
  return output
}

async function persistDraft() {
  if (!draft.value) {
    const offering = selectedOffering.value
    if (!offering) return // 尚未選方案,先留在本地狀態
    draft.value = await createDraft({ domainType: offering.domainType ?? 'general', values: snapshot() })
    await router.replace({ query: { ...route.query, draft: draft.value.id } })
  } else {
    draft.value = await updateDraft(draft.value.id, {
      expectedVersion: draft.value.version,
      values: snapshot(),
    })
  }
}

async function handlePersistFailure(reason: unknown): Promise<void> {
  if (reason instanceof ApiError && reason.status === 409 && draft.value) {
    conflictNotice.value = '草稿已在別處更新，已重新載入最新內容，請再確認一次。'
    try {
      const restored = await getDraft(draft.value.id)
      draft.value = restored
      for (const key of Object.keys(values)) delete values[key]
      Object.assign(values, restored.values)
      stepIndex.value = Math.min(stepIndex.value, inferStep())
    } catch {
      loadError.value = '草稿重新載入失敗，請重新整理頁面。'
    }
    return
  }
  stepError.value = messageOf(reason, '暫時無法儲存草稿，請稍後再試。')
}

// ── 步驟推進 ──
function validateDetails(): boolean {
  const errors: Record<string, string> = {}
  for (const field of domainFields.value) {
    if (field.optional) continue // 選填欄位不參與必填驗證
    if (!filled(values[field.id])) {
      errors[field.id] =
        field.kind === 'checkbox' ? `請勾選「${field.label}」後才能繼續。` : `請填寫${field.label}。`
    }
  }
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function goNext() {
  stepError.value = ''
  conflictNotice.value = ''
  if (stepId.value === 'location' && !values.location_id) {
    stepError.value = '請先選擇服務據點。'
    return
  }
  if (stepId.value === 'offering' && !values.offering_id) {
    stepError.value = '請先選擇服務方案。'
    return
  }
  if (stepId.value === 'slot' && !values.slot_id) {
    stepError.value = '請先選擇一個可預約時段。'
    return
  }
  if (stepId.value === 'details' && !validateDetails()) return
  try {
    await persistDraft()
  } catch (reason) {
    await handlePersistFailure(reason)
    return
  }
  stepIndex.value = Math.min(stepIndex.value + 1, steps.value.length - 1)
}

function goBack() {
  stepError.value = ''
  stepIndex.value = Math.max(stepIndex.value - 1, 0)
}

function goTo(index: number) {
  if (index < stepIndex.value) {
    stepError.value = ''
    stepIndex.value = index
  }
}

function setField(fieldId: string, value: unknown) {
  values[fieldId] = value
  if (fieldErrors.value[fieldId]) {
    const next = { ...fieldErrors.value }
    delete next[fieldId]
    fieldErrors.value = next
  }
}

function selectSlot(slot: CatalogSlot) {
  // 欄位名 snake_case,與後端 domain 驗證一致
  values.slot_id = slot.id
  values.starts_at = slot.startsAt
  values.ends_at = slot.endsAt
  if (slot.locationId) values.location_id = slot.locationId
  values.resource_id = slot.resourceId
  stepError.value = ''
}

// ── 時段與試算 ──
async function loadSlots() {
  if (!provider.value) return
  try {
    slots.value = await listAvailability({
      providerId: provider.value.id,
      offeringId: typeof values.offering_id === 'string' ? values.offering_id : undefined,
    })
  } catch (reason) {
    stepError.value = messageOf(reason, '暫時無法載入可預約時段，請稍後再試。')
  }
}

async function runQuote() {
  if (!values.offering_id) return
  quoteError.value = ''
  try {
    quote.value = await createQuote({
      offeringId: String(values.offering_id),
      quantity: Math.max(1, Number(values.quantity) || 1),
      pointsToRedeem: pointsToRedeem.value,
    })
  } catch (reason) {
    quote.value = null
    quoteError.value = messageOf(reason, '試算失敗，請稍後再試。')
  }
}

watch(stepId, async (id) => {
  if (!provider.value) return
  if (id === 'slot') await loadSlots()
  if (id === 'confirm') await runQuote()
})

function onPointsInput(event: Event) {
  pointsToRedeem.value = Math.max(0, Number((event.target as HTMLInputElement).value) || 0)
  void runQuote()
}

// ── 送出:transition(ready) → submit → payment ──
async function submit() {
  if (submitting.value || quoteError.value) return
  submitting.value = true
  submitError.value = ''
  try {
    await persistDraft()
    if (!draft.value) throw new Error('草稿尚未建立，請回上一步確認方案。')
    if (draft.value.status === 'drafting') {
      draft.value = await transitionDraft(draft.value.id, {
        expectedVersion: draft.value.version,
        status: 'ready',
      })
    }
    const result = await submitDraft(draft.value.id, draft.value.version)
    draft.value = result.draft
    // 產品規則(2026-07-31):預約類不預收款,最多做到預約;只有商品下單走 Demo 付款
    const payable = quote.value?.payable ?? 0
    const redeemed = quote.value?.pointsToRedeem ?? 0
    if (result.subjectType === 'commerce_order' && (payable > 0 || redeemed > 0)) {
      await createPayment({
        subjectType: result.subjectType,
        subjectId: result.subjectId,
        amount: payable,
        pointsRedeemed: redeemed,
        outcome: 'success',
      })
    }
    done.value = { subjectType: result.subjectType, subjectId: result.subjectId, syncFailed: false }
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 503) {
      // recoverable:預約已建立,只是與廠商同步失敗
      const detail = reason.detail as Record<string, unknown> | null
      const subjectId = String(
        detail?.subjectId ?? detail?.subject_id ?? detail?.bookingId ?? detail?.booking_id ?? '',
      )
      if (subjectId) {
        done.value = { subjectType: 'booking', subjectId, syncFailed: true }
        return
      }
    }
    if (reason instanceof ApiError && reason.status === 409) {
      await handlePersistFailure(reason)
      return
    }
    submitError.value = messageOf(reason, '送出失敗，請稍後再試。')
  } finally {
    submitting.value = false
  }
}

async function retrySync() {
  if (!done.value || retrying.value) return
  retrying.value = true
  try {
    await retryBookingSync(done.value.subjectId)
    done.value = { ...done.value, syncFailed: false }
  } catch (reason) {
    submitError.value = messageOf(reason, '重試同步失敗，請稍後再試。')
  } finally {
    retrying.value = false
  }
}
</script>

<template>
  <section class="member-page booking-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">BOOKING</p>
        <h1>預約服務</h1>
        <p class="demo-note">價格與時段為競賽展示資料（partner-demo-v5）。</p>
      </div>
      <span v-if="provider" class="page-status">{{ provider.name }}</span>
    </header>

    <div v-if="loading" class="panel state-panel" role="status">正在載入預約資訊…</div>

    <div v-else-if="loadError" class="panel state-panel" role="alert">
      <h2>目前無法開始預約</h2>
      <p>{{ loadError }}</p>
      <div class="button-row">
        <button class="button" type="button" @click="load">再試一次</button>
        <RouterLink class="button" to="/user/services">回服務探索</RouterLink>
      </div>
    </div>

    <div v-else-if="done" class="panel done-panel" data-testid="booking-done">
      <h2>{{ done.syncFailed ? '已建立但與廠商同步失敗' : done.subjectType === 'booking' ? '預約已送出' : '訂單已成立' }}</h2>
      <p>
        訂單編號
        <strong data-testid="order-id">{{ done.subjectId }}</strong>
      </p>
      <p v-if="done.syncFailed" class="field-error" role="alert">
        你的預約已保留，稍後可重試與廠商同步；不會重複建立第二筆。
      </p>
      <div class="button-row">
        <button
          v-if="done.syncFailed"
          class="button"
          type="button"
          data-testid="retry-sync"
          :disabled="retrying"
          @click="retrySync"
        >
          重試同步
        </button>
        <RouterLink class="button primary" :to="`/user/orders/${done.subjectId}`">查看訂單</RouterLink>
        <RouterLink class="button" to="/user/calendar">查看行事曆</RouterLink>
      </div>
      <p v-if="submitError" class="field-error" role="alert">{{ submitError }}</p>
    </div>

    <template v-else-if="provider">
      <p v-if="conflictNotice" class="status warn" role="status" data-testid="draft-conflict">{{ conflictNotice }}</p>

      <StepIndicator :steps="steps" :current="stepIndex" @select="goTo" />

      <section class="panel step-panel" :aria-label="currentStep.label">
        <h2 data-testid="step-title">{{ currentStep.label }}</h2>

        <!-- 步驟:選據點 -->
        <fieldset v-if="stepId === 'location'" class="option-set">
          <legend class="visually-hidden">選擇服務據點</legend>
          <label v-for="location in provider.locations" :key="location.id" class="option-card">
            <input
              type="radio"
              name="booking-location"
              :value="location.id"
              :checked="values.location_id === location.id"
              @change="values.location_id = location.id"
            />
            <span class="option-copy">
              <strong>{{ location.name }}</strong>
              <span class="muted">{{ location.address ?? `${location.countyName ?? ''}${location.districtName ?? ''}` }}</span>
            </span>
          </label>
        </fieldset>

        <!-- 步驟:選方案 -->
        <fieldset v-else-if="stepId === 'offering'" class="option-set">
          <legend class="visually-hidden">選擇服務方案</legend>
          <label v-for="offering in visibleOfferings" :key="offering.id" class="option-card">
            <input
              type="radio"
              name="booking-offering"
              :value="offering.id"
              :checked="values.offering_id === offering.id"
              @change="values.offering_id = offering.id"
            />
            <span class="option-copy">
              <strong>{{ offering.name }}</strong>
              <span class="muted">{{ offering.description }}</span>
              <span>{{ offering.basePrice > 0 ? `${money(offering.basePrice)}／${offering.pricingUnit ?? '次'}` : '免費預約' }}</span>
            </span>
          </label>
          <div v-if="isCommerce" class="field-group quantity-field">
            <label for="booking-quantity">數量</label>
            <input
              id="booking-quantity"
              data-testid="field-quantity"
              type="number"
              min="1"
              :value="Number(values.quantity) || 1"
              @input="values.quantity = Math.max(1, Number(($event.target as HTMLInputElement).value) || 1)"
            />
          </div>
        </fieldset>

        <!-- 步驟:選時段 -->
        <div v-else-if="stepId === 'slot'">
          <div v-for="group in slotGroups" :key="group.date" class="slot-day">
            <h3>{{ group.date }}</h3>
            <div class="slot-grid">
              <button
                v-for="slot in group.slots"
                :key="slot.id"
                type="button"
                class="slot-chip"
                data-testid="slot-option"
                :aria-pressed="values.slot_id === slot.id"
                @click="selectSlot(slot)"
              >
                {{ timeOf(slot.startsAt) }}–{{ timeOf(slot.endsAt) }}
              </button>
            </div>
          </div>
          <div v-if="!slotGroups.length" class="empty-state compact">
            <h3>目前沒有可預約時段</h3>
            <p>請稍後再試，或回上一步換一個方案。</p>
          </div>
        </div>

        <!-- 步驟:需求內容 -->
        <form v-else-if="stepId === 'details'" class="intake-form" novalidate @submit.prevent>
          <div v-for="field in domainFields" :key="field.id" class="field-group">
            <label v-if="field.kind === 'checkbox'" class="check-label" :for="`bw-${field.id}`">
              <input
                :id="`bw-${field.id}`"
                type="checkbox"
                :data-testid="`field-${field.id}`"
                :checked="Boolean(values[field.id])"
                :aria-invalid="Boolean(fieldErrors[field.id])"
                @change="setField(field.id, ($event.target as HTMLInputElement).checked)"
              />
              {{ field.label }}{{ field.optional ? '（選填）' : '（必填）' }}
            </label>
            <fieldset v-else-if="field.kind === 'radio'" class="radio-set">
              <legend>{{ field.label }}{{ field.optional ? '（選填）' : '（必填）' }}</legend>
              <label v-for="option in field.options" :key="option.value" class="radio-option">
                <input
                  type="radio"
                  :name="`bw-${field.id}`"
                  :value="option.value"
                  :data-testid="`field-${field.id}-${option.value}`"
                  :checked="values[field.id] === option.value"
                  :aria-invalid="Boolean(fieldErrors[field.id])"
                  @change="setField(field.id, option.value)"
                />
                {{ option.label }}
              </label>
            </fieldset>
            <template v-else>
              <label :for="`bw-${field.id}`">{{ field.label }}{{ field.optional ? '（選填）' : '（必填）' }}</label>
              <textarea
                v-if="field.kind === 'textarea'"
                :id="`bw-${field.id}`"
                :data-testid="`field-${field.id}`"
                rows="3"
                :value="String(values[field.id] ?? '')"
                :aria-invalid="Boolean(fieldErrors[field.id])"
                @input="setField(field.id, ($event.target as HTMLTextAreaElement).value)"
              />
              <input
                v-else
                :id="`bw-${field.id}`"
                :data-testid="`field-${field.id}`"
                :type="field.kind === 'number' ? 'number' : 'text'"
                :min="field.kind === 'number' ? 1 : undefined"
                :value="String(values[field.id] ?? '')"
                :aria-invalid="Boolean(fieldErrors[field.id])"
                @input="setField(field.id, ($event.target as HTMLInputElement).value)"
              />
            </template>
            <p v-if="fieldErrors[field.id]" class="field-error" role="alert">{{ fieldErrors[field.id] }}</p>
            <p v-else-if="field.note" class="field-hint">{{ field.note }}</p>
          </div>
        </form>

        <!-- 步驟:確認與付款 -->
        <div v-else-if="stepId === 'confirm'" class="confirm-step">
          <dl class="summary-list">
            <div>
              <dt>服務方案</dt>
              <dd>{{ selectedOffering?.name ?? '—' }}</dd>
            </div>
            <div v-if="!isCommerce && values.starts_at">
              <dt>預約時段</dt>
              <dd>{{ String(values.starts_at).slice(0, 10) }} {{ timeOf(String(values.starts_at)) }}–{{ timeOf(String(values.ends_at ?? '')) }}</dd>
            </div>
            <div v-if="isCommerce">
              <dt>數量</dt>
              <dd>{{ Number(values.quantity) || 1 }}</dd>
            </div>
          </dl>

          <!-- 商品下單才有折抵與付款;預約類不預收款(2026-07-31 產品規則) -->
          <div v-if="isCommerce" class="field-group points-field">
            <label for="booking-points">
              使用 OPENPOINT 折抵（可折上限 {{ quote?.maxRedeemablePoints ?? 0 }} 點）
            </label>
            <input
              id="booking-points"
              data-testid="points-input"
              type="number"
              min="0"
              :value="pointsToRedeem"
              @input="onPointsInput"
            />
          </div>
          <p v-if="quoteError" class="field-error" role="alert" data-testid="quote-error">{{ quoteError }}</p>

          <dl v-if="quote" class="summary-list" data-testid="quote-summary">
            <div>
              <dt>{{ isCommerce ? '小計' : '預估費用' }}</dt>
              <dd>{{ money(quote.subtotal) }}</dd>
            </div>
            <div v-if="isCommerce && quote.pointsDiscount">
              <dt>點數折抵</dt>
              <dd>− {{ money(quote.pointsDiscount) }}</dd>
            </div>
            <div v-if="isCommerce">
              <dt>應付金額</dt>
              <dd data-testid="quote-payable">{{ money(quote.payable) }}</dd>
            </div>
          </dl>
          <p v-if="isCommerce" class="muted">{{ quote?.ruleSummary }}</p>
          <p v-else class="muted" data-testid="no-prepayment-note">
            本服務不預收款：費用依廠商到場報價，於現場或服務完成後支付；平台只完成預約。
          </p>
          <p class="muted">
            取消規則：{{
              (selectedOffering?.cancelPolicyHours ?? 0) > 0
                ? `開始前 ${selectedOffering?.cancelPolicyHours} 小時前可免費取消。`
                : '送出後如需取消請儘速聯繫客服。'
            }}
          </p>
          <p v-if="submitError" class="field-error" role="alert">{{ submitError }}</p>
        </div>

        <p v-if="stepError" class="field-error" role="alert">{{ stepError }}</p>

        <div class="button-row">
          <button v-if="stepIndex > 0" class="button" type="button" data-testid="wizard-back" @click="goBack">上一步</button>
          <button
            v-if="stepId !== 'confirm'"
            class="button primary"
            type="button"
            data-testid="wizard-next"
            @click="goNext"
          >
            下一步
          </button>
          <button
            v-else
            class="button primary"
            type="button"
            data-testid="wizard-submit"
            :disabled="submitting || Boolean(quoteError)"
            @click="submit"
          >
            {{ submitting ? '送出中…' : '確認送出' }}
          </button>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.demo-note {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.8rem;
}

.step-panel h2 {
  margin-top: 0;
}

.option-set {
  display: grid;
  gap: 0.6rem;
  margin: 0;
  padding: 0;
  border: 0;
}

.option-card {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  min-height: 44px;
  padding: 0.7rem 0.85rem;
  border: var(--border-chunky) solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface);
  cursor: pointer;
}

.option-card:has(input:checked) {
  background: var(--cta);
  box-shadow: 4px 4px 0 var(--ink);
}

.option-copy {
  display: grid;
  gap: 0.15rem;
}

.slot-day h3 {
  margin: 0.8rem 0 0.4rem;
}

.slot-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.slot-chip {
  min-height: 44px;
  padding: 0 0.9rem;
  border: var(--border-chunky) solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface);
  font-weight: 700;
  box-shadow: 4px 4px 0 var(--ink);
  cursor: pointer;
}

.slot-chip[aria-pressed='true'] {
  background: var(--cta);
}

.radio-set {
  margin: 0;
  padding: 0;
  border: 0;
}

.radio-set legend {
  font-weight: 700;
  margin-bottom: 0.3rem;
}

.radio-option,
.check-label {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  min-height: 44px;
  margin-right: 1rem;
  cursor: pointer;
}

.points-field input {
  max-width: 10rem;
}

.done-panel h2 {
  margin-top: 0;
}
</style>
