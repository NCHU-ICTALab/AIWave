<script setup lang="ts">
/**
 * M8「桌面主工作區+Agent 側欄」(spec 15 §4.1)。
 *
 * 側欄與 /user/assistant 全頁掛同一個 AgentConversation、讀寫同一個
 * agent-session store,所以兩邊天然是同一段對話與草稿。
 *
 * 刻意不用 native dialog:spec 的版型是「主要工作區+側欄」並存,
 * 側欄不阻擋主內容,因此用 aside + aria-label,不做焦點陷阱;
 * 只保證 Esc 可關、開啟時焦點移入、關閉後焦點回到開關鈕。
 */
import { nextTick, ref } from 'vue'

import AgentConversation from '@/components/AgentConversation.vue'
import AppIcon from '@/components/AppIcon.vue'
import { useAgentSessionStore } from '@/stores/agentSession'

const store = useAgentSessionStore()
const open = ref(false)
const drawer = ref<HTMLElement | null>(null)
const toggle = ref<HTMLButtonElement | null>(null)

async function openDrawer() {
  open.value = true
  // 對話持久化在後端:開側欄時取回同一段對話(與 AI 頁一致)
  void store.restore()
  await nextTick()
  drawer.value?.focus()
}

async function closeDrawer() {
  open.value = false
  await nextTick()
  toggle.value?.focus()
}

function onToggle() {
  if (open.value) void closeDrawer()
  else void openDrawer()
}
</script>

<template>
  <button
    ref="toggle"
    class="agent-drawer-toggle"
    type="button"
    data-testid="agent-drawer-toggle"
    :aria-expanded="open"
    @click="onToggle"
  >
    <AppIcon name="ai" />
    <span>AI 管家</span>
  </button>

  <aside
    v-if="open"
    ref="drawer"
    class="agent-drawer"
    tabindex="-1"
    aria-label="AI 管家側欄"
    data-testid="agent-drawer"
    @keydown.esc="closeDrawer"
  >
    <header class="agent-drawer-head">
      <h2>AI 管家</h2>
      <RouterLink class="text-link" to="/user/assistant" data-testid="agent-drawer-full-page">
        開啟完整 AI 頁
      </RouterLink>
      <button
        class="agent-drawer-close"
        type="button"
        data-testid="agent-drawer-close"
        aria-label="關閉 AI 管家側欄"
        @click="closeDrawer"
      >關閉</button>
    </header>
    <div class="agent-drawer-body">
      <AgentConversation />
    </div>
  </aside>
</template>

<style scoped>
/* z-index:高於手機底部導覽(40)與吸頂導覽(20),低於 modal-layer(60)。 */
.agent-drawer-toggle {
  position: fixed;
  right: 1rem;
  bottom: 1rem;
  z-index: 45;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  min-width: var(--tap, 44px);
  min-height: var(--tap, 44px);
  padding: 0 1rem;
  border: var(--border-chunky, 3px) solid var(--ink, #2d3748);
  border-radius: 999px;
  background: var(--cta, #22c55e);
  color: var(--ink, #2d3748);
  font-weight: 800;
  box-shadow: var(--shadow-soft, 4px 4px 0 #2d3748);
}
.agent-drawer-toggle:hover {
  background: var(--cta-dark, #1fba59);
}
.agent-drawer-toggle .nav-icon {
  width: 20px;
  height: 20px;
}

.agent-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  display: flex;
  flex-direction: column;
  width: min(420px, 100%);
  border-left: var(--border-chunky, 3px) solid var(--ink, #2d3748);
  background: var(--surface, #fff);
}
.agent-drawer-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 1rem;
  border-bottom: var(--border-chunky, 3px) solid var(--ink, #2d3748);
  background: var(--peach, #fdbcb4);
}
.agent-drawer-head h2 {
  flex: 1;
  margin: 0;
  font-size: 1.1rem;
}
.agent-drawer-close {
  min-height: var(--tap, 44px);
  padding: 0 0.9rem;
  border: 2px solid var(--ink, #2d3748);
  border-radius: 14px;
  background: var(--surface, #fff);
  font-weight: 800;
}
.agent-drawer-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 1rem;
}

/* 手機:側欄全螢幕,但底邊停在底部導覽之上,五項主導覽維持可用;
   開關鈕也墊高避開固定導覽(main.css 為它保留 76px + 安全區)。 */
@media (max-width: 650px) {
  .agent-drawer {
    left: 0;
    width: 100%;
    bottom: calc(76px + env(safe-area-inset-bottom));
    border-left: 0;
  }
  .agent-drawer-toggle {
    bottom: calc(88px + env(safe-area-inset-bottom));
  }
}
</style>
