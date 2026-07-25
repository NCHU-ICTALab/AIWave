<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ROLE_HOME, ROLE_LABEL, useSessionStore, type Role } from '@/stores/session'

interface AccountOption {
  accountId: string
  orderCount: number
  serviceCount: number
  openCount: number
  topService: string
  topServiceCount: number
}

const router = useRouter()
const session = useSessionStore()
const accounts = ref<AccountOption[]>([])
const accountsStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')

onMounted(async () => {
  try {
    const response = await fetch('/api/v1/insights/accounts', { headers: { Accept: 'application/json' } })
    if (!response.ok) throw new Error('unavailable')
    accounts.value = ((await response.json()) as { data: AccountOption[] }).data
    accountsStatus.value = 'ready'
  } catch {
    accountsStatus.value = 'unavailable'
  }
})

function describe(account: AccountOption) {
  const parts = [`${account.orderCount} 筆紀錄`, `${account.serviceCount} 種服務`]
  if (account.openCount) parts.push(`${account.openCount} 件進行中`)
  return parts.join('・')
}

async function enter(role: Role, accountId: string | null, displayName: string) {
  session.signIn({ role, accountId, displayName })
  await router.push(ROLE_HOME[role])
}
</script>

<template>
  <main id="main-content" class="login-page" tabindex="-1">
    <section class="login-intro">
      <p class="eyebrow">AI 生活服務平台</p>
      <h1>說一句話，生活的事就有人接手</h1>
      <p class="login-lede">
        描述你的需求，平台會判讀該用哪項服務、引導你填好必要資訊，並媒合能服務你的合作夥伴。
      </p>
    </section>

    <div class="login-panels">
      <section class="panel login-card" aria-labelledby="resident-entry">
        <h2 id="resident-entry">我是住戶</h2>
        <button
          class="button primary full"
          type="button"
          data-testid="start-new-user"
          @click="enter('user', null, '新使用者')"
        >建立新帳號開始</button>
        <p class="muted login-hint">全新帳號，沒有任何紀錄——首頁會帶你完成第一件事。</p>

        <div class="login-divider" role="separator"><span>或使用既有帳號</span></div>

        <p v-if="accountsStatus === 'loading'" class="muted" role="status">載入帳號中…</p>
        <p v-else-if="accountsStatus === 'unavailable'" class="muted" role="status">
          目前無法取得帳號清單，請確認後端服務已啟動。
        </p>
        <ul v-else class="account-list" data-testid="account-list">
          <li v-for="(account, index) in accounts" :key="account.accountId">
            <button
              class="account-option"
              type="button"
              :data-account-id="account.accountId"
              @click="enter('user', account.accountId, `使用者 ${index + 1}`)"
            >
              <strong>{{ account.topService || '一般' }}使用者</strong>
              <span class="muted">{{ describe(account) }}</span>
            </button>
          </li>
        </ul>
      </section>

      <section class="panel login-card" aria-labelledby="staff-entry">
        <h2 id="staff-entry">我是工作人員</h2>
        <p class="muted login-hint">社區管理者與合作廠商使用各自的工作台。</p>
        <div class="staff-options">
          <button
            v-for="role in (['manager', 'partner'] as Role[])"
            :key="role"
            class="button full"
            type="button"
            :data-testid="`enter-${role}`"
            @click="enter(role, null, ROLE_LABEL[role])"
          >{{ ROLE_LABEL[role] }}工作台</button>
        </div>
      </section>
    </div>
  </main>
</template>
