<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import {
  getExecutionGrant,
  type AgentAction,
  type AgentProposal,
  type ExecutionGrant,
} from '@/api/agentClient'
import { useAgentSessionStore } from '@/stores/agentSession'

/**
 * M8 Agent 對話核心元件（「換腦不換臉」）。
 *
 * 側欄（AgentDrawer）與 /user/assistant 全頁掛同一個元件、讀寫同一個
 * agent-session store（spec 15 §4.1）；對話與草稿都持久化在後端，
 * 這裡只是即時鏡像。所有互動（釐清、選方案、授權）都是真動作——
 * 以結構化 action 直接送回協調器，不經 LLM 也不在前端自演流程。
 *
 * 依 design-system/ai/MASTER.md：訊息區自行捲動、composer 固定底部、
 * 選項放在輸入框上方、等待期間只顯示可驗證階段（不顯示思考鏈）、
 * 交易必須明確核准——沒有自動核准。
 */
const store = useAgentSessionStore()

const prompt = ref('')
/** 送出中的使用者訊息先回顯在畫面上；後端回覆後由 session.messages 接手。 */
const pendingEcho = ref('')
const input = ref<HTMLTextAreaElement | null>(null)
const messageList = ref<HTMLElement | null>(null)
const grant = ref<ExecutionGrant | null>(null)

/** 起手式示例：按下就是真的送出訊息，不是導頁。 */
const starters = ['浴室的燈不亮了', '想找人來打掃', '這週末想訂餐廳']

const messages = computed(() => store.messages)
const awaiting = computed(() => store.awaiting)

/** 互動區(收合式)是否有內容,與 summary 摘要文字。 */
const hasActions = computed(() =>
  clarifySubtasks.value.length > 0 || optionSubtasks.value.length > 0
  || fieldsSubtasks.value.length > 0 || awaiting.value === 'grant')
const actionSummary = computed(() => {
  if (awaiting.value === 'grant') return '執行授權待核准'
  if (optionSubtasks.value.length) {
    const total = optionSubtasks.value.reduce((sum, item) => sum + item.proposals.length, 0)
    return `${total} 個方案待選擇`
  }
  if (fieldsSubtasks.value.length) return '還差幾個欄位'
  if (clarifySubtasks.value.length) return '需要你釐清'
  return '待處理'
})
const subtasks = computed(() => store.subtasks)

const clarifySubtasks = computed(() =>
  awaiting.value === 'clarify' ? subtasks.value.filter((item) => item.clarifyOptions.length) : [],
)
const optionSubtasks = computed(() =>
  awaiting.value === 'option' ? subtasks.value.filter((item) => item.proposals.length && !item.selected) : [],
)
const fieldsSubtasks = computed(() =>
  awaiting.value === 'fields' ? subtasks.value.filter((item) => item.status === 'fields' && item.draftId) : [],
)
const submittedSubtasks = computed(() =>
  subtasks.value.filter((item) => item.status === 'submitted' && item.subjectId),
)
const lastAssistantText = computed(
  () => [...messages.value].reverse().find((item) => item.role === 'assistant')?.content ?? '',
)
const showStarters = computed(() => !messages.value.length && !store.busy && !pendingEcho.value)

const FIELD_LABELS: Record<string, string> = {
  problem: '問題描述',
  address: '服務地址',
  phone: '聯絡電話',
  note: '備註',
  quantity: '數量',
}
function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field
}

function slotLabel(slot: AgentProposal['slot']): string {
  if (!slot) return '時間再議'
  return `${slot.startsAt.slice(0, 10)} ${slot.startsAt.slice(11, 16)}–${slot.endsAt.slice(11, 16)}`
}

const money = (value: number) => `NT$ ${Number(value ?? 0).toLocaleString('zh-TW')}`

/** 只捲動訊息列本身，不帶著整頁跳動。 */
async function scrollToEnd() {
  await nextTick()
  const list = messageList.value
  if (list) list.scrollTop = list.scrollHeight
}

watch(
  () => [messages.value.length, store.stages.length, store.busy] as const,
  () => void scrollToEnd(),
)

// 授權卡需要可稽核的摘要（服務商／時間範圍／預算上限／有效期）；
// 拿不到時退回 assistant 最後訊息的文字說明，內容仍含相同的授權範圍。
watch(
  () => (awaiting.value === 'grant' ? (store.session?.grantId ?? null) : null),
  async (grantId) => {
    if (!grantId) {
      grant.value = null
      return
    }
    try {
      grant.value = await getExecutionGrant(grantId)
    } catch {
      grant.value = null
    }
  },
  { immediate: true },
)

