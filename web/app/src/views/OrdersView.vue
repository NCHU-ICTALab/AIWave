<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { createInquiryLifecycleClient, type Inquiry } from '@/api/inquiryLifecycleClient'
import { useDemoStore } from '@/stores/demo'

const store = useDemoStore()
const client = createInquiryLifecycleClient()
const inquiries = ref<Inquiry[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const acting = ref<string | null>(null)
const error = ref('')

const hasAnything = computed(() => inquiries.value.length > 0 || store.orders.length > 0)
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`

/** 舊資料或部分回應可能沒有摘要，畫面不該因此崩掉。 */
const lines = (inquiry: Inquiry) => inquiry.summary ?? []
const events = (inquiry: Inquiry) => inquiry.events ?? []

async function load() {
  try {
    inquiries.value = await client.listMine()
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
  }
}

async function confirmQuote(inquiry: Inquiry) {
  acting.value = inquiry.id
  error.value = ''
  try {
    const updated = await client.confirm(inquiry.id)
    inquiries.value = inquiries.value.map((item) => (item.id === updated.id ? updated : item))
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '確認未完成，請稍後再試。'
  } finally {
    acting.value = null
  }
}

onMounted(load)
</script>

<template>
  <header class="page-heading">
    <div><p class="eyebrow">訂單與進度</p><h1>你的委託</h1></div>
    <span class="page-status">
      {{ status === 'ready' ? `${inquiries.length} 件` : status === 'loading' ? '載入中…' : '離線' }}
    </span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>

  <div v-if="status === 'ready' && hasAnything" class="grid">
    <section class="panel span-8" aria-labelledby="active-orders">
      <h2 id="active-orders">進行中</h2>

      <article v-for="inquiry in inquiries" :key="inquiry.id" class="inquiry-card" :data-inquiry-id="inquiry.id">
        <div class="inquiry-head">
          <div>
            <strong>{{ lines(inquiry)[0]?.value || '服務委託' }}</strong>
            <div class="row-meta">{{ inquiry.id }}</div>
          </div>
          <span class="status" :data-status="inquiry.status">{{ inquiry.status_label }}</span>
        </div>

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
          <button
            v-if="inquiry.status === 'quoted'"
            class="button primary"
            type="button"
            :data-testid="`confirm-quote-${inquiry.id}`"
            :disabled="acting === inquiry.id"
            @click="confirmQuote(inquiry)"
          >{{ acting === inquiry.id ? '處理中…' : '同意這個報價' }}</button>
        </div>

        <p v-else-if="inquiry.status === 'pending_quote'" class="muted">
          已送達合作夥伴，報價回覆後會顯示在這裡。
        </p>

        <ol class="timeline compact">
          <li v-for="event in events(inquiry)" :key="`${event.type}-${event.occurred_at}`">
            <strong>{{ ({
              'inquiry.created': '需求已送出',
              'quote.created': '收到報價',
              'quote.confirmed': '你已同意報價',
              'service.completed': '服務完成',
            } as Record<string, string>)[event.type] || event.type }}</strong>
            <span v-if="event.detail" class="muted">・{{ event.detail }}</span>
          </li>
        </ol>
      </article>

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
        <li><strong>你同意後才進行</strong><p>不同意就不會有任何費用</p></li>
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
