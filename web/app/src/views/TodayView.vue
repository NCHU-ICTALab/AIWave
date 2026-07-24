<script setup lang="ts">
import { useDemoStore } from '@/stores/demo'

const store = useDemoStore()
</script>

<template>
  <header class="page-heading"><div><p class="eyebrow">Individual workspace</p><h1>早安，小圓</h1></div><span class="page-status">今天有 3 件事值得處理</span></header>
  <div class="grid">
    <section class="panel hero"><p class="eyebrow">Today's plan</p><h2>把生活中的零散需求，整理成今天做得到的事。</h2><p>包裹即將到期、咖啡券還有 3 天，週末也有適合清洗冷氣的空檔。</p><div class="button-row"><RouterLink class="button primary inline" to="/app/services">找一項服務</RouterLink><button class="button" type="button">查看今日任務</button></div></section>
    <aside class="panel aside"><h2>本月概況</h2><div class="metric-row"><div class="metric"><span>消費</span><strong>$3,280</strong></div><div class="metric"><span>OPENPOINT</span><strong>426</strong></div><div class="metric"><span>可用優惠</span><strong>8</strong></div><div class="metric"><span>待取包裹</span><strong>1</strong></div></div></aside>
    <section class="panel span-7" aria-labelledby="recommendation-title">
      <template v-if="!store.recommendationDismissed"><p class="eyebrow">Personalized</p><h2 id="recommendation-title">咖啡券快到期，明早使用最順路</h2><p class="muted">依你的咖啡購買時間、券效期與明日行程推薦。</p><details class="reason-details"><summary>為什麼推薦？</summary><ul><li>你平日多在 08:00 前購買 CITY CAFE。</li><li>這張咖啡券將在 3 天後到期。</li><li>明早的常用路線會經過可兌換門市。</li></ul></details><div class="button-row"><button class="button primary" type="button">加入明日提醒</button><button class="button" type="button" @click="store.dismissRecommendation">不感興趣</button></div></template>
      <div v-else class="feedback-state" role="status"><h2>已調整你的偏好</h2><p>之後會減少這類推薦；這不會永久封鎖咖啡相關服務。</p><button class="text-button" type="button" @click="store.undoDismissRecommendation">復原</button></div>
    </section>
    <section class="panel span-5"><p class="eyebrow">Best value</p><h2>這筆補貨可省 NT$ 84</h2><p class="muted">自動比較優惠券、OPENPOINT 與付款方式。</p><button class="button" type="button">查看折扣試算</button></section>
  </div>
</template>
