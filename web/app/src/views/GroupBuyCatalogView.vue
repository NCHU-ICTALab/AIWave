<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  GROUP_BUY_CATALOG,
  GROUP_BUY_CATEGORIES,
  catalogItemFromGroup,
  type GroupBuyCatalogCategory,
  type GroupBuyCatalogItem,
} from '@/data/groupBuyCatalog'
import { useCommunityDemoStore } from '@/stores/communityDemo'

const router = useRouter()
const demo = useCommunityDemoStore()
const search = ref('')
const selectedCategory = ref<GroupBuyCatalogCategory>('全部')

const items = computed<GroupBuyCatalogItem[]>(() => {
  const history = demo.residentDashboard?.groupBuyHistory.map(catalogItemFromGroup) ?? []
  const existingNames = new Set(history.map((item) => item.name))
  return [...history, ...GROUP_BUY_CATALOG.filter((item) => !existingNames.has(item.name))]
})

const filteredItems = computed(() => {
  const keyword = search.value.trim().toLocaleLowerCase('zh-TW')
  return items.value.filter((item) => {
    const matchesCategory = selectedCategory.value === '全部' || item.category === selectedCategory.value
    const matchesSearch = !keyword || [item.name, item.description, item.supplierName, item.category]
      .join(' ').toLocaleLowerCase('zh-TW').includes(keyword)
    return matchesCategory && matchesSearch
  })
})

const featuredItems = computed(() => filteredItems.value.slice(0, 3))

const money = (value: number) => `NT$ ${value.toLocaleString('zh-TW')}`
const dateLabel = (value: string) => value.slice(5, 10).replace('-', '/')
const progressWidth = (item: GroupBuyCatalogItem) => `${Math.min(100, Math.round(((item.progressUnits ?? 0) / item.thresholdUnits) * 100))}%`

function openGroup(item: GroupBuyCatalogItem) {
  void router.push({
    name: 'community-group-buy-open',
    query: {
      prefill: 'catalog',
      source: item.id,
      name: item.name,
      marketPrice: String(item.marketPrice),
      thresholdUnits: String(item.thresholdUnits),
      pickupLocation: item.pickupLocation,
      expectedArrival: item.expectedArrival,
      closeAt: item.closeAt.slice(0, 16),
      supplierType: item.supplierType,
      supplierName: item.supplierName,
      variants: JSON.stringify(item.variants),
    },
  })
}

onMounted(() => {
  demo.loadResident()
})
</script>

