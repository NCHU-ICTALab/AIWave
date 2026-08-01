<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createInquiryLifecycleClient,
  type Inquiry,
  type VendorWorkload,
} from '@/api/inquiryLifecycleClient'
import { createJointServiceClient, type JointServiceCampaign } from '@/api/jointServiceClient'
import { ApiError } from '@/api/http'
import {
  getProviderAvailability,
  getProviderSnapshot,
  listBookings,
  listCommerceOrders,
  saveProviderAvailability,
  transitionBooking,
  transitionCommerceOrder,
  type Booking,
  type CatalogSlot,
  type CommerceOrder,
} from '@/api/platformClient'
import { createVendorApiClient, type VendorApiInquiry, type VendorApiOrder } from '@/api/vendorApiClient'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const client = createInquiryLifecycleClient({ accountId: session.accountId, role: 'partner' })
const jointClient = createJointServiceClient({ accountId: session.accountId })
const vendorApi = createVendorApiClient({ accountId: session.accountId })
const workload = ref<VendorWorkload>({ pendingQuote: [], awaitingResident: [], scheduled: [] })
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const acting = ref<string | null>(null)
const error = ref('')
const jointCampaigns = ref<JointServiceCampaign[]>([])
const jointStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const confirmingJoint = ref<{ id: number; action: 'start' | 'complete' } | null>(null)
const jointNotes = reactive<Record<number, string>>({})
const externalInquiries = ref<VendorApiInquiry[]>([])
const externalOrders = ref<VendorApiOrder[]>([])
const externalStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const externalDrafts = reactive<Record<string, number>>({})

/** 每筆待報價各自的報價草稿（材料費＋施工費，對齊官方 order_items 的分項慣例）。 */
const drafts = reactive<Record<string, { material: number; labour: number }>>({})

// ── M4 平台案件(Booking / CommerceOrder;partner Bearer 下後端只回自家案件) ──

/** Booking 狀態的顯示名稱;未知狀態原樣顯示,不假裝認得。 */
const BOOKING_STATUS_LABEL: Record<string, string> = {
  pending_provider: '待接單',
  confirmed: '已預約',
  in_service: '服務中',
  completed: '已完成',
  cancelled: '已取消',
}

/** 合法的廠商端 Booking 狀態轉移;不在表內就不顯示按鈕。 */
const BOOKING_NEXT: Record<string, { to: string; label: string }> = {
  pending_provider: { to: 'confirmed', label: '確認接單' },
  confirmed: { to: 'in_service', label: '開始服務' },
  in_service: { to: 'completed', label: '回報完成' },
}

const ORDER_STATUS_LABEL: Record<string, string> = {
  placed: '已下單',
  accepted: '已接單',
  preparing: '備貨中',
  shipped: '已出貨',
  ready_for_pickup: '到店可取',
  delivered: '已送達',
  cancelled: '已取消',
}

/** 合法的廠商端訂單狀態轉移(placed→accepted→preparing→shipped/ready_for_pickup→delivered)。 */
const ORDER_NEXT: Record<string, Array<{ to: string; label: string }>> = {
  placed: [{ to: 'accepted', label: '接受訂單' }],
  accepted: [{ to: 'preparing', label: '開始備貨' }],
  preparing: [
    { to: 'shipped', label: '出貨' },
    { to: 'ready_for_pickup', label: '到店可取' },
  ],
  shipped: [{ to: 'delivered', label: '完成配送' }],
  ready_for_pickup: [{ to: 'delivered', label: '完成取貨' }],
}

/** booking.details 的履約必要欄位中文化對照;未知鍵原樣顯示,不假裝認得。 */
const DETAIL_LABELS: Record<string, string> = {
  problem: '問題描述',
  address: '服務地址',
  phone: '聯絡電話',
  party_size: '人數',
  contact_name: '聯絡人',
  plate_number: '車牌',
  car_type: '車型',
  rx_type: '處方箋類型',
  patient_name: '領藥人',
  pickup_in_person: '本人領取',
  package_size: '包裹尺寸',
  pickup_address: '取件地址',
  receiver_address: '送達地址',
}

