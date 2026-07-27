<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  AiInquiryApiError,
  createAiInquiryClient,
  type AiOperation,
  type AiQuestion,
  type AiTraceStep,
} from '@/api/aiInquiryClient'
import { createAssistantClient, type Plan, type PlanStep } from '@/api/assistantClient'
import PlanStepCard from '@/components/PlanStepCard.vue'
import { useDemoStore } from '@/stores/demo'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const store = useDemoStore()
const session = useSessionStore()
const client = createAiInquiryClient()
const assistant = createAssistantClient()

const messages = ref<Array<{ role: 'assistant' | 'user'; text: string }>>([])
const question = ref<AiQuestion | null>(null)
const trace = ref<AiTraceStep[]>([])
const progress = ref({ answered: 0, total: 0 })
const operation = ref<AiOperation | null>(null)
const awaitingConfirmation = ref(false)
const serviceName = ref('')
const sessionId = ref('')
const prompt = ref('')
const loading = ref(false)
const error = ref('')
const messageList = ref<HTMLElement | null>(null)
const input = ref<HTMLTextAreaElement | null>(null)

const serviceId = computed(() => {
  const slug = route.query.service
  return typeof slug === 'string' && slug ? slug : 'service-repair'
})

/**
 * 兩種模式：
 * - **規劃模式**（`?need=一句話`）：先讓規劃器拆解需求，可能一句話做好幾件事。
 * - **填答模式**（`?service=`）：已經確定要辦哪項服務，走既有的題組引導。
 *
 * 規劃結果若含「準備諮詢單」，按下「開始填寫」就會帶著 service 切到填答模式——
 * 兩段是同一條路上的前後半，不是兩個入口。
 */
const need = computed(() => {
  const raw = route.query.need
  return typeof raw === 'string' ? raw.trim() : ''
})
const planning = computed(() => Boolean(need.value) && typeof route.query.service !== 'string')

const plan = ref<Plan | null>(null)
const planError = ref('')
const planBusy = ref(false)

async function buildPlan() {
  plan.value = null
  planError.value = ''
  loading.value = true
  const outcome = await assistant.plan(need.value, {
    accountId: session.accountId,
    role: 'user',
    displayName: session.displayName,
  })
  loading.value = false
  if (outcome.status === 'error') {
    planError.value = outcome.message
    return
  }
  plan.value = outcome.plan
}

/** 確認某一步之後再送回後端執行；後端會重新驗證，前端送什麼都不算數。 */
async function approve(index: number) {
  if (!plan.value || planBusy.value) return
  planBusy.value = true
  const outcome = await assistant.execute(need.value, plan.value.steps, [index], {
    accountId: session.accountId,
    role: 'user',
    displayName: session.displayName,
  })
  planBusy.value = false
  if (outcome.status === 'error') {
    planError.value = outcome.message
    return
  }
  plan.value = outcome.plan
}

function openForm(id: string) {
  void router.push({ name: 'assistant', query: { service: id, need: need.value } })
}

/** 選了廠商就進入該服務的填答流程；廠商偏好隨需求一起帶過去。 */
function chooseVendor(vendorId: string, stepArguments: Record<string, unknown>) {
  const id = String(stepArguments.service_id ?? '')
  if (id) void router.push({ name: 'assistant', query: { service: id, need: need.value, vendor: vendorId } })
}

function stepArgumentsOf(step: PlanStep) {
  return step.arguments
}

/** 有選項時直接給按鈕；只有真的需要自由文字才要求打字。 */
const choices = computed(() => question.value?.options ?? [])
const needsTyping = computed(() =>
  !operation.value && !awaitingConfirmation.value && choices.value.length === 0,
)
const inputPlaceholder = computed(() =>
  awaitingConfirmation.value ? '想改哪一項就直接說，例如：時間改成下午' : (question.value?.hint || '用你自己的話回答，按 Enter 送出'),
)

