<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useDemoStore } from '@/stores/demo'
import { ROLE_LABEL, useSessionStore } from '@/stores/session'

const mainContent = ref<HTMLElement | null>(null)
const router = useRouter()
const route = useRoute()
const store = useDemoStore()
const session = useSessionStore()

/** 導覽由身分決定；工作人員的工作台只有單頁，不需要導覽列。 */
const navItems = computed(() => {
  if (session.role !== 'user') return []
  return [
    { to: '/user', label: '今日' },
    { to: '/user/services', label: '找服務' },
    { to: '/user/orders', label: '訂單' },
  ]
})

const showChrome = computed(() => route.name !== 'login')

async function signOut() {
  session.signOut()
  store.resetDemo()
  await router.push('/login')
}

watch(() => route.fullPath, async () => {
  await nextTick()
  mainContent.value?.focus()
})
</script>

<template>
  <RouterView v-if="!showChrome" />

  <template v-else>
    <a class="skip-link" href="#main-content">跳至主要內容</a>
    <header class="topbar">
      <div class="topbar-main">
        <RouterLink class="wordmark" to="/user" aria-label="回到首頁">
          <span class="wordmark-mark" aria-hidden="true">生</span>
          <span>AI 生活服務平台</span>
        </RouterLink>

        <nav v-if="navItems.length" class="main-nav" aria-label="主要導覽">
          <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-link">
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="top-actions">
          <span class="identity-badge">
            {{ session.identity?.displayName }}
            <span class="muted">・{{ session.role ? ROLE_LABEL[session.role] : '' }}</span>
          </span>
          <RouterLink v-if="session.role === 'user'" class="button primary" to="/user/assistant">
            問生活管家
          </RouterLink>
          <button class="button" type="button" data-testid="sign-out" @click="signOut">登出</button>
        </div>
      </div>
    </header>

    <main id="main-content" ref="mainContent" tabindex="-1">
      <RouterView />
    </main>
  </template>
</template>
