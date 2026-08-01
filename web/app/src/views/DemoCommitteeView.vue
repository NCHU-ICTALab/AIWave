<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useCommunityDemoStore } from '@/stores/communityDemo'

const demo = useCommunityDemoStore()
const dashboard = computed(() => demo.committeeDashboard)
const publishFeedback = ref('')
const wikiFeedback = ref('')

const chocolateId = 'group-dubai-chocolate-2026-08'
const draft = computed(() => dashboard.value?.draftGroupBuy ?? null)
const chocolate = computed(() => dashboard.value?.groupBuys.find((group) => group.id === chocolateId) ?? null)
const chocolateOrders = computed(() => dashboard.value?.orders.filter((order) => order.groupBuyId === chocolateId) ?? [])
const chocolateHouseholds = computed(() => dashboard.value?.ordersByHousehold.filter((row) => row.items.some((item) => item.groupBuyId === chocolateId)) ?? [])
const chocolateRevenue = computed(() => chocolateOrders.value.reduce((sum, order) => sum + order.amount, 0))

const money = (value: number, decimals = false) => `NT$ ${value.toLocaleString('zh-TW', decimals ? { minimumFractionDigits: 2, maximumFractionDigits: 2 } : undefined)}`

function publishChocolate() {
  demo.publishDemoGroupBuy()
  publishFeedback.value = '杜拜巧克力已發布，住戶端現在看得到這檔團購。'
}

function markForWiki(id: string) {
  demo.markUnansweredForWiki(id)
  wikiFeedback.value = '已標記為待補充，下一次 Wiki 更新可優先處理。'
}

onMounted(() => {
  demo.loadCommittee()
})
</script>

