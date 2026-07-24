import {
  createRouter,
  createWebHistory,
  type RouterHistory,
  type RouteRecordRaw,
} from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/app/today' },
  { path: '/app/today', name: 'today', component: () => import('@/views/TodayView.vue') },
  { path: '/app/services/:serviceSlug?', name: 'services', component: () => import('@/views/ServicesView.vue') },
  { path: '/app/orders', name: 'orders', component: () => import('@/views/OrdersView.vue') },
  { path: '/app/community', name: 'community', component: () => import('@/views/CommunityView.vue') },
  { path: '/app/vendor', name: 'vendor', component: () => import('@/views/VendorView.vue') },
  { path: '/app/platform', name: 'platform', component: () => import('@/views/PlatformView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/app/today' },
]

export function createAppRouter(history: RouterHistory = createWebHistory()) {
  return createRouter({ history, routes })
}
