<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getProvider, listListings, listProviders, type CatalogProvider, type ListedBrand } from '@/api/platformClient'

// 2026-07-31 產品決策:移除 legacy「用需求描述找服務」區塊(搜尋列、常用服務、推薦卡、
// 所有服務 grid、intake aside)。有新廠商目錄與六大場景後,服務探索只保留:
// 頁首 + 場景錨點 + 六場景區(tier-1 合作品牌卡 + tier-2 目錄陳列)。
// route `/user/services/:serviceSlug?` 的 slug 只服務舊 deep link,保留路由但忽略 slug。
const router = useRouter()

// ── M4 六大生活場景探索(合作品牌目錄,由 platform API 提供) ──
// 場景副標比照核准原型 services.html;行/樂依 partner-demo-v5 實際內容微調(行含洗車、樂已有核准品牌)。
const SCENES = [
  { key: 'food', label: '食', title: '食・外送與訂位' },
  { key: 'med', label: '醫', title: '醫・處方箋與藥局' },
  { key: 'home', label: '住', title: '住・修繕與清潔' },
  { key: 'move', label: '行', title: '行・寄件與物流' },
  { key: 'pre', label: '預', title: '預・預購購物' },
  { key: 'fun', label: '樂', title: '樂・休閒娛樂' },
] as const

const BRAND_ICONS: Record<string, string> = {
  'vendor-711-shop': '/brand-icons/711.ico',
  'vendor-duskin': '/brand-icons/duskin.ico',
  'vendor-cosmed': '/brand-icons/cosmed.ico',
  'vendor-blackcat': '/brand-icons/blackcat.ico',
  'vendor-smile': '/brand-icons/smile.ico',
  'vendor-uni-resort': '/brand-icons/uniresort.png',
  'vendor-foodomo': '/brand-icons/foodomo.png',
  'vendor-iopenmall': '/brand-icons/711.ico',
  'vendor-ibon-ticket': '/brand-icons/711.ico',
  'vendor-711-c2c': '/brand-icons/711.ico',
}

const exploreProviders = ref<CatalogProvider[]>([])
const exploreStatus = ref<'loading' | 'ready' | 'error'>('loading')
const exploreError = ref('')
const bookingPending = ref('')

// 起價來自各品牌 offerings 的最低 basePrice(後端唯一權威;失敗只影響單卡的價格標示)
const priceFrom = ref<Record<string, number>>({})

function priceLabel(amount: number) {
  return amount > 0 ? `NT$${amount.toLocaleString('zh-TW')} 起` : '免費'
}

function loadPriceFrom(providers: CatalogProvider[]) {
  for (const provider of providers) {
    void getProvider(provider.id)
      .then((detail) => {
        const prices = detail.offerings.map((offering) => offering.basePrice)
        if (prices.length) priceFrom.value = { ...priceFrom.value, [provider.id]: Math.min(...prices) }
      })
      .catch(() => undefined)
  }
}

// tier-2 目錄陳列(統一體系其餘品牌):可看、可連官網,誠實標示不可下單。
// 載入失敗只影響陳列區,不影響 tier-1 可交易目錄。
const listings = ref<ListedBrand[]>([])
const listingsStatus = ref<'loading' | 'ready' | 'error'>('loading')

const sceneGroups = computed(() => SCENES
  .map((scene) => ({
    ...scene,
    providers: exploreProviders.value.filter((item) => item.scene === scene.key),
    listings: listings.value.filter((item) => item.scene === scene.key),
  }))
  .filter((group) => group.providers.length > 0 || group.listings.length > 0))

async function loadExplore() {
  exploreStatus.value = 'loading'
  exploreError.value = ''
  try {
    exploreProviders.value = await listProviders()
    exploreStatus.value = 'ready'
    loadPriceFrom(exploreProviders.value)
  } catch (reason) {
    exploreStatus.value = 'error'
    exploreError.value = reason instanceof Error ? reason.message : '暫時無法載入合作品牌。'
  }
  listingsStatus.value = 'loading'
  try {
    listings.value = await listListings()
    listingsStatus.value = 'ready'
  } catch {
    listings.value = []
    listingsStatus.value = 'error'
  }
}

function openProviderDetail(provider: CatalogProvider) {
  void router.push({ name: 'provider-detail', params: { providerId: provider.id } })
}

async function startBooking(provider: CatalogProvider) {
  bookingPending.value = provider.id
  try {
    const detail = await getProvider(provider.id).catch(() => null)
    const offeringId = detail?.offerings[0]?.id
    await router.push({
      name: 'booking-wizard',
      query: { provider: provider.id, ...(offeringId ? { offering: offeringId } : {}) },
    })
  } finally {
    bookingPending.value = ''
  }
}

onMounted(() => {
  void loadExplore()
})
</script>