const detailLabel = (key: string) => DETAIL_LABELS[key] ?? key
const detailValue = (value: unknown) =>
  typeof value === 'boolean' ? (value ? '是' : '否') : String(value ?? '')
const detailEntries = (booking: Booking) => Object.entries(booking.details ?? {})

interface ProviderSnapshotView {
  providerId: string | null
  seedVersion: string | null
  bookingCount: number | null
}

const platformBookings = ref<Booking[]>([])
const platformOrders = ref<CommerceOrder[]>([])
const platformSnapshot = ref<ProviderSnapshotView | null>(null)
const platformStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const platformError = ref('')
const platformToast = ref('')

// ── 本週可服務時段(provider availability) ──

const availabilitySlots = ref<CatalogSlot[]>([])
const availabilityStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const availabilityError = ref('')
const availabilityToast = ref('')
const editingAvailability = ref(false)
const savingSlot = ref(false)
const slotDraft = reactive({ date: '2026-08-02', start: '19:00', end: '21:00' })

/** 依日期分組(startsAt 的日期部分),讓時段表和原型一樣按天呈現。 */
const availabilityByDate = computed(() => {
  const groups = new Map<string, CatalogSlot[]>()
  for (const slot of availabilitySlots.value) {
    const day = slot.startsAt.slice(0, 10)
    if (!groups.has(day)) groups.set(day, [])
    groups.get(day)!.push(slot)
  }
  return [...groups.entries()]
})

const slotTimeRange = (slot: CatalogSlot) => `${slot.startsAt.slice(11, 16)}–${slot.endsAt.slice(11, 16)}`
const slotStatusLabel = (status: string) =>
  status === 'available' ? '空檔' : status === 'booked' ? '已預約' : status

async function loadAvailability() {
  availabilityStatus.value = 'loading'
  try {
    availabilitySlots.value = await getProviderAvailability()
    availabilityStatus.value = 'ready'
  } catch {
    availabilityStatus.value = 'unavailable'
  }
}

/**
 * 工作台接入廠商可整批回報時段;標準接入廠商(如王子水電)後端會回 409
 * 「availability 由廠商系統維護」——那是正確行為,誠實顯示,不假裝成功。
 */
async function submitSlot() {
  const providerId =
    platformSnapshot.value?.providerId ?? availabilitySlots.value[0]?.providerId ?? ''
  const offeringId =
    availabilitySlots.value[0]?.offeringId ?? platformBookings.value[0]?.offeringId ?? ''
  savingSlot.value = true
  availabilityError.value = ''
  availabilityToast.value = ''
  try {
    await saveProviderAvailability([{
      id: `slot-manual-${Date.now()}`,
      providerId,
      offeringId,
      startsAt: `${slotDraft.date}T${slotDraft.start}:00+08:00`,
      endsAt: `${slotDraft.date}T${slotDraft.end}:00+08:00`,
      status: 'available',
      capacity: 1,
    }])
    availabilityToast.value = '可服務時段已更新,會員端下一次查詢就會看到這個空檔。'
    editingAvailability.value = false
    await loadAvailability()
  } catch (reason) {
    availabilityError.value =
      reason instanceof Error ? reason.message : '可服務時段未更新,請稍後再試。'
  } finally {
    savingSlot.value = false
  }
}

const bookingStatusLabel = (status: string) => BOOKING_STATUS_LABEL[status] ?? status
const orderStatusLabel = (status: string) => ORDER_STATUS_LABEL[status] ?? status
const slotRange = (booking: Booking) => `${booking.startsAt} — ${booking.endsAt}`

