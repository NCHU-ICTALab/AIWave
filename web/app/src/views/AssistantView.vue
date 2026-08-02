<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

import AgentConversation from '@/components/AgentConversation.vue'
import AgentSessionHistory from '@/components/AgentSessionHistory.vue'
import { AI_CAPABILITIES } from '@/data/aiCapabilities'
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
    <!--
      能力總覽:預設收合,展開時內容自己限高內捲,不把下方對話擠沒。
      標題層級:h1(AI 管家) → h2(這一區的 summary) → h3(每張能力卡),
      不跳級也不讓五張卡變成與頁面同層的 h2。
    -->
    <details class="assistant-capability-wiki" data-testid="assistant-capability-wiki">
      <summary><h2>我目前能幫你處理什麼？</h2></summary>
      <div class="assistant-capability-grid">
        <article v-for="capability in AI_CAPABILITIES" :key="capability.id" class="assistant-capability-card">
          <div>
            <h3>{{ capability.title }}</h3>
            <p>{{ capability.summary }}</p>
            <small>{{ capability.examples }}</small>
          </div>
          <RouterLink class="text-link" :to="capability.to">查看相關頁面</RouterLink>
        </article>
      </div>
      <p class="assistant-capability-note">AI 會先理解、整理與推薦；預約、下單或建立團購前一定會停下來讓你確認。</p>
    </details>
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
  grid-template-rows: auto auto minmax(0, 1fr);
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
/*
 * 左右兩欄用同一套規則:欄位吃滿列高 → 面板 flex 撐滿 → 真正捲動的只有面板裡的
 * 那一塊(左欄是 .session-history-list、右欄是 .message-list),中間每一層都要
 * min-height: 0,否則內容會把容器撐開。
 *
 * 左欄再留一層 overflow-y: auto 當保險:視窗極矮時寧可整欄捲動,也不要用
 * overflow: hidden 把「＋ 新對話」「封存對話」裁掉——被裁掉的按鈕仍可被 Tab 聚焦
 * 卻看不見,那是 WCAG 2.4.11(焦點不被遮蔽)的失敗,不是版面修好。
 */
.assistant-session-column {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.assistant-session-column :deep(.agent-session-history) {
  flex: 1 1 auto;
  min-height: 0;
}
/* 桌機:列高是確定值,清單直接吃掉剩餘高度,不需要魔術數字上限 */
.assistant-session-column :deep(.session-history-list) {
  max-height: none;
}
.assistant-session-column :deep(.session-history-list.archived) {
  max-height: 10rem;
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
  /* 單欄時列高由內容決定,所以清單必須改回自己限高內捲——
     這裡若沿用桌機的 max-height: none 就會又長成一條。 */
  .assistant-session-column {
    overflow-y: visible;
  }
  .assistant-session-column :deep(.session-history-list) {
    max-height: 11rem;
  }
  .assistant-session-column :deep(.session-history-list.archived) {
    max-height: 8rem;
  }
  .assistant-chat-column :deep(.agent-conversation) {
    height: min(70dvh, 42rem);
    min-height: 0;
  }
}
.assistant-capability-wiki {
  display: grid;
  gap: .7rem;
  padding: .75rem 1rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--yellow, #fde68a);
}
/* summary 維持預設的 list-item 顯示,否則瀏覽器會把展開三角形拿掉 */
.assistant-capability-wiki summary { cursor: pointer; padding: .45rem 0; font-weight: 900; }
/* summary 裡的 h2 只是為了正確的文件大綱,視覺上仍是同一行摘要文字 */
.assistant-capability-wiki summary h2 { display: inline; margin: 0; font-size: .95rem; font-weight: 900; }
/* auto-fit 讓卡片自己決定幾欄:1160px 桌機五欄、平板兩三欄、320px 手機一欄,
   不需要再靠斷點硬切 */
.assistant-capability-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: .55rem;
  /* 展開時最多吃掉這麼多高度,其餘自己捲;卡片裡的連結本身可聚焦,
     所以這個捲動區不需要額外 tabindex */
  max-height: min(34vh, 20rem);
  overflow-y: auto;
  overscroll-behavior: contain;
}
.assistant-capability-card { display: grid; gap: .35rem; padding: .65rem; border: 1px solid var(--ink); border-radius: 12px; background: var(--surface); }
.assistant-capability-card h3, .assistant-capability-card p { margin: 0; }
.assistant-capability-card h3 { font-size: .9rem; }
.assistant-capability-card p, .assistant-capability-card small { color: var(--muted); font-size: .72rem; line-height: 1.45; }
.assistant-capability-card .text-link { align-self: end; font-size: .72rem; }
.assistant-capability-note { margin: 0; color: var(--accent-ink); font-size: .76rem; font-weight: 800; }
</style>
