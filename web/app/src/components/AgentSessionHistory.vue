<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useAgentSessionStore } from '@/stores/agentSession'

const store = useAgentSessionStore()
const showArchived = ref(false)
const renameOpen = ref(false)
const renameValue = ref('')

const activeSessions = computed(() => store.sessions.filter((item) => item.status !== 'archived'))
const archivedSessions = computed(() => store.sessions.filter((item) => item.status === 'archived'))

function beginRename() {
  renameValue.value = store.session?.title ?? '新對話'
  renameOpen.value = true
}

async function submitRename() {
  const title = renameValue.value.trim()
  if (!title) return
  await store.renameSession(title)
  renameOpen.value = false
}

async function archiveCurrent() {
  if (!store.session) return
  await store.archiveSession()
}

async function toggleArchived() {
  showArchived.value = !showArchived.value
  await store.loadSessions(showArchived.value)
}

onMounted(() => void store.restore())
</script>

<template>
  <section class="agent-session-history" aria-label="對話 Session 管理" data-testid="agent-session-history">
    <div class="session-history-head">
      <div>
        <p class="eyebrow">對話工作區</p>
        <h2>{{ store.session?.title ?? '新對話' }}</h2>
      </div>
      <button
        class="button primary session-new"
        type="button"
        data-testid="new-agent-session"
        :disabled="store.busy"
        @click="store.newSession()"
      >＋ 新對話</button>
    </div>

    <form v-if="renameOpen" class="session-rename" @submit.prevent="submitRename">
      <label for="agent-session-title">對話名稱</label>
      <div class="session-rename-row">
        <input id="agent-session-title" v-model="renameValue" maxlength="120" />
        <button class="button primary" type="submit" :disabled="!renameValue.trim()">儲存</button>
        <button class="button" type="button" @click="renameOpen = false">取消</button>
      </div>
    </form>

    <div v-else class="session-history-actions">
      <button class="button" type="button" data-testid="rename-agent-session" @click="beginRename">重新命名</button>
      <button
        v-if="store.session && store.session.status !== 'archived'"
        class="button"
        type="button"
        data-testid="archive-agent-session"
        @click="archiveCurrent"
      >封存對話</button>
      <button class="text-link" type="button" @click="toggleArchived">
        {{ showArchived ? '隱藏已封存' : '顯示已封存' }}
      </button>
    </div>

    <!--
      清單本身就是捲動區(CSS 的 .session-history-list)。它不另外加 tabindex="0":
      裡面每一筆都是原生 <button>,鍵盤已經走得進來,而瀏覽器 Tab 到焦點時會自動
      把該筆捲進可視範圍(WCAG 2.4.11 焦點不被遮蔽)。空清單時沒有可捲內容,
      所以也不需要可聚焦的捲動容器。
      role="listitem" 放在外層 <div> 而不是 <button> 上:寫在按鈕上會把 button
      角色整個覆蓋掉,螢幕閱讀器會唸成純清單項、讀不出「可以按」(WCAG 4.1.2)。
    -->
    <div class="session-history-list" role="list" aria-label="對話歷史">
      <div v-for="item in activeSessions" :key="item.id" class="session-history-row" role="listitem">
        <button
          class="session-history-item"
          :class="{ selected: item.id === store.session?.id }"
          type="button"
          :aria-current="item.id === store.session?.id ? 'true' : undefined"
          @click="store.selectSession(item.id)"
        >
          <span class="session-history-title">{{ item.title || '新對話' }}</span>
          <span v-if="item.pendingGrantId" class="session-history-status">待授權</span>
        </button>
      </div>
    </div>
    <p v-if="!activeSessions.length" class="muted session-history-empty">還沒有其他對話。</p>

    <template v-if="showArchived">
      <div class="session-history-list archived" role="list" aria-label="已封存對話">
        <div v-for="item in archivedSessions" :key="item.id" class="session-history-row" role="listitem">
          <button
            class="session-history-item"
            type="button"
            @click="store.restoreSession(item.id, item.version ?? 1)"
          >
            <span class="session-history-title">{{ item.title || '新對話' }}</span>
            <span class="session-history-status">已封存・點擊恢復</span>
          </button>
        </div>
      </div>
      <p v-if="!archivedSessions.length" class="muted session-history-empty">沒有已封存對話。</p>
    </template>

    <p v-if="store.session?.pendingGrantId" class="session-pending" role="status">
      這段對話有待確認授權；切換 Session 不會自動核准或延長。
    </p>
    <p v-if="store.error" class="session-error" role="status" aria-live="polite">{{ store.error }}</p>
  </section>
