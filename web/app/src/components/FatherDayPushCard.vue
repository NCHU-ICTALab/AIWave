<script setup lang="ts">
import { computed, ref } from 'vue'

import { FATHER_DAY_RECOMMENDATIONS } from '@/data/memberDemoContent'
import { useSessionStore } from '@/stores/session'

withDefaults(defineProps<{ calendarTo?: string }>(), {
  calendarTo: '/user/calendar',
})

const session = useSessionStore()
const dismissed = ref(false)
const prepared = ref(false)
const displayName = computed(() => session.displayName || '住戶')

function addToPreparationList() {
  prepared.value = true
}
</script>

<template>
  <section
    v-if="!dismissed"
    class="father-day-push panel"
    data-testid="father-day-push"
    aria-labelledby="father-day-push-title"
  >
    <div class="father-day-push-head">
      <div class="father-day-push-icon" aria-hidden="true">💌</div>
      <div class="father-day-push-copy">
        <p class="eyebrow">AI 主動提醒・8/8</p>
        <h2 id="father-day-push-title">父親節快到了，{{ displayName }}要不要先安排一下？</h2>
        <p>我先整理幾個可能有用的服務與送禮方向；這只是推薦，不會直接下單。</p>
        <span class="father-day-meta">資料來源：競賽 Demo 固定事件・不背景追蹤位置</span>
      </div>
    </div>

    <div class="father-day-recommendations" aria-label="父親節推薦">
      <article
        v-for="item in FATHER_DAY_RECOMMENDATIONS"
        :key="item.id"
        class="father-day-recommendation"
        :data-kind="item.category"
        data-testid="father-day-recommendation"
      >
        <span class="father-day-recommendation-label">{{ item.label }}</span>
        <h3>{{ item.title }}</h3>
        <p>{{ item.detail }}</p>
        <strong>{{ item.priceLabel }}</strong>
        <RouterLink class="button inline" :to="item.to">{{ item.actionLabel }}</RouterLink>
      </article>
    </div>

    <div class="father-day-push-actions">
      <RouterLink class="button primary" data-testid="father-day-calendar-link" :to="calendarTo">看月曆</RouterLink>
      <RouterLink class="button" to="/user/assistant?need=爸媽週末要來，幫我安排清潔和晚餐">交給 AI 一起安排</RouterLink>
      <button
        class="button"
        type="button"
        data-testid="father-day-prepare"
        :aria-pressed="prepared"
        @click="addToPreparationList"
      >{{ prepared ? '已加入準備清單' : '加入準備清單' }}</button>
      <button class="text-button" type="button" data-testid="father-day-snooze" @click="dismissed = true">稍後提醒</button>
    </div>
  </section>
</template>

<style scoped>
.father-day-push {
  display: grid;
  gap: 1rem;
  border-color: var(--ink);
  background: var(--yellow, #fde68a);
}
.father-day-push-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
.father-day-push-icon {
  font-size: 2.25rem;
  line-height: 1;
}
.father-day-push-copy {
  min-width: 0;
}
.father-day-push-copy h2 {
  margin: 0 0 .35rem;
}
.father-day-push-copy p {
  margin: .2rem 0 .45rem;
}
.father-day-meta {
  color: var(--muted);
  font-size: .78rem;
}
.father-day-recommendations {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: .75rem;
}
.father-day-recommendation {
  display: grid;
  gap: .35rem;
  align-content: start;
  padding: .8rem;
  border: 2px solid var(--ink);
  border-radius: 14px;
  background: var(--surface);
  box-shadow: 2px 2px 0 var(--ink);
}
.father-day-recommendation[data-kind='purchase'] {
  background: var(--peach, #ffd9c9);
}
.father-day-recommendation-label {
  color: var(--muted);
  font-size: .72rem;
  font-weight: 900;
  letter-spacing: .04em;
}
.father-day-recommendation h3 {
  margin: 0;
  font-size: 1rem;
}
.father-day-recommendation p {
  min-height: 3.1em;
  margin: 0;
  color: var(--muted);
  font-size: .82rem;
}
.father-day-recommendation strong {
  font-size: .78rem;
}
.father-day-recommendation .button {
  justify-self: start;
  margin-top: .25rem;
}
.father-day-push-actions {
  display: flex;
  flex-wrap: wrap;
  gap: .55rem;
  align-items: center;
}
.father-day-push-actions .text-button {
  margin-left: auto;
}
@media (max-width: 820px) {
  .father-day-recommendations {
    grid-template-columns: 1fr;
  }
  .father-day-recommendation p {
    min-height: 0;
  }
}
@media (max-width: 520px) {
  .father-day-push-head {
    grid-template-columns: 1fr;
  }
  .father-day-push-actions .text-button {
    margin-left: 0;
  }
}
</style>