/** 只把我們自己的訊息給使用者看；底層例外（如 'offline'）不該直接曝光。 */
function describeFailure(reason: unknown) {
  if (reason instanceof AiInquiryApiError) return reason.message
  return '目前無法連線到服務，請確認後端已啟動後再試一次。'
}

/**
 * 只捲動訊息列本身。
 *
 * 原本用 `scrollIntoView` 捲一個哨兵元素，但它會連整頁一起捲，把頁面標題推到
 * 吸頂導覽底下——訊息列本來就是獨立捲動區，新訊息不該讓整個頁面跳動。
 */
async function scrollToEnd() {
  await nextTick()
  const list = messageList.value
  if (list) list.scrollTop = list.scrollHeight
}

function applyResponse(response: {
  reply: string
  question?: AiQuestion | null
  progress: { answered: number; total: number }
  trace: AiTraceStep[]
  awaiting_confirmation?: boolean
  operation?: AiOperation
}) {
  messages.value.push({ role: 'assistant', text: response.reply })
  question.value = response.question ?? null
  progress.value = response.progress
  trace.value = response.trace
  awaitingConfirmation.value = Boolean(response.awaiting_confirmation)
  if (response.operation) {
    operation.value = response.operation
    store.recordAiInquiry(response.operation.id)
  }
  void scrollToEnd()
}

async function begin() {
  loading.value = true
  error.value = ''
  try {
    const response = await client.start(serviceId.value)
    sessionId.value = response.session_id
    serviceName.value = response.service_name ?? ''
    messages.value = []
    applyResponse(response)
  } catch (reason) {
    error.value = describeFailure(reason)
  } finally {
    loading.value = false
  }
}

async function send(text: string) {
  const content = text.trim()
  if (!content || !sessionId.value || loading.value) return
  messages.value.push({ role: 'user', text: content })
  prompt.value = ''
  loading.value = true
  error.value = ''
  void scrollToEnd()
  try {
    applyResponse(await client.message(sessionId.value, content))
  } catch (reason) {
    error.value = describeFailure(reason)
  } finally {
    loading.value = false
    if (needsTyping.value) await nextTick(() => input.value?.focus())
  }
}

/** Enter 送出，Shift+Enter 換行。 */
function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  void send(prompt.value)
}

/** 規劃模式不去開題組 session——那是使用者按下「開始填寫」之後的事。 */
function enter() {
  if (planning.value) return buildPlan()
  return begin()
}

onMounted(enter)
watch(() => route.fullPath, enter)
</script>

