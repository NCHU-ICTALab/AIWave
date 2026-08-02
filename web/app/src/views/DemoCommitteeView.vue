<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import type { DemoGroupBuyVariant } from '@/domain/communityDemo'
import { useCommunityDemoStore } from '@/stores/communityDemo'

const demo = useCommunityDemoStore()
const route = useRoute()
const dashboard = computed(() => demo.committeeDashboard)
const publishFeedback = ref('')
const wikiFeedback = ref('')
const manageFeedback = ref('')
const manageError = ref('')

const chocolateId = 'group-dubai-chocolate-2026-08'
const draft = computed(() => dashboard.value?.draftGroupBuy ?? null)
const chocolate = computed(() => dashboard.value?.groupBuys.find((group) => group.id === chocolateId) ?? null)
const chocolateOrders = computed(() => dashboard.value?.orders.filter((order) => order.groupBuyId === chocolateId) ?? [])
const chocolateHouseholds = computed(() => dashboard.value?.ordersByHousehold.filter((row) => row.items.some((item) => item.groupBuyId === chocolateId)) ?? [])
const chocolateRevenue = computed(() => chocolateOrders.value.reduce((sum, order) => sum + order.amount, 0))
const editableGroup = computed(() => draft.value ?? chocolate.value)
const editableName = ref('')
const editableMarketPrice = ref(149)
const editableThresholdUnits = ref(10)
const editablePickupLocation = ref('社區管理室')
const editableExpectedArrival = ref('2026-08-07')
const editableCloseAt = ref('2026-08-06T21:00')
const editableSupplierType = ref<'external' | 'group'>('external')
const editableSupplierName = ref('可可日常食品')
const editableVariants = ref<DemoGroupBuyVariant[]>([])
const prefillNotice = ref('')
const prefillApplied = ref(false)

function queryText(key: string) {
  return typeof route.query[key] === 'string' ? route.query[key] as string : ''
}

function queryVariants(): DemoGroupBuyVariant[] {
  const raw = queryText('variants')
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is DemoGroupBuyVariant => (
      Boolean(item) && typeof item === 'object'
      && typeof (item as DemoGroupBuyVariant).id === 'string'
      && typeof (item as DemoGroupBuyVariant).label === 'string'
      && typeof (item as DemoGroupBuyVariant).price === 'number'
    ))
  } catch {
    return []
  }
}

watch(editableGroup, (group) => {
  if (!group) return
  editableName.value = group.name
  editableMarketPrice.value = group.marketPrice
  editableThresholdUnits.value = group.thresholdUnits
  editablePickupLocation.value = group.pickupLocation
  editableExpectedArrival.value = group.expectedArrival
  editableCloseAt.value = group.closeAt.slice(0, 16)
  editableSupplierType.value = group.supplierType
  editableSupplierName.value = group.supplierName
  editableVariants.value = group.variants.map((variant) => ({ ...variant }))

  if (route.query.prefill === 'catalog' && !prefillApplied.value) {
    const name = queryText('name')
    const marketPrice = Number(queryText('marketPrice'))
    const thresholdUnits = Number(queryText('thresholdUnits'))
    if (name) editableName.value = name
    if (Number.isFinite(marketPrice) && marketPrice > 0) editableMarketPrice.value = marketPrice
    if (Number.isInteger(thresholdUnits) && thresholdUnits > 0) editableThresholdUnits.value = thresholdUnits
    if (queryText('pickupLocation')) editablePickupLocation.value = queryText('pickupLocation')
    if (queryText('expectedArrival')) editableExpectedArrival.value = queryText('expectedArrival')
    if (queryText('closeAt')) editableCloseAt.value = queryText('closeAt').slice(0, 16)
    if (queryText('supplierName')) editableSupplierName.value = queryText('supplierName')
    if (queryText('supplierType') === 'group' || queryText('supplierType') === 'external') editableSupplierType.value = queryText('supplierType') as 'external' | 'group'
    const variants = queryVariants()
    if (variants.length) editableVariants.value = variants.map((variant) => ({ ...variant }))
    prefillApplied.value = true
    prefillNotice.value = '已從商品列表帶入這檔商品；你可以修改條件後再發布。'
  }
}, { immediate: true })

const money = (value: number, decimals = false) => `NT$ ${value.toLocaleString('zh-TW', decimals ? { minimumFractionDigits: 2, maximumFractionDigits: 2 } : undefined)}`

function publishChocolate() {
  demo.publishDemoGroupBuy({
    name: editableName.value,
    marketPrice: editableMarketPrice.value,
    variants: editableVariants.value,
    thresholdUnits: editableThresholdUnits.value,
    pickupLocation: editablePickupLocation.value,
    expectedArrival: editableExpectedArrival.value,
    closeAt: `${editableCloseAt.value}:00+08:00`,
    supplierType: editableSupplierType.value,
    supplierName: editableSupplierName.value,
  })
  publishFeedback.value = `${editableName.value}已發布，住戶端現在看得到這檔團購。`
}