<template>
  <section class="demo-page group-buy-catalog-page" data-testid="group-buy-catalog">
    <div class="demo-back-row">
      <RouterLink class="demo-text-button" to="/user/community">← 回社區</RouterLink>
      <span class="demo-kicker">日光森林・COMMUNITY SHOPPING</span>
    </div>

    <header class="group-buy-catalog-hero">
      <div>
        <p class="eyebrow">社區快團・本週熱選</p>
        <h1>想買什麼，先看看社區有沒有一起買</h1>
        <p>先瀏覽商品與社區價；有想買的品項，就把它帶進開團表單，條件仍然可以自己編輯。</p>
      </div>
      <div class="group-buy-catalog-hero-stat"><strong>{{ filteredItems.length }}</strong><span>個 Demo 商品</span><small>管理室集中取貨</small></div>
    </header>

    <section class="panel group-buy-catalog-toolbar" aria-label="搜尋與分類">
      <label class="group-buy-search">
        <span>搜尋商品</span>
        <input v-model="search" data-testid="group-buy-search" type="search" placeholder="例如：水果、清潔、巧克力" />
      </label>
      <div class="group-buy-category-tabs" role="tablist" aria-label="商品分類">
        <button
          v-for="category in GROUP_BUY_CATEGORIES"
          :key="category"
          class="group-buy-category-tab"
          :class="{ active: selectedCategory === category }"
          type="button"
          role="tab"
          :aria-selected="selectedCategory === category"
          :data-category="category"
          @click="selectedCategory = category"
        >{{ category }}</button>
      </div>
    </section>

    <section v-if="featuredItems.length" class="group-buy-featured" aria-labelledby="group-buy-featured-title">
      <div class="group-buy-section-heading"><div><p class="eyebrow">HOT PICKS</p><h2 id="group-buy-featured-title">熱銷排行</h2></div><span class="demo-count-badge">社區價優先</span></div>
      <div class="group-buy-featured-grid">
        <article v-for="(item, index) in featuredItems" :key="item.id" class="group-buy-featured-card" :data-testid="`group-buy-featured-${index}`">
          <span class="group-buy-rank">{{ index + 1 }}</span>
          <div class="group-buy-product-art" :data-visual="item.visual">{{ item.visual }}</div>
          <div><span class="group-buy-product-badge">{{ item.badge }}</span><h3>{{ item.name }}</h3><p>{{ item.description }}</p></div>
          <div class="group-buy-price-row"><del>{{ money(item.marketPrice) }}</del><strong>{{ money(item.communityPrice) }}</strong></div>
          <button class="button primary" type="button" data-testid="featured-open-group" @click="openGroup(item)">我想開團</button>
        </article>
      </div>
    </section>

    <section class="panel group-buy-product-section" aria-labelledby="group-buy-product-title">
      <div class="group-buy-section-heading"><div><p class="eyebrow">ALL COMMUNITY PICKS</p><h2 id="group-buy-product-title">商品列表</h2></div><span class="muted">{{ filteredItems.length }} 項</span></div>
      <div v-if="filteredItems.length" class="group-buy-product-grid">
        <article v-for="item in filteredItems" :key="item.id" class="group-buy-product-card" :data-testid="`group-buy-product-${item.id}`">
          <div class="group-buy-product-art" :data-visual="item.visual">{{ item.visual }}</div>
          <div class="group-buy-product-body">
            <div class="group-buy-product-meta"><span>{{ item.category }}</span><span class="group-buy-product-badge">{{ item.badge }}</span></div>
            <h3>{{ item.name }}</h3>
            <p>{{ item.description }}</p>
            <div class="group-buy-price-row"><span>社區價</span><strong>{{ money(item.communityPrice) }}</strong><del>{{ money(item.marketPrice) }}</del></div>
            <div v-if="item.progressUnits !== undefined" class="group-buy-progress-row"><span>{{ item.statusLabel }}</span><strong>{{ item.progressUnits }}/{{ item.thresholdUnits }}</strong></div>
            <div v-if="item.progressUnits !== undefined" class="group-buy-progress" role="progressbar" :aria-valuenow="item.progressUnits" :aria-valuemin="0" :aria-valuemax="item.thresholdUnits"><span :style="{ width: progressWidth(item) }" /></div>
            <dl class="group-buy-product-facts"><div><dt>到貨</dt><dd>{{ dateLabel(item.expectedArrival) }}</dd></div><div><dt>取貨</dt><dd>{{ item.pickupLocation }}</dd></div></dl>
            <div class="group-buy-card-actions">
              <RouterLink v-if="item.sourceGroupBuyId && item.status === 'open'" class="button" :to="{ name: 'community-group-buy', params: { groupBuyId: item.sourceGroupBuyId } }">查看跟團</RouterLink>
              <button class="button primary" type="button" data-testid="open-group-from-list" @click="openGroup(item)">{{ item.status === 'open' ? '也想開一團' : '帶入開團' }}</button>
            </div>
          </div>
        </article>
      </div>
      <div v-else class="group-buy-empty"><strong>找不到符合的商品</strong><span>換個關鍵字或回到全部分類看看。</span></div>
    </section>

    <p class="group-buy-catalog-note">這是日光森林社區的前端 Demo 目錄；商品、價格與取貨資訊是展示資料，任何住戶都能編輯條件並直接發起開團。</p>
  </section>
</template>

