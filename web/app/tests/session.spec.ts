// @vitest-environment happy-dom

import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * 憑證的送出路徑。
 *
 * 使用者回報「小明沒有憑證、存取不到後端」時，後端的固定 Demo credential 其實
 * 是好的（見 tests/test_wang_demo_credential.py）。會壞在前端這一層的有兩種：
 * 舊版本存下來的身分沒有 `accessToken`，以及 localStorage 不可用時憑證整個消失。
 * 兩種都會讓每個請求少掉 Authorization，後端回 401「請提供 Bearer 存取憑證」。
 */

const STORAGE_KEY = 'life-ai.identity'

/** 每個案例都重新載入模組：模組層的身分鏡像是在 import 時從 localStorage 還原的。 */
async function loadSessionModule() {
  vi.resetModules()
  const module = await import('@/stores/session')
  setActivePinia(createPinia())
  return module
}

describe('session credentials', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the Wang demo bearer once the resident signs in', async () => {
    const { currentAuthorizationHeaders, useSessionStore, DEMO_RESIDENT_IDENTITY } = await loadSessionModule()

    useSessionStore().signIn({ ...DEMO_RESIDENT_IDENTITY })

    expect(currentAuthorizationHeaders()).toEqual({ Authorization: 'Bearer aiwave-demo-resident' })
  })

  it('keeps sending the bearer when localStorage cannot be used', async () => {
    // 無痕模式／封鎖網站資料時 setItem 會丟例外；憑證不能因此消失
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('storage disabled') },
      setItem: () => { throw new Error('storage disabled') },
      removeItem: () => { throw new Error('storage disabled') },
      clear: () => {},
    })
    const { currentAuthorizationHeaders, useSessionStore, DEMO_RESIDENT_IDENTITY } = await loadSessionModule()

    useSessionStore().signIn({ ...DEMO_RESIDENT_IDENTITY })

    expect(currentAuthorizationHeaders()).toEqual({ Authorization: 'Bearer aiwave-demo-resident' })
  })

  it('repairs an identity persisted before accessToken existed', async () => {
    globalThis.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      role: 'user', accountId: 'household-wang-xiaoming', displayName: '王小明',
    }))

    const { currentAuthorizationHeaders, useSessionStore } = await loadSessionModule()

    expect(currentAuthorizationHeaders()).toEqual({ Authorization: 'Bearer aiwave-demo-resident' })
    expect(useSessionStore().accessToken).toBe('aiwave-demo-resident')
    // 修好的身分寫回去，回訪時不必再修一次
    expect(JSON.parse(globalThis.localStorage.getItem(STORAGE_KEY)!).accessToken)
      .toBe('aiwave-demo-resident')
  })

  it('discards a persisted identity whose credential cannot be derived', async () => {
    // 早期版本的住戶 accountId 已經不在對照表裡：留著只會永遠送不出 Authorization
    globalThis.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      role: 'user', accountId: 'legacy-household-id', displayName: '王小明',
    }))

    const { currentAuthorizationHeaders, useSessionStore } = await loadSessionModule()

    expect(currentAuthorizationHeaders()).toEqual({})
    expect(useSessionStore().isSignedIn).toBe(false)
    expect(globalThis.localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('fills in the bearer for identities signed in without one', async () => {
    const { currentAuthorizationHeaders, useSessionStore } = await loadSessionModule()

    useSessionStore().signIn({ role: 'user', accountId: 'demo-new-member', displayName: '新使用者' })

    expect(currentAuthorizationHeaders()).toEqual({ Authorization: 'Bearer aiwave-new' })
  })

  it('stops sending a bearer after signing out', async () => {
    const { currentAuthorizationHeaders, useSessionStore, DEMO_RESIDENT_IDENTITY } = await loadSessionModule()
    const session = useSessionStore()
    session.signIn({ ...DEMO_RESIDENT_IDENTITY })

    session.signOut()

    expect(currentAuthorizationHeaders()).toEqual({})
  })
})
