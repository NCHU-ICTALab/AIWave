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

    <div class="session-history-list" role="list" aria-label="對話歷史">
      <button
        v-for="item in activeSessions"
        :key="item.id"
        class="session-history-item"
        :class="{ selected: item.id === store.session?.id }"
        type="button"
        role="listitem"
        :aria-current="item.id === store.session?.id ? 'true' : undefined"
        @click="store.selectSession(item.id)"
      >
        <span class="session-history-title">{{ item.title || '新對話' }}</span>
        <span v-if="item.pendingGrantId" class="session-history-status">待授權</span>
      </button>
      <p v-if="!activeSessions.length" class="muted">還沒有其他對話。</p>
    </div>

    <div v-if="showArchived" class="session-history-list archived" role="list" aria-label="已封存對話">
      <button
        v-for="item in archivedSessions"
        :key="item.id"
        class="session-history-item"
        type="button"
        role="listitem"
        @click="store.restoreSession(item.id, item.version ?? 1)"
      >
        <span class="session-history-title">{{ item.title || '新對話' }}</span>
        <span class="session-history-status">已封存・點擊恢復</span>
      </button>
      <p v-if="!archivedSessions.length" class="muted">沒有已封存對話。</p>
    </div>

    <p v-if="store.session?.pendingGrantId" class="session-pending" role="status">
      這段對話有待確認授權；切換 Session 不會自動核准或延長。
    </p>
    <p v-if="store.error" class="session-error" role="status" aria-live="polite">{{ store.error }}</p>
  </section>
</template>

<style scoped>
.agent-session-history {
  display: grid;
  gap: 0.6rem;
  padding: 0.75rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface-2, var(--bg));
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
.session-history-list {
  display: grid;
  gap: 0.35rem;
  max-height: 9rem;
  overflow-y: auto;
}
.session-history-list.archived {
  border-top: 1px dashed var(--ink);
  padding-top: 0.5rem;
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
