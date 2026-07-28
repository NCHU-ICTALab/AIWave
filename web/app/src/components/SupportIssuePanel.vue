<script setup lang="ts">
import { ref, watch } from 'vue'

import { createSupportClient, type SupportDiagnostic, type SupportTicket } from '@/api/supportClient'

const props = defineProps<{ accountId: string; subjectId: string; ticket?: SupportTicket | null }>()
const emit = defineEmits<{ created: [ticket: SupportTicket] }>()
const client = createSupportClient()
const opened = ref(false)
const issueText = ref('')
const diagnosis = ref<SupportDiagnostic | null>(null)
const busy = ref(false)
const error = ref('')

watch(issueText, () => {
  if (diagnosis.value && issueText.value.trim() !== diagnosis.value.issueText) diagnosis.value = null
})

async function diagnose() {
  if (issueText.value.trim().length < 4 || busy.value) return
  busy.value = true
  error.value = ''
  try {
    diagnosis.value = await client.diagnose(props.accountId, props.subjectId, issueText.value.trim())
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '目前無法整理問題，請稍後再試。'
  } finally {
    busy.value = false
  }
}

async function createTicket() {
  if (!diagnosis.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const ticket = await client.create(
      props.accountId,
      props.subjectId,
      diagnosis.value.issueText,
      diagnosis.value.diagnosisToken,
    )
    emit('created', ticket)
    opened.value = false
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '客服工單目前無法建立，請稍後再試。'
  } finally {
    busy.value = false
  }
}

const eventLabel = (type: string) => ({
  'support.created': '問題已送出',
  'support.in_progress': '客服已接手',
  'support.resolved': '問題已處理',
} as Record<string, string>)[type] ?? type
const deadline = (value: string) => new Intl.DateTimeFormat('zh-TW', {
  month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
}).format(new Date(value))
const priorityLabel = (priority: SupportTicket['priority']) => ({ high: '優先處理', medium: '中優先處理', normal: '一般處理' })[priority]
const slaLabel = (ticket: SupportTicket) => {
  const due = new Date(ticket.dueAt).getTime()
  const started = ticket.events.find((event) => event.type === 'support.in_progress')
  if (started) return new Date(started.occurred_at).getTime() <= due ? '已在期限內接手' : '逾期接手'
  if (ticket.status === 'resolved') return '已完成'
  return ticket.asOf && new Date(ticket.asOf).getTime() > due ? '已逾期，客服應優先跟進' : '等待客服接手'
}
</script>

<template>
  <section v-if="ticket" class="support-ticket" :data-ticket-id="ticket.id" aria-label="客服工單進度">
    <div class="support-ticket-head">
      <div><p class="eyebrow">客服工單 {{ ticket.id }}</p><strong>{{ ticket.categoryLabel }}</strong></div>
      <span class="status" :data-status="ticket.status">{{ ticket.statusLabel }}</span>
    </div>
    <p>{{ ticket.issueText }}</p>
    <p v-if="ticket.status !== 'resolved'" class="support-sla">
      處理期限 {{ deadline(ticket.dueAt) }}
      <strong>・{{ slaLabel(ticket) }}</strong>
    </p>
    <ol class="timeline compact">
      <li v-for="event in ticket.events" :key="`${event.type}-${event.occurred_at}`">
        <strong>{{ eventLabel(event.type) }}</strong><span class="muted">・{{ event.actor }}</span>
        <span v-if="event.detail" class="muted">・{{ event.detail }}</span>
        <time class="muted" :datetime="event.occurred_at">・{{ deadline(event.occurred_at) }}</time>
      </li>
    </ol>
  </section>

  <div v-if="!ticket || ticket.status === 'resolved'" class="support-entry">
      <button v-if="!opened" class="text-button" type="button"
      :data-testid="`support-action-${subjectId}`" @click="opened = true">
        {{ ticket?.status === 'resolved' ? '仍有問題？建立新的客服工單' : '遇到問題？回報客服' }}
      </button>

    <form v-else class="support-form" @submit.prevent="diagnose">
      <div class="support-form-heading">
        <div><p class="eyebrow">訂單協助</p><strong>發生什麼事？</strong></div>
        <button class="text-button" type="button" @click="opened = false">收起</button>
      </div>
      <label :for="`support-issue-${subjectId}`">問題描述</label>
      <textarea :id="`support-issue-${subjectId}`" v-model="issueText" rows="3" maxlength="500"
        :data-testid="`support-issue-${subjectId}`" placeholder="例如：師傅已晚兩小時還沒到，也沒有通知" />
      <p class="muted">請描述實際情況，系統會根據訂單狀態整理處理方向；送出工單前仍會讓你確認。</p>
      <p v-if="error" class="need-error" role="alert">{{ error }}</p>
      <button v-if="!diagnosis" class="button" type="button"
        :data-testid="`support-diagnose-${subjectId}`" :disabled="busy || issueText.trim().length < 4" @click="diagnose">
        {{ busy ? '整理中…' : '整理問題與處理方式' }}
      </button>

      <section v-else class="support-preview" aria-label="客服工單送出預覽">
        <div class="support-ticket-head">
          <div><p class="eyebrow">系統判斷</p><strong>{{ diagnosis.categoryLabel }}</strong></div>
          <span class="status warn">{{ priorityLabel(diagnosis.priority) }}</span>
        </div>
        <p>客服會在 {{ diagnosis.slaHours }} 小時內開始處理，並路由給適合的處理窗口。</p>
        <details class="reason-details">
          <summary>查看判斷依據</summary>
          <ul><li v-for="evidence in diagnosis.evidence" :key="evidence">{{ evidence }}</li></ul>
          <p class="muted source-note">分類與 SLA 由可重算規則產生，不由語言模型決定。</p>
        </details>
        <div class="button-row">
          <button class="button primary" type="button" :data-testid="`support-confirm-${subjectId}`"
            :disabled="busy" @click="createTicket">{{ busy ? '建立中…' : '確認建立客服工單' }}</button>
          <button class="button" type="button" @click="diagnosis = null">修改描述</button>
        </div>
      </section>
    </form>
  </div>
</template>
