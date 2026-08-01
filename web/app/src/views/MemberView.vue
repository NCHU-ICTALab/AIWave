<script setup lang="ts">
// 版面比照核准原型 design-system/aiwave/pages/member.html:
// 個人資料 → 我的入口(entry list)→ Workspace 切換 → 重置 DemoWorkspace → 登出。
// 後端沒有個人資料編輯 API,故不做假編輯按鈕;登出行為與 App.vue signOut 等價。
import { computed, nextTick, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { resetDemo } from '@/api/platformClient'
import { useDemoStore } from '@/stores/demo'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const demo = useDemoStore()
const communityLink = computed(() => route.path.startsWith('/demo') ? '/demo/community' : '/user/community')
const showResetConfirm = ref(false)
const resetStatus = ref<'idle' | 'resetting' | 'done' | 'error'>('idle')
const resetMessage = ref('')
const confirmResetButton = ref<HTMLButtonElement | null>(null)

async function openReset() {
  showResetConfirm.value = true
  resetStatus.value = 'idle'
  resetMessage.value = ''
  await nextTick()
  confirmResetButton.value?.focus()
}

async function resetDemoData() {
  resetStatus.value = 'resetting'
  resetMessage.value = ''
  try {
    // 走共用 platform client(Bearer/錯誤正規化都在 http 層),不再自組 fetch
    const payload = (await resetDemo()) as { status?: 'ready' | 'partial' }
    demo.resetDemo()
    resetStatus.value = 'done'
    resetMessage.value = payload?.status === 'partial'
      ? '本地 Demo 資料已還原；fake upstream 未完成重設，請確認控制金鑰與服務狀態。'
      : '已還原成 Demo 初始資料。重新進入各頁面時會載入初始狀態。'
    showResetConfirm.value = false
  } catch (reason) {
    resetStatus.value = 'error'
    resetMessage.value = reason instanceof Error ? reason.message : 'Demo 資料未能還原，請確認後端與 fake server 狀態。'
  }
}

/** 與 App.vue topbar 的 signOut 等價:清 session、還原本地 demo store、回登入頁。 */
async function signOut() {
  session.signOut()
  demo.resetDemo()
  await router.push('/login')
}
</script>

<template>
  <section class="member-page member-center">
    <h1>會員中心</h1>
    <p class="page-lead">個人資料、訂單、群組與社區入口，以及 Demo 工作區管理。</p>

    <section class="panel" data-testid="member-identity" aria-labelledby="profile-title">
      <h2 id="profile-title">個人資料</h2>
      <div class="profile-body">
        <div class="member-avatar" aria-hidden="true">{{ session.displayName.slice(0, 1) }}</div>
        <table class="profile-table">
          <tbody>
            <tr>
              <th scope="row">姓名</th>
              <td>{{ session.displayName }}</td>
            </tr>
            <tr>
              <th scope="row">身分</th>
              <td>模擬 uniopen 身分 · {{ session.accountId ? '競賽展示會員' : '新會員' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="demo-note">目前為競賽用模擬登入，尚未提供資料編輯；正式串接時由身份服務與會員系統管理。</p>
    </section>

    <section class="panel" aria-labelledby="entries-title">
      <h2 id="entries-title">我的入口</h2>
      <ul class="entry-list">
        <li>
          <span class="badge badge-mint">訂單</span>
          <span class="grow">查看報價、服務進度、異常處理與完成紀錄</span>
          <RouterLink class="button" to="/user/orders">我的訂單 →</RouterLink>
        </li>
        <li>
          <span class="badge badge-blue">群組</span>
          <span class="grow">以不同群組範圍共享任務、提醒與團購</span>
          <RouterLink class="button" to="/user/community">我的群組 →</RouterLink>
        </li>
        <li>
          <span class="badge badge-peach">社區</span>
          <span class="grow">社區公告、問社區、團購與聯合服務進度</span>
          <RouterLink class="button" data-testid="member-community-link" :to="communityLink">我的社區 →</RouterLink>
        </li>
        <li>
          <span class="badge badge-lilac">行事曆</span>
          <span class="grow">訂單行程與自己的事件放在同一份時間軸</span>
          <RouterLink class="button" to="/user/calendar">行事曆 →</RouterLink>
        </li>
      </ul>
    </section>

    <section class="panel" aria-labelledby="workspace-title">
      <h2 id="workspace-title">Workspace 切換</h2>
      <p>目前身分：<span class="workspace-chip">{{ session.displayName }}・個人</span></p>
      <p>要切換到其他角色（社區管理、廠商、平台）需重新以該身分登入，不能在同一個登入狀態內直接切換。</p>
      <div class="button-row">
        <RouterLink class="button" to="/login">以其他身分重新登入</RouterLink>
      </div>
    </section>

    <section class="panel" aria-labelledby="demo-reset-title">
      <h2 id="demo-reset-title">重置我的 DemoWorkspace</h2>
      <p class="muted">清除本次操作產生的諮詢單、訂單、群組、偏好與社區進度，再補回競賽初始種子資料，方便重複展示同一段流程。</p>
      <div class="button-row">
        <button class="button danger" type="button" data-testid="open-demo-reset" :disabled="!session.accountId" @click="openReset">
          重設 Demo 資料
        </button>
      </div>
      <p v-if="resetMessage" :class="resetStatus === 'error' ? 'need-error' : 'feedback-inline'"
        :role="resetStatus === 'error' ? 'alert' : 'status'">{{ resetMessage }}</p>
    </section>

    <section class="panel" aria-labelledby="logout-title">
      <h2 id="logout-title">登出</h2>
      <p>登出後回到登入頁；重置後的展示資料保留在後端，重新登入即可繼續。</p>
      <div class="button-row">
        <button class="button" type="button" data-testid="member-sign-out" @click="signOut">登出</button>
      </div>
    </section>

    <div v-if="showResetConfirm" class="modal-layer" @keydown.esc="showResetConfirm = false">
      <section class="modal-card reset-dialog" role="dialog" aria-modal="true" aria-labelledby="reset-dialog-title">
        <h2 id="reset-dialog-title">確定還原 Demo 初始資料？</h2>
        <p>所有展示操作紀錄都會被清除，包括你剛送出的諮詢單、報價流程、新建群組與偏好設定。</p>
        <p class="muted">官方唯讀樣本不會被修改；初始群組與社區聯合服務會重新建立。</p>
        <div class="modal-actions">
          <button class="button ghost" type="button" :disabled="resetStatus === 'resetting'" @click="showResetConfirm = false">保留目前資料</button>
          <button ref="confirmResetButton" class="button danger" type="button" data-testid="confirm-demo-reset"
            :disabled="resetStatus === 'resetting'" @click="resetDemoData">
            {{ resetStatus === 'resetting' ? '還原中…' : '確認還原' }}
          </button>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
/* 寬度與卡片間距沿用全域 .member-page;此頁為單欄 card 堆疊(比照原型)。 */
.member-center h1 { margin-bottom: 0; }
.page-lead { margin: 0 0 .25rem; color: var(--muted); }

.profile-body { display: flex; align-items: center; gap: 1rem; }
.profile-table { flex: 1 1 220px; border-collapse: collapse; width: 100%; }
.profile-table th, .profile-table td { padding: 6px 8px; border-bottom: 2px solid var(--line); text-align: left; vertical-align: top; }
.profile-table th { width: 32%; color: var(--muted); font-size: .9rem; }

.entry-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
.entry-list li { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; border: 2px solid var(--ink); border-radius: 14px; padding: 10px 14px; background: var(--surface); }
.entry-list .grow { flex: 1 1 200px; }

.badge { display: inline-flex; align-items: center; padding: .1rem .55rem; border: 2px solid var(--ink); border-radius: 999px; background: var(--surface-2); font-size: .75rem; font-weight: 800; white-space: nowrap; }
.badge-mint { background: var(--mint); }
.badge-blue { background: var(--blue); }
.badge-peach { background: var(--peach); }
.badge-lilac { background: var(--lilac); }

.workspace-chip { display: inline-flex; align-items: center; padding: .15rem .65rem; border: 2px solid var(--ink); border-radius: 999px; background: var(--mint); font-size: .82rem; font-weight: 800; }

.demo-note { margin: .9rem 0 0; color: var(--muted); font-size: .8rem; }

@media (max-width: 700px) {
  .profile-body { flex-direction: column; align-items: flex-start; }
}
</style>
