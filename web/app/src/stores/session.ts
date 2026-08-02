import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/**
 * 目前登入身分。
 *
 * 競賽期間以輕量假登入實作，但**語意是登入，不是 demo 切換**（見 ADR-0015）：
 * 看到多少資料取決於登入成哪個帳號，而不是某個展示開關。日後接 OIDC 只需替換
 * `signIn` 取得身分的方式，路由與畫面不變。
 */

/**
 * 角色是「人」，不是「範圍」。
 *
 * 社區是住戶共享的**範圍**（見 ADR-0003），不是一種身分——所以住戶端本身就看得到
 * 社區的團購與公設；`manager` 指的是管委會／物業那個**管理者**，負責社區層級的結單、審核與營運；
 * 開團本身是社區共享功能，任何已登入住戶都可以發起。
 * 先前叫 `admin` 把兩者混為一談，也與「平台管理者」語意衝突。
 */
export type Role = 'user' | 'manager' | 'partner' | 'admin'

export interface Identity {
  role: Role
  /** 住戶身分對應的帳號；新使用者為 null（＝完全沒有紀錄）。 */
  accountId: string | null
  displayName: string
  /** Opaque server-issued/fixed Demo Bearer credential; never an account id. */
  accessToken?: string
}

export type DemoRole = 'user' | 'manager'

export const DEMO_RESIDENT_IDENTITY: Identity = {
  role: 'user',
  accountId: 'household-wang-xiaoming',
  displayName: '王小明',
  accessToken: 'aiwave-demo-resident',
}

export const DEMO_MANAGER_IDENTITY: Identity = {
  role: 'manager',
  accountId: 'demo-committee-chen',
  displayName: '主委陳建華',
  accessToken: 'aiwave-demo-manager',
}

const STORAGE_KEY = 'life-ai.identity'

export const ROLE_HOME: Record<Role, string> = {
  user: '/user',
  manager: '/community',
  partner: '/partner',
  admin: '/platform',
}

export const ROLE_LABEL: Record<Role, string> = {
  user: '會員',
  manager: '社區管理者',
  partner: '合作廠商',
  admin: '平台營運者',
}

const DEMO_MEMBER_TOKENS: Record<string, string> = {
  'household-wang-xiaoming': 'aiwave-demo-resident',
  '019a52d3-7f6b-7da3-b48d-9c9e2522d616': 'aiwave',
  '019c0464-2d01-73f0-9f9b-d1392fdb941a': 'aiwave-chen',
  '019e6c8c-a061-7197-be0f-b7d341dbafdd': 'aiwave-vivian',
  'demo-new-member': 'aiwave-new',
}

/**
 * M4 六場景的合作方 Demo 帳號。`accountId` 沿用 Provider id(舊 LoginView 慣例):
 * 平台身分由 Bearer 決定,accountId 只是 legacy vendor-api 的 `vendor_id` 查詢鍵。
 */
export const DEMO_PARTNER_ACCOUNTS: ReadonlyArray<{ accountId: string; token: string; label: string }> = [
  { accountId: 'vendor-prince-electric', token: 'aiwave-partner', label: '王子水電' },
  { accountId: 'vendor-duskin', token: 'aiwave-partner-duskin', label: 'DUSKIN 樂清' },
  { accountId: 'vendor-21plus', token: 'aiwave-partner-21plus', label: '21PLUS 餐廳' },
  { accountId: 'vendor-smile', token: 'aiwave-partner-smile', label: '速邁樂加油站' },
  { accountId: 'vendor-blackcat', token: 'aiwave-partner-blackcat', label: '黑貓宅急便' },
  { accountId: 'vendor-cosmed', token: 'aiwave-partner-cosmed', label: '康是美' },
  { accountId: 'vendor-711-shop', token: 'aiwave-partner-711shop', label: '7-ELEVEN 線上購物中心' },
  { accountId: 'vendor-uni-resort', token: 'aiwave-partner-resort', label: '統一渡假村' },
  { accountId: 'vendor-foodomo', token: 'aiwave-partner-foodomo', label: 'foodomo' },
  { accountId: 'vendor-711-c2c', token: 'aiwave-partner-711c2c', label: '7-ELEVEN 交貨便' },
  { accountId: 'vendor-iopenmall', token: 'aiwave-partner-iopenmall', label: 'iOPEN Mall' },
  { accountId: 'vendor-ibon-ticket', token: 'aiwave-partner-ibonticket', label: 'ibon 售票' },
]

const DEMO_PARTNER_TOKENS: Record<string, string> = Object.fromEntries(
  DEMO_PARTNER_ACCOUNTS.map((item) => [item.accountId, item.token]),
)

export function demoAccessToken(role: Role, accountId: string | null): string {
  if (role === 'partner') return DEMO_PARTNER_TOKENS[accountId ?? ''] ?? 'aiwave-partner'
  if (role === 'manager') return 'aiwave-manager'
  if (role === 'admin') return 'aiwave-admin'
  return DEMO_MEMBER_TOKENS[accountId ?? 'demo-new-member'] ?? ''
}

function readStored(): Identity | null {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Identity
    return parsed.role in ROLE_HOME ? parsed : null
  } catch {
    return null
  }
}

function persist(identity: Identity | null) {
  try {
    if (identity) globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(identity))
    else globalThis.localStorage?.removeItem(STORAGE_KEY)
  } catch {
    // 隱私模式等情況無法寫入，僅影響重新整理後是否保留登入
  }
}

export function currentAuthorizationHeaders(): Record<string, string> {
  const stored = readStored()
  if (!stored) return {}
  const token = stored.accessToken || demoAccessToken(stored.role, stored.accountId)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const useSessionStore = defineStore('session', () => {
  const identity = ref<Identity | null>(readStored())

  const isSignedIn = computed(() => identity.value !== null)
  const role = computed(() => identity.value?.role ?? null)
  /** 住戶資料的查詢鍵；新使用者沒有帳號，因此不會有任何紀錄。 */
  const accountId = computed(() => identity.value?.accountId ?? null)
  const accessToken = computed(() => {
    const current = identity.value
    return current ? (current.accessToken || demoAccessToken(current.role, current.accountId)) : null
  })
  /** 寫入類操作（跟團、開團）要記錄是誰做的，未登入時退回角色名稱。 */
  const displayName = computed(() => identity.value?.displayName ?? ROLE_LABEL[identity.value?.role ?? 'user'])
  const isNewUser = computed(() => identity.value?.role === 'user'
    && (identity.value.accountId === null || identity.value.accountId === 'demo-new-member'))

  function signIn(next: Identity) {
    identity.value = next
    persist(next)
  }

  function signOut() {
    identity.value = null
    persist(null)
  }

  /** Demo 專用的明確身分切換；正式登入與既有 router guard 不受影響。 */
  function switchDemoRole(nextRole: DemoRole) {
    signIn(nextRole === 'user' ? { ...DEMO_RESIDENT_IDENTITY } : { ...DEMO_MANAGER_IDENTITY })
  }

  return {
    identity,
    isSignedIn,
    role,
    accountId,
    accessToken,
    displayName,
    isNewUser,
    signIn,
    signOut,
    switchDemoRole,
  }
})
