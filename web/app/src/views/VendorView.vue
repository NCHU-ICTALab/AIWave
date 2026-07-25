<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  createInquiryLifecycleClient,
  type Inquiry,
  type VendorWorkload,
} from '@/api/inquiryLifecycleClient'

const client = createInquiryLifecycleClient()
const workload = ref<VendorWorkload>({ pendingQuote: [], awaitingResident: [], scheduled: [] })
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const acting = ref<string | null>(null)
const error = ref('')

/** 每筆待報價各自的報價草稿（材料費＋施工費，對齊官方 order_items 的分項慣例）。 */
const drafts = reactive<Record<string, { material: number; labour: number }>>({})

const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`
/** 部分回應可能沒有摘要，畫面不該因此崩掉。 */
const lines = (inquiry: Inquiry) => inquiry.summary ?? []

function draftFor(id: string) {
  if (!drafts[id]) drafts[id] = { material: 300, labour: 900 }
  return drafts[id]
}

async function load() {
  try {
    workload.value = await client.vendorWorkload()
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
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
    ], '安心修繕')
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

  <div v-else class="grid">
    <section class="panel span-7" aria-labelledby="pending-quote">
      <h2 id="pending-quote">待報價</h2>
      <p v-if="!workload.pendingQuote.length" class="muted">目前沒有待報價的需求。</p>

      <article v-for="inquiry in workload.pendingQuote" :key="inquiry.id" class="inquiry-card" :data-inquiry-id="inquiry.id">
        <div class="inquiry-head">
          <div>
            <strong>{{ lines(inquiry)[0]?.value || '服務需求' }}</strong>
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
          <strong>{{ lines(inquiry)[0]?.value || '服務需求' }}</strong>
          <div class="row-meta">{{ inquiry.id }} · {{ inquiry.quote ? currency(inquiry.quote.amount) : '' }}</div>
        </div>
        <span class="status">已報價</span>
      </div>

      <h3 class="subhead">待履約（{{ workload.scheduled.length }}）</h3>
      <p v-if="!workload.scheduled.length" class="muted">無</p>
      <div v-for="inquiry in workload.scheduled" :key="inquiry.id" class="queue-row">
        <div>
          <strong>{{ lines(inquiry)[0]?.value || '服務需求' }}</strong>
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