<template>
  <section v-if="dashboard" class="demo-page demo-committee-page">
    <header class="demo-hero demo-hero-committee">
      <div>
        <p class="eyebrow">AI 智慧社區・管委會工作台</p>
        <h1>社區營運工作台</h1>
        <p class="demo-hero-lede">{{ dashboard.community.name }}・{{ dashboard.manager.displayName }}・任期 {{ dashboard.manager.term }}</p>
        <div class="demo-chip-row"><span class="demo-chip demo-chip-mint">訂閱戶數 {{ dashboard.community.households }} 戶</span><span class="demo-chip">開團 → 跟團 → 統計，一份資料即時同步</span></div>
      </div>
      <div class="demo-hero-side"><span class="demo-kicker">管委會的商業價值</span><strong>把訂閱費變成住戶看得見的優惠</strong><span>今日先發布一檔杜拜巧克力</span></div>
    </header>

    <section class="demo-kpi-grid" aria-label="管委會 KPI">
      <article class="demo-kpi-card demo-kpi-blue" data-testid="committee-household-kpi"><span class="demo-kpi-icon" aria-hidden="true">🏢</span><div><strong>{{ dashboard.community.households }}</strong><span>社區戶數</span></div><small>標準方案落在 101–200 戶</small></article>
      <article class="demo-kpi-card demo-kpi-peach" data-testid="committee-open-kpi"><span class="demo-kpi-icon" aria-hidden="true">🛒</span><div><strong>{{ dashboard.kpis.openGroupBuys }}</strong><span>檔團購進行中</span></div><small>進度與門檻即時同步</small></article>
      <article class="demo-kpi-card demo-kpi-mint" data-testid="committee-revenue-kpi"><span class="demo-kpi-icon" aria-hidden="true">💰</span><div><strong>{{ money(dashboard.kpis.groupBuyRevenue) }}</strong><span>團購成交額</span></div><small>本檔杜拜巧克力 {{ money(chocolateRevenue) }}</small></article>
      <article class="demo-kpi-card demo-kpi-lilac" data-testid="committee-savings-kpi"><span class="demo-kpi-icon" aria-hidden="true">✨</span><div><strong>{{ money(dashboard.kpis.savedForResidents) }}</strong><span>本月住戶省下</span></div><small>訂閱回饋的可見成果</small></article>
    </section>

    <section class="panel demo-panel demo-publish-panel" data-testid="publish-group-buy-panel" aria-labelledby="publish-group-buy-title">
      <div class="demo-section-heading"><div><p class="eyebrow">STEP 1・PUBLISH</p><h2 id="publish-group-buy-title">發布一檔示範團購</h2></div><span class="demo-count-badge">{{ draft ? '草稿已備妥' : '已發布' }}</span></div>
      <p class="demo-panel-lede">商品資料預先備妥，主委只要確認商業條件就能發布；發布後住戶端立即讀取同一份資料。</p>
      <div class="demo-product-card">
        <div class="demo-product-main"><span class="demo-product-icon" aria-hidden="true">🍫</span><div><h3>杜拜巧克力</h3><p>外部廠商：可可日常食品・預計 8/7 到貨・取貨地點：{{ (draft ?? chocolate)?.pickupLocation ?? '社區管理室' }}</p></div></div>
        <dl class="demo-product-specs">
          <div><dt>市價</dt><dd>{{ money((draft ?? chocolate)?.marketPrice ?? 149) }}</dd></div>
          <div><dt>社區價</dt><dd>單入 {{ money((draft ?? chocolate)?.variants[0]?.price ?? 135) }}<br />六入 {{ money((draft ?? chocolate)?.variants[1]?.price ?? 780) }}</dd></div>
          <div><dt>成團門檻</dt><dd>{{ (draft ?? chocolate)?.thresholdUnits ?? 10 }} 個跟團單位</dd></div>
          <div><dt>廠商抽成</dt><dd>外部 3%<br />集團商品 0%</dd></div>
        </dl>
      </div>
      <div class="demo-product-progress"><span>發布後初始進度固定為</span><strong>{{ (draft ?? chocolate)?.progressUnits ?? 7 }}/10</strong><span>・截止 {{ (draft ?? chocolate)?.closeAt?.slice(0, 16).replace('T', ' ') ?? '2026-08-06 21:00' }}</span></div>
      <button v-if="draft" class="button primary demo-wide-button" data-testid="publish-dubai-group-buy" type="button" @click="publishChocolate">發布杜拜巧克力開團</button>
      <p v-else class="demo-success" data-testid="publish-feedback" role="status">{{ publishFeedback || '已發布，等待住戶跟團。' }}</p>
      <p v-if="draft && publishFeedback" class="demo-success" data-testid="publish-feedback" role="status">{{ publishFeedback }}</p>
    </section>

    <div class="demo-two-column">
      <section class="panel demo-panel" data-testid="committee-orders" aria-labelledby="committee-orders-title">
        <div class="demo-section-heading"><div><p class="eyebrow">STEP 2・ORDER SUMMARY</p><h2 id="committee-orders-title">訂單彙總</h2></div><span class="demo-count-badge">{{ chocolateOrders.length }} 筆本檔訂單</span></div>
        <div v-if="!chocolateOrders.length" class="demo-empty"><strong>住戶跟團後，這裡會即時出現整單彙總。</strong><span>先切換到住戶王小明，選擇六入 × 1 並送出。</span></div>
        <template v-else>
          <div v-for="row in chocolateHouseholds" :key="row.householdId" class="demo-order-household" data-testid="committee-household-order">
            <div><strong>{{ row.displayName }}</strong><span class="demo-meta">{{ row.householdLabel }}</span></div>
            <div v-for="item in row.items.filter((entry) => entry.groupBuyId === chocolateId)" :key="item.id" class="demo-order-item"><span>{{ item.variantLabel }} × {{ item.quantity }}</span><strong>{{ money(item.amount) }}</strong></div>
            <div class="demo-order-total"><span>住戶小計</span><strong>{{ money(row.amount) }}</strong></div>
          </div>
          <div class="demo-order-summary-row"><span>依規格彙總</span><span v-for="variant in dashboard.variantSummary.filter((item) => chocolateOrders.some((order) => order.variantLabel === item.variantLabel))" :key="variant.variantLabel">{{ variant.variantLabel }} {{ variant.quantity }} 組・{{ money(variant.amount) }}</span></div>
          <div class="demo-highlight-metric"><span>本檔杜拜巧克力成交額</span><strong data-testid="chocolate-revenue">{{ money(chocolateRevenue) }}</strong></div>
        </template>
      </section>

      <section class="panel demo-panel" aria-labelledby="commission-title">
        <div class="demo-section-heading"><div><p class="eyebrow">STEP 3・ECONOMICS</p><h2 id="commission-title">分潤試算</h2></div><span class="demo-count-badge">透明規則</span></div>
        <div class="demo-economics-grid"><div><span>外部廠商</span><strong>3%</strong><small>本檔估算 {{ money(dashboard.kpis.externalCommission, true) }}</small></div><div><span>統一集團商品</span><strong>0%</strong><small>以價格優勢回饋社區</small></div></div>
        <ul class="demo-check-list"><li>管委會付月訂閱費，平台負責資料與流程。</li><li>訂閱費的一部分回饋成住戶社區優惠。</li><li>不需要硬體、施工或重新登入 LINE Bot。</li></ul>
      </section>
    </div>

    <section class="panel demo-panel" data-testid="wiki-management-summary" aria-labelledby="wiki-management-title">
      <div class="demo-section-heading"><div><p class="eyebrow">WIKI MANAGEMENT</p><h2 id="wiki-management-title">Wiki 管理摘要</h2></div><span class="demo-count-badge">{{ dashboard.wiki.unanswered.length }} 個待處理</span></div>
      <div class="demo-three-column demo-wiki-grid">
        <div><h3>查詢次數排行</h3><ol class="demo-ranking-list"><li v-for="item in dashboard.wiki.queryRanking.slice(0, 4)" :key="item.query"><span>{{ item.query }}</span><strong>{{ item.count }} 次</strong></li></ol></div>
        <div><h3>最新被詢問問題</h3><ul class="demo-list demo-compact-list"><li v-for="item in dashboard.wiki.latestQueries.slice(0, 4)" :key="item"><span>{{ item }}</span></li></ul></div>
        <div><h3>未回答問題</h3><p v-if="wikiFeedback" class="demo-success" role="status">{{ wikiFeedback }}</p><ul v-if="dashboard.wiki.unanswered.length" class="demo-list demo-compact-list"><li v-for="item in dashboard.wiki.unanswered" :key="item.id"><div><strong>{{ item.query }}</strong><span class="demo-meta">{{ item.askedAt }}</span></div><button v-if="item.status === 'new'" class="button" type="button" :data-testid="`mark-wiki-${item.id}`" @click="markForWiki(item.id)">標記待補充</button><span v-else class="status">待補充</span></li></ul><p v-else class="demo-empty">目前沒有未回答問題。</p></div>
      </div>
    </section>

    <section class="demo-business-cta" data-testid="subscription-cta">
      <div><p class="eyebrow">STEP 4・SUBSCRIPTION</p><h2>最後用一張帳務卡，說清楚這個模式</h2><p>112 戶社區適用標準月費 NT$12,000；Demo 試辦優惠是另一個清楚標示的價格。</p></div>
      <RouterLink class="button primary" to="/demo/subscription">查看訂閱與帳務 →</RouterLink>
    </section>
  </section>
  <section v-else class="panel demo-loading" role="status">正在整理管委會工作台…</section>
</template>
