<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { createInquiryLifecycleClient, type Inquiry, type PlatformOrder } from '@/api/inquiryLifecycleClient'
import { backendAnswered } from '@/api/http'
import { createLifeTaskClient, type LifeTask } from '@/api/lifeTaskClient'
import { listBookings, listCommerceOrders, type Booking, type CommerceOrder } from '@/api/platformClient'
import { createSupportClient, type SupportTicket } from '@/api/supportClient'
import SupportIssuePanel from '@/components/SupportIssuePanel.vue'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const session = useSessionStore()
const client = createInquiryLifecycleClient({ accountId: session.accountId, role: 'user' })
const supportClient = createSupportClient()
const lifeTaskClient = createLifeTaskClient()
const inquiries = ref<Inquiry[]>([])
const platformOrders = ref<PlatformOrder[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
/** 後端有回應但這次失敗(401/500…)時,不能講成「後端沒啟動」。 */
const backendAnsweredError = ref(false)
const acting = ref<string | null>(null)
const error = ref('')
const supportTickets = ref<SupportTicket[]>([])
const supportStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const lifeTasks = ref<LifeTask[]>([])

const hasAnything = computed(() => lifeTasks.value.length > 0 || inquiries.value.length > 0 || platformOrders.value.length > 0)
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`

// ── M4 平台 Booking / CommerceOrder:與舊區塊各自載入,任一邊失敗不拖垮另一邊 ──
const BOOKING_STATUS_LABELS: Record<string, string> = {
  pending_provider: '需求送出', confirmed: '已預約', in_service: '服務中',
  completed: '已完成', cancelled: '已取消', rejected: '廠商婉拒', exception: '履約異常',
}
const COMMERCE_STATUS_LABELS: Record<string, string> = {
  placed: '收到訂單', accepted: '已接單', preparing: '備貨中', shipped: '已出貨',
  ready_for_pickup: '可取貨', delivered: '已送達', payment_failed: '付款失敗', cancelled: '已取消',
}
const m4Bookings = ref<Booking[]>([])
const m4Orders = ref<CommerceOrder[]>([])
const m4Status = ref<'loading' | 'ready' | 'unavailable'>('loading')

interface M4Row { id: string; title: string; meta: string; status: string; statusLabel: string }
const formatTime = (value: string | null | undefined) => (value ?? '').replace('T', ' ').slice(0, 16)

const m4Rows = computed<M4Row[]>(() => [
  ...m4Bookings.value.map((booking) => ({
    id: booking.id,
    title: '服務預約',
    meta: `${formatTime(booking.startsAt)} – ${formatTime(booking.endsAt)}`,
    status: booking.status,
    statusLabel: BOOKING_STATUS_LABELS[booking.status] ?? booking.status,
  })),
  ...m4Orders.value.map((order) => ({
    id: order.id,
    title: order.items[0]?.name ?? '購物訂單',
    meta: currency(order.total),
    status: order.status,
    statusLabel: COMMERCE_STATUS_LABELS[order.status] ?? order.status,
  })),
])

async function loadPlatform() {
  m4Status.value = 'loading'
  try {
    const [bookings, orders] = await Promise.all([listBookings(), listCommerceOrders()])
    m4Bookings.value = Array.isArray(bookings) ? bookings : []
    m4Orders.value = Array.isArray(orders) ? orders : []
    m4Status.value = 'ready'
  } catch {
    m4Status.value = 'unavailable'
  }
}

/** 舊資料或部分回應可能沒有摘要，畫面不該因此崩掉。 */
const lines = (inquiry: Inquiry) => inquiry.summary ?? []
const inquiryTitle = (inquiry: Inquiry) => inquiry.title
  || lines(inquiry).find((line) => /服務/.test(line.label))?.value
  || '服務委託'
const events = (inquiry: Inquiry) => inquiry.events ?? []

async function load() {
  try {
    inquiries.value = await client.listMine()
    platformOrders.value = session.accountId
      ? await client.listOrders(session.accountId).catch(() => [])
      : []
    lifeTasks.value = session.accountId
      ? await lifeTaskClient.list({ accountId: session.accountId }).catch(() => [])
      : []
    status.value = 'ready'
    void loadSupport()
  } catch (reason) {
    backendAnsweredError.value = backendAnswered(reason)
    status.value = 'unavailable'
  }
}

async function refreshLifeTask(task: LifeTask) {
  if (!session.accountId) return
  acting.value = task.id
  error.value = ''
  try {
    const updated = await lifeTaskClient.get(task.id, { accountId: session.accountId })
    lifeTasks.value = lifeTasks.value.map((item) => item.id === updated.id ? updated : item)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '生活任務進度無法更新。'
  } finally {
    acting.value = null
  }
}

async function acceptLifeTask(task: LifeTask) {
  if (!session.accountId) return
  acting.value = task.id
  error.value = ''
  try {
    const updated = await lifeTaskClient.acceptQuotes(task, { accountId: session.accountId })
    lifeTasks.value = lifeTasks.value.map((item) => item.id === updated.id ? updated : item)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '報價沒有完整確認。'
  } finally {
    acting.value = null
  }
}

async function loadSupport() {
  if (!session.accountId) {
    supportTickets.value = []
    supportStatus.value = 'ready'
    return
  }
  supportStatus.value = 'loading'
  try {
    supportTickets.value = await supportClient.listMine(session.accountId)
    supportStatus.value = 'ready'
  } catch {
    supportStatus.value = 'unavailable'
  }
}

const supportFor = (subjectId: string) => supportTickets.value.find((ticket) => ticket.subjectId === subjectId) ?? null

function recordSupport(ticket: SupportTicket) {
  supportTickets.value = [ticket, ...supportTickets.value.filter((item) => item.id !== ticket.id)]
}

function replace(updated: Inquiry) {
  inquiries.value = inquiries.value.map((item) => (item.id === updated.id ? updated : item))
}

async function act(inquiry: Inquiry, run: () => Promise<Inquiry>, fallback: string) {
  acting.value = inquiry.id
  error.value = ''
  try {
    replace(await run())
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : fallback
  } finally {
    acting.value = null
  }
}

const confirmQuote = (inquiry: Inquiry) =>
  act(inquiry, () => client.confirm(inquiry.id), '確認未完成，請稍後再試。')

/**
 * 收到報價後住戶有三條路，不是只有同意。
 *
 * 議價與「想換一家」在系統裡是同一個動作：案件退回待報價，附上住戶的說明，
 * 原廠商或別家都能重新出價。分成兩個按鈕只會讓使用者猶豫該按哪個。
 */
const revising = ref<string | null>(null)
const revisionNote = ref('')

function startRevision(inquiry: Inquiry) {
  revising.value = inquiry.id
  revisionNote.value = ''
}

async function submitRevision(inquiry: Inquiry) {
  const note = revisionNote.value.trim()
  if (!note) return
  await act(inquiry, () => client.requestRevision(inquiry.id, note), '退回未完成，請稍後再試。')
  revising.value = null
}

const cancelling = ref<string | null>(null)

async function confirmCancel(inquiry: Inquiry) {
  await act(inquiry, () => client.cancel(inquiry.id), '取消未完成，請稍後再試。')
  cancelling.value = null
}

onMounted(() => {
  void load()
  void loadPlatform()
})
</script>

<template>
  <header class="page-heading">
    <div><p class="eyebrow">訂單與進度</p><h1>你的委託</h1></div>
    <span class="page-status">
      {{ status === 'ready' ? `${lifeTasks.length + inquiries.length + platformOrders.length} 件` : status === 'loading' ? '載入中…' : '離線' }}
    </span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>

  <!-- M4 平台預約/訂單:獨立資料源,不與舊 inquiries/orders 混在一起 -->
  <section class="panel" aria-labelledby="m4-orders-title" data-testid="m4-order-section">
    <h2 id="m4-orders-title">服務預約與訂單</h2>
    <p v-if="m4Status === 'loading'" role="status">正在載入平台預約與訂單…</p>
    <div v-else-if="m4Status === 'unavailable'" class="error-state compact" role="alert">
      <strong>平台預約與訂單暫時無法載入</strong>
      <p>下方的委託紀錄不受影響;重新連線後可再載入。</p>
      <button class="button" type="button" @click="loadPlatform">重新載入</button>
    </div>
    <template v-else>
      <div v-if="m4Rows.length">
        <RouterLink
          v-for="row in m4Rows"
          :key="row.id"
          class="order-row"
          data-testid="m4-order-row"
          :to="`/user/orders/${row.id}`"
        >
          <div>
            <strong>{{ row.title }}</strong>
            <span class="row-meta">{{ row.id }}・{{ row.meta }}</span>
          </div>
          <span class="status" :data-status="row.status">{{ row.statusLabel }}</span>
        </RouterLink>
      </div>
      <div v-else class="empty-state compact">
        <h3>尚無平台預約或訂單</h3>
        <p>從服務探索建立第一筆預約或購物,進度會顯示在這裡。</p>
        <RouterLink class="button primary inline" to="/user/services">去探索服務</RouterLink>
      </div>
    </template>
    <p class="source-note muted">進度、通知與行事曆來自同一份 StatusEvent(展示資料)。</p>
  </section>

  <div v-if="status === 'ready' && hasAnything" class="grid">
    <section class="panel span-8" aria-labelledby="active-orders">
      <h2 id="active-orders">進行中</h2>
      <div v-if="supportStatus === 'unavailable'" class="error-state compact" role="alert">
        <strong>客服進度暫時無法載入</strong>
        <p>訂單資料仍可查看；重新連線後再載入客服進度。</p>
        <button class="button" type="button" @click="loadSupport">重新載入客服</button>
      </div>

      <details
        v-for="(task, taskIndex) in lifeTasks"
        :key="task.id"
        class="inquiry-card order-disclosure life-task-disclosure"
        data-testid="life-task-disclosure"
        :data-life-task-id="task.id"
        :open="route.query.task === task.id || taskIndex === 0"
      >
        <summary class="inquiry-head order-summary">
          <span class="order-summary-copy"><strong>{{ task.items.map((item) => item.title).join('＋') }}</strong><span class="row-meta">{{ task.id }}・{{ task.items.length }} 件服務</span></span>
          <span class="status" :data-status="task.status">{{ task.statusLabel }}</span>
          <span class="disclosure-mark" aria-hidden="true"></span>
        </summary>
        <div class="order-disclosure-body">
          <dl class="summary-list compact">
            <div><dt>日期</dt><dd>{{ task.scheduledDate }}</dd></div>
            <div><dt>地址</dt><dd>{{ task.address?.label }}</dd></div>
            <div v-if="task.estimate"><dt>預估點數後</dt><dd><strong>{{ currency(task.estimate.finalAmount) }}</strong></dd></div>
          </dl>
          <ol class="timeline compact life-task-order-items">
            <li v-for="item in task.items" :key="item.id">
              <strong>{{ item.title }}・{{ item.vendorName }}</strong>
              <span class="muted">{{ item.externalOrderId || item.externalInquiryId || '尚未送出' }}・{{ item.status }}</span>
              <div v-for="quote in item.quotes" :key="quote.id" class="task-quote-row">
                <span>正式報價 {{ quote.id }}</span><strong>{{ currency(quote.total) }}</strong>
              </div>
              <p v-if="item.syncError" class="result-notice">同步較慢：{{ item.syncError }}</p>
            </li>
          </ol>
          <div class="button-row">
            <button class="button" type="button" :disabled="acting === task.id" @click="refreshLifeTask(task)">重新整理進度</button>
            <button v-if="task.status === 'quoted'" class="button primary" type="button" :disabled="acting === task.id" @click="acceptLifeTask(task)">確認全部報價並排程</button>
            <RouterLink class="button inline" :to="`/user/assistant?need=${encodeURIComponent(task.utterance)}`">回 AI 查看</RouterLink>
          </div>
          <p class="source-note muted">案件、報價與履約事件來自獨立 Vendor API；點數為競賽展示帳本。</p>
        </div>
      </details>

      <details
        v-for="order in platformOrders"
        :key="order.id"
        class="inquiry-card order-disclosure"
        data-testid="platform-order-disclosure"
      >
        <summary class="inquiry-head order-summary">
          <span class="order-summary-copy"><strong>日用品補貨訂單</strong><span class="row-meta">{{ order.id }}</span></span>
          <span class="status" :data-status="order.status">{{ order.statusLabel }}</span>
          <span class="disclosure-mark" aria-hidden="true"></span>
        </summary>
        <div class="order-disclosure-body">
          <dl class="summary-list compact">
            <div><dt>應付金額</dt><dd><strong>{{ currency(order.amount) }}</strong></dd></div>
            <div><dt>計價方式</dt><dd>確定性優惠規則</dd></div>
          </dl>
          <ol class="timeline compact">
            <li v-for="event in order.events" :key="`${event.type}-${event.occurred_at}`">
              <strong>{{ event.type === 'order.created' ? '訂單已建立' : event.type }}</strong>
              <span v-if="event.detail" class="muted">・{{ event.detail }}</span>
            </li>
          </ol>
          <p class="muted source-note">平台訂單已持久化；品牌履約接入目前為競賽模擬。</p>
          <SupportIssuePanel
            v-if="session.accountId"
            :account-id="session.accountId"
            :subject-id="order.id"
            :ticket="supportFor(order.id)"
            @created="recordSupport"
          />
        </div>
      </details>

      <details
        v-for="(inquiry, index) in inquiries"
        :key="inquiry.id"
        class="inquiry-card order-disclosure"
        :data-inquiry-id="inquiry.id"
        data-testid="order-disclosure"
        :open="index === 0"
      >
        <summary class="inquiry-head order-summary">
          <span class="order-summary-copy">
            <strong>{{ inquiryTitle(inquiry) }}</strong>
            <span class="row-meta">{{ inquiry.id }}</span>
          </span>
          <span class="status" :data-status="inquiry.status">{{ inquiry.status_label }}</span>
          <span class="disclosure-mark" aria-hidden="true"></span>
        </summary>

        <div class="order-disclosure-body">

        <dl v-if="lines(inquiry).length" class="summary-list compact">
          <div v-for="line in lines(inquiry)" :key="line.label">
            <dt>{{ line.label }}</dt><dd>{{ line.value }}</dd>
          </div>
        </dl>

        <!-- 廠商報價回來了，等你確認 -->
        <div v-if="inquiry.quote" class="quote-box" :data-quote-for="inquiry.id">
          <p class="eyebrow">{{ inquiry.quote.vendorName }} 的報價</p>
          <dl class="summary-list compact">
            <div v-for="item in inquiry.quote.items" :key="item.name">
              <dt>{{ item.name }}</dt><dd>{{ currency(item.amount) }}</dd>
            </div>
            <div><dt>合計</dt><dd><strong>{{ currency(inquiry.quote.amount) }}</strong></dd></div>
          </dl>
          <!-- 三條路：同意、請對方調整（含換一家）、不做了 -->
          <div v-if="inquiry.status === 'quoted' && revising !== inquiry.id" class="quote-actions">
            <button
              class="button primary"
              type="button"
              :data-testid="`confirm-quote-${inquiry.id}`"
              :disabled="acting === inquiry.id"
              @click="confirmQuote(inquiry)"
            >{{ acting === inquiry.id ? '處理中…' : '同意這個報價' }}</button>
            <button
              class="button"
              type="button"
              :data-testid="`revise-quote-${inquiry.id}`"
              :disabled="acting === inquiry.id"
              @click="startRevision(inquiry)"
            >想調整或換一家</button>
            <button
              class="button danger"
              type="button"
              :data-testid="`cancel-inquiry-${inquiry.id}`"
              :disabled="acting === inquiry.id"
              @click="cancelling = inquiry.id"
            >不需要了</button>
          </div>

          <!-- 退回時一定要說明希望怎麼改，否則廠商只能重猜一次 -->
          <form
            v-else-if="revising === inquiry.id"
            class="quote-revision"
            @submit.prevent="submitRevision(inquiry)"
          >
            <label :for="`revision-${inquiry.id}`">希望怎麼調整？</label>
            <textarea
              :id="`revision-${inquiry.id}`"
              v-model="revisionNote"
              rows="2"
              :data-testid="`revision-note-${inquiry.id}`"
              placeholder="例如：預算希望壓在 1000 以內，或想多比較一家"
            />
            <p class="muted">送出後案件會退回待報價，原廠商或其他廠商都能重新出價。</p>
            <div class="button-row">
              <button
                class="button primary"
                type="submit"
                :data-testid="`revision-submit-${inquiry.id}`"
                :disabled="acting === inquiry.id || !revisionNote.trim()"
              >送出並請對方重新報價</button>
              <button class="button" type="button" @click="revising = null">取消</button>
            </div>
          </form>
        </div>

        <p v-else-if="inquiry.status === 'pending_quote'" class="muted">
          已送達合作夥伴，報價回覆後會顯示在這裡。
        </p>

        <!-- 取消是不可逆的，先問過再做（ADR-0008） -->
        <div v-if="cancelling === inquiry.id" class="quote-cancel" role="alertdialog" :aria-label="`確認取消 ${inquiry.id}`">
          <p><strong>要取消這件委託嗎？</strong>取消後無法復原，需要時得重新提出需求。</p>
          <div class="button-row">
            <button
              class="button danger"
              type="button"
              :data-testid="`cancel-confirm-${inquiry.id}`"
              :disabled="acting === inquiry.id"
              @click="confirmCancel(inquiry)"
            >確定取消委託</button>
            <button class="button" type="button" @click="cancelling = null">先不要</button>
          </div>
        </div>

        <!-- 待報價時也能取消（還沒有人開始做事） -->
        <button
          v-else-if="inquiry.status === 'pending_quote'"
          class="text-button"
          type="button"
          :data-testid="`cancel-inquiry-${inquiry.id}`"
          @click="cancelling = inquiry.id"
        >取消這件委託</button>

        <ol class="timeline compact">
          <li v-for="event in events(inquiry)" :key="`${event.type}-${event.occurred_at}`">
            <strong>{{ ({
              'inquiry.created': '需求已送出',
              'quote.created': '收到報價',
              'quote.confirmed': '你已同意報價',
              'quote.revision_requested': '你請對方重新報價',
              'inquiry.cancelled': '你已取消委託',
              'service.completed': '服務完成',
            } as Record<string, string>)[event.type] || event.type }}</strong>
            <span v-if="event.detail" class="muted">・{{ event.detail }}</span>
          </li>
        </ol>
        <SupportIssuePanel
          v-if="session.accountId && inquiry.status !== 'cancelled'"
          :account-id="session.accountId"
          :subject-id="inquiry.id"
          :ticket="supportFor(inquiry.id)"
          @created="recordSupport"
        />
        </div>
      </details>

    </section>

    <aside class="panel span-4" aria-labelledby="order-timeline">
      <h2 id="order-timeline">流程說明</h2>
      <ol class="timeline">
        <li><strong>需求送出</strong><p>合作夥伴會收到你填的內容</p></li>
        <li><strong>對方回覆報價</strong><p>金額與項目都會列出來</p></li>
        <li><strong>你可以同意、請對方調整，或不做了</strong><p>同意前不會有任何費用</p></li>
        <li><strong>完工回報</strong><p>完成後這裡會更新</p></li>
      </ol>
    </aside>
  </div>

  <div v-else-if="status === 'ready'" class="panel empty-state compact">
    <h2>還沒有任何委託</h2>
    <p>在首頁描述你的需求，或直接挑一項服務——送出後進度都會顯示在這裡。</p>
    <RouterLink class="button primary inline" to="/user">回首頁描述需求</RouterLink>
  </div>

  <p v-else-if="status === 'unavailable'" class="panel muted" role="status" data-testid="orders-unavailable">
    {{ backendAnsweredError
      ? '後端有回應但無法取得委託紀錄，請稍後再試或重新登入。'
      : '無法取得委託紀錄，連不上後端服務，請確認後端是否啟動。' }}
  </p>
</template>
