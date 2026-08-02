<script setup lang="ts">
type AppIconName = 'home' | 'community' | 'points' | 'ai' | 'services' | 'member'

defineProps<{ name: AppIconName }>()
</script>

<template>
  <svg
    class="nav-icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-if="name === 'home'">
      <path d="m3 11 9-8 9 8" />
      <path d="M5 10v10h14V10" />
      <path d="M9 20v-6h6v6" />
    </template>
    <template v-else-if="name === 'community'">
      <path d="M4 20V8l8-5 8 5v12" />
      <path d="M8 20v-5h8v5M8 10h.01M12 10h.01M16 10h.01" />
    </template>
    <template v-else-if="name === 'points'">
      <circle cx="12" cy="12" r="9" />
      <path d="M9 8.5h4.5a2.5 2.5 0 0 1 0 5H9V6" />
      <path d="M9 13.5h5" />
    </template>
    <template v-else-if="name === 'ai'">
      <path d="M9 4h6" />
      <rect x="4" y="7" width="16" height="12" rx="4" />
      <path d="M8 12h.01M16 12h.01M9 16h6M12 4V2" />
    </template>
    <template v-else-if="name === 'services'">
      <path d="M14.5 6.5a4 4 0 0 0-5.8 5.4L3 17.6 6.4 21l5.7-5.7a4 4 0 0 0 5.4-5.8l-2.7 2.7-3-3z" />
    </template>
    <template v-else>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </template>
  </svg>
</template>