async function loadPlatform() {
  platformStatus.value = 'loading'
  platformError.value = ''
  try {
    const [bookings, orders, snapshot] = await Promise.all([
      listBookings(),
      listCommerceOrders(),
      getProviderSnapshot(),
    ])
    platformBookings.value = bookings
    platformOrders.value = orders
    const counts = (snapshot as { counts?: { bookings?: number } }).counts
    platformSnapshot.value = {
      providerId: typeof snapshot.providerId === 'string' ? snapshot.providerId : null,
      seedVersion: typeof snapshot.seedVersion === 'string' ? snapshot.seedVersion : null,
      bookingCount: typeof counts?.bookings === 'number' ? counts.bookings : bookings.length,
    }
    platformStatus.value = 'ready'
  } catch (reason) {
    platformStatus.value = 'unavailable'
    platformError.value = reason instanceof Error ? reason.message : '無法取得平台案件。'
  }
}

async function advanceBooking(booking: Booking, to: string) {
  acting.value = `platform-${booking.id}`
  platformError.value = ''
  platformToast.value = ''
  try {
    const updated = await transitionBooking(
      booking.id,
      { expectedVersion: booking.version, status: to },
      `${booking.id}-${to}`,
    )
    platformBookings.value = platformBookings.value.map((item) => (item.id === updated.id ? updated : item))
    platformToast.value = '會員端進度/通知/行事曆同步更新'
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 409) {
      platformError.value = '版本已更新，已重新載入最新狀態。'
      await loadPlatform()
    } else {
      platformError.value = reason instanceof Error ? reason.message : '狀態未更新，請稍後再試。'
    }
  } finally {
    acting.value = null
  }
}

async function advanceOrder(order: CommerceOrder, to: string) {
  acting.value = `platform-${order.id}`
  platformError.value = ''
  platformToast.value = ''
  try {
    const updated = await transitionCommerceOrder(
      order.id,
      { expectedVersion: order.version, status: to },
      `${order.id}-${to}`,
    )
    platformOrders.value = platformOrders.value.map((item) => (item.id === updated.id ? updated : item))
    platformToast.value = '會員端進度/通知/行事曆同步更新'
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 409) {
      platformError.value = '版本已更新，已重新載入最新狀態。'
      await loadPlatform()
    } else {
      platformError.value = reason instanceof Error ? reason.message : '狀態未更新，請稍後再試。'
    }
  } finally {
    acting.value = null
  }
}

