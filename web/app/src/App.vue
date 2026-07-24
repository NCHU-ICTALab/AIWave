<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CopilotDrawer from '@/components/CopilotDrawer.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { navItems } from '@/data/demoFixtures'
import type { AiOperation } from '@/api/aiInquiryClient'
import { useDemoStore } from '@/stores/demo'

const copilotOpen = ref(false)
const resetOpen = ref(false)
const mainContent = ref<HTMLElement | null>(null)
const router = useRouter()
const route = useRoute()
const store = useDemoStore()

const workspaceRoutes: Record<string, string> = {
  resident: '/app/today', community: '/app/community', vendor: '/app/vendor', platform: '/app/platform',
}
const currentWorkspace = computed(() => {
  if (route.path.startsWith('/app/community')) return 'community'
  if (route.path.startsWith('/app/vendor')) return 'vendor'
  if (route.path.startsWith('/app/platform')) return 'platform'
  return 'resident'
})

function changeWorkspace(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  void router.push(workspaceRoutes[value] ?? '/app/today')
}

function confirmReset() {
  store.resetDemo()
  resetOpen.value = false
}

function handleAiOperation(operation: AiOperation) {
  if (operation.type === 'inquiry.created') store.recordAiInquiry(operation.id)
}

watch(() => route.fullPath, async () => {
  await nextTick()
  mainContent.value?.focus()
})
</script>

<template>
  <a class="skip-link" href="#main-content">跳至主要內容</a>
  <header class="topbar">
    <div class="topbar-main">
      <RouterLink class="wordmark" to="/app/today" aria-label="回到今日生活中心">
        <span class="wordmark-mark" aria-hidden="true">生</span>
        <span>生活 AI 管家<small>名稱待定</small></span>
      </RouterLink>
      <nav class="main-nav" aria-label="主要導覽">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-link">
          <span aria-hidden="true">{{ item.code }}</span> {{ item.label }}
        </RouterLink>
      </nav>
      <div class="top-actions">
        <label class="role-field">
          <span class="visually-hidden">目前工作區</span>
          <select :value="currentWorkspace" aria-label="切換工作區" @change="changeWorkspace">
            <option value="resident">個人／住戶</option>
            <option value="community">社區管理者</option>
            <option value="vendor">合作廠商</option>
            <option value="platform">平台營運者</option>
          </select>
        </label>
        <button class="button reset-action" type="button" @click="resetOpen = true">重設</button>
        <button class="button primary" type="button" aria-haspopup="dialog" @click="copilotOpen = true">問生活管家</button>
      </div>
    </div>
  </header>
  <main id="main-content" ref="mainContent" tabindex="-1">
    <RouterView />
  </main>
  <CopilotDrawer :open="copilotOpen" @close="copilotOpen = false" @inquiry-created="handleAiOperation" />
  <ConfirmDialog :open="resetOpen" title="確認重設展示資料" description="訂單、推薦偏好與跨角色服務流程將還原成 demo_seed_v1。" @cancel="resetOpen = false" @confirm="confirmReset" />
</template>
