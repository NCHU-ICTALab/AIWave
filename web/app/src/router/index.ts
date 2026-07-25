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
  { path: '/user/orders', name: 'orders', component: () => import('@/views/OrdersView.vue'), meta: { role: 'user' } },

  // 社區管理者／合作廠商
  { path: '/admin', name: 'admin-home', component: () => import('@/views/CommunityView.vue'), meta: { role: 'admin' } },
  { path: '/partner', name: 'partner-home', component: () => import('@/views/VendorView.vue'), meta: { role: 'partner' } },

  // 後續加分：不在登入選項與主導覽中
  { path: '/platform', name: 'platform', component: () => import('@/views/PlatformView.vue'), meta: { role: 'admin' } },

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
