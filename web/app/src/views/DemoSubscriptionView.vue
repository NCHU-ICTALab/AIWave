<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useCommunityDemoStore } from '@/stores/communityDemo'

const demo = useCommunityDemoStore()
const summary = computed(() => demo.subscription)
const money = (value: number) => `NT$ ${value.toLocaleString('zh-TW')}`
/** 最高一級沒有固定價格，畫面上必須說「客製報價」而不是假裝有金額。 */
const feeLabel = computed(() => {
  const fee = summary.value?.monthlyFee
  return fee === null || fee === undefined ? '客製報價' : money(fee)
})

onMounted(() => {
  demo.getSubscriptionSummary()
})
</script>

<template>
  <section v-if="summary" class="demo-page demo-subscription-page">
    <div class="demo-back-row"><RouterLink class="demo-text-button" to="/demo/committee">← 回管委會工作台</RouterLink><span class="demo-kicker">BUSINESS MODEL</span></div>
    <header class="demo-hero demo-hero-subscription">
      <div><p class="eyebrow">AI 智慧社區・訂閱與帳務</p><h1>讓社區優惠成為訂閱的成果</h1><p class="demo-hero-lede">日光森林有 {{ summary.householdCount }} 戶，月費依戶數分級，級距與住戶省下的金額分開呈現，數字才不會互相矛盾。</p></div>
      <div class="demo-hero-side"><span class="demo-kicker">本月淨效益</span><strong>+{{ money(summary.netBenefit) }}</strong><span>住戶省下 − 訂閱月費</span></div>
    </header>

    <section class="demo-subscription-grid" data-testid="subscription-pricing">
      <article class="panel demo-plan-card"><p class="eyebrow">社區方案</p><h2>{{ summary.tier.sizeLabel }}</h2><strong class="demo-big-price">{{ feeLabel }}<small>／月</small></strong><p>{{ summary.householdCount }} 戶落在這個級距，平均{{ summary.tier.perHouseholdLabel }}。</p><span class="demo-plan-label">訂閱月費</span></article>
      <article class="panel demo-plan-card demo-plan-highlight"><p class="eyebrow">導入期</p><h2>免費試用</h2><strong class="demo-big-price">NT$ 0<small>／月</small></strong><p>{{ summary.trialMonths }}；試用期結束後才回到 {{ feeLabel }}／月的級距價。</p><span class="demo-plan-label">先試再決定</span></article>
    </section>

    <section class="panel demo-panel demo-benefit-panel" aria-labelledby="benefit-title">
      <div class="demo-section-heading"><div><p class="eyebrow">THE LOOP</p><h2 id="benefit-title">訂閱費如何回到住戶身上？</h2></div><span class="demo-count-badge">{{ summary.householdCount }} 戶社區</span></div>
      <div class="demo-benefit-flow"><div><span class="demo-flow-number">1</span><strong>管委會訂閱</strong><span>平台提供公告、Wiki、團購與彙總。</span></div><div class="demo-flow-arrow" aria-hidden="true">→</div><div><span class="demo-flow-number">2</span><strong>形成社區優惠</strong><span>本月住戶累計省下 {{ money(summary.residentSavings) }}。</span></div><div class="demo-flow-arrow" aria-hidden="true">→</div><div class="demo-benefit-result"><span class="demo-flow-number">3</span><strong>社區淨效益</strong><strong>+{{ money(summary.netBenefit) }}</strong><span>{{ money(summary.residentSavings) }} − {{ feeLabel }}</span></div></div>
      <p class="demo-meta">淨效益用級距月費 {{ feeLabel }} 保守計算；試用期間社區實際不付費，效益只會更高。</p>
    </section>

    <div class="demo-two-column">
      <section class="panel demo-panel" data-testid="commission-rules" aria-labelledby="commission-rules-title"><div class="demo-section-heading"><div><p class="eyebrow">TRANSACTION RULES</p><h2 id="commission-rules-title">成交分潤規則</h2></div><span class="demo-count-badge">清楚可驗證</span></div><div class="demo-rule-grid"><div><strong>{{ Math.round(summary.externalSupplierFeeRate * 100) }}%</strong><span>外部廠商成交抽成</span></div><div><strong>{{ Math.round(summary.groupSupplierFeeRate * 100) }}%</strong><span>統一集團商品抽成</span></div></div><ul class="demo-check-list"><li>外部廠商透過平台成交時抽成 3%。</li><li>統一集團商品免抽成，因此具有價格優勢。</li><li>交易規則與住戶看到的價格同一套資料。</li></ul></section>
      <section class="panel demo-panel" aria-labelledby="implementation-title"><div class="demo-section-heading"><div><p class="eyebrow">LOW FRICTION</p><h2 id="implementation-title">導入門檻</h2></div><span class="demo-count-badge">先試再決定</span></div><div class="demo-friction-card"><strong>{{ summary.hardware }}</strong><p>純軟體、零硬體、免施工。住戶可從 Web 使用，未來 LINE Bot 讀取同一份 typed service 資料邊界。</p><span class="demo-chip demo-chip-mint">{{ summary.trialMonths }}</span></div></section>
    </div>

    <footer class="demo-final-note"><span class="demo-product-icon" aria-hidden="true">🌱</span><div><strong>日光森林社區的故事很簡單：</strong><p>管委會用可負擔的訂閱費換到可管理的工具，住戶用得到優惠，平台在真實成交時才產生抽成。</p><p class="demo-meta">價目表與省下金額是競賽 Demo 的商業模型示意（competition_seed），不是統一集團的正式報價。</p></div><RouterLink class="button" to="/demo/resident">回到住戶首頁</RouterLink></footer>
  </section>
  <section v-else class="panel demo-loading" role="status">正在整理訂閱試算…</section>
</template>
