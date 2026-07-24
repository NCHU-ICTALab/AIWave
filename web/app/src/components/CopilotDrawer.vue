<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import { createAiInquiryClient, type AiOperation, type AiTraceStep } from '@/api/aiInquiryClient'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; inquiryCreated: [operation: AiOperation] }>()
const client = createAiInquiryClient()
const drawer = ref<HTMLElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const prompt = ref('')
const sessionId = ref('')
const loading = ref(false)
const error = ref('')
const messages = ref<Array<{ role: 'assistant' | 'user'; text: string }>>([])
const trace = ref<AiTraceStep[]>([])
const progress = ref({ answered: 0, total: 0 })
const operation = ref<AiOperation | null>(null)
let previousFocus: HTMLElement | null = null

watch(() => props.open, async (open) => {
  if (open) {
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    await nextTick()
    closeButton.value?.focus()
  } else previousFocus?.focus()
})

function close() { emit('close') }

async function startInquiry() {
  loading.value = true
  error.value = ''
  try {
    const response = await client.start('repair')
    sessionId.value = response.session_id
    messages.value = [{ role: 'assistant', text: response.reply }]
    trace.value = response.trace
    progress.value = response.progress
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : 'AI 服務暫時無法使用'
  } finally {
    loading.value = false
  }
}

async function sendMessage() {
  const text = prompt.value.trim()
  if (!text || !sessionId.value || loading.value) return
  messages.value.push({ role: 'user', text })
  prompt.value = ''
  loading.value = true
  error.value = ''
  try {
    const response = await client.message(sessionId.value, text)
    messages.value.push({ role: 'assistant', text: response.reply })
    trace.value = response.trace
    progress.value = response.progress
    if (response.operation) {
      operation.value = response.operation
      emit('inquiryCreated', response.operation)
    }
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : 'AI 服務暫時無法使用'
  } finally {
    loading.value = false
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); close(); return }
  if (event.key !== 'Tab' || !drawer.value) return
  const focusable = [...drawer.value.querySelectorAll<HTMLElement>('button, input, textarea, select, [href], [tabindex]:not([tabindex="-1"])')]
  const first = focusable[0]
  const last = focusable.at(-1)
  if (!first || !last) return
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="drawer-backdrop" @click.self="close">
      <aside ref="drawer" class="drawer" role="dialog" aria-modal="true" aria-labelledby="copilot-title" @keydown="onKeydown">
        <div class="drawer-head">
          <div><p class="eyebrow">Agent + tools + rules</p><h2 id="copilot-title">AI 生活管家</h2></div>
          <button ref="closeButton" class="icon-button" type="button" aria-label="關閉生活管家" @click="close">×</button>
        </div>

        <section v-if="!sessionId" class="chat-block">
          <strong>這不是固定文案聊天框。</strong>
          <p>AI 會理解口語回答，題組引擎負責驗證；最後經你確認才由後端建立諮詢單。</p>
          <button class="button primary full" type="button" data-testid="start-ai-inquiry" :disabled="loading" @click="startInquiry">
            {{ loading ? '正在連接 AI…' : '開始 AI 修繕諮詢' }}
          </button>
        </section>

        <template v-else>
          <div class="agent-progress" aria-live="polite">
            <span>題組進度</span><strong>{{ progress.answered }} / {{ progress.total }}</strong>
          </div>
          <div class="message-list" aria-live="polite">
            <div v-for="(message, index) in messages" :key="index" class="message" :class="message.role">
              <span>{{ message.role === 'assistant' ? 'AI 管家' : '你' }}</span>
              <p>{{ message.text }}</p>
            </div>
          </div>
          <div v-if="trace.length" class="tool-trace" aria-label="本輪執行軌跡">
            <p class="eyebrow">本輪真實執行</p>
            <div v-for="step in trace" :key="`${step.tool}-${step.topic_id ?? ''}`" class="trace-step">
              <code>{{ step.tool }}</code><span>{{ step.status }}</span>
            </div>
          </div>
          <form v-if="!operation" class="copilot-form" @submit.prevent="sendMessage">
            <label for="copilot-input">回答目前問題</label>
            <textarea id="copilot-input" v-model="prompt" rows="3" :disabled="loading" placeholder="可用自然語言回答…" />
            <button class="button primary" type="submit" :disabled="loading || !prompt.trim()">{{ loading ? 'AI 解析中…' : '送出回答' }}</button>
          </form>
          <div v-else class="operation-success" role="status">
            <p class="eyebrow">後端寫入成功</p><strong>{{ operation.id }}</strong>
            <p>諮詢單已寫入 SQLite repository，並同步到訂單中心。</p>
            <RouterLink class="button primary inline" to="/app/orders" @click="close">查看訂單進度</RouterLink>
          </div>
        </template>

        <div v-if="error" class="error-state" role="alert"><strong>目前無法繼續</strong><p>{{ error }}</p><button class="button" type="button" @click="sessionId ? sendMessage() : startInquiry()">重試</button></div>
      </aside>
    </div>
  </Teleport>
</template>
