<script setup lang="ts">
import { computed, ref } from 'vue'

import { COMMUNITY_DEMO_SEED, SUBSCRIPTION_TIERS } from '@/data/communityDemoSeed'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const feedback = ref('')

/**
 * 方案價格與管委會端的 `/demo/subscription` 共用同一份 seed。
 * 兩頁各寫一次數字的話，住戶看到的月費隨時可能跟主委看到的對不起來。
 * 月費本身是從社區戶數對照 `SUBSCRIPTION_TIERS` 得出，這裡不寫死金額。
 */
const plan = COMMUNITY_DEMO_SEED.subscription
const tiers = SUBSCRIPTION_TIERS
const money = (value: number) => `NT$ ${value.toLocaleString('zh-TW')}`
/** 最高一級沒有固定價格，型別是 `number | null`，畫面要說「客製報價」。 */
const feeLabel = (value: number | null) => (value === null ? '客製報價' : money(value))
const planFeeLabel = computed(() => feeLabel(plan.monthlyFee))

const featureRows = [
  { id: 'group-buy', label: '社區團購列表、開團與跟團', free: true, subscriber: true },
  { id: 'wiki', label: '公告與社區生活 Wiki', free: false, subscriber: true },
  { id: 'life-circle', label: '生活圈地圖與附近服務', free: false, subscriber: true },
  { id: 'ai', label: 'AI 管家自然語言安排服務', free: false, subscriber: true },
  { id: 'calendar', label: '行事曆、提醒與通知整合', free: false, subscriber: true },
  { id: 'benefit', label: '訂閱回饋的社區優惠服務', free: false, subscriber: true },
] as const

const currentPlanLabel = computed(() => session.isSubscriber ? 'VIP 訂閱社區' : '免費社區')

function upgrade() {
  session.upgradeMembership()
  feedback.value = 'Demo 已啟用 VIP 訂閱社區；所有住戶功能現在都已解鎖。'
}
</script>