async function sendText(text: string) {
  const content = text.trim()
  if (!content || store.busy) return
  prompt.value = ''
  await nextTick()
  resizeInput()
  pendingEcho.value = content
  try {
    await store.send({ message: content })
  } finally {
    pendingEcho.value = ''
    void nextTick(() => input.value?.focus())
  }
}

async function sendAction(action: AgentAction) {
  if (store.busy) return
  await store.send({ action })
}

/**
 * 輸入框跟著內容長高（禁止手動拖曳 resize）；每次先回到 auto，
 * 刪字時才縮得回去，否則 scrollHeight 只會愈來愈大。
 */
function resizeInput() {
  const element = input.value
  if (!element) return
  element.style.height = 'auto'
  const maxHeight = 160
  element.style.height = `${Math.min(element.scrollHeight, maxHeight)}px`
  element.style.overflowY = element.scrollHeight > maxHeight ? 'auto' : 'hidden'
}

/** Enter 送出，Shift+Enter 換行。 */
function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  void sendText(prompt.value)
}

onMounted(async () => {
  // 取回同一段對話（重新整理不遺失），再把首頁入口排隊的訊息送出。
  await store.restore()
  await store.flushPending()
  await scrollToEnd()
})
</script>

<template>
  <div class="assistant-body agent-conversation" data-testid="agent-conversation">
    <!-- 訊息區：使用者右、AI 左，內部自行捲動 -->
    <section ref="messageList" class="message-list" aria-live="polite" aria-label="對話內容">
      <div v-if="!messages.length && !pendingEcho" class="message from-assistant">
        <span>AI 管家</span>
        <p>嗨，我可以幫你把一句話的需求拆成可執行的安排：找方案、比時段、備妥表單，最後由你核准才會真的送出。</p>
      </div>

      <div
        v-for="(message, index) in messages"
        :key="index"
        class="message"
        :class="message.role === 'user' ? 'from-user' : 'from-assistant'"
      >
        <span>{{ message.role === 'user' ? '你' : 'AI 管家' }}</span>
        <p>{{ message.content }}</p>
      </div>

      <div v-if="pendingEcho" class="message from-user">
        <span>你</span>
        <p>{{ pendingEcho }}</p>
      </div>

      <!-- 已送單結果：訂單編號＋可追蹤連結 -->
      <article
        v-for="subtask in submittedSubtasks"
        :key="`result-${subtask.id}`"
        class="agent-card agent-result"
        data-testid="agent-result"
      >
        <p class="eyebrow">已送出</p>
        <strong class="agent-result-id">{{ subtask.subjectId }}</strong>
        <p>「{{ subtask.goal }}」的訂單已建立，進度、通知與行事曆都會同步更新。</p>
        <RouterLink class="button primary inline" data-testid="order-link" :to="`/user/orders/${subtask.subjectId}`">
          查看訂單進度
        </RouterLink>
      </article>

      <!-- 串流階段：只顯示可驗證的工作階段（不顯示思考鏈）；完成後保留靜態文字 -->
      <div
        v-if="store.busy || store.stages.length"
        class="agent-stages"
        :class="{ busy: store.busy }"
        :role="store.busy ? 'status' : undefined"
        data-testid="agent-stages"
      >
        <span v-if="store.busy" class="activity-dots" aria-hidden="true"><i></i><i></i><i></i></span>
        <ol v-if="store.stages.length">
          <li v-for="(stage, index) in store.stages" :key="`${index}-${stage}`">{{ stage }}</li>
        </ol>
        <span v-else>正在理解需求</span>
      </div>
    </section>

    <!-- 選項／動作列固定在輸入框上方；composer 固定在工作區底部 -->
    <section class="assistant-answer assistant-composer" data-testid="assistant-composer">
      <div v-if="store.error" class="error-state" role="alert">
        <strong>目前無法繼續</strong>
        <p>{{ store.error }}</p>
      </div>

      <!-- 互動區收合(2026-07-31):限高內捲,不擋聊天;composer 隨時可打字 -->
      <details v-if="hasActions" class="agent-actions" open data-testid="agent-actions">
        <summary>{{ actionSummary }}</summary>
        <div class="agent-actions-body">

      <!-- 釐清：每個選項都是真動作（結構化 clarify_option，不經 LLM 重新解讀） -->
      <template v-if="clarifySubtasks.length">
        <div
          v-for="subtask in clarifySubtasks"
          :key="`clarify-${subtask.id}`"
          class="answer-choices"
          :aria-label="subtask.clarify ?? `釐清「${subtask.goal}」`"
        >
          <button
            v-for="option in subtask.clarifyOptions"
            :key="option.label"
            class="choice-button"
            type="button"
            data-testid="clarify-option"
            :disabled="store.busy"
            @click="sendAction({ type: 'clarify_option', subtaskId: subtask.id, domain: option.domain, label: option.label })"
          >{{ option.label }}</button>
        </div>
      </template>

      <!-- 方案卡：每張卡回答「為何推薦」（reasons）；選擇後才會預填表單 -->
      <template v-else-if="optionSubtasks.length">
        <div
          v-for="subtask in optionSubtasks"
          :key="`options-${subtask.id}`"
          class="agent-proposals"
          :aria-label="`「${subtask.goal}」的可選方案`"
        >
          <article
            v-for="proposal in subtask.proposals"
            :key="proposal.id"
            class="agent-card agent-proposal"
            data-testid="proposal-card"
          >
            <header class="agent-proposal-head">
              <div>
                <strong>{{ proposal.providerName }}</strong>
                <p class="muted">{{ proposal.offeringName }}</p>
              </div>
              <div class="agent-proposal-price">
                <strong>{{ money(proposal.basePrice) }}</strong>
                <small class="muted">{{ slotLabel(proposal.slot) }}</small>
              </div>
            </header>
            <ul class="agent-reasons" aria-label="為何推薦">
              <li v-for="reason in proposal.reasons" :key="reason">{{ reason }}</li>
            </ul>
            <button
              class="button primary"
              type="button"
              data-testid="proposal-select"
              :disabled="store.busy"
              @click="sendAction({ type: 'select_option', subtaskId: subtask.id, optionId: proposal.id })"
            >選這個</button>
          </article>
        </div>
      </template>

      <!-- 缺欄位：可直接在下方回覆，或切到手動填寫（兩邊是同一份草稿） -->
      <template v-else-if="fieldsSubtasks.length">
        <div v-for="subtask in fieldsSubtasks" :key="`fields-${subtask.id}`" class="agent-fields" role="status">
          <p>
            「{{ subtask.goal }}」還缺：<strong>{{ subtask.missingFields.map(fieldLabel).join('、') }}</strong>。
            直接在下方回覆就可以，我會幫你帶進表單。
          </p>
          <RouterLink
            class="button inline"
            data-testid="handoff-manual"
            :to="`/user/booking?draft=${subtask.draftId}`"
          >切到手動填寫</RouterLink>
        </div>
      </template>

      <!-- 授權卡：交易必須明確核准——沒有自動核准 -->
      <article v-else-if="awaiting === 'grant'" class="agent-card agent-grant" data-testid="grant-card">
        <p class="eyebrow">執行授權</p>
        <p class="agent-grant-summary">{{ grant?.summary ?? lastAssistantText }}</p>
        <dl v-if="grant" class="agent-grant-facts">
          <div><dt>預算上限</dt><dd>{{ money(grant.budgetLimit) }}</dd></div>
          <div><dt>時間範圍</dt><dd>{{ grant.windowStart }} ～ {{ grant.windowEnd }}</dd></div>
          <div><dt>有效期至</dt><dd>{{ grant.expiresAt.slice(0, 16).replace('T', ' ') }}</dd></div>
        </dl>
        <p class="muted">核准後我才會實際送出；「先不要」就不會建立任何訂單。</p>
        <div class="button-row">
          <button
            class="button primary"
            type="button"
            data-testid="grant-approve"
            :disabled="store.busy"
            @click="sendAction({ type: 'approve_grant' })"
          >核准並執行</button>
          <button
            class="button"
            type="button"
            data-testid="grant-revoke"
            :disabled="store.busy"
            @click="sendAction({ type: 'revoke_grant' })"
          >先不要</button>
        </div>
      </article>

        </div>
      </details>

      <!-- 起手式：按下就是真的送出訊息 -->
      <div v-if="showStarters" class="answer-choices" aria-label="常見需求">
        <button
          v-for="starter in starters"
          :key="starter"
          class="choice-button"
          type="button"
          data-testid="starter-chip"
          @click="sendText(starter)"
        >{{ starter }}</button>
      </div>

      <form class="assistant-form" @submit.prevent="sendText(prompt)">
        <label class="visually-hidden" for="agent-input">告訴 AI 管家你的需求</label>
        <textarea
          id="agent-input"
          ref="input"
          v-model="prompt"
          rows="1"
          data-autogrow="true"
          placeholder="用一句話描述需求，按 Enter 送出"
          @input="resizeInput"
          @keydown="onKeydown"
        />
        <button class="button primary" type="submit" :disabled="store.busy || !prompt.trim()">送出</button>
      </form>
    </section>
  </div>
