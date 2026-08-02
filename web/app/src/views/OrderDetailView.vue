<script setup lang="ts">
// M4 訂單詳情:單一 Booking / CommerceOrder 的摘要、StatusEvent 時間軸與會員操作。
// 狀態顯示名稱寫死對照後端 core/catalog/domains.py;後端是唯一權威,這裡只翻譯給人看。
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError, backendAnswered } from '@/api/http'
import {
  cancelBooking,
  cancelCommerceOrder,
  createPayment,
  getBooking,
  getProvider,
  listAvailability,
  listCommerceOrders,
  requestReschedule,
  retryBookingSync,
  transitionCommerceOrder,
  type Booking,
  type CatalogSlot,
  type CommerceOrder,
  type PaymentRecord,
  type StatusEvent,
} from '@/api/platformClient'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const BOOKING_STATUS_LABELS: Record<string, string> = {
  pending_provider: '需求送出', confirmed: '已預約', in_service: '服務中',
  completed: '已完成', cancelled: '已取消', rejected: '廠商婉拒', exception: '履約異常',
}
const COMMERCE_STATUS_LABELS: Record<string, string> = {
  placed: '收到訂單', accepted: '已接單', preparing: '備貨中', shipped: '已出貨',
  ready_for_pickup: '可取貨', delivered: '已送達', payment_failed: '付款失敗', cancelled: '已取消',
}
const ACTOR_LABELS: Record<string, string> = { partner_staff: '廠商', member: '你', platform: '平台' }
const DETAIL_LABELS: Record<string, string> = {
  problem: '問題描述', address: '服務地址', phone: '聯絡電話', party_size: '人數',
  contact_name: '聯絡人', plate_number: '車牌號碼', car_type: '車型',
  rx_type: '處方箋類型', patient_name: '領藥人', pickup_in_person: '本人領取',
  package_size: '包裹尺寸', pickup_address: '取件地址', receiver_address: '送達地址',
}

const route = useRoute()
const orderId = computed(() => String(route.params.orderId ?? ''))
const isBooking = computed(() => orderId.value.startsWith('booking-'))

const booking = ref<Booking | null>(null)
const order = ref<CommerceOrder | null>(null)
const offeringName = ref('')
const status = ref<'loading' | 'ready' | 'not-found' | 'unavailable'>('loading')
/** 後端有回應但這次失敗(401/500…)時,不能講成「後端沒啟動」。 */
const backendAnsweredError = ref(false)
const error = ref('')
const notice = ref('')
const acting = ref(false)
const refunds = ref<PaymentRecord[]>([])

