<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AgentDrawer from '@/components/AgentDrawer.vue'
import AppIcon from '@/components/AppIcon.vue'
import DemoRoleSwitcher from '@/components/DemoRoleSwitcher.vue'
import { useDemoStore } from '@/stores/demo'
import { ROLE_HOME, ROLE_LABEL, useSessionStore } from '@/stores/session'

const mainContent = ref<HTMLElement | null>(null)
const router = useRouter()
const route = useRoute()
const store = useDemoStore()
const session = useSessionStore()
type AppIconName = 'home' | 'community' | 'points' | 'ai' | 'services' | 'member'

/** 導覽由身分決定；工作人員的工作台只有單頁，不需要導覽列。 */
const navItems = computed(() => {
  if (session.role !== 'user') return []
  // Wang Xiaoming and every regular resident use the same five destinations.
  // The /demo/* paths remain valid presentation aliases, but never get a
  // second, special navigation shell.
  return [
    { to: '/user', label: '首頁', icon: 'home' },
    { to: '/user/community', label: '社區', icon: 'community' },
    { to: '/user/assistant', label: 'AI', icon: 'ai' },
    { to: '/user/services', label: '服務', icon: 'services' },
    { to: '/user/member', label: '個人檔案', icon: 'member' },
  ] satisfies Array<{ to: string; label: string; icon: AppIconName }>
})

const showChrome = computed(() => route.name !== 'login' && route.name !== 'home-public')

/** M8(spec 15 §4.1):會員殼掛 Agent 側欄;完整 AI 頁本身就是同一段對話,不重複疊側欄。 */
const showAgentDrawer = computed(
  () => showChrome.value && session.role === 'user' && route.name !== 'assistant' && !route.path.startsWith('/demo'),
)

const homeLink = computed(() => {
  if (route.path.startsWith('/demo') && session.role === 'manager') return '/demo/committee'
  return session.role ? ROLE_HOME[session.role] : '/login'
})

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
        <RouterLink class="wordmark" :to="homeLink" aria-label="回到首頁">
          <span class="wordmark-mark" aria-hidden="true">生</span>
          <span>AI 生活服務平台</span>
        </RouterLink>

        <nav v-if="navItems.length" class="main-nav" aria-label="主要導覽">
          <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-link">
            <AppIcon :name="item.icon" />
            <span>{{ item.label }}</span>
          </RouterLink>
        </nav>

        <div class="top-actions">
          <DemoRoleSwitcher />
          <span class="identity-badge">
            {{ session.identity?.displayName }}
            <span class="muted">・{{ session.role ? ROLE_LABEL[session.role] : '' }}</span>
          </span>
          <button class="button" type="button" data-testid="sign-out" @click="signOut">登出</button>
        </div>
      </div>
    </header>

    <main id="main-content" ref="mainContent" tabindex="-1">
      <RouterView />
    </main>

    <AgentDrawer v-if="showAgentDrawer" />
  </template>
</template>
