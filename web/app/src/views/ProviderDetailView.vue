<script setup lang="ts">
// 服務詳情頁(方向 A 原型 service-detail.html):tier-1 Provider 的完整介紹。
// 內容全部來自 getProvider();據點/方案/取消規則由後端目錄投影提供,
// 「進度會如何呈現」依第一個 offering 的 domainType 顯示對應時間軸
// (標籤鏡射後端 core/catalog/domains.py 的 status_labels;後端是唯一權威)。
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/http'
import { getProvider, type CatalogOffering, type CatalogProviderDetail } from '@/api/platformClient'

const route = useRoute()
const router = useRouter()

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

// domainType → 顯示名與正向時間軸標籤(鏡射 core/catalog/domains.py)
const DOMAIN_META: Record<string, { name: string; timeline: string[] }> = {
  home_repair: { name: '水電修繕', timeline: ['需求送出', '已預約', '服務中', '已完成'] },
  home_cleaning: { name: '居家清潔', timeline: ['需求送出', '已預約', '服務中', '已完成'] },
  dining_reservation: { name: '餐廳訂位', timeline: ['已建立', '店家確認', '即將到店', '已完成'] },
  car_wash: { name: '洗車保養', timeline: ['已預約', '站點確認', '施作中', '已完成'] },
  resort_booking: { name: '渡假村訂房', timeline: ['訂房送出', '訂房確認', '已入住', '已退房'] },
  shipping_pickup: { name: '宅配寄件', timeline: ['已預約收件', '司機已排班', '收件中', '已收件寄出'] },
  pharmacy_pickup: { name: '處方箋領藥', timeline: ['領藥申請送出', '藥局已備藥', '可前往領藥', '已領藥'] },
  ec_preorder: { name: 'i 預購/商城', timeline: ['收到訂單', '已接單', '備貨中', '已出貨', '已送達'] },
  food_delivery: { name: '美食外送', timeline: ['收到訂單', '店家接單', '餐點製作中', '外送中', '已送達'] },
  c2c_shipping: { name: '交貨便寄件', timeline: ['收到訂單', '寄件單成立', '門市收件', '運送中', '已到店', '已取件'] },
  ticket_purchase: { name: '票券購買', timeline: ['收到訂單', '訂單確認', '出票中', '可取票(ibon)', '已取票'] },
}

const provider = ref<CatalogProviderDetail | null>(null)
const status = ref<'loading' | 'ready' | 'not-found' | 'error'>('loading')
const errorMessage = ref('')

const providerId = computed(() => String(route.params.providerId ?? ''))
const firstOffering = computed(() => provider.value?.offerings[0] ?? null)
const timelinePreview = computed(() => {
  const domainType = firstOffering.value?.domainType ?? ''
  return DOMAIN_META[domainType]?.timeline ?? []
})
const ctaLabel = computed(() =>
  firstOffering.value?.fulfillmentKind === 'commerce' ? '開始購買' : '開始預約')

function domainName(offering: CatalogOffering): string {
  return DOMAIN_META[offering.domainType ?? '']?.name ?? (offering.domainType ?? '—')
}

function money(value: number): string {
  return `NT$ ${value.toLocaleString('zh-TW')}`
}

function priceText(offering: CatalogOffering): string {
  return offering.basePrice > 0
    ? `${money(offering.basePrice)}／${offering.pricingUnit ?? '次'}`
    : '免費預約'
}

function cancelText(offering: CatalogOffering): string {
  const hours = offering.cancelPolicyHours ?? 0
  return hours > 0 ? `開始前 ${hours} 小時可免費取消` : '送出後如需取消請儘速聯繫客服'
}

async function load() {
  status.value = 'loading'
  errorMessage.value = ''
  try {
    provider.value = await getProvider(providerId.value)
    status.value = 'ready'
  } catch (reason) {
    provider.value = null
    if (reason instanceof ApiError && reason.status === 404) {
      status.value = 'not-found'
    } else {
      status.value = 'error'
      errorMessage.value = reason instanceof Error ? reason.message : '暫時無法載入服務詳情。'
    }
  }
}

function startFlow(offering: CatalogOffering) {
  void router.push({
    name: 'booking-wizard',
    query: { provider: providerId.value, offering: offering.id },
  })
}

onMounted(load)
watch(providerId, load)
</script>

