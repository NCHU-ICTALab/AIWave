<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

import AgentConversation from '@/components/AgentConversation.vue'
import AgentSessionHistory from '@/components/AgentSessionHistory.vue'
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
    <header class="assistant-head compact">
      <div>
        <p class="eyebrow">EVERYDAY CONVERSATION</p>
        <h1 title="用日常說法描述需求，我會先複述理解到的事，再一起安排。">AI 管家</h1>
      </div>
      <p class="assistant-head-copy">不用先知道服務分類，直接說你現在遇到的事；任何送出前都會先讓你確認。</p>
    </header>
    <div class="assistant-workspace-grid">
      <aside class="assistant-session-column" data-testid="assistant-session-column" aria-label="AI 對話列表">
        <AgentSessionHistory />
      </aside>
      <section class="assistant-chat-column" data-testid="assistant-chat-column" aria-label="AI 對話內容">
        <AgentConversation />
      </section>
    </div>
  </div>
</template>

<style scoped>
.assistant-fill {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  /* topbar 約 4rem + 頁面上下留白;讓對話工作區吃滿剩餘視窗高度 */
  min-height: calc(100dvh - 8.5rem);
  height: calc(100dvh - 8.5rem);
  width: min(100%, 1160px);
  margin-inline: auto;
  gap: .65rem;
}
.assistant-head.compact {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0;
}
.assistant-head > div,
.assistant-head-copy {
  min-width: 0;
}
.assistant-head-copy {
  max-width: 38rem;
  margin: 0;
  color: var(--muted);
  font-size: .88rem;
  text-align: right;
}
.assistant-head.compact h1 {
  margin: .1rem 0 0;
  font-size: clamp(1.15rem, 2.5vw, 1.55rem);
}
.assistant-workspace-grid {
  display: grid;
  grid-template-columns: minmax(15rem, 18rem) minmax(0, 1fr);
  min-height: 0;
  gap: .8rem;
}
.assistant-session-column,
.assistant-chat-column {
  min-width: 0;
  min-height: 0;
}
.assistant-session-column :deep(.agent-session-history) {
  height: 100%;
  min-height: 0;
  grid-template-rows: auto auto minmax(0, 1fr) auto auto;
  overflow: auto;
  align-content: start;
}
.assistant-session-column :deep(.session-history-list) {
  max-height: none;
}
.assistant-chat-column :deep(.agent-conversation) {
  height: 100%;
  min-height: 0;
}

@media (max-width: 760px) {
  .assistant-fill {
    height: auto;
    min-height: calc(100dvh - 8.5rem);
  }
  .assistant-head.compact {
    align-items: flex-start;
    flex-direction: column;
    gap: .25rem;
  }
  .assistant-head-copy {
    max-width: none;
    text-align: left;
  }
  .assistant-workspace-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(30rem, 1fr);
  }
  .assistant-session-column :deep(.agent-session-history) {
    height: auto;
    max-height: 14rem;
  }
  .assistant-session-column :deep(.session-history-list) {
    max-height: 6rem;
  }
  .assistant-chat-column :deep(.agent-conversation) {
    height: min(70dvh, 42rem);
    min-height: 0;
  }
}
</style>
