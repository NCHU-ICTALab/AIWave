import {
  createRouter,
  createWebHistory,
  type RouterHistory,
  type RouteRecordRaw,
} from 'vue-router'

import { ROLE_HOME, useSessionStore, type Role } from '@/stores/session'

/**
 * 角色分離入口（ADR-0015）：住戶、社區管理者、合作廠商各自有介面，
 * 不再用同一個殼加下拉切換。未登入一律導向 `/login`。
 *
 * **社區是範圍不是角色**（ADR-0003）：住戶端本身就有 `/user/community` 看團購與公設；
 * `/community` 是管委會的管理工作台。
 *
 * `/platform`（平台營運）依決策屬後續加分，保留路由但不列入登入選項與主導覽。
 */
const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },

  // 住戶
  { path: '/user', name: 'user-home', component: () => import('@/views/TodayView.vue'), meta: { role: 'user' } },
  {
    path: '/user/services/:serviceSlug?',
    name: 'services',
    component: () => import('@/views/ServicesView.vue'),
    meta: { role: 'user' },
  },
  { path: '/user/assistant', name: 'assistant', component: () => import('@/views/AssistantView.vue'), meta: { role: 'user' } },
  { path: '/user/orders', name: 'orders', component: () => import('@/views/OrdersView.vue'), meta: { role: 'user' } },
  { path: '/user/community', name: 'community-board', component: () => import('@/views/CommunityBoardView.vue'), meta: { role: 'user' } },

  // 管委會／合作廠商的管理工作台
  { path: '/community', name: 'community-home', component: () => import('@/views/CommunityView.vue'), meta: { role: 'manager' } },
  { path: '/partner', name: 'partner-home', component: () => import('@/views/VendorView.vue'), meta: { role: 'partner' } },

  // 後續加分：不在登入選項與主導覽中
  { path: '/platform', name: 'platform', component: () => import('@/views/PlatformView.vue'), meta: { role: 'manager' } },

  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

export function createAppRouter(history: RouterHistory = createWebHistory()) {
  const router = createRouter({ history, routes })

  router.beforeEach((to) => {
    if (to.meta.public) return true
    const session = useSessionStore()
    if (!session.isSignedIn) return { name: 'login' }
    // 身分不符時導回自己的首頁，而不是顯示別人的工作台
    const required = to.meta.role as Role | undefined
    if (required && session.role !== required) return ROLE_HOME[session.role as Role]
    return true
  })

  return router
}
