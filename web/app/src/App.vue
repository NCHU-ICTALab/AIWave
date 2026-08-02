<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

// 走 bundler import 而不是 `/aiwave.ico`：`public/` 只有 dev server 與 build 看得到，
// vitest 解析不到那個路徑，會讓所有掛載 App.vue 的測試在 import 階段就炸掉。
import brandMark from '@/assets/aiwave.ico'
import AgentDrawer from '@/components/AgentDrawer.vue'
import AppIcon from '@/components/AppIcon.vue'
import DemoRoleSwitcher from '@/components/DemoRoleSwitcher.vue'
import SubscriptionLock from '@/components/SubscriptionLock.vue'
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
    { to: '/user', label: '首頁', icon: 'home', locked: false },
    { to: '/user/community', label: '社區', icon: 'community', locked: false },
    { to: '/user/assistant', label: 'AI', icon: 'ai', locked: !session.isSubscriber },
    { to: '/user/services', label: '服務', icon: 'services', locked: !session.isSubscriber },
    { to: '/user/member', label: '個人檔案', icon: 'member', locked: false },
  ] satisfies Array<{ to: string; label: string; icon: AppIconName; locked: boolean }>
})

const showChrome = computed(() => route.name !== 'login' && route.name !== 'home-public')

/** 訂閱功能的顯示名稱；遮罩會唸成「XXX・需要社區訂閱」。 */
const LOCKED_FEATURE_LABEL: Record<string, string> = {
  assistant: 'AI 管家',
  services: '服務探索與預約',
  'provider-detail': '服務探索與預約',
  'booking-wizard': '預約精靈',
  calendar: '行事曆與提醒',
  'life-circle': '生活圈地圖',
  wellbeing: '生活關懷與成果',
}

/**
 * 這一頁要不要整頁鎖住。回傳功能名稱（給遮罩當標題），沒鎖就是空字串。
 * 判斷同時看 route meta 與目前身分，所以升級後不必重新導覽就會自動解鎖。
 */
const lockedFeature = computed(() => {
  if (!route.meta.subscriberOnly || session.role !== 'user' || session.isSubscriber) return ''
  return LOCKED_FEATURE_LABEL[String(route.name ?? '')] ?? '這項功能'
})

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
          <img class="wordmark-mark" :src="brandMark" alt="" width="32" height="32" aria-hidden="true" />
          <span>社區小統</span>
        </RouterLink>

        <nav v-if="navItems.length" class="main-nav" aria-label="主要導覽">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="nav-link"
            :aria-label="item.locked ? `${item.label}，訂閱解鎖` : item.label"
          >
            <AppIcon :name="item.icon" />
            <span>{{ item.label }}<span v-if="item.locked" aria-hidden="true"> 🔒</span></span>
          </RouterLink>
        </nav>

        <div class="top-actions">
          <DemoRoleSwitcher />
          <span class="identity-badge">
            {{ session.identity?.displayName }}
            <span class="muted">・{{ session.role ? ROLE_LABEL[session.role] : '' }}</span>
          </span>
          <RouterLink
            v-if="session.role === 'user'"
            class="identity-membership"
            :class="{ subscriber: session.isSubscriber }"
            to="/user/subscription"
            data-testid="membership-badge"
            :aria-label="`${session.membershipLabel}，查看訂閱方案`"
          >
            <span aria-hidden="true">{{ session.isSubscriber ? '♛' : '○' }}</span>
            <span>{{ session.isSubscriber ? 'VIP' : '免費' }}</span>
          </RouterLink>
          <button class="button" type="button" data-testid="sign-out" @click="signOut">登出</button>
        </div>
      </div>
    </header>

    <main id="main-content" ref="mainContent" tabindex="-1">
      <!--
        免費社區照樣進得來，但整頁內容霧面鎖住：看得到訂閱換到什麼，卻真的用不到
        （`SubscriptionLock` 會把內容設成 inert，鍵盤與螢幕閱讀器都進不去）。
      -->
      <SubscriptionLock :locked="!!lockedFeature" :title="lockedFeature || '這項功能'" :heading-level="2" variant="page">
        <RouterView />
      </SubscriptionLock>
    </main>

    <AgentDrawer v-if="showAgentDrawer" />
  </template>
</template>
