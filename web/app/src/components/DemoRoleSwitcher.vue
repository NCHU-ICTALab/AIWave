<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useCommunityDemoStore } from '@/stores/communityDemo'
import { useSessionStore, type DemoRole } from '@/stores/session'

const router = useRouter()
const route = useRoute()
const session = useSessionStore()
const demo = useCommunityDemoStore()

const selectedRole = computed(() => session.role === 'manager' ? 'manager' : 'user')

async function changeRole(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  if (value === 'reset') {
    demo.resetDemo()
    session.switchDemoRole('user')
    await router.push('/demo/resident')
    return
  }
  if (value !== 'user' && value !== 'manager') return
  session.switchDemoRole(value as DemoRole)
  await router.push(value === 'manager' ? '/demo/committee' : '/demo/resident')
}

const isDemoRoute = computed(() => route.path.startsWith('/demo/'))
</script>

<template>
  <label v-if="isDemoRoute && (session.role === 'user' || session.role === 'manager')" class="demo-role-field" :class="{ 'is-demo-route': isDemoRoute }">
    <span class="visually-hidden">Demo 角色切換</span>
    <select
      data-testid="demo-role-switcher"
      aria-label="Demo 角色切換"
      :value="selectedRole"
      @change="changeRole"
    >
      <option value="user">住戶王小明</option>
      <option value="manager">主委陳建華</option>
      <option value="reset">重設 Demo</option>
    </select>
  </label>
</template>
