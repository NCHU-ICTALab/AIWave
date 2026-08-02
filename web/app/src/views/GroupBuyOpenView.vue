<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { DemoGroupBuyVariant, DemoSupplierType } from '@/domain/communityDemo'
import { useCommunityDemoStore } from '@/stores/communityDemo'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const demo = useCommunityDemoStore()
const session = useSessionStore()

const queryValue = (key: string, fallback: string) => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const numberValue = (key: string, fallback: number) => Number(queryValue(key, String(fallback))) || fallback

const form = reactive({
  name: queryValue('name', '新的社區團購'),
  marketPrice: numberValue('marketPrice', 399),
  thresholdUnits: numberValue('thresholdUnits', 10),
  pickupLocation: queryValue('pickupLocation', '社區管理室'),
  expectedArrival: queryValue('expectedArrival', '2026-08-15'),
  closeAt: queryValue('closeAt', '2026-08-10T21:00'),
  supplierType: (queryValue('supplierType', 'external') === 'group' ? 'group' : 'external') as DemoSupplierType,
  supplierName: queryValue('supplierName', '住戶推薦廠商'),
})

const variants = computed<DemoGroupBuyVariant[]>(() => {
  const raw = queryValue('variants', '')
  try {
    const parsed = JSON.parse(raw) as unknown
    if (Array.isArray(parsed) && parsed.every((item) => item && typeof item === 'object')) {
      return parsed.filter((item): item is DemoGroupBuyVariant => (
        typeof (item as DemoGroupBuyVariant).id === 'string'
        && typeof (item as DemoGroupBuyVariant).label === 'string'
        && typeof (item as DemoGroupBuyVariant).price === 'number'
      ))
    }
  } catch {
    // The catalog still has a usable default if a copied query was truncated.
  }
  return [{ id: 'catalog-default', label: '標準規格', price: Math.max(1, Math.round(form.marketPrice * .9)) }]
})

const sourceLabel = computed(() => queryValue('source', '住戶自訂商品'))
const openError = ref('')

function openGroupBuy() {
  openError.value = ''
  try {
    const group = demo.openResidentGroupBuy({
      name: form.name,
      description: `由${session.displayName}發起的社區團購，管理室集中取貨。`,
      marketPrice: form.marketPrice,
      thresholdUnits: form.thresholdUnits,
      pickupLocation: form.pickupLocation,
      expectedArrival: form.expectedArrival,
      closeAt: `${form.closeAt}:00+08:00`,
      supplierType: form.supplierType,
      supplierName: form.supplierName,
      variants: variants.value,
    })
    void router.push({ name: 'community-group-buy', params: { groupBuyId: group.id } })
  } catch (reason) {
    openError.value = reason instanceof Error ? reason.message : '開團未完成，請稍後再試。'
  }
}
</script>

<template>
  <section class="demo-page group-buy-open-page" data-testid="group-buy-open-page">
    <div class="demo-back-row"><button class="demo-text-button" type="button" @click="router.push({ name: 'community-group-buys' })">← 回商品列表</button><span class="demo-kicker">OPEN A COMMUNITY GROUP</span></div>
    <header class="demo-hero demo-hero-resident">
      <div>
        <p class="eyebrow">住戶想買這個</p>
        <h1>把商品帶進開團流程</h1>
        <p class="demo-hero-lede">這些條件是從商品列表帶進來的。你可以先修改，再由你直接發起這檔社區團購。</p>
      </div>
      <div class="demo-hero-side"><span class="demo-kicker">已選商品</span><strong>{{ form.name }}</strong><span>{{ sourceLabel }}</span></div>
    </header>

    <div class="demo-two-column group-buy-open-layout">
      <section class="panel demo-panel" aria-labelledby="group-buy-open-form-title">
        <div class="demo-section-heading"><div><p class="eyebrow">EDIT BEFORE HANDOFF</p><h2 id="group-buy-open-form-title">先確認團購條件</h2></div><span class="demo-count-badge">可編輯</span></div>
        <form class="group-buy-open-form" @submit.prevent="openGroupBuy">
          <label><span>團購名稱</span><input v-model="form.name" data-testid="open-group-name" type="text" required /></label>
          <div class="group-buy-open-form-grid">
            <label><span>市價</span><input v-model.number="form.marketPrice" data-testid="open-group-market-price" type="number" min="1" required /></label>
            <label><span>成團門檻</span><input v-model.number="form.thresholdUnits" data-testid="open-group-threshold" type="number" min="1" required /></label>
          </div>
          <div class="group-buy-open-form-grid">
            <label><span>預計到貨</span><input v-model="form.expectedArrival" data-testid="open-group-arrival" type="date" required /></label>
            <label><span>收單截止</span><input v-model="form.closeAt" data-testid="open-group-close-at" type="datetime-local" required /></label>
          </div>
          <label><span>取貨地點</span><input v-model="form.pickupLocation" data-testid="open-group-pickup" type="text" required /></label>
          <div class="group-buy-open-form-grid">
            <label><span>供應商類型</span><select v-model="form.supplierType" data-testid="open-group-supplier-type"><option value="external">外部廠商</option><option value="group">集團商品</option></select></label>
            <label><span>供應商</span><input v-model="form.supplierName" data-testid="open-group-supplier" type="text" required /></label>
          </div>
          <button class="button primary" data-testid="continue-to-group-buy-editor" type="submit">確認開團並發布 →</button>
          <p v-if="openError" class="demo-error" data-testid="open-group-error" role="alert">{{ openError }}</p>
        </form>
      </section>

      <aside class="panel demo-panel group-buy-open-summary" aria-labelledby="group-buy-open-summary-title">
        <div class="demo-section-heading"><div><p class="eyebrow">PREVIEW</p><h2 id="group-buy-open-summary-title">帶入內容</h2></div><span class="status">未發布</span></div>
        <dl class="demo-definition-list">
          <div><dt>商品</dt><dd>{{ form.name }}</dd></div>
          <div><dt>規格</dt><dd><span v-for="variant in variants" :key="variant.id">{{ variant.label }}・NT$ {{ variant.price.toLocaleString('zh-TW') }}<br /></span></dd></div>
          <div><dt>門檻</dt><dd>{{ form.thresholdUnits }} 個跟團單位</dd></div>
          <div><dt>到貨</dt><dd>{{ form.expectedArrival }}</dd></div>
          <div><dt>取貨</dt><dd>{{ form.pickupLocation }}</dd></div>
        </dl>
        <p class="demo-note">任何已登入住戶都能發起團購。發布後立即進入社區收單，主委可在管理工作台做後續結單與彙總。</p>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.group-buy-open-page { width: min(100%, 1080px); }
.group-buy-open-layout { align-items: start; }
.group-buy-open-form { display: grid; gap: .75rem; }
.group-buy-open-form label { display: grid; gap: .3rem; font-weight: 800; }
.group-buy-open-form input, .group-buy-open-form select { min-width: 0; min-height: var(--tap); padding: .45rem .6rem; border: 2px solid var(--ink); border-radius: 10px; background: var(--surface); font: inherit; }
.group-buy-open-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; }
.group-buy-open-form .button { margin-top: .3rem; }
.group-buy-open-summary { background: var(--blue); }
.group-buy-open-summary dd { overflow-wrap: anywhere; }
@media (max-width: 600px) { .group-buy-open-form-grid { grid-template-columns: 1fr; } }
</style>
