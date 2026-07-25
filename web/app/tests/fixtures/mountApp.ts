import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import App from '@/App.vue'
import { createAppRouter } from '@/router'
import { useSessionStore, type Identity } from '@/stores/session'

import { insightSummary } from './catalog.generated'

/** 官方資料中的既有使用者（有紀錄）。 */
export const EXISTING_USER: Identity = {
  role: 'user',
  accountId: insightSummary.accountId,
  displayName: '測試使用者',
}

/** 全新住戶：沒有帳號，因此沒有任何紀錄。 */
export const NEW_USER: Identity = { role: 'user', accountId: null, displayName: '新使用者' }

/**
 * 先建立身分再掛載 App。
 *
 * 路由有登入守衛（ADR-0015），未登入會被導向 `/login`，因此元件測試一律走這裡。
 * 傳 `identity: null` 可測未登入情境。
 */
export async function mountApp(
  path: string,
  options: { identity?: Identity | null; attach?: boolean } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const session = useSessionStore()
  const identity = options.identity === undefined ? EXISTING_USER : options.identity
  if (identity) session.signIn(identity)
  else session.signOut()

  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()

  const wrapper = mount(App, {
    global: { plugins: [pinia, router] },
    ...(options.attach ? { attachTo: document.body } : {}),
  })
  await flushPromises()
  return { wrapper, router, session }
}