<template>
  <header class="services-head">
    <h1>服務探索</h1>
    <p class="page-lead">六大生活場景，合作品牌皆為平台核准店家。評分與價格為展示資料（partner-demo-v5 seed）。</p>
  </header>

  <!-- 場景快速錨點膠囊列(比照原型 .scene-anchors) -->
  <nav aria-label="六大生活場景快速連結">
    <ul class="scene-anchors">
      <li v-for="scene in SCENES" :key="scene.key"><a :href="`#scene-${scene.key}`">{{ scene.label }}</a></li>
    </ul>
  </nav>

  <!-- M4 六大生活場景:合作品牌探索為頁面主體,每場景一張 card,主 CTA 進入預約流程 -->
  <p v-if="exploreStatus === 'loading'" class="muted" role="status">正在載入合作品牌…</p>
  <section v-else-if="exploreStatus === 'error'" class="panel">
    <div class="empty-state compact" role="alert" data-testid="explore-error">
      <h3>目前無法載入合作品牌</h3>
      <p>{{ exploreError }}</p>
      <button class="button inline" type="button" data-testid="explore-retry" @click="loadExplore">再試一次</button>
    </div>
  </section>
  <template v-else>
    <section
      v-for="group in sceneGroups"
      :id="`scene-${group.key}`"
      :key="group.key"
      class="panel scene-card"
      :aria-labelledby="`scene-title-${group.key}`"
      data-testid="scene-group"
      :data-scene="group.key"
    >
      <h2 :id="`scene-title-${group.key}`">{{ group.title }}</h2>
      <ul class="provider-grid">
        <li v-for="provider in group.providers" :key="provider.id">
          <article class="provider-card" data-testid="provider-card" :data-provider-id="provider.id">
            <img v-if="BRAND_ICONS[provider.id]" class="brand-icon" :src="BRAND_ICONS[provider.id]" alt="" />
            <span v-else class="brand-badge" aria-hidden="true">{{ provider.name.slice(0, 1) }}</span>
            <div class="provider-copy">
              <strong>{{ provider.name }}</strong>
              <span class="svc-meta">
                <span class="rating-pill">評分 {{ provider.rating?.toFixed(1) ?? '—' }}（{{ provider.reviewCount ?? 0 }} 則・展示資料）</span>
                <span v-if="priceFrom[provider.id] !== undefined" class="svc-price">{{ priceLabel(priceFrom[provider.id]!) }}</span>
              </span>
              <p>{{ provider.summary }}</p>
            </div>
            <div class="provider-actions">
              <button
                class="button primary"
                type="button"
                data-testid="provider-detail-cta"
                @click="openProviderDetail(provider)"
              >
                查看詳情
              </button>
              <button
                class="button"
                type="button"
                data-testid="provider-book"
                :disabled="bookingPending === provider.id"
                @click="startBooking(provider)"
              >
                預約
              </button>
            </div>
          </article>
        </li>
      </ul>

      <!-- 醫場景:處方箋辨識流程說明(純文字步驟,不做假上傳)與醒目免責,比照原型 rx-flow -->
      <details v-if="group.key === 'med'" class="rx" data-testid="rx-flow">
        <summary>處方箋辨識流程示意（展開）</summary>
        <ol class="rx-flow">
          <li><span><strong>上傳處方箋照片</strong><small>支援手機拍照或相簿選取，照片僅用於本次辨識。</small></span></li>
          <li><span><strong>OCR 結果逐欄人工確認</strong><small>藥品名稱、劑量、天數每一欄都由你逐一核對修改，系統不會替你確認。</small></span></li>
          <li><span><strong>選擇門市領藥</strong><small>依你的地址列出可領藥門市，確認後產生領藥單。</small></span></li>
        </ol>
        <p class="rx-disclaimer">免責聲明：本流程僅提供辨識展示，不提供任何診斷或用藥建議；用藥問題請諮詢醫師或藥師。</p>
      </details>

      <!-- tier-2:統一體系其餘品牌,目錄陳列、誠實標示不可下單 -->
      <details v-if="group.listings.length" class="listing-collapse" data-testid="listing-section" :data-scene="group.key">
        <summary>更多統一體系品牌（{{ group.listings.length }}）</summary>
        <ul class="listing-grid">
          <li v-for="brand in group.listings" :key="brand.id">
            <article class="listing-card" data-testid="listing-card" :data-listing-id="brand.id">
              <div class="listing-copy">
                <strong>{{ brand.name }}</strong>
                <span class="muted">{{ brand.company }}</span>
                <span v-if="brand.tags.length" class="listing-tags">
                  <span v-for="tag in brand.tags" :key="tag" class="listing-tag">{{ tag }}</span>
                </span>
                <p v-if="brand.note" class="listing-note" data-testid="listing-note">{{ brand.note }}</p>
              </div>
              <span class="listing-flag">未開放線上交易</span>
              <a
                v-if="brand.url"
                class="listing-link"
                :href="brand.url"
                target="_blank"
                rel="noopener"
              >
                官網<span class="visually-hidden">（另開新視窗）</span>
              </a>
            </article>
          </li>
        </ul>
      </details>
    </section>
    <p v-if="listingsStatus === 'error'" class="muted" role="alert" data-testid="listings-error">
      目前無法載入統一體系品牌陳列，稍後再試；不影響上方可預約的合作品牌。
    </p>
  </template>
