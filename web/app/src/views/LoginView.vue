<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ROLE_HOME, useSessionStore, type Role } from '@/stores/session'

/**
 * 展示住戶（不是原始通路帳號）。
 *
 * 官方樣本的 10 個帳號有 7 個只用過單一服務——那是通路切分的結果，不是
 * 10 個真實的人。後端先以官方 member_*_hash 做行為指紋解析，再組成三位
 * 有完整生活樣貌的住戶；`name`／`roleSummary` 由此而來。
 */
interface AccountOption {
  accountId: string
  name: string
  roleSummary: string
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
const staffEntries = [
  { role: 'manager' as const, accountId: null, label: '社區管理者工作台', name: '社區管理者' },
  { role: 'partner' as const, accountId: 'vendor-prince-electric', label: '王子水電工作台', name: '王子水電' },
  { role: 'partner' as const, accountId: 'vendor-duskin', label: 'DUSKIN 樂清工作台', name: 'DUSKIN 樂清' },
  { role: 'partner' as const, accountId: 'vendor-prince-property', label: '太子物業工作台', name: '太子物業' },
]

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
    <div class="login-hero">
      <section class="login-intro">
        <p class="eyebrow">AI 生活服務平台</p>
        <h1>說一句話，<br />生活的事就有人接手</h1>
        <p class="login-lede">
          描述你的需求，平台會判讀該用哪項服務、引導你填好必要資訊，並媒合能服務你的合作夥伴。
        </p>
        <ul class="login-trust" aria-label="平台特色">
          <li>先確認再送出</li>
          <li>進度隨時可追蹤</li>
          <li>推薦理由看得懂</li>
        </ul>
      </section>

      <aside class="panel login-preview" aria-labelledby="login-preview-title">
        <p class="eyebrow">HOW IT WORKS</p>
        <h2 id="login-preview-title">從需求到完成，三步就好</h2>
        <ol class="login-preview-list">
          <li>
            <span aria-hidden="true">1</span>
            <div><strong>說出需求</strong><small>日常說法就可以，不必先找服務分類。</small></div>
          </li>
          <li>
            <span aria-hidden="true">2</span>
            <div><strong>確認方案</strong><small>價格、廠商與必要資料都會先讓你看過。</small></div>
          </li>
          <li>
            <span aria-hidden="true">3</span>
            <div><strong>追蹤進度</strong><small>從送出到完成，每一步都有清楚紀錄。</small></div>
          </li>
        </ol>
      </aside>
    </div>

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
          <li v-for="account in accounts" :key="account.accountId">
            <button
              class="account-option"
              type="button"
              :data-account-id="account.accountId"
              @click="enter('user', account.accountId, account.name)"
            >
              <strong>{{ account.name }}</strong>
              <span class="muted">{{ account.roleSummary }}</span>
              <span class="muted">{{ describe(account) }}</span>
            </button>
          </li>
        </ul>
        <p class="muted login-hint">展示住戶由官方樣本訂單組成（行為指紋見個人頁說明）。</p>
      </section>

      <section class="panel login-card" aria-labelledby="staff-entry">
        <h2 id="staff-entry">我是工作人員</h2>
        <p class="muted login-hint">社區管理者與合作廠商使用各自的工作台。</p>
        <div class="staff-options">
          <button
            v-for="entry in staffEntries"
            :key="`${entry.role}-${entry.accountId}`"
            class="button full"
            type="button"
            :data-testid="entry.role === 'manager' ? 'enter-manager' : `enter-${entry.accountId}`"
            @click="enter(entry.role, entry.accountId, entry.name)"
          >{{ entry.label }}</button>
        </div>
      </section>
    </div>
  </main>
</template>