<template>
  <section class="member-page subscription-page" data-testid="subscription-page">
    <header class="page-heading subscription-heading">
      <div>
        <p class="eyebrow">COMMUNITY MEMBERSHIP</p>
        <h1>選擇你的社區身分</h1>
        <p class="page-lead">免費會員可以參加團購；社區訂閱後，AI、生活圈、Wiki 與優惠服務一起解鎖。</p>
      </div>
      <div class="subscription-current" data-testid="current-membership">
        <span aria-hidden="true">{{ session.isSubscriber ? '♛' : '○' }}</span>
        <div><small>目前身分</small><strong>{{ currentPlanLabel }}</strong></div>
      </div>
    </header>

    <section class="subscription-plan-grid" aria-label="社區方案">
      <article class="panel subscription-plan-card free-plan" data-testid="free-plan-card">
        <p class="eyebrow">START HERE</p>
        <h2>免費社區</h2>
        <p class="subscription-plan-price">NT$ 0 <small>/ 住戶</small></p>
        <p>先用團購感受社區一起買的價值，不需要等待社區完成訂閱。</p>
        <ul class="subscription-feature-list">
          <li><span aria-hidden="true">✓</span>瀏覽統一商品與社區團購</li>
          <li><span aria-hidden="true">✓</span>任何住戶都可以開團</li>
          <li class="locked"><span aria-hidden="true">🔒</span>其餘社區智慧功能顯示訂閱解鎖</li>
        </ul>
        <RouterLink class="button" to="/user/community/group-buys">前往社區團購</RouterLink>
      </article>

      <article class="panel subscription-plan-card vip-plan" data-testid="subscriber-plan-card">
        <span class="subscription-recommended">日光森林目前方案</span>
        <p class="eyebrow">COMMUNITY VIP</p>
        <h2>訂閱社區</h2>
        <p class="subscription-plan-price">{{ planFeeLabel }} <small>/ 月・{{ plan.tier.sizeLabel }}</small></p>
        <p>由管委會以社區方案訂閱（日光森林 {{ plan.householdCount }} 戶，{{ plan.tier.perHouseholdLabel }}），住戶不個別付費，享有回饋價與完整 AI 生活服務。</p>
        <div class="subscription-trial"><strong>導入期免費試用</strong><span>{{ plan.trialMonths }}，再由社區決定要不要開始付月費。</span></div>
        <ul class="subscription-feature-list">
          <li v-for="feature in featureRows" :key="feature.id"><span aria-hidden="true">✓</span>{{ feature.label }}</li>
        </ul>
        <button v-if="!session.isSubscriber" class="button primary" type="button" data-testid="upgrade-membership" @click="upgrade">模擬啟用 VIP</button>
        <span v-else class="subscription-active" data-testid="subscription-active">♛ 目前已解鎖完整功能</span>
      </article>
    </section>

    <p v-if="feedback" class="panel subscription-feedback" role="status" data-testid="subscription-feedback">{{ feedback }}</p>

    <section class="panel subscription-comparison" aria-labelledby="subscription-pricing-title" data-testid="subscription-pricing-tiers">
      <div class="section-title-row">
        <div><p class="eyebrow">PRICING BY SIZE</p><h2 id="subscription-pricing-title">月費依社區戶數分級</h2></div>
        <span class="muted">日光森林 {{ plan.householdCount }} 戶</span>
      </div>
      <div class="subscription-table-wrap">
        <table data-testid="subscription-tier-table">
          <caption class="visually-hidden">社區訂閱月費級距表，依社區戶數分級</caption>
          <thead><tr><th scope="col">社區戶數</th><th scope="col">月費</th><th scope="col">平均每戶</th><th scope="col">目前方案</th></tr></thead>
          <tbody>
            <tr v-for="tier in tiers" :key="tier.id" :class="{ current: tier.id === plan.tier.id }">
              <th scope="row">{{ tier.sizeLabel }}</th>
              <td>{{ feeLabel(tier.monthlyFee) }}<span v-if="tier.monthlyFee !== null"> / 月</span></td>
              <td>{{ tier.perHouseholdLabel }}</td>
              <td><span v-if="tier.id === plan.tier.id" class="subscription-tier-badge">目前方案</span><span v-else aria-hidden="true">—</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="subscription-note">訂閱由管委會以社區為單位購買，住戶不個別付費；500 戶以上的社區採客製報價。</p>
    </section>

    <section class="panel subscription-comparison" aria-labelledby="subscription-comparison-title">
      <div class="section-title-row">
        <div><p class="eyebrow">FEATURE ACCESS</p><h2 id="subscription-comparison-title">功能解鎖一眼看懂</h2></div>
        <span class="muted">目前：{{ currentPlanLabel }}</span>
      </div>
      <div class="subscription-table-wrap">
        <table data-testid="subscription-feature-table">
          <caption class="visually-hidden">免費社區與訂閱社區功能比較</caption>
          <thead><tr><th scope="col">功能</th><th scope="col">免費</th><th scope="col">VIP 訂閱</th></tr></thead>
          <tbody>
            <tr v-for="feature in featureRows" :key="feature.id">
              <th scope="row">{{ feature.label }}</th>
              <td :class="{ locked: !feature.free }">{{ feature.free ? '可使用' : '訂閱解鎖' }}</td>
              <td>{{ feature.subscriber ? '可使用' : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p class="subscription-note">方案價格是競賽 Demo 的商業模型示意（competition_seed），不是統一集團的正式報價：月費依社區戶數分級、由管委會付費，住戶不會被誤認為個人付費。</p>
  </section>
</template>

<style scoped>
.subscription-page { display: grid; gap: var(--space-5, 1.25rem); width: min(100%, 76rem); }
.subscription-heading { align-items: center; }
.subscription-heading h1 { margin-bottom: .35rem; }
.subscription-current { display: flex; align-items: center; gap: .55rem; min-width: 11rem; padding: .75rem 1rem; border: 2px solid var(--ink); border-radius: var(--radius-md); background: var(--yellow, #fde68a); box-shadow: 3px 3px 0 var(--ink); }
.subscription-current > span { font-size: 1.8rem; }
.subscription-current div { display: grid; gap: .1rem; }
.subscription-current small { color: var(--muted); font-size: .7rem; }
.subscription-current strong { font-size: .9rem; }
.subscription-plan-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-5, 1.25rem); align-items: stretch; }
.subscription-plan-card { position: relative; display: grid; align-content: start; gap: .7rem; }
.subscription-plan-card h2, .subscription-plan-card p { margin: 0; }
.subscription-plan-card > p:not(.eyebrow):not(.subscription-plan-price) { color: var(--muted); }
.subscription-plan-price { color: var(--primary); font: 900 clamp(1.8rem, 4vw, 2.8rem)/1 var(--font-mono); }
.subscription-plan-price small { color: var(--muted); font: 800 .75rem/1.2 var(--font-sans, sans-serif); }
.free-plan { background: var(--surface); }
.vip-plan { border-color: var(--ink); background: var(--mint); }
.subscription-recommended { position: absolute; top: .85rem; right: .85rem; padding: .2rem .45rem; border: 1px solid var(--ink); border-radius: 999px; background: var(--yellow, #fde68a); font-size: .68rem; font-weight: 900; }
.subscription-feature-list { display: grid; gap: .45rem; margin: .25rem 0; padding: 0; list-style: none; }
.subscription-feature-list li { display: flex; gap: .45rem; align-items: flex-start; font-size: .82rem; font-weight: 750; }
.subscription-feature-list li > span { flex: 0 0 auto; }
.subscription-feature-list .locked { color: var(--muted); }
.subscription-trial { display: grid; gap: .2rem; padding: .65rem .75rem; border: 2px dashed var(--ink); border-radius: 12px; background: var(--peach); }
.subscription-trial strong { font-size: .88rem; }
.subscription-trial span { color: var(--muted); font-size: .75rem; }
.subscription-active { display: inline-flex; align-items: center; width: fit-content; min-height: var(--tap); padding: .45rem .75rem; border: 2px solid var(--ink); border-radius: 12px; background: var(--yellow, #fde68a); font-weight: 900; }
.subscription-feedback { margin: 0; background: var(--mint); font-weight: 800; }
.subscription-comparison { display: grid; gap: .8rem; }
.subscription-comparison h2 { margin: .1rem 0 0; }
.subscription-table-wrap { overflow-x: auto; }
.subscription-table-wrap table { width: 100%; min-width: 34rem; border-collapse: collapse; }
.subscription-table-wrap th, .subscription-table-wrap td { padding: .7rem .75rem; border-bottom: 1px solid color-mix(in srgb, var(--ink) 22%, transparent); text-align: left; }
.subscription-table-wrap thead th { background: var(--surface-2); font-size: .78rem; }
.subscription-table-wrap tbody th { font-size: .82rem; }
.subscription-table-wrap td { color: #176245; font-size: .78rem; font-weight: 850; }
.subscription-table-wrap td.locked { color: var(--muted); }
/* 目前級距不能只靠底色標示;每一列都另外有「目前方案」文字徽章。 */
.subscription-table-wrap tbody tr.current { background: var(--mint); }
.subscription-table-wrap tbody tr.current th, .subscription-table-wrap tbody tr.current td { font-weight: 900; }
.subscription-tier-badge { display: inline-flex; align-items: center; padding: .15rem .5rem; border: 2px solid var(--ink); border-radius: 999px; background: var(--yellow, #fde68a); color: var(--ink); font-size: .7rem; font-weight: 900; }
.subscription-note { margin: 0; color: var(--muted); font-size: .78rem; }
@media (max-width: 720px) {
  .subscription-heading { align-items: flex-start; }
  .subscription-plan-grid { grid-template-columns: 1fr; }
  .subscription-current { width: fit-content; }
}
</style>