function saveChocolate() {
  manageFeedback.value = ''
  manageError.value = ''
  try {
    demo.updateGroupBuy(chocolateId, {
      name: editableName.value,
      marketPrice: editableMarketPrice.value,
      thresholdUnits: editableThresholdUnits.value,
      pickupLocation: editablePickupLocation.value,
      expectedArrival: editableExpectedArrival.value,
      closeAt: `${editableCloseAt.value}:00+08:00`,
    })
    manageFeedback.value = '團購條件已更新，住戶端會讀取最新資料；規格與供應商會在發布時一起帶入。'
  } catch (reason) {
    manageError.value = reason instanceof Error ? reason.message : '團購條件未能更新。'
  }
}

function changeGroupStatus(groupId: string, action: 'close' | 'reopen') {
  manageFeedback.value = ''
  manageError.value = ''
  try {
    if (action === 'close') demo.closeGroupBuy(groupId)
    else demo.reopenGroupBuy(groupId)
    manageFeedback.value = action === 'close' ? '已結束收單；住戶不能再新增跟團。' : '已重新開放收單；住戶可以繼續跟團。'
  } catch (reason) {
    manageError.value = reason instanceof Error ? reason.message : '團購狀態未能更新。'
  }
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
      <article class="demo-kpi-card demo-kpi-blue" data-testid="committee-household-kpi"><span class="demo-kpi-icon" aria-hidden="true">🏢</span><div><strong>{{ dashboard.community.households }}</strong><span>社區戶數</span></div><small>月費依戶數分級</small></article>
      <article class="demo-kpi-card demo-kpi-peach" data-testid="committee-open-kpi"><span class="demo-kpi-icon" aria-hidden="true">🛒</span><div><strong>{{ dashboard.kpis.openGroupBuys }}</strong><span>檔團購進行中</span></div><small>進度與門檻即時同步</small></article>
      <article class="demo-kpi-card demo-kpi-mint" data-testid="committee-revenue-kpi"><span class="demo-kpi-icon" aria-hidden="true">💰</span><div><strong>{{ money(dashboard.kpis.groupBuyRevenue) }}</strong><span>團購成交額</span></div><small>本檔杜拜巧克力 {{ money(chocolateRevenue) }}</small></article>
      <article class="demo-kpi-card demo-kpi-lilac" data-testid="committee-savings-kpi"><span class="demo-kpi-icon" aria-hidden="true">✨</span><div><strong>{{ money(dashboard.kpis.savedForResidents) }}</strong><span>本月住戶省下</span></div><small>訂閱回饋的可見成果</small></article>
    </section>

    <section class="panel demo-panel demo-publish-panel" data-testid="publish-group-buy-panel" aria-labelledby="publish-group-buy-title">
      <div class="demo-section-heading"><div><p class="eyebrow">STEP 1・PUBLISH</p><h2 id="publish-group-buy-title">發布一檔示範團購</h2></div><span class="demo-count-badge">{{ draft ? '草稿已備妥' : '已發布' }}</span></div>
        <p class="demo-panel-lede">商品資料可以從住戶商品列表帶入，主委確認或修改商業條件後就能發布；發布後住戶端立即讀取同一份資料。</p>
      <p v-if="prefillNotice" class="demo-success" data-testid="group-buy-prefill-notice" role="status">{{ prefillNotice }}</p>
      <div class="demo-product-card">
        <div class="demo-product-main"><span class="demo-product-icon" aria-hidden="true">🛒</span><div><h3>{{ editableName || (draft ?? chocolate)?.name || '新的社區團購' }}</h3><p>{{ editableSupplierType === 'external' ? '外部廠商' : '集團商品' }}：{{ editableSupplierName }}・預計 {{ editableExpectedArrival }} 到貨・取貨地點：{{ editablePickupLocation }}</p></div></div>
        <dl class="demo-product-specs">
          <div><dt>市價</dt><dd>{{ money(editableMarketPrice) }}</dd></div>
          <div><dt>社區價</dt><dd v-for="variant in editableVariants" :key="variant.id">{{ variant.label }} {{ money(variant.price) }}</dd></div>
          <div><dt>成團門檻</dt><dd>{{ editableThresholdUnits }} 個跟團單位</dd></div>
          <div><dt>廠商抽成</dt><dd>{{ editableSupplierType === 'external' ? '外部 3%' : '集團商品 0%' }}</dd></div>
        </dl>
      </div>
      <div class="demo-product-progress"><span>發布後初始進度固定為</span><strong>{{ (draft ?? chocolate)?.progressUnits ?? 7 }}/{{ editableThresholdUnits }}</strong><span>・截止 {{ editableCloseAt.replace('T', ' ') }}</span></div>
      <div class="demo-edit-grid" data-testid="group-buy-editor">
        <label><span>團購名稱</span><input v-model="editableName" data-testid="group-buy-name" type="text" /></label>
        <label><span>市價</span><input v-model.number="editableMarketPrice" data-testid="group-buy-market-price" type="number" min="1" /></label>
        <label><span>成團門檻</span><input v-model.number="editableThresholdUnits" data-testid="group-buy-threshold" type="number" min="1" /></label>
        <label><span>預計到貨</span><input v-model="editableExpectedArrival" data-testid="group-buy-expected-arrival" type="date" /></label>
        <label><span>收單截止</span><input v-model="editableCloseAt" data-testid="group-buy-close-at" type="datetime-local" /></label>
        <label><span>取貨地點</span><input v-model="editablePickupLocation" data-testid="group-buy-pickup" type="text" /></label>
        <label><span>供應商</span><input v-model="editableSupplierName" data-testid="group-buy-supplier" type="text" /></label>
        <label><span>規格名稱</span><input v-if="editableVariants[0]" v-model="editableVariants[0].label" data-testid="group-buy-variant-label" type="text" /></label>
        <label><span>規格價格</span><input v-if="editableVariants[0]" v-model.number="editableVariants[0].price" data-testid="group-buy-variant-price" type="number" min="1" /></label>
        <label><span>供應商類型</span><select v-model="editableSupplierType" data-testid="group-buy-supplier-type"><option value="external">外部廠商</option><option value="group">集團商品</option></select></label>
        <button class="button" data-testid="save-group-buy" type="button" @click="saveChocolate">儲存條件</button>
      </div>
      <p v-if="manageFeedback" class="demo-success" data-testid="group-buy-manage-feedback" role="status">{{ manageFeedback }}</p>
      <p v-if="manageError" class="demo-error" data-testid="group-buy-manage-error" role="alert">{{ manageError }}</p>
      <button v-if="draft" class="button primary demo-wide-button" data-testid="publish-dubai-group-buy" type="button" @click="publishChocolate">發布「{{ editableName || '這檔商品' }}」開團</button>
      <p v-else class="demo-success" data-testid="publish-feedback" role="status">{{ publishFeedback || '已發布，等待住戶跟團。' }}</p>
      <p v-if="draft && publishFeedback" class="demo-success" data-testid="publish-feedback" role="status">{{ publishFeedback }}</p>
    </section>

    <section class="panel demo-panel" data-testid="group-buy-management" aria-labelledby="group-buy-management-title">
      <div class="demo-section-heading"><div><p class="eyebrow">MANAGE GROUP BUYS</p><h2 id="group-buy-management-title">團購管理</h2></div><span class="demo-count-badge">可即時操作</span></div>
      <p class="demo-panel-lede">主委可以結束收單或重新開放；狀態會同步到住戶端，已存在的跟團資料不會被偷偷刪除。</p>
      <ul class="demo-management-list">
        <li v-for="group in dashboard.groupBuys" :key="group.id" :data-testid="`managed-group-buy-${group.id}`">
          <div><strong>{{ group.name }}</strong><span class="demo-meta">{{ group.progressUnits }}/{{ group.thresholdUnits }} 單位・截止 {{ group.closeAt.slice(0, 16).replace('T', ' ') }}</span></div>
          <div class="button-row">
            <span class="status" :data-status="group.status">{{ group.statusLabel }}</span>
            <button v-if="group.status === 'open'" class="button" type="button" :data-testid="`close-group-buy-${group.id}`" @click="changeGroupStatus(group.id, 'close')">結束收單</button>
            <button v-else-if="group.status === 'closed'" class="button" type="button" :data-testid="`reopen-group-buy-${group.id}`" @click="changeGroupStatus(group.id, 'reopen')">重新開放</button>
          </div>
        </li>
      </ul>
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
      <div><p class="eyebrow">STEP 4・SUBSCRIPTION</p><h2>最後用一張帳務卡，說清楚這個模式</h2><p>月費依社區戶數分級，{{ dashboard.community.households }} 戶的日光森林落在最小的級距；導入期還可以先免費試用。</p></div>
      <RouterLink class="button primary" to="/demo/subscription">查看訂閱與帳務 →</RouterLink>
    </section>
  </section>
  <section v-else class="panel demo-loading" role="status">正在整理管委會工作台…</section>
</template>

<style scoped>
.demo-edit-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(7rem, .6fr) minmax(0, 1fr) auto;
  gap: .75rem;
  align-items: end;
  margin-top: 1rem;
  padding: .85rem;
  border: 2px dashed var(--ink);
  border-radius: 14px;
  background: var(--surface-2);
}
.demo-edit-grid label { display: grid; gap: .3rem; font-weight: 800; }
.demo-edit-grid input { min-width: 0; min-height: var(--tap); padding: .45rem .55rem; border: 2px solid var(--ink); border-radius: 10px; background: var(--surface); }
.demo-management-list { display: grid; gap: .6rem; margin: 0; padding: 0; list-style: none; }
.demo-management-list li { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: .75rem; border: 2px solid var(--ink); border-radius: 12px; background: var(--surface); }
.demo-management-list li > div:first-child { display: grid; gap: .2rem; }
.demo-management-list .button-row { justify-content: flex-end; }
@media (max-width: 780px) {
  .demo-edit-grid { grid-template-columns: 1fr 1fr; }
  .demo-edit-grid .button { justify-self: start; }
}
@media (max-width: 560px) {
  .demo-edit-grid, .demo-management-list li { grid-template-columns: 1fr; display: grid; }
  .demo-management-list .button-row { justify-content: flex-start; }
}
</style>
