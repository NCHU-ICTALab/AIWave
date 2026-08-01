<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

import AgentConversation from '@/components/AgentConversation.vue'
import { useAgentSessionStore } from '@/stores/agentSession'

/**
 * M8「換腦不換臉」：AI 頁只剩一個殼（h1＋lead），內容全部交給 AgentConversation。
 *
 * 舊的 planner／life-task／題組填答模式已退場——唯一後端入口是
 * `/api/v1/platform/agent/*`（agentClient＋agent-session store），
 * 對話與草稿持久化在後端，側欄與本頁讀寫同一份。
 */
const route = useRoute()
const router = useRouter()
const agent = useAgentSessionStore()

// 舊入口（首頁 `?need=一句話`）仍會帶需求進來：轉成排隊訊息，
// 由 AgentConversation 掛載後經 flushPending 送出；同時把網址清乾淨，
// 避免重新整理時重送同一句話。
const need = route.query.need
if (typeof need === 'string' && need.trim()) {
  agent.queueMessage(need)
  void router.replace({ query: {} })
}
</script>

<template>
  <div class="assistant assistant-fill" data-testid="assistant-workspace">
    <!-- 2026-07-31:標題壓成單行,聊天視窗撐滿;描述移入 title 提示不佔高度 -->
    <header class="assistant-head compact">
      <h1 title="用一句話描述需求，我會拆解成可執行的安排；任何交易都會先問過你才執行。">AI 管家</h1>
    </header>
    <AgentConversation />
  </div>
</template>

<style scoped>
.assistant-fill {
  display: flex;
  flex-direction: column;
  /* topbar 約 4rem + 頁面上下留白;讓對話工作區吃滿剩餘視窗高度 */
  min-height: calc(100dvh - 8.5rem);
}
.assistant-head.compact {
  margin-bottom: 0.4rem;
}
.assistant-head.compact h1 {
  font-size: 1.05rem;
  margin: 0;
}
.assistant-fill :deep(.agent-conversation),
.assistant-fill > :last-child {
  flex: 1;
  min-height: 0;
}
</style>