</template>

<style scoped>
/* 互動區收合:原生 details(鍵盤可用),內容限高內捲,永不擋住訊息流 */
.agent-actions {
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface-2, var(--bg));
  margin-bottom: 0.5rem;
}
.agent-actions > summary {
  cursor: pointer;
  min-height: var(--tap);
  display: flex;
  align-items: center;
  padding: 0.35rem 0.9rem;
  font-weight: 800;
}
.agent-actions-body {
  max-height: 38vh;
  overflow-y: auto;
  padding: 0.35rem 0.9rem 0.9rem;
  display: grid;
  gap: 0.6rem;
}

/* 卡片沿用品牌語彙：深墨粗框＋硬偏移陰影；按鈕至少 44px、focus 用全域 3px 外框。 */
.agent-card {
  padding: 0.9rem 1rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface);
  box-shadow: 3px 3px 0 var(--ink);
}

.agent-card .button {
  min-height: var(--tap, 44px);
}

.agent-result {
  justify-self: start;
  max-width: min(90%, 44rem);
  background: var(--success-soft);
}
.agent-result-id {
  display: block;
  margin: 0.2rem 0 0.4rem;
  font-family: var(--font-mono);
  font-size: 1.05rem;
}
.agent-result p {
  margin: 0 0 0.6rem;
}

