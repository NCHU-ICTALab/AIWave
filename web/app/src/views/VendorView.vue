<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  createInquiryLifecycleClient,
  type Inquiry,
  type VendorWorkload,
} from '@/api/inquiryLifecycleClient'
import { createJointServiceClient, type JointServiceCampaign } from '@/api/jointServiceClient'
import { useSessionStore } from '@/stores/session'

const client = createInquiryLifecycleClient()
const session = useSessionStore()
const jointClient = createJointServiceClient({ accountId: session.accountId })
const workload = ref<VendorWorkload>({ pendingQuote: [], awaitingResident: [], scheduled: [] })
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const acting = ref<string | null>(null)
const error = ref('')
const jointCampaigns = ref<JointServiceCampaign[]>([])
const jointStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const confirmingJoint = ref<{ id: number; action: 'start' | 'complete' } | null>(null)
const jointNotes = reactive<Record<number, string>>({})

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
    void loadJointServices()
  } catch {
    status.value = 'unavailable'
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
