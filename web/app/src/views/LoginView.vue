<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  DEMO_MANAGER_IDENTITY,
  DEMO_PARTNER_ACCOUNTS,
  DEMO_RESIDENT_IDENTITY,
  demoAccessToken,
  demoCommunityMembership,
  ROLE_HOME,
  useSessionStore,
  type DemoRole,
  type Role,
} from '@/stores/session'

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
/** 後端有回應但這次失敗(如 500)時,不能叫使用者去「確認後端已啟動」。 */
const accountsErrorStatus = ref(0)
const staffEntries = [
  { role: 'manager' as const, accountId: null, label: '社區管理者工作台', name: '社區管理者' },
  { role: 'admin' as const, accountId: null, label: '平台營運管理台', name: '社區小統平台營運者' },
]

onMounted(async () => {
  try {
    const response = await fetch('/api/v1/insights/accounts', { headers: { Accept: 'application/json' } })
    if (!response.ok) {
      accountsErrorStatus.value = response.status
      accountsStatus.value = 'unavailable'
      return
    }
    accounts.value = ((await response.json()) as { data: AccountOption[] }).data
    accountsStatus.value = 'ready'
  } catch {
    accountsErrorStatus.value = 0
    accountsStatus.value = 'unavailable'
  }
})

function describe(account: AccountOption) {
  const parts = [`${account.orderCount} 筆紀錄`, `${account.serviceCount} 種服務`]
  if (account.openCount) parts.push(`${account.openCount} 件進行中`)
  return parts.join('・')
}

/** 合作廠商登入:每家品牌一個 Demo 帳號,Bearer 與 core/access seed 一致。 */
async function enterPartner(item: (typeof DEMO_PARTNER_ACCOUNTS)[number]) {
  session.signIn({
    role: 'partner',
    accountId: item.accountId,
    displayName: `${item.label}人員`,
    accessToken: item.token,
  })
  await router.push('/partner')
}

// ── 帳密登入(方向 A 原型:示範驗證與錯誤狀態;展示環境一律登入為王小明) ──
const loginEmail = ref('')
const loginPassword = ref('')
const emailError = ref('')
const passwordError = ref('')

async function submitPassword() {
  emailError.value = loginEmail.value.includes('@') ? '' : '請輸入有效的電子郵件。'
  passwordError.value = loginPassword.value ? '' : '請輸入密碼。'
  if (emailError.value || passwordError.value) return
  await enterCommunityDemo('user')
}

async function enter(role: Role, accountId: string | null, displayName: string) {
  const normalizedAccount = role === 'user' && accountId === null ? 'demo-new-member' : accountId
  session.signIn({
    role, accountId: normalizedAccount, displayName,
    communityMembership: demoCommunityMembership(role, normalizedAccount),
    accessToken: demoAccessToken(role, normalizedAccount),
  })
  await router.push(ROLE_HOME[role])
}

/**
 * 競賽主展示的統一入口：住戶與主委共用同一個 Demo 殼層，登入後即可走完整閉環。
 * 舊生活服務工作台仍由下方既有入口保留，方便回看原本的六大場景。
 */
async function enterCommunityDemo(role: DemoRole) {
  session.signIn(role === 'user' ? { ...DEMO_RESIDENT_IDENTITY } : { ...DEMO_MANAGER_IDENTITY })
  await router.push(role === 'user' ? '/demo/resident' : '/demo/committee')
}
</script>

