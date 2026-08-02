<script setup lang="ts">
import { computed } from 'vue'

/**
 * 付費功能的霧面遮罩：讓免費社區「看得到但用不到」。
 *
 * 直接把內容藏起來，住戶不知道訂閱換到什麼；整段模糊掉又會出事——
 * **模糊只是視覺**：螢幕閱讀器照唸，Tab 也照樣跳得進去看不見的按鈕，
 * 等於鎖了個寂寞，還踩到 WCAG 2.4.11（焦點不可見）。
 *
 * 所以被鎖的內容一律 `inert`（同時擋掉焦點與 a11y tree，瀏覽器原生行為），
 * 解鎖卡片才是這一區唯一可互動、也是唯一被唸出來的東西。
 */
const props = withDefaults(defineProps<{
  /** 這一區是什麼功能，會唸成「XXX 需要社區訂閱」。 */
  title: string
  /**
   * 要不要上鎖。預設 true，但傳 `:locked="!session.isSubscriber"` 才是常用寫法——
   * 未上鎖時直接把 slot 原樣渲染出去，呼叫端就不必為了兩種狀態寫兩份一樣的內容
   * （寫兩份的下場是改了一份忘了另一份）。
   */
  locked?: boolean
  /** 一句話說明訂閱後可以做什麼。 */
  description?: string
  /** 標題層級：巢狀在頁面區塊裡時用 3，整頁遮罩時用 2。 */
  headingLevel?: 2 | 3
  /** 整頁遮罩會給更高的最小高度，避免只有一條。 */
  variant?: 'section' | 'page'
}>(), {
  locked: true,
  description: '這是訂閱社區的功能。社區完成訂閱後就會解鎖，免費社區仍可使用社區團購。',
  headingLevel: 3,
  variant: 'section',
})

const headingTag = computed(() => `h${props.headingLevel}` as 'h2' | 'h3')
</script>

<template>
  <slot v-if="!locked" />

  <div v-else class="subscription-lock" :class="`is-${variant}`" data-testid="subscription-lock">
    <!--
      inert 讓整棵子樹退出焦點順序與 a11y tree；Vue 需要 `.prop` 才會設成
      DOM property 而不是字串屬性（happy-dom 與瀏覽器都吃這個）。
    -->
    <div class="subscription-lock-content" :inert.prop="true" aria-hidden="true">
      <slot />
    </div>

    <div class="subscription-lock-overlay">
      <div class="subscription-lock-card" data-testid="subscription-lock-card">
        <span class="subscription-lock-icon" aria-hidden="true">🔒</span>
        <component :is="headingTag" class="subscription-lock-title">{{ title }}・需要社區訂閱</component>
        <p>{{ description }}</p>
        <div class="subscription-lock-actions">
          <RouterLink class="button primary" to="/user/subscription">查看訂閱方案</RouterLink>
          <RouterLink class="button" to="/user/community/group-buys">先去逛社區團購</RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.subscription-lock {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border-radius: var(--radius-md, 18px);
}
.subscription-lock.is-page {
  min-height: 26rem;
}
.subscription-lock-content {
  filter: blur(6px) saturate(.75);
  opacity: .5;
  pointer-events: none;
  user-select: none;
}
.subscription-lock-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 1rem;
  /* 霧面：色彩來自底下的內容，但文字必須落在不透明卡片上才讀得清楚。 */
  background: color-mix(in srgb, var(--bg, #fff9f5) 62%, transparent);
}
.subscription-lock-card {
  display: grid;
  justify-items: center;
  gap: .55rem;
  width: min(100%, 26rem);
  padding: 1.1rem 1.25rem;
  border: var(--border-chunky, 3px) solid var(--ink);
  border-radius: var(--radius-md, 18px);
  /* 不透明底：色彩對比必須靠卡片本身成立，不能靠背後那層模糊。 */
  background: var(--surface, #fff);
  box-shadow: var(--shadow, 4px 4px 0 var(--ink));
  text-align: center;
}
.subscription-lock-icon {
  display: grid;
  place-items: center;
  width: 2.6rem;
  height: 2.6rem;
  border: 2px solid var(--ink);
  border-radius: 50%;
  background: var(--yellow, #fde68a);
  font-size: 1.3rem;
}
.subscription-lock-title {
  margin: 0;
  font-size: 1.02rem;
}
.subscription-lock-card p {
  margin: 0;
  color: var(--muted);
  font-size: .82rem;
  line-height: 1.5;
}
.subscription-lock-actions {
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  justify-content: center;
  margin-top: .15rem;
}
/* 動態模糊對前庭敏感的使用者不友善；改用純粹的低透明度。 */
@media (prefers-reduced-motion: reduce) {
  .subscription-lock-content { filter: none; opacity: .35; }
}
/* 高對比模式下模糊會讓底層變成一團噪點，直接收掉。 */
@media (prefers-contrast: more) {
  .subscription-lock-content { filter: none; opacity: .25; }
  .subscription-lock-overlay { background: var(--bg, #fff9f5); }
}
@media (max-width: 640px) {
  .subscription-lock-actions .button { width: 100%; }
}
</style>