const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`
const formatTime = (value: string | null | undefined) => (value ?? '').replace('T', ' ').slice(0, 16)

const statusLabel = computed(() => {
  if (booking.value) return BOOKING_STATUS_LABELS[booking.value.status] ?? booking.value.status
  if (order.value) return COMMERCE_STATUS_LABELS[order.value.status] ?? order.value.status
  return ''
})
const rawStatus = computed(() => booking.value?.status ?? order.value?.status ?? '')
const title = computed(() => offeringName.value
  || order.value?.items[0]?.name
  || (isBooking.value ? '服務預約' : '購物訂單'))
const events = computed<StatusEvent[]>(() => booking.value?.events ?? order.value?.events ?? [])
const actorLabel = (role: string) => ACTOR_LABELS[role] ?? role
const eventLabel = (event: StatusEvent) => (booking.value
  ? BOOKING_STATUS_LABELS[event.toStatus]
  : COMMERCE_STATUS_LABELS[event.toStatus]) ?? event.type

const syncBroken = computed(() => {
  const sync = booking.value?.providerSync
  return Boolean(sync && ['failed', 'state_unknown'].includes(sync.syncStatus))
})

const canCancelBooking = computed(() => booking.value != null
  && ['pending_provider', 'confirmed'].includes(booking.value.status))
const canReschedule = computed(() => booking.value?.status === 'confirmed')
const canCancelOrder = computed(() => order.value != null
  && ['placed', 'payment_failed', 'accepted', 'preparing'].includes(order.value.status))
const canRetryPayment = computed(() => order.value?.status === 'payment_failed')

async function resolveOfferingName() {
  const current = booking.value
  if (!current) return
  try {
    const provider = await getProvider(current.providerId)
    offeringName.value = provider.offerings.find((item) => item.id === current.offeringId)?.name ?? ''
  } catch {
    // 目錄查不到時退回泛稱;不因輔助資訊失敗而擋住詳情頁
  }
}

async function load() {
  error.value = ''
  try {
    if (isBooking.value) {
      booking.value = await getBooking(orderId.value)
      refunds.value = booking.value.refunds ?? refunds.value
      status.value = 'ready'
      void resolveOfferingName()
      return
    }
    const orders = await listCommerceOrders()
    const found = orders.find((item) => item.id === orderId.value) ?? null
    order.value = found
    if (!found) {
      status.value = 'not-found'
      return
    }
    refunds.value = found.refunds ?? refunds.value
    status.value = 'ready'
  } catch (reason) {
    backendAnsweredError.value = backendAnswered(reason)
    status.value = reason instanceof ApiError && reason.status === 404 ? 'not-found' : 'unavailable'
  }
}

/** 409 表示狀態已被別的角色改掉:誠實告知並重載,不假裝操作成功。 */
async function handleConflict(reason: unknown, fallback: string): Promise<boolean> {
  if (reason instanceof ApiError && reason.status === 409) {
    error.value = '狀態已被更新,操作未執行;已重新載入最新進度。'
    await load()
    return true
  }
  error.value = reason instanceof ApiError ? reason.message : fallback
  return false
}

// ── ConfirmDialog 二次確認 ──
type PendingAction = 'cancel-booking' | 'cancel-order' | 'retry-payment'
const pendingAction = ref<PendingAction | null>(null)
const confirmCopy = computed(() => ({
  'cancel-booking': {
    title: '取消這筆預約?',
    description: '取消後如已付款,款項與點數會依原路退回;需要服務時得重新預約。',
  },
  'cancel-order': {
    title: '取消這筆訂單?',
    description: '出貨前可取消;取消後如已付款會依原路退款。',
  },
  'retry-payment': {
    title: '重新付款?',
    description: `以 Demo 支付重新付款 ${currency(order.value?.total ?? 0)},成功後訂單回到「收到訂單」。`,
  },
}[pendingAction.value ?? 'cancel-booking']))

async function runConfirmed() {
  const action = pendingAction.value
  pendingAction.value = null
  if (!action || acting.value) return
  acting.value = true
  error.value = ''
  notice.value = ''
  try {
    if (action === 'cancel-booking' && booking.value) {
      const updated = await cancelBooking(booking.value.id, { expectedVersion: booking.value.version })
      booking.value = updated
      refunds.value = updated.refunds ?? []
      notice.value = refunds.value.length
        ? '預約已取消,款項與點數將依原路退回。'
        : '預約已取消。'
    } else if (action === 'cancel-order' && order.value) {
      const updated = await cancelCommerceOrder(order.value.id, { expectedVersion: order.value.version })
      order.value = updated
      refunds.value = updated.refunds ?? []
      notice.value = refunds.value.length
        ? '訂單已取消,款項與點數將依原路退回。'
        : '訂單已取消。'
    } else if (action === 'retry-payment' && order.value) {
      const current = order.value
      await createPayment({
        subjectType: 'commerce_order', subjectId: current.id,
        amount: current.total, outcome: 'success',
      })
      // 真後端在付款成功時會自動把 payment_failed 轉回 placed(版本已跳,這裡會 409 被忽略);
      // 測試替身不會自動轉,由前端補一次 transition 讓兩邊的畫面一致。
      try {
        await transitionCommerceOrder(
          current.id,
          { expectedVersion: current.version, status: 'placed', note: '重新付款成功' },
          `repay-${current.id}-v${current.version}`,
        )
      } catch {
        // 後端已自行轉狀態時忽略,以重載結果為準
      }
      await load()
      notice.value = '已重新付款,訂單回到「收到訂單」。'
    }
  } catch (reason) {
    await handleConflict(reason, '操作未完成,請稍後再試。')
  } finally {
    acting.value = false
  }
}

// ── 改期:必須重新查詢 availability,不能沿用舊時段 ──
const rescheduleOpen = ref(false)
const slots = ref<CatalogSlot[]>([])
const slotsStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const selectedSlotId = ref('')

async function openReschedule() {
  const current = booking.value
  if (!current) return
  rescheduleOpen.value = true
  selectedSlotId.value = ''
  slotsStatus.value = 'loading'
  try {
    slots.value = await listAvailability({ providerId: current.providerId, offeringId: current.offeringId })
    slotsStatus.value = 'ready'
  } catch {
    slotsStatus.value = 'unavailable'
  }
}

async function submitReschedule() {
  const current = booking.value
  const slot = slots.value.find((item) => item.id === selectedSlotId.value)
  if (!current || !slot || acting.value) return
  acting.value = true
  error.value = ''
  try {
    await requestReschedule(current.id, { slotId: slot.id, startsAt: slot.startsAt, endsAt: slot.endsAt })
    rescheduleOpen.value = false
    notice.value = '改期申請已送出,等待廠商回覆;確認前原時段仍然有效。'
  } catch (reason) {
    await handleConflict(reason, '改期申請未送出,請稍後再試。')
  } finally {
    acting.value = false
  }
}

async function retrySync() {
  const current = booking.value
  if (!current || acting.value) return
  acting.value = true
  error.value = ''
  try {
    booking.value = await retryBookingSync(current.id)
    notice.value = '已重新嘗試與廠商系統同步。'
  } catch (reason) {
    await handleConflict(reason, '同步重試失敗,請稍後再試。')
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>

<template>
  <header class="page-heading">
    <div>
      <p class="eyebrow">訂單詳情</p>
      <h1>{{ title }}</h1>
      <p class="muted">{{ orderId }}</p>
    </div>
    <RouterLink class="text-link" to="/user/orders">回訂單列表</RouterLink>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>
  <p v-if="notice" class="feedback-inline" role="status" data-testid="detail-notice">{{ notice }}</p>

  <template v-if="status === 'ready'">
    <section class="panel" aria-labelledby="detail-summary-title">
      <div class="section-title-row">
        <h2 id="detail-summary-title">摘要</h2>
        <span class="status" :data-status="rawStatus" data-testid="detail-status">{{ statusLabel }}</span>
      </div>

      <dl v-if="booking" class="summary-list compact">
        <div><dt>服務</dt><dd>{{ title }}</dd></div>
        <div><dt>時段</dt><dd>{{ formatTime(booking.startsAt) }} – {{ formatTime(booking.endsAt) }}</dd></div>
        <template v-if="booking.details">
          <div v-for="(value, key) in booking.details" :key="key" data-testid="booking-detail-field">
            <dt>{{ DETAIL_LABELS[String(key)] ?? key }}</dt><dd>{{ value }}</dd>
          </div>
        </template>
      </dl>
      <dl v-else-if="order" class="summary-list compact">
        <div v-for="item in order.items" :key="item.offeringId">
          <dt>{{ item.name }} × {{ item.quantity }}</dt><dd>{{ currency(item.amount) }}</dd>
        </div>
        <div><dt>應付金額</dt><dd><strong>{{ currency(order.total) }}</strong></dd></div>
      </dl>

      <!-- 同步失敗要誠實說,不能假裝廠商已收到 -->
      <div v-if="syncBroken" class="error-state compact" role="alert" data-testid="sync-warning">
        <strong>與廠商系統的同步目前{{ booking?.providerSync?.syncStatus === 'failed' ? '失敗' : '狀態不明' }}</strong>
        <p>畫面上的狀態可能不是廠商端的最新狀態。{{ booking?.providerSync?.lastError || '' }}</p>
        <button class="button" type="button" data-testid="retry-sync" :disabled="acting" @click="retrySync">重試同步</button>
      </div>

      <div v-if="refunds.length" class="quote-box" data-testid="refund-info">
        <p class="eyebrow">退款資訊</p>
        <dl class="summary-list compact">
          <div v-for="refund in refunds" :key="refund.id">
            <dt>{{ refund.label }}</dt>
            <dd>退回 {{ currency(refund.refundedAmount) }}<template v-if="refund.refundedPoints">・點數 {{ refund.refundedPoints }} 點</template></dd>
          </div>
        </dl>
      </div>

      <div class="button-row">
        <button v-if="canCancelBooking" class="button danger" type="button" data-testid="cancel-booking"
          :disabled="acting" @click="pendingAction = 'cancel-booking'">取消預約</button>
        <button v-if="canReschedule" class="button" type="button" data-testid="open-reschedule"
          :disabled="acting" @click="openReschedule">申請改期</button>
        <button v-if="canCancelOrder" class="button danger" type="button" data-testid="cancel-order"
          :disabled="acting" @click="pendingAction = 'cancel-order'">取消訂單</button>
        <button v-if="canRetryPayment" class="button primary" type="button" data-testid="retry-payment"
          :disabled="acting" @click="pendingAction = 'retry-payment'">重新付款</button>
      </div>
    </section>

    <section class="panel" aria-labelledby="detail-timeline-title">
      <h2 id="detail-timeline-title">進度時間軸</h2>
      <ol class="timeline" data-testid="detail-timeline">
        <li v-for="event in events" :key="event.id">
          <strong>{{ eventLabel(event) }}</strong>
          <p>{{ formatTime(event.occurredAt) }}・{{ actorLabel(event.actorRole) }}<template v-if="event.note">・{{ event.note }}</template></p>
        </li>
      </ol>
      <p class="source-note muted">進度、通知與行事曆來自同一份 StatusEvent(展示資料)。</p>
    </section>
  </template>

  <div v-else-if="status === 'not-found'" class="panel empty-state compact">
    <h2>找不到這筆訂單</h2>
    <p>它可能已被移除,或編號有誤。</p>
    <RouterLink class="button inline" to="/user/orders">回訂單列表</RouterLink>
  </div>
  <p v-else-if="status === 'unavailable'" class="panel muted" role="status" data-testid="order-detail-unavailable">
    {{ backendAnsweredError
      ? '後端有回應但無法取得這筆訂單,請稍後再試或重新登入。'
      : '目前連不上後端服務,取不到這筆訂單,請確認後端是否啟動。' }}
  </p>
  <div v-else class="panel" role="status">正在載入訂單詳情…</div>

  <ConfirmDialog
    :open="pendingAction !== null"
    :title="confirmCopy.title"
    :description="confirmCopy.description"
    @cancel="pendingAction = null"
    @confirm="runConfirmed"
  />

  <!-- 改期一定重查 availability,選項來自當下的可預約時段 -->
  <div v-if="rescheduleOpen" class="modal-layer" @keydown.esc="rescheduleOpen = false">
    <section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="reschedule-title">
      <p class="eyebrow">申請改期</p>
      <h2 id="reschedule-title">選擇新的時段</h2>
      <p class="muted">送出後由廠商確認;廠商同意前,原時段仍然有效。</p>
      <p v-if="slotsStatus === 'loading'" role="status">正在查詢可預約時段…</p>
      <p v-else-if="slotsStatus === 'unavailable'" class="need-error" role="alert">目前查不到可預約時段,請稍後再試。</p>
      <fieldset v-else class="plain-fieldset">
        <legend class="visually-hidden">可預約時段</legend>
        <label v-for="slot in slots" :key="slot.id" class="order-row" :data-testid="`reschedule-slot-${slot.id}`">
          <input v-model="selectedSlotId" type="radio" name="reschedule-slot" :value="slot.id" />
          <span>{{ formatTime(slot.startsAt) }} – {{ formatTime(slot.endsAt) }}</span>
        </label>
      </fieldset>
      <div class="modal-actions">
        <button class="button ghost" type="button" @click="rescheduleOpen = false">先不改期</button>
        <button class="button primary" type="button" data-testid="submit-reschedule"
          :disabled="acting || !selectedSlotId" @click="submitReschedule">送出改期申請</button>
      </div>
    </section>
  </div>
</template>