<template>
  <div class="assistant">
    <header class="assistant-head">
      <div>
        <p class="eyebrow">生活管家</p>
        <h1>{{ planning ? (plan?.understanding || '正在理解你的需求…') : (serviceName || '正在準備…') }}</h1>
        <p v-if="planning && need" class="assistant-echo muted">你說：「{{ need }}」</p>
      </div>
      <div v-if="!planning && progress.total" class="assistant-progress" aria-live="polite">
        <span class="visually-hidden">已完成</span>
        <strong>{{ progress.answered }} / {{ progress.total }}</strong>
        <div class="progress-bar" aria-hidden="true">
          <span :style="{ width: `${(progress.answered / progress.total) * 100}%` }" />
        </div>
      </div>
    </header>

    <!-- 規劃模式：步驟卡片本身就是內容容器，不再外包一層 panel（會變成雙層邊框） -->
    <div v-if="planning" class="assistant-plan">
      <p v-if="loading" class="panel muted" role="status" data-testid="plan-loading">正在理解你的需求…</p>

      <div v-else-if="planError" class="error-state" role="alert">
        <strong>目前無法繼續</strong>
        <p>{{ planError }}</p>
        <button class="button" type="button" @click="buildPlan">重試</button>
      </div>

      <template v-else-if="plan">
        <ol v-if="plan.steps.length" class="plan-steps" data-testid="plan-steps">
          <PlanStepCard
            v-for="(step, index) in plan.steps"
            :key="`${step.tool}-${index}`"
            :step="step"
            :busy="planBusy"
            @approve="approve(index)"
            @open-form="openForm"
            @choose="chooseVendor($event, stepArgumentsOf(step))"
          />
        </ol>

        <!-- 沒有可執行的步驟：說清楚為什麼，並給下一步 -->
        <section v-else class="panel empty-state" data-testid="plan-rejected">
          <h2>這件事我還幫不上忙</h2>
          <p class="muted">{{ plan.rejectedReason || '目前沒有對應的能力可以處理這個需求。' }}</p>
          <div class="button-row">
            <RouterLink class="button primary inline" to="/user/services">瀏覽所有服務</RouterLink>
            <RouterLink class="button inline" to="/user">回首頁</RouterLink>
          </div>
        </section>
      </template>
    </div>

    <div v-else class="assistant-body">
      <section ref="messageList" class="message-list" aria-live="polite" aria-label="對話內容">
        <div v-for="(message, index) in messages" :key="index" class="message" :class="message.role">
          <span>{{ message.role === 'assistant' ? '生活管家' : '你' }}</span>
          <p>{{ message.text }}</p>
        </div>
        <p v-if="loading" class="message assistant thinking" role="status">
          <span>生活管家</span><em>思考中…</em>
        </p>
      </section>

      <!-- 完成 -->
      <section v-if="operation" class="assistant-done" role="status">
        <p class="eyebrow">已送出</p>
        <strong>{{ operation.id }}</strong>
        <p>合作夥伴收到後會回覆報價，進度可在訂單頁追蹤。</p>
        <div class="button-row">
          <RouterLink class="button primary inline" to="/user/orders">查看進度</RouterLink>
          <RouterLink class="button inline" to="/user">回首頁</RouterLink>
        </div>
      </section>

      <!-- 答題：能點就不要打字 -->
      <section v-else class="assistant-answer">
        <div v-if="error" class="error-state" role="alert">
          <strong>目前無法繼續</strong><p>{{ error }}</p>
          <button class="button" type="button" @click="sessionId ? send(prompt || '重試') : begin()">重試</button>
        </div>

        <div v-if="awaitingConfirmation" class="answer-choices">
          <button class="button primary" type="button" data-testid="confirm-send" :disabled="loading" @click="send('確認送出')">
            確認送出
          </button>
        </div>

        <div v-else-if="choices.length" class="answer-choices" data-testid="answer-choices">
          <button
            v-for="choice in choices"
            :key="choice.value"
            class="choice-button"
            type="button"
            :data-choice="choice.value"
            :disabled="loading"
            @click="send(choice.label)"
          >{{ choice.label }}</button>
          <button v-if="!question?.required" class="button" type="button" :disabled="loading" @click="send('沒有')">
            略過
          </button>
        </div>

        <form v-if="needsTyping || awaitingConfirmation" class="assistant-form" @submit.prevent="send(prompt)">
          <label class="visually-hidden" for="assistant-input">
            {{ awaitingConfirmation ? '說明想修改的內容' : '回答目前問題' }}
          </label>
          <textarea
            id="assistant-input"
            ref="input"
            v-model="prompt"
            rows="2"
            :disabled="loading"
            :placeholder="inputPlaceholder"
            @keydown="onKeydown"
          />
          <button class="button primary" type="submit" :disabled="loading || !prompt.trim()">送出</button>
        </form>
        <p v-else-if="choices.length" class="muted assistant-hint">
          直接點選上面的選項即可，也可以
          <button class="text-button" type="button" @click="question = null">自己輸入</button>。
        </p>
      </section>

      <details v-if="trace.length" class="assistant-trace">
        <summary>這一步是怎麼完成的</summary>
        <div v-for="step in trace" :key="`${step.tool}-${step.topic_id ?? ''}`" class="trace-step">
          <code>{{ step.tool }}</code>
          <span>{{ step.stage === 'ai' ? 'AI 判讀' : step.stage === 'rule' ? '規則驗證' : step.stage === 'write' ? '寫入' : '檢查' }}・{{ step.status }}</span>
        </div>
      </details>
    </div>
  </div>
</template>
