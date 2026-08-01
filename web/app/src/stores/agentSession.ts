// M8 Agent 對話 store:AI 頁與側欄共用同一段對話(spec 15 §4.1)。
// 對話本體持久化在後端;這個 store 只是前端的即時鏡像。
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  getLatestAgentSession,
  sendAgentMessage,
  sendAgentMessageStream,
  type AgentAction,
  type AgentSession,
} from '@/api/agentClient'

export const useAgentSessionStore = defineStore('agent-session', () => {
  const session = ref<AgentSession | null>(null)
  const stages = ref<string[]>([])
  const busy = ref(false)
  const error = ref('')
  const restored = ref(false)

  const awaiting = computed(() => session.value?.awaiting ?? null)
  const messages = computed(() => session.value?.messages ?? [])
  const subtasks = computed(() => session.value?.subtasks ?? [])

  /** 進入 AI 頁或開側欄時呼叫:取回同一段對話(重新整理不遺失)。 */
  async function restore(): Promise<void> {
    if (restored.value) return
    try {
      session.value = await getLatestAgentSession()
    } catch {
      // 未登入或後端不可用時保持空白;送訊息時會誠實回報
    } finally {
      restored.value = true
    }
  }

  async function send(input: { message?: string; action?: AgentAction }): Promise<void> {
    if (busy.value) return
    busy.value = true
    error.value = ''
    stages.value = []
    try {
      const result = await sendAgentMessageStream(
        { sessionId: session.value?.id ?? null, ...input },
        (stage) => stages.value.push(stage),
      ).catch(async () => {
        // 串流不可用時退回一般請求;內容相同,只少了漸進階段
        return sendAgentMessage({ sessionId: session.value?.id ?? null, ...input })
      })
      session.value = result.session
      if (!stages.value.length) stages.value = result.stages
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : '目前無法連到 AI 管家,請稍後再試。'
    } finally {
      busy.value = false
    }
  }

  function resetLocal(): void {
    session.value = null
    stages.value = []
    error.value = ''
    restored.value = false
    pendingMessage.value = ''
  }

  /** 首頁「交給 AI」等入口:先排隊訊息,導頁到 AI 工作區後由它送出。 */
  const pendingMessage = ref('')
  function queueMessage(text: string): void {
    pendingMessage.value = text.trim()
  }
  async function flushPending(): Promise<void> {
    const text = pendingMessage.value
    pendingMessage.value = ''
    if (text) await send({ message: text })
  }

  return {
    session, stages, busy, error, awaiting, messages, subtasks,
    pendingMessage, restore, send, resetLocal, queueMessage, flushPending,
  }
})