</template>

<style scoped>
/*
 * 版面契約:面板是「可壓縮的直向 flex」——標題列、動作列、提示各佔自己的高度且
 * 永不壓縮,唯一會伸縮並自行捲動的是對話清單。
 *
 * `min-height: 0` 是關鍵:flex/grid item 的預設 `min-height: auto` 會讓清單被內容
 * 撐開,面板就跟著長成使用者回報的「超長一條」。面板本身刻意 **不** 設
 * `overflow: hidden`——那只會把「＋ 新對話」「封存對話」等按鈕裁掉,變成看得到
 * 卻按不到(甚至 Tab 得到卻看不見)的內容,那是 a11y 缺陷而不是修好。
 */
.agent-session-history {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  min-height: 0;
  padding: 0.75rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface-2, var(--bg));
}
/* 清單以外的區塊固定高度,不被擠扁 */
.agent-session-history > :not(.session-history-list) {
  flex: 0 0 auto;
}
.session-history-head,
.session-history-actions,
.session-rename-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.session-history-head h2 {
  margin: 0.1rem 0 0;
  font-size: 1rem;
}
.session-history-head > div:first-child {
  flex: 1 1 12rem;
  min-width: 0;
}
.session-new {
  min-height: var(--tap, 44px);
}
.session-history-actions .button,
.session-history-actions .text-link {
  min-height: 40px;
}
.session-rename {
  display: grid;
  gap: 0.35rem;
}
.session-rename label {
  font-weight: 800;
}
.session-rename input {
  flex: 1 1 12rem;
  min-height: 44px;
  min-width: 0;
  padding: 0.5rem 0.65rem;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface);
}
/*
 * 唯一的捲動區。父層有確定高度時(AI 全頁的左欄)靠 `flex: 1 1 auto` 吃掉剩餘高度;
 * 父層高度不確定時(側欄 AgentDrawer)退回自己的 `max-height` 限高內捲。
 * 兩種情況都不會無限長高。
 * 註:全域 `prefers-reduced-motion` 已強制 `scroll-behavior: auto`(main.css),
 * 這裡不引入平滑捲動。
 */
.session-history-list {
  display: grid;
  align-content: start;
  gap: 0.35rem;
  flex: 1 1 auto;
  min-height: 3rem;
  max-height: 9rem;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
/* 沒有任何對話時不要留一塊空捲動區(空狀態文字在清單外面) */
.session-history-list:empty {
  min-height: 0;
}
/* 已封存是次要清單:不跟主清單搶剩餘高度,自己限高內捲 */
.session-history-list.archived {
  flex: 0 1 auto;
  max-height: 8rem;
  border-top: 1px dashed var(--ink);
  padding-top: 0.5rem;
}
.session-history-row {
  min-width: 0;
}
.session-history-empty {
  margin: 0;
}
.session-history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 44px;
  width: 100%;
  padding: 0.45rem 0.65rem;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface);
  color: var(--ink);
  text-align: left;
}
.session-history-item.selected {
  background: var(--yellow, #fde68a);
  box-shadow: 2px 2px 0 var(--ink);
}
.session-history-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 800;
}
.session-history-status {
  flex: 0 0 auto;
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 800;
}
.session-pending,
.session-error {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 700;
}
.session-error {
  color: var(--danger, #b91c1c);
}
</style>