<template>
  <main id="main-content" class="login-page" tabindex="-1">
    <div class="login-hero">
      <section class="login-intro">
        <p class="eyebrow">社區小統・AI 生活服務平台</p>
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

    <section class="panel login-demo-entry" aria-labelledby="community-demo-entry-title" data-testid="community-demo-entry">
      <div class="login-demo-copy">
        <p class="eyebrow">本次競賽主展示・統一入口</p>
        <h2 id="community-demo-entry-title">AI 智慧社區 × 社區團購</h2>
        <p>
          從這裡登入後，住戶與主委會進入同一套介面；公告、問社區、開團、跟團、訂單彙總與訂閱效益都使用同一份 Demo 資料。
        </p>
        <span class="muted">進入後可在右上角切換角色，完整走一次住戶 → 管委會的展示流程。</span>
      </div>
      <div class="login-demo-actions">
        <button class="button primary" type="button" data-testid="enter-community-demo-resident" @click="enterCommunityDemo('user')">
          以住戶王小明進入
        </button>
        <button class="button" type="button" data-testid="enter-community-demo-manager" @click="enterCommunityDemo('manager')">
          以主委陳建華進入
        </button>
      </div>
      <dl class="login-demo-credentials" data-testid="wang-demo-credentials">
        <div><dt>主要 Demo 帳號</dt><dd><code>household-wang-xiaoming</code></dd></div>
        <div><dt>Demo Bearer</dt><dd><code>aiwave-demo-resident</code></dd></div>
        <div><dt>住戶</dt><dd>王小明・A 棟 12F-3</dd></div>
      </dl>
    </section>

    <div class="login-panels">
      <section class="panel login-card" aria-labelledby="password-entry">
        <h2 id="password-entry">帳號密碼登入</h2>
        <form class="password-form" novalidate @submit.prevent="submitPassword">
          <label for="login-email">電子郵件</label>
          <input
            id="login-email" v-model="loginEmail" type="email" autocomplete="username"
            :aria-invalid="emailError ? 'true' : 'false'" data-testid="login-email"
          />
          <p v-if="emailError" class="field-error" role="alert">{{ emailError }}</p>
          <label for="login-password">密碼</label>
          <input
            id="login-password" v-model="loginPassword" type="password" autocomplete="current-password"
            :aria-invalid="passwordError ? 'true' : 'false'" data-testid="login-password"
          />
          <p v-if="passwordError" class="field-error" role="alert">{{ passwordError }}</p>
          <button class="button primary full" type="submit" data-testid="login-submit">登入</button>
        </form>
        <p class="muted login-hint">競賽展示:任何格式正確的帳密都會以主要展示住戶「王小明」登入;正式版由平台簽發憑證。</p>
      </section>

      <section class="panel login-card" aria-labelledby="resident-entry">
        <h2 id="resident-entry">Demo 快速登入</h2>
        <button
          class="button primary full"
          type="button"
          data-testid="start-new-user"
          @click="enter('user', null, '新使用者')"
        >建立新帳號開始</button>
        <p class="muted login-hint">全新帳號，沒有任何紀錄——首頁會帶你完成第一件事。</p>

        <div class="login-divider" role="separator"><span>或使用既有帳號</span></div>

        <p v-if="accountsStatus === 'loading'" class="muted" role="status">載入帳號中…</p>
        <p v-else-if="accountsStatus === 'unavailable'" class="muted" role="status" data-testid="account-list-unavailable">
          {{ accountsErrorStatus
            ? `後端有回應但取不到帳號清單（HTTP ${accountsErrorStatus}）；可以先用上方的入口進入 Demo。`
            : '連不上後端服務，取不到帳號清單，請確認後端是否啟動。' }}
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
            :key="entry.role"
            class="button full"
            type="button"
            :data-testid="entry.role === 'manager' ? 'enter-manager' : 'enter-admin'"
            @click="enter(entry.role, entry.accountId, entry.name)"
          >{{ entry.label }}</button>
        </div>

        <div class="login-divider" role="separator"><span>合作廠商</span></div>
        <h3 id="partner-entry">合作廠商工作台</h3>
        <p class="muted login-hint">M4 六場景的 8 家合作方 Demo 帳號，各自只看得到自己的案件。</p>
        <div class="staff-options" data-testid="partner-list" aria-labelledby="partner-entry">
          <button
            v-for="item in DEMO_PARTNER_ACCOUNTS"
            :key="item.accountId"
            class="button full"
            type="button"
            :data-testid="`enter-partner-${item.accountId}`"
            @click="enterPartner(item)"
          >{{ item.label }}</button>
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.password-form {
  display: grid;
  gap: var(--space-2);
}
.password-form label {
  font-weight: 700;
}
.password-form input {
  min-height: var(--tap);
  padding: 0 var(--space-3);
  border: var(--border-chunky) solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface);
  font: inherit;
}
.password-form .button {
  margin-top: var(--space-2);
}
.login-demo-entry {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 1.25rem;
  margin-bottom: 1rem;
  border: var(--border-chunky) solid var(--ink);
  background: var(--mint);
  box-shadow: var(--shadow);
}
.login-demo-copy h2 {
  margin: .25rem 0 .45rem;
  font-size: clamp(1.45rem, 3vw, 2.15rem);
}
.login-demo-copy p:not(.eyebrow) {
  max-width: 52rem;
  margin: 0 0 .35rem;
  color: var(--accent-ink);
}
.login-demo-copy > span {
  display: block;
  font-size: .82rem;
}
.login-demo-actions {
  display: grid;
  min-width: 15rem;
  gap: .55rem;
}
.login-demo-credentials {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: .55rem;
  margin: 0;
  padding-top: .75rem;
  border-top: 2px dashed var(--ink);
}
.login-demo-credentials > div {
  display: grid;
  gap: .15rem;
  min-width: 0;
}
.login-demo-credentials dt {
  color: var(--muted);
  font-size: .72rem;
  font-weight: 800;
}
.login-demo-credentials dd {
  margin: 0;
  font-size: .82rem;
  font-weight: 800;
  overflow-wrap: anywhere;
}
.login-demo-credentials code {
  font-size: .76rem;
}
@media (max-width: 720px) {
  .login-demo-entry {
    grid-template-columns: 1fr;
  }
  .login-demo-actions {
    min-width: 0;
  }
  .login-demo-actions .button {
    width: 100%;
  }
  .login-demo-credentials {
    grid-template-columns: 1fr;
  }
}
</style>