<style scoped>
.group-buy-catalog-page { width: min(100%, 1180px); }
.group-buy-catalog-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 13rem;
  gap: 1rem;
  align-items: center;
  padding: clamp(1.3rem, 4vw, 2.6rem);
  border: var(--border-chunky) solid var(--ink);
  border-radius: var(--radius-lg);
  background: var(--peach);
  box-shadow: var(--shadow);
}
.group-buy-catalog-hero h1 { max-width: 42rem; margin: .2rem 0 .65rem; font-size: clamp(2rem, 5vw, 3.4rem); }
.group-buy-catalog-hero p:last-child { max-width: 44rem; margin: 0; color: var(--accent-ink); }
.group-buy-catalog-hero-stat { display: grid; gap: .2rem; padding: 1rem; border: 2px solid var(--ink); border-radius: var(--radius-md); background: var(--surface); text-align: center; }
.group-buy-catalog-hero-stat strong { color: var(--primary); font: 900 3rem/1 var(--font-mono); }
.group-buy-catalog-hero-stat span { font-weight: 900; }
.group-buy-catalog-hero-stat small { color: var(--muted); }
.group-buy-catalog-toolbar { display: grid; gap: .85rem; }
.group-buy-search { display: grid; gap: .3rem; font-weight: 900; }
.group-buy-search input { min-height: 48px; padding: 0 .8rem; border: var(--border-chunky) solid var(--ink); border-radius: var(--radius-md); background: var(--surface); font: inherit; }
.group-buy-category-tabs { display: flex; gap: .45rem; overflow-x: auto; padding-bottom: .15rem; }
.group-buy-category-tab { min-height: 40px; padding: .2rem .8rem; border: 2px solid var(--ink); border-radius: 999px; background: var(--surface-2); color: var(--ink); font-weight: 800; white-space: nowrap; }
.group-buy-category-tab.active { background: var(--yellow, #fde68a); box-shadow: 3px 3px 0 var(--ink); }
.group-buy-featured, .group-buy-product-section { display: grid; gap: .8rem; }
.group-buy-section-heading { display: flex; justify-content: space-between; align-items: end; gap: 1rem; }
.group-buy-section-heading h2 { margin: .15rem 0 0; }
.group-buy-featured-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .8rem; }
.group-buy-featured-card { position: relative; display: grid; gap: .55rem; min-width: 0; padding: 1rem; border: 2px solid var(--ink); border-radius: var(--radius-md); background: var(--surface); box-shadow: 3px 3px 0 var(--ink); }
.group-buy-rank { position: absolute; top: .7rem; left: .7rem; display: grid; place-items: center; width: 2rem; height: 2rem; border: 2px solid var(--ink); border-radius: 50%; background: var(--yellow, #fde68a); font-weight: 900; }
.group-buy-product-art { display: grid; place-items: center; min-height: 10rem; border: 2px solid var(--ink); border-radius: 14px; background: linear-gradient(135deg, var(--blue), var(--mint)); font-size: 5rem; }
.group-buy-featured-card:nth-child(2) .group-buy-product-art { background: linear-gradient(135deg, var(--lilac), var(--peach)); }
.group-buy-featured-card:nth-child(3) .group-buy-product-art { background: linear-gradient(135deg, var(--yellow, #fde68a), var(--peach)); }
.group-buy-product-art[data-visual='🍫'] { background: linear-gradient(135deg, #d9b59f, var(--peach)); }
.group-buy-product-art[data-visual='🧼'], .group-buy-product-art[data-visual='🫧'] { background: linear-gradient(135deg, var(--blue), #d9f5ee); }
.group-buy-product-art[data-visual='💧'] { background: linear-gradient(135deg, #cde7f7, var(--blue)); }
.group-buy-product-badge { display: inline-flex; width: fit-content; padding: .15rem .45rem; border: 1px solid var(--ink); border-radius: 999px; background: var(--mint); color: var(--ink); font-size: .68rem; font-weight: 900; }
.group-buy-featured-card h3, .group-buy-featured-card p, .group-buy-product-card h3, .group-buy-product-card p { margin: 0; }
.group-buy-featured-card h3, .group-buy-product-card h3 { margin-top: .35rem; font-size: 1.05rem; }
.group-buy-featured-card p, .group-buy-product-card p { color: var(--muted); font-size: .8rem; line-height: 1.5; }
.group-buy-price-row { display: flex; align-items: baseline; gap: .45rem; flex-wrap: wrap; }
.group-buy-price-row strong { color: var(--primary); font: 900 1.25rem/1 var(--font-mono); }
.group-buy-price-row del { color: var(--muted); font-size: .75rem; }
.group-buy-featured-card .button { width: 100%; }
.group-buy-product-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .85rem; }
.group-buy-product-card { display: grid; grid-template-rows: auto 1fr; min-width: 0; overflow: hidden; border: 2px solid var(--ink); border-radius: var(--radius-md); background: var(--surface-2); box-shadow: 3px 3px 0 var(--ink); }
.group-buy-product-card .group-buy-product-art { min-height: 8.5rem; border: 0; border-bottom: 2px solid var(--ink); border-radius: 0; font-size: 4rem; }
.group-buy-product-body { display: grid; align-content: start; gap: .55rem; padding: .85rem; }
.group-buy-product-meta, .group-buy-progress-row { display: flex; justify-content: space-between; align-items: center; gap: .4rem; color: var(--muted); font-size: .72rem; font-weight: 800; }
.group-buy-progress-row strong { color: var(--primary); font-family: var(--font-mono); }
.group-buy-progress { height: 9px; overflow: hidden; border: 2px solid var(--ink); border-radius: 999px; background: var(--line); }
.group-buy-progress span { display: block; height: 100%; border-radius: inherit; background: var(--cta); }
.group-buy-product-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .45rem; margin: 0; }
.group-buy-product-facts > div { padding: .45rem; border-radius: 9px; background: var(--surface); }
.group-buy-product-facts dt { color: var(--muted); font-size: .65rem; }
.group-buy-product-facts dd { margin: .1rem 0 0; font-size: .72rem; font-weight: 800; overflow-wrap: anywhere; }
.group-buy-card-actions { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .2rem; }
.group-buy-card-actions .button { flex: 1 1 8rem; min-height: 42px; padding-inline: .55rem; font-size: .78rem; }
.group-buy-empty { display: grid; gap: .2rem; place-items: start; padding: 2rem 0; color: var(--muted); }
.group-buy-empty strong { color: var(--ink); }
.group-buy-catalog-note { margin: 0; color: var(--muted); font-size: .78rem; }
@media (max-width: 900px) {
  .group-buy-featured-grid, .group-buy-product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 650px) {
  .group-buy-catalog-hero { grid-template-columns: 1fr; }
  .group-buy-catalog-hero-stat { justify-self: start; grid-template-columns: auto auto; text-align: left; align-items: center; }
  .group-buy-catalog-hero-stat strong { grid-row: span 2; }
  .group-buy-featured-grid, .group-buy-product-grid { grid-template-columns: 1fr; }
}
</style>