const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`
/** 部分回應可能沒有摘要，畫面不該因此崩掉。 */
const lines = (inquiry: Inquiry) => inquiry.summary ?? []
const inquiryTitle = (inquiry: Inquiry) => inquiry.title
  || lines(inquiry).find((line) => /服務/.test(line.label))?.value
  || '服務需求'

function draftFor(id: string) {
  if (!drafts[id]) drafts[id] = { material: 300, labour: 900 }
  return drafts[id]
}

async function load() {
  void loadPlatform()
  void loadAvailability()
  try {
    workload.value = await client.vendorWorkload()
    status.value = 'ready'
    void loadJointServices()
    void loadVendorApi()
  } catch {
    status.value = 'unavailable'
  }
}

async function loadVendorApi() {
  if (!session.accountId) {
    externalStatus.value = 'ready'
    return
  }
  externalStatus.value = 'loading'
  try {
    const [inquiries, orders] = await Promise.all([
      vendorApi.listInquiries(session.accountId), vendorApi.listOrders(session.accountId),
    ])
    externalInquiries.value = inquiries
    externalOrders.value = orders
    for (const inquiry of inquiries) {
      if (!(inquiry.id in externalDrafts)) externalDrafts[inquiry.id] = Math.max(0, inquiry.budget ?? 1200)
    }
    externalStatus.value = 'ready'
  } catch (reason) {
    externalStatus.value = 'unavailable'
    error.value = reason instanceof Error ? reason.message : '無法取得 Vendor API 案件。'
  }
}

async function sendExternalQuote(inquiry: VendorApiInquiry) {
  if (!session.accountId) return
  acting.value = `external-${inquiry.id}`
  error.value = ''
  try {
    await vendorApi.createQuote(
      inquiry.id, session.accountId, inquiry.summary,
      Math.max(0, Number(externalDrafts[inquiry.id]) || 0),
    )
    await loadVendorApi()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : 'Vendor API 報價未送出。'
  } finally {
    acting.value = null
  }
}

async function advanceExternalOrder(order: VendorApiOrder, next: 'in_service' | 'completed') {
  acting.value = `external-${order.id}`
  error.value = ''
  try {
    await vendorApi.appendOrderEvent(
      order.id, next, next === 'completed' ? '已完工並完成現場確認' : '技師已開始服務',
    )
    await loadVendorApi()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '履約狀態未更新。'
  } finally {
    acting.value = null
  }
}

async function loadJointServices() {
  jointStatus.value = 'loading'
  try {
    jointCampaigns.value = await jointClient.partnerList()
    jointStatus.value = 'ready'
  } catch {
    jointStatus.value = 'unavailable'
  }
}

function replaceJoint(updated: JointServiceCampaign) {
  jointCampaigns.value = jointCampaigns.value.map((item) => item.id === updated.id ? updated : item)
}

async function startJoint(campaign: JointServiceCampaign) {
  acting.value = `joint-${campaign.id}`
  try {
    replaceJoint(await jointClient.start(campaign.id))
    confirmingJoint.value = null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '開工回報未完成。'
  } finally {
    acting.value = null
  }
}

async function completeJoint(campaign: JointServiceCampaign) {
  const note = (jointNotes[campaign.id] ?? '').trim()
  if (!note) return
  acting.value = `joint-${campaign.id}`
  try {
    replaceJoint(await jointClient.complete(campaign.id, note))
    confirmingJoint.value = null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '完工回報未完成。'
  } finally {
    acting.value = null
  }
}

async function sendQuote(inquiry: Inquiry) {
  const draft = draftFor(inquiry.id)
  acting.value = inquiry.id
  error.value = ''
  try {
    await client.quote(inquiry.id, [
      { name: '材料費', amount: Number(draft.material) || 0 },
      { name: '施工費', amount: Number(draft.labour) || 0 },
    ], session.displayName)
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '報價未送出，請稍後再試。'
  } finally {
    acting.value = null
  }
}

async function reportCompletion(inquiry: Inquiry) {
  acting.value = inquiry.id
  error.value = ''
  try {
    await client.complete(inquiry.id, '已完成服務')
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '回報未完成，請稍後再試。'
  } finally {
    acting.value = null
  }
}

onMounted(load)
</script>

<template>
  <header class="page-heading">
    <div><p class="eyebrow">合作廠商</p><h1>廠商工作台</h1></div>
    <span class="page-status">待報價 {{ workload.pendingQuote.length }} 件</span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>
  <p v-if="status === 'unavailable'" class="panel muted" role="status">
    無法取得待處理需求，請確認後端服務是否啟動。
  </p>

  <section class="panel" aria-labelledby="platform-bookings-title" data-testid="platform-bookings">
    <div class="section-heading">
      <div>
        <p class="eyebrow">平台案件（M4）・展示資料</p>
        <h2 id="platform-bookings-title">平台案件</h2>
      </div>
      <button class="button" type="button" :disabled="platformStatus === 'loading'" @click="loadPlatform">
        {{ platformStatus === 'loading' ? '載入中…' : '重新整理' }}
      </button>
    </div>
    <p v-if="platformSnapshot" class="data-notice">
      目錄版本 {{ platformSnapshot.seedVersion ?? '未知' }}・案件 {{ platformSnapshot.bookingCount ?? platformBookings.length }} 件（展示資料，非真實營運數字）
    </p>
    <p aria-live="polite" role="status" data-testid="platform-toast" :class="platformToast ? 'data-notice' : 'visually-hidden'">
      {{ platformToast }}
    </p>
    <p v-if="platformError" class="need-error" role="alert">{{ platformError }}</p>

    <p v-if="platformStatus === 'loading'" class="muted" role="status">正在取得平台案件…</p>
    <template v-else-if="platformStatus === 'unavailable'">
      <p class="result-notice" role="status">平台案件暫時無法取得，這是真實的連線失敗，不是沒有案件。</p>
      <button class="button" type="button" data-testid="platform-retry" @click="loadPlatform">重試</button>
    </template>
    <template v-else>
      <p v-if="!platformBookings.length" class="empty-state compact">目前沒有平台預約案件。</p>
      <article
        v-for="booking in platformBookings"
        :key="booking.id"
        class="queue-row"
        :data-platform-booking="booking.id"
      >
        <div>
          <strong>{{ booking.id }}</strong>
          <p class="row-meta">{{ slotRange(booking) }}</p>
          <details :data-testid="`booking-details-${booking.id}`">
            <summary>查看需求</summary>
            <template v-if="detailEntries(booking).length">
              <dl class="summary-list compact">
                <div v-for="[key, value] in detailEntries(booking)" :key="key">
                  <dt>{{ detailLabel(key) }}</dt>
                  <dd>{{ detailValue(value) }}</dd>
                </div>
              </dl>
              <p class="data-notice">個資最小化:僅顯示履約必要資料,看不到會員的其他訂單、點數與個人檔案。</p>
            </template>
            <p v-else class="muted">此案件無補充需求資料。</p>
          </details>
        </div>
        <div class="button-row">
          <span class="status" :data-status="booking.status">{{ bookingStatusLabel(booking.status) }}</span>
          <button
            v-if="BOOKING_NEXT[booking.status]"
            class="button primary"
            type="button"
            :data-testid="`booking-transition-${booking.id}`"
            :disabled="acting === `platform-${booking.id}`"
            @click="advanceBooking(booking, BOOKING_NEXT[booking.status]!.to)"
          >{{ BOOKING_NEXT[booking.status]!.label }}</button>
        </div>
      </article>

      <template v-if="platformOrders.length">
        <h3 class="subhead">商城訂單</h3>
        <article
          v-for="order in platformOrders"
          :key="order.id"
          class="queue-row"
          :data-platform-order="order.id"
        >
          <div>
            <strong>{{ order.id }}</strong>
            <p class="row-meta">{{ order.items.map((item) => `${item.name} ×${item.quantity}`).join('、') }}・NT$ {{ (order.total ?? 0).toLocaleString('zh-TW') }}</p>
          </div>
          <div class="button-row">
            <span class="status" :data-status="order.status">{{ orderStatusLabel(order.status) }}</span>
            <button
              v-for="next in ORDER_NEXT[order.status] ?? []"
              :key="next.to"
              class="button"
              type="button"
              :data-testid="`order-transition-${order.id}-${next.to}`"
              :disabled="acting === `platform-${order.id}`"
              @click="advanceOrder(order, next.to)"
            >{{ next.label }}</button>
          </div>
        </article>
      </template>
    </template>
  </section>

  <section class="panel" aria-labelledby="availability-title" data-testid="provider-availability">
    <div class="section-heading">
      <div>
        <p class="eyebrow">排程・展示資料</p>
        <h2 id="availability-title">本週可服務時段</h2>
      </div>
      <button
        class="button"
        type="button"
        data-testid="edit-availability"
        @click="editingAvailability = !editingAvailability"
      >{{ editingAvailability ? '收合編輯' : '編輯可用時段' }}</button>
    </div>
    <p class="data-notice">會員預約頁只會列出這裡的空檔;「已預約」時段在會員端不可選取。</p>
    <p aria-live="polite" role="status" data-testid="availability-toast" :class="availabilityToast ? 'data-notice' : 'visually-hidden'">
      {{ availabilityToast }}
    </p>
    <p v-if="availabilityError" class="need-error" role="alert" data-testid="availability-error">{{ availabilityError }}</p>

    <p v-if="availabilityStatus === 'loading'" class="muted" role="status">正在取得可服務時段…</p>
    <template v-else-if="availabilityStatus === 'unavailable'">
      <p class="result-notice" role="status">可服務時段暫時無法取得，這是真實的連線失敗，不是沒有時段。</p>
      <button class="button" type="button" @click="loadAvailability">重試</button>
    </template>
    <template v-else>
      <p v-if="!availabilitySlots.length" class="empty-state compact">目前沒有已回報的可服務時段。</p>
      <div v-for="[day, slots] in availabilityByDate" :key="day" :data-availability-day="day">
        <h3 class="subhead">{{ day }}</h3>
        <ul class="summary-list compact">
          <li v-for="slot in slots" :key="slot.id" :data-availability-slot="slot.id">
            {{ slotTimeRange(slot) }}
            <span class="status" :data-status="slot.status">{{ slotStatusLabel(slot.status) }}</span>
          </li>
        </ul>
      </div>
    </template>

    <form
      v-if="editingAvailability"
      class="quote-form"
      data-testid="availability-form"
      @submit.prevent="submitSlot"
    >
      <label class="field">日期
        <input v-model="slotDraft.date" type="date" data-testid="slot-date" required />
      </label>
      <label class="field">開始時間
        <input v-model="slotDraft.start" type="time" data-testid="slot-start" required />
      </label>
      <label class="field">結束時間
        <input v-model="slotDraft.end" type="time" data-testid="slot-end" required />
      </label>
      <button class="button primary" type="submit" data-testid="save-availability" :disabled="savingSlot">
        {{ savingSlot ? '送出中…' : '新增可服務空檔' }}
      </button>
      <p class="data-notice">標準接入(Partner API)廠商的時段由自家系統維護,平台不代管;此表單僅適用工作台接入廠商。</p>
    </form>
  </section>

  <section class="panel vendor-api-panel" aria-labelledby="vendor-api-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">Vendor API・同一份上游狀態</p>
        <h2 id="vendor-api-title">AI 跨服務案件</h2>
      </div>
      <button class="button" type="button" :disabled="externalStatus === 'loading'" @click="loadVendorApi">重新整理</button>
    </div>
    <p class="data-notice">只顯示指派給 {{ session.displayName }} 的案件；聯絡資料來自會員送出前同意的生活任務。</p>
    <p v-if="externalStatus === 'loading'" class="muted" role="status">正在從獨立廠商 API 取得案件…</p>
    <p v-else-if="externalStatus === 'unavailable'" class="result-notice" role="status">Vendor API 暫時無法連線，可稍後重試。</p>
    <p v-else-if="!externalInquiries.length && !externalOrders.length" class="muted">目前沒有 AI 跨服務案件。</p>

    <div v-if="externalInquiries.length" class="vendor-api-grid">
      <article v-for="inquiry in externalInquiries" :key="inquiry.id" class="inquiry-card" :data-external-inquiry="inquiry.id">
        <div class="inquiry-head">
          <div><strong>{{ inquiry.summary }}</strong><p class="row-meta">{{ inquiry.id }}・{{ inquiry.externalReference }}</p></div>
          <span class="status" :data-status="inquiry.status">{{ inquiry.status === 'submitted' ? '待報價' : inquiry.status === 'quoted' ? '已報價' : inquiry.status }}</span>
        </div>
        <dl class="summary-list compact">
          <div><dt>服務日期</dt><dd>{{ inquiry.answers.scheduledDate }}</dd></div>
          <div><dt>地址</dt><dd>{{ inquiry.location.address }}</dd></div>
          <div><dt>聯絡人</dt><dd>{{ inquiry.consumer.name }}・{{ inquiry.consumer.phone }}</dd></div>
          <div><dt>需求</dt><dd>{{ inquiry.answers.description }}</dd></div>
        </dl>
        <form v-if="inquiry.status === 'submitted'" class="quote-form" @submit.prevent="sendExternalQuote(inquiry)">
          <label class="field">正式報價（新台幣）
            <input v-model.number="externalDrafts[inquiry.id]" type="number" min="0" :data-external-quote="inquiry.id" />
          </label>
          <div class="quote-total">合計 <strong>{{ currency(externalDrafts[inquiry.id] ?? 0) }}</strong></div>
          <button class="button primary" type="submit" :disabled="acting === `external-${inquiry.id}`">
            {{ acting === `external-${inquiry.id}` ? '送出中…' : '送出正式報價' }}
          </button>
        </form>
        <p v-else class="muted">正式報價已回到會員的 AI 與訂單頁，等待會員確認。</p>
      </article>
    </div>

    <div v-if="externalOrders.length" class="vendor-order-list">
      <h3>履約訂單</h3>
      <article v-for="order in externalOrders" :key="order.id" class="queue-row" :data-external-order="order.id">
        <div><strong>{{ order.id }}</strong><p class="row-meta">{{ order.externalReference }}・{{ order.status }}</p></div>
        <div class="button-row">
          <button v-if="order.status === 'confirmed'" class="button" type="button" :disabled="acting === `external-${order.id}`" @click="advanceExternalOrder(order, 'in_service')">回報開始服務</button>
          <button v-if="order.status === 'in_service'" class="button primary" type="button" :disabled="acting === `external-${order.id}`" @click="advanceExternalOrder(order, 'completed')">回報完工</button>
          <span v-if="order.status === 'completed'" class="status" data-status="completed">已完成</span>
        </div>
      </article>
    </div>
  </section>

  <section v-if="jointStatus !== 'unavailable'" class="panel vendor-joint-panel" aria-labelledby="vendor-joint-title">
    <div class="section-heading">
      <div><p class="eyebrow">社區聯合服務</p><h2 id="vendor-joint-title">已指派標準工單</h2></div>
      <span class="page-status">{{ jointCampaigns.filter((item) => item.status !== 'completed').length }} 件進行中</span>
    </div>
    <p v-if="jointStatus === 'loading'" class="muted" role="status">正在取得聯合服務工單…</p>
    <p v-else-if="!jointCampaigns.length" class="muted">目前沒有指派給你的聯合服務。</p>
    <article v-for="campaign in jointCampaigns" :key="campaign.id" class="joint-work-order">
      <div class="inquiry-head">
        <div><h3>{{ campaign.title }}</h3><p class="row-meta">{{ campaign.demand.householdCount }} 戶／{{ campaign.demand.unitCount }} 台・{{ campaign.communityId }}</p></div>
        <span class="status" :data-status="campaign.status">{{ campaign.statusLabel }}</span>
      </div>
      <p class="data-notice">{{ campaign.dataNotice }}</p>
      <div class="work-order-grid">
        <div><span>方案總額</span><strong>{{ currency(campaign.selectedProposal?.total ?? 0) }}</strong></div>
        <div><span>排程</span><strong>{{ campaign.selectedProposal?.availableSlots.join('、') }}</strong></div>
        <div><span>特殊需求</span><strong>{{ campaign.demand.specialRequirements?.join('；') }}</strong></div>
      </div>
      <dl class="quote-breakdown">
        <div v-for="item in campaign.selectedProposal?.items" :key="item.name"><dt>{{ item.name }}</dt><dd>{{ currency(item.amount) }}</dd></div>
      </dl>

      <button v-if="campaign.status === 'assigned'" class="button primary" type="button" :data-testid="`start-joint-${campaign.id}`" @click="confirmingJoint = { id: campaign.id, action: 'start' }">回報開工</button>
      <div v-if="confirmingJoint?.id === campaign.id && confirmingJoint.action === 'start'" class="inline-confirm" role="group" aria-label="確認聯合服務開工">
        <p>確認已核對工單與排程，並回報開始服務？管委會會立即看到狀態。</p>
        <div class="button-row"><button class="button primary" type="button" :data-testid="`confirm-start-joint-${campaign.id}`" @click="startJoint(campaign)">確認開工</button><button class="button" type="button" @click="confirmingJoint = null">取消</button></div>
      </div>

      <div v-if="campaign.status === 'in_progress'" class="completion-form">
        <label :for="`joint-note-${campaign.id}`">完工說明</label>
        <textarea :id="`joint-note-${campaign.id}`" v-model="jointNotes[campaign.id]" rows="3" :data-testid="`joint-note-${campaign.id}`" placeholder="完成台數、異常與交付紀錄" />
        <button class="button" type="button" :data-testid="`complete-joint-${campaign.id}`" :disabled="!(jointNotes[campaign.id] ?? '').trim()" @click="confirmingJoint = { id: campaign.id, action: 'complete' }">預覽完工回報</button>
      </div>
      <div v-if="confirmingJoint?.id === campaign.id && confirmingJoint.action === 'complete'" class="inline-confirm" role="group" aria-label="確認聯合服務完工">
        <p>將以「{{ jointNotes[campaign.id] }}」完成工單並同步管委會。</p>
        <div class="button-row"><button class="button primary" type="button" :data-testid="`confirm-complete-joint-${campaign.id}`" @click="completeJoint(campaign)">確認完工</button><button class="button" type="button" @click="confirmingJoint = null">返回修改</button></div>
      </div>
    </article>
  </section>

  <div v-if="status !== 'unavailable'" class="grid">
    <section class="panel span-7" aria-labelledby="pending-quote">
      <h2 id="pending-quote">待報價</h2>
      <p v-if="!workload.pendingQuote.length" class="muted">目前沒有待報價的需求。</p>

      <article v-for="inquiry in workload.pendingQuote" :key="inquiry.id" class="inquiry-card" :data-inquiry-id="inquiry.id">
        <div class="inquiry-head">
          <div>
            <strong>{{ inquiryTitle(inquiry) }}</strong>
            <div class="row-meta">{{ inquiry.id }}</div>
          </div>
          <span class="status warn">{{ inquiry.status_label }}</span>
        </div>

        <dl v-if="lines(inquiry).length" class="summary-list compact">
          <div v-for="line in lines(inquiry)" :key="line.label">
            <dt>{{ line.label }}</dt><dd>{{ line.value }}</dd>
          </div>
        </dl>

        <div class="quote-form">
          <label class="field">材料費
            <input v-model.number="draftFor(inquiry.id).material" type="number" min="0" :data-material-for="inquiry.id" />
          </label>
          <label class="field">施工費
            <input v-model.number="draftFor(inquiry.id).labour" type="number" min="0" :data-labour-for="inquiry.id" />
          </label>
          <div class="quote-total">
            合計 <strong>{{ currency((draftFor(inquiry.id).material || 0) + (draftFor(inquiry.id).labour || 0)) }}</strong>
          </div>
          <button
            class="button primary"
            type="button"
            :data-testid="`send-quote-${inquiry.id}`"
            :disabled="acting === inquiry.id"
            @click="sendQuote(inquiry)"
          >{{ acting === inquiry.id ? '送出中…' : '送出報價' }}</button>
        </div>
      </article>
    </section>

    <aside class="panel span-5" aria-labelledby="vendor-progress">
      <h2 id="vendor-progress">後續進度</h2>

      <h3 class="subhead">等待住戶確認（{{ workload.awaitingResident.length }}）</h3>
      <p v-if="!workload.awaitingResident.length" class="muted">無</p>
      <div v-for="inquiry in workload.awaitingResident" :key="inquiry.id" class="queue-row">
        <div>
          <strong>{{ inquiryTitle(inquiry) }}</strong>
          <div class="row-meta">{{ inquiry.id }} · {{ inquiry.quote ? currency(inquiry.quote.amount) : '' }}</div>
        </div>
        <span class="status">已報價</span>
      </div>

      <h3 class="subhead">待履約（{{ workload.scheduled.length }}）</h3>
      <p v-if="!workload.scheduled.length" class="muted">無</p>
      <div v-for="inquiry in workload.scheduled" :key="inquiry.id" class="queue-row">
        <div>
          <strong>{{ inquiryTitle(inquiry) }}</strong>
          <div class="row-meta">{{ inquiry.id }}</div>
        </div>
        <button
          class="button"
          type="button"
          :data-testid="`complete-${inquiry.id}`"
          :disabled="acting === inquiry.id"
          @click="reportCompletion(inquiry)"
        >回報完工</button>
      </div>
    </aside>
  </div>
</template>
