<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { createInquiryLifecycleClient, type Inquiry, type PlatformOrder } from '@/api/inquiryLifecycleClient'
import { useDemoStore } from '@/stores/demo'
import { useSessionStore } from '@/stores/session'

const store = useDemoStore()
const session = useSessionStore()
const client = createInquiryLifecycleClient()
const inquiries = ref<Inquiry[]>([])
const platformOrders = ref<PlatformOrder[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const acting = ref<string | null>(null)
const error = ref('')

const hasAnything = computed(() => inquiries.value.length > 0 || platformOrders.value.length > 0 || store.orders.length > 0)
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`

/** 舊資料或部分回應可能沒有摘要，畫面不該因此崩掉。 */
const lines = (inquiry: Inquiry) => inquiry.summary ?? []
const events = (inquiry: Inquiry) => inquiry.events ?? []

async function load() {
  try {
    inquiries.value = await client.listMine()
    platformOrders.value = session.accountId
      ? await client.listOrders(session.accountId).catch(() => [])
      : []
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
  }
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

onMounted(load)
</script>

<template>
  <header class="page-heading">
    <div><p class="eyebrow">訂單與進度</p><h1>你的委託</h1></div>
    <span class="page-status">
      {{ status === 'ready' ? `${inquiries.length + platformOrders.length} 件` : status === 'loading' ? '載入中…' : '離線' }}
    </span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>

  <div v-if="status === 'ready' && hasAnything" class="grid">
    <section class="panel span-8" aria-labelledby="active-orders">
      <h2 id="active-orders">進行中</h2>

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
            <strong>{{ lines(inquiry)[0]?.value || '服務委託' }}</strong>
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
        </div>
      </details>

      <article v-for="order in store.orders" :key="order.id" class="order-row">
        <div><strong>{{ order.service.name }}</strong><div class="row-meta">{{ order.id }} · {{ order.service.partner }}</div></div>
        <span class="status">{{ order.status }}</span>
      </article>
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

  <p v-else-if="status === 'unavailable'" class="panel muted" role="status">
    無法取得委託紀錄，請確認後端服務是否啟動。
  </p>
</template>
