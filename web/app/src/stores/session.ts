import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/**
 * 目前登入身分。
 *
 * 競賽期間以輕量假登入實作，但**語意是登入，不是 demo 切換**（見 ADR-0015）：
 * 看到多少資料取決於登入成哪個帳號，而不是某個展示開關。日後接 OIDC 只需替換
 * `signIn` 取得身分的方式，路由與畫面不變。
 */

export type Role = 'user' | 'admin' | 'partner'

export interface Identity {
  role: Role
  /** 住戶身分對應的帳號；新使用者為 null（＝完全沒有紀錄）。 */
  accountId: string | null
  displayName: string
}

const STORAGE_KEY = 'life-ai.identity'

export const ROLE_HOME: Record<Role, string> = {
  user: '/user',
  admin: '/admin',
  partner: '/partner',
}

export const ROLE_LABEL: Record<Role, string> = {
  user: '住戶',
  admin: '社區管理者',
  partner: '合作廠商',
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

export const useSessionStore = defineStore('session', () => {
  const identity = ref<Identity | null>(readStored())

  const isSignedIn = computed(() => identity.value !== null)
  const role = computed(() => identity.value?.role ?? null)
  /** 住戶資料的查詢鍵；新使用者沒有帳號，因此不會有任何紀錄。 */
  const accountId = computed(() => identity.value?.accountId ?? null)
  const isNewUser = computed(() => identity.value?.role === 'user' && identity.value.accountId === null)

  function signIn(next: Identity) {
    identity.value = next
    persist(next)
  }

  function signOut() {
    identity.value = null
    persist(null)
  }

  return { identity, isSignedIn, role, accountId, isNewUser, signIn, signOut }
})