</template>

<style scoped>
/* 頁首與場景錨點:比照核准原型 services.html(單欄 card 堆疊、無 eyebrow mono) */
.services-head {
  margin-bottom: 1rem;
}

.services-head h1 {
  margin: 0;
}

.page-lead {
  margin: 0.35rem 0 0;
  max-width: 62ch;
  color: var(--muted);
  font-weight: 600;
}

.scene-anchors {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin: 0 0 1.25rem;
  padding: 0;
  list-style: none;
}

.scene-anchors a {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  padding: 0.3rem 1.1rem;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--surface);
  box-shadow: 2px 2px 0 var(--ink);
  color: var(--ink);
  font-weight: 800;
  text-decoration: none;
}

.scene-anchors a:hover,
.scene-anchors a:focus-visible {
  background: var(--surface-2);
}

.scene-card {
  margin-bottom: 1.25rem;
  scroll-margin-top: 5rem;
}

.scene-card h2 {
  margin: 0 0 0.75rem;
}

.svc-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}

.rating-pill {
  padding: 0.05rem 0.6rem;
  border: 1px solid var(--ink);
  border-radius: 999px;
  background: var(--surface-2);
  font-size: 0.78rem;
  font-weight: 700;
}

.svc-price {
  font-size: 0.85rem;
  font-weight: 900;
}

/* 醫場景:處方箋辨識流程與免責(比照原型 rx-flow / rx-disclaimer) */
.rx {
  margin-top: 0.9rem;
}

.rx > summary {
  display: flex;
  align-items: center;
  min-height: 44px;
  font-weight: 800;
  cursor: pointer;
}

.rx-flow {
  display: grid;
  gap: 0.6rem;
  margin: 0.6rem 0 0;
  padding: 0;
  list-style: none;
  counter-reset: rx;
}

.rx-flow li {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  padding: 0.65rem 0.85rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface);
  counter-increment: rx;
}

.rx-flow li::before {
  content: counter(rx);
  display: grid;
  flex: none;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 2px solid var(--ink);
  border-radius: 50%;
  background: var(--surface-2);
  font-weight: 900;
}

.rx-flow small {
  display: block;
  color: var(--muted);
}

.rx-disclaimer {
  margin: 0.75rem 0 0;
  padding: 0.75rem 1rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--accent-soft, var(--surface-2));
  font-weight: 800;
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.7rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.provider-card {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 0.35rem 0.7rem;
  height: 100%;
  padding: 0.85rem;
  border: var(--border-chunky) solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface);
  box-shadow: 4px 4px 0 var(--ink);
}

.brand-icon,
.brand-badge {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  object-fit: contain;
}

.brand-badge {
  display: grid;
  place-items: center;
  border: 2px solid var(--ink);
  border-radius: 50%;
  background: var(--surface-2);
  font-weight: 800;
  font-size: 1.2rem;
}

.provider-copy {
  display: grid;
  gap: 0.15rem;
  min-width: 0;
}

.provider-copy p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--muted);
}

.provider-actions {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.provider-card .button {
  min-height: 44px;
}

.listing-collapse {
  margin-top: 0.7rem;
  padding: 0.5rem 0.85rem;
  border: 2px dashed var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface-2);
}

.listing-collapse > summary {
  display: flex;
  align-items: center;
  min-height: 44px;
  font-weight: 800;
  cursor: pointer;
}

.listing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 0.6rem;
  margin: 0.5rem 0 0.3rem;
  padding: 0;
  list-style: none;
}

.listing-card {
  display: grid;
  gap: 0.3rem;
  height: 100%;
  padding: 0.7rem 0.85rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface);
}

.listing-copy {
  display: grid;
  gap: 0.15rem;
}

.listing-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.listing-tag {
  padding: 0 0.5rem;
  border: 1px solid var(--ink);
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
}

.listing-note {
  margin: 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.listing-flag {
  justify-self: start;
  padding: 0.1rem 0.55rem;
  border: 1px solid var(--muted);
  border-radius: 999px;
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 700;
}

.listing-link {
  justify-self: start;
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  font-weight: 700;
}
</style>