<template>
  <section class="member-page provider-detail-page">
    <p class="back-link-row">
      <RouterLink to="/user/services">← 回服務探索</RouterLink>
    </p>

    <div v-if="status === 'loading'" class="panel state-panel" role="status">正在載入服務詳情…</div>

    <div v-else-if="status === 'not-found'" class="panel state-panel" role="alert" data-testid="provider-not-found">
      <h1>找不到這個服務品牌</h1>
      <p>目錄中查無此 Provider，可能已下架或網址有誤。</p>
      <RouterLink class="button" to="/user/services">回服務探索</RouterLink>
    </div>

    <div v-else-if="status === 'error'" class="panel state-panel" role="alert">
      <h1>目前無法載入服務詳情</h1>
      <p>{{ errorMessage }}</p>
      <div class="button-row">
        <button class="button" type="button" @click="load">再試一次</button>
        <RouterLink class="button" to="/user/services">回服務探索</RouterLink>
      </div>
    </div>

    <template v-else-if="provider">
      <header class="page-heading provider-heading">
        <img v-if="BRAND_ICONS[provider.id]" class="brand-icon" :src="BRAND_ICONS[provider.id]" alt="" />
        <span v-else class="brand-badge" aria-hidden="true">{{ provider.name.slice(0, 1) }}</span>
        <div>
          <p class="eyebrow">服務詳情</p>
          <h1>{{ provider.name }}</h1>
          <p class="muted">
            評分 {{ provider.rating?.toFixed(1) ?? '—' }}（{{ provider.reviewCount ?? 0 }} 則・展示資料）
          </p>
          <p v-if="provider.summary" class="provider-summary">{{ provider.summary }}</p>
          <p class="demo-note">內容為競賽展示資料（{{ provider.seedVersion }}）。</p>
        </div>
      </header>

      <section class="panel" aria-labelledby="locations-title">
        <h2 id="locations-title">服務據點</h2>
        <ul class="site-list" data-testid="provider-locations">
          <li v-for="location in provider.locations" :key="location.id">
            <strong>{{ location.name }}</strong>
            <span class="muted">
              {{ location.address ?? `${location.countyName ?? ''}${location.districtName ?? ''}` }}
              <template v-if="location.phone">・{{ location.phone }}</template>
            </span>
          </li>
        </ul>
        <p v-if="!provider.locations.length" class="muted">此品牌目前未提供實體據點資訊。</p>
      </section>

      <section class="panel" aria-labelledby="pricing-title">
        <h2 id="pricing-title">方案價目</h2>
        <div class="table-scroll">
          <table class="price-table" data-testid="provider-offerings">
            <thead>
              <tr>
                <th scope="col">方案</th>
                <th scope="col">服務類型</th>
                <th scope="col">價格</th>
                <th scope="col">取消規則</th>
                <th scope="col"><span class="visually-hidden">動作</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="offering in provider.offerings" :key="offering.id">
                <th scope="row">{{ offering.name }}</th>
                <td>{{ domainName(offering) }}</td>
                <td>{{ priceText(offering) }}</td>
                <td>{{ cancelText(offering) }}</td>
                <td>
                  <button
                    class="button inline"
                    type="button"
                    data-testid="offering-cta"
                    :data-offering-id="offering.id"
                    @click="startFlow(offering)"
                  >
                    {{ offering.fulfillmentKind === 'commerce' ? '購買' : '預約' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!provider.offerings.length" class="muted">此品牌目前沒有可預約或可購買的方案。</p>
      </section>

      <section v-if="timelinePreview.length" class="panel" aria-labelledby="progress-title">
        <h2 id="progress-title">進度會如何呈現</h2>
        <p>送出後，訂單詳情頁會用時間軸呈現每一步，狀態更新同步推送通知並寫入行事曆：</p>
        <ol class="status-preview" data-testid="status-preview">
          <li v-for="label in timelinePreview" :key="label"><span class="status-chip">{{ label }}</span></li>
        </ol>
      </section>

      <section v-if="firstOffering" class="panel cta-panel" aria-labelledby="cta-title">
        <h2 id="cta-title">準備好了嗎？</h2>
        <p>分步完成，填寫內容會自動存成草稿。</p>
        <button
          class="button primary"
          type="button"
          data-testid="provider-start"
          @click="startFlow(firstOffering)"
        >
          {{ ctaLabel }}
        </button>
      </section>
    </template>
  </section>
</template>

<style scoped>
.back-link-row {
  margin: 0 0 0.8rem;
}

.provider-heading {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 0.9rem;
  align-items: start;
}

.brand-icon,
.brand-badge {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  object-fit: contain;
}

.brand-badge {
  display: grid;
  place-items: center;
  border: 2px solid var(--ink);
  border-radius: 50%;
  background: var(--surface-2);
  font-weight: 800;
  font-size: 1.4rem;
}

.provider-summary {
  margin: 0.3rem 0 0;
}

.demo-note {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.8rem;
}

.panel + .panel {
  margin-top: 1rem;
}

.site-list {
  display: grid;
  gap: 0.6rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.site-list li {
  display: grid;
  gap: 0.15rem;
  padding: 0.7rem 0.9rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface);
}

.table-scroll {
  overflow-x: auto;
}

.price-table {
  width: 100%;
  border-collapse: collapse;
}

.price-table th,
.price-table td {
  padding: 0.55rem 0.6rem;
  text-align: left;
  border-bottom: 2px solid var(--surface-2);
  vertical-align: top;
}

.price-table thead th {
  color: var(--muted);
  font-size: 0.85rem;
}

.price-table .button.inline {
  min-height: 44px;
}

.status-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  margin: 0.6rem 0 0;
  padding: 0;
  list-style: none;
}

.status-preview li {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.status-preview li + li::before {
  content: '→';
  font-weight: 900;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 0.7rem;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--surface-2);
  font-weight: 700;
  font-size: 0.85rem;
}

.cta-panel .button {
  min-height: 44px;
}
</style>