.agent-stages {
  display: flex;
  align-items: center;
  justify-self: start;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0.55rem 0.85rem;
  border: 2px solid var(--ink);
  border-radius: 16px;
  background: var(--surface-2);
  color: var(--ink);
  font-size: var(--text-sm);
  font-weight: 700;
}
.agent-stages.busy {
  background: var(--blue);
  font-weight: 800;
}
.agent-stages ol {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem 0.6rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.agent-stages li + li::before {
  content: '→';
  margin-right: 0.6rem;
  opacity: 0.6;
}

.agent-proposals {
  display: grid;
  gap: var(--space-3);
}

.agent-proposal-head {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 1rem;
}
.agent-proposal-head p {
  margin: 0.15rem 0 0;
}
.agent-proposal-price {
  text-align: right;
}
.agent-proposal-price small {
  display: block;
  margin-top: 0.15rem;
  font-weight: 600;
}

.agent-reasons {
  margin: 0.6rem 0;
  padding-left: 1.15rem;
}
.agent-reasons li {
  margin: 0.15rem 0;
  font-size: var(--text-sm);
}

.agent-fields {
  display: grid;
  gap: var(--space-2);
  padding: 0.8rem 1rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface-2);
}
.agent-fields p {
  margin: 0;
}

.agent-grant {
  background: var(--surface-2);
}
.agent-grant-summary {
  margin: 0.3rem 0 0.6rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.agent-grant-facts {
  display: grid;
  gap: 0.3rem;
  margin: 0 0 0.5rem;
}
.agent-grant-facts div {
  display: flex;
  gap: 0.6rem;
}
.agent-grant-facts dt {
  min-width: 5em;
  color: var(--muted);
  font-size: var(--text-sm);
  font-weight: 700;
}
.agent-grant-facts dd {
  margin: 0;
  font-weight: 700;
}
.agent-grant .muted {
  margin: 0 0 0.2rem;
  font-size: var(--text-sm);
}

/* 側欄裡沒有 .assistant 祖先時的保底：訊息列仍要自行捲動、泡泡左右分邊。 */
.agent-conversation {
  min-height: 0;
}
.agent-conversation .message-list {
  flex: 1 1 0;
  min-height: 0;
  max-height: none;
  align-content: start;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: clamp(0.75rem, 2vw, 1.5rem);
}
.agent-conversation .message.from-user {
  justify-self: end;
}
.agent-conversation .message.from-assistant {
  justify-self: start;
}

@media (max-width: 640px) {
  .agent-proposal-head {
    flex-direction: column;
  }
  .agent-proposal-price {
    text-align: left;
  }
}
</style>
