<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ServiceIntakeForm from '@/components/ServiceIntakeForm.vue'
import { summarizeServiceAnswers, validateServiceAnswers } from '@/domain/serviceIntake'
import { useDemoStore } from '@/stores/demo'

const store = useDemoStore()
const router = useRouter()
const route = useRoute()
const search = ref('')
const dialogOpen = ref(false)
const errors = ref<Record<string, string>>({})
const selectedForm = computed(() => store.selectedForm)
const categories = ['居家維護', '生活支援', '餐飲購物'] as const
const visibleServices = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('zh-TW')
  if (!query) return store.services
  return store.services.filter((service) => `${service.name}${service.summary}${service.partner}`.toLocaleLowerCase('zh-TW').includes(query))
})

async function applyRouteService(slug: unknown) {
  if (typeof slug !== 'string') return
  const serviceId = `service-${slug}`
  if (store.services.some(({ id }) => id === serviceId)) await store.selectService(serviceId)
}

onMounted(async () => {
  if (store.catalogStatus === 'idle') await store.loadCatalog()
  await applyRouteService(route.params.serviceSlug)
})

watch(() => store.selectedServiceId, () => { errors.value = {} })
watch(() => route.params.serviceSlug, (slug) => { void applyRouteService(slug) })

// 從首頁帶過來的原始需求——要讓使用者看到自己說的話有被接住
const submittedNeed = computed(() => (typeof route.query.need === 'string' ? route.query.need : ''))
const matchReason = computed(() => (typeof route.query.why === 'string' ? route.query.why : ''))
const unmatched = computed(() => route.query.unmatched === '1')

async function chooseService(serviceId: string) {
  await store.selectService(serviceId)
  void router.replace({
    name: 'services',
    params: { serviceSlug: serviceId.replace('service-', '') },
    query: { ...route.query },
  })
}

async function continueWithService() {
  if (!store.selectedService || !selectedForm.value) return
  errors.value = validateServiceAnswers(selectedForm.value, store.selectedAnswers)
  if (Object.keys(errors.value).length) {
    await nextTick()
    document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
    return
  }
  dialogOpen.value = true
}

async function setAnswer(fieldId: string, value: string | number) {
  await store.setServiceAnswer(fieldId, value)
  if (errors.value[fieldId]) {
    const nextErrors = { ...errors.value }
    delete nextErrors[fieldId]
    errors.value = nextErrors
  }
}

async function confirmOrder() {
  const order = store.submitSelectedService()
  dialogOpen.value = false
  if (order) await router.push('/user/orders')
}
</script>

<template>
  <header class="page-heading">
    <div><p class="eyebrow">找服務</p><h1>需要什麼服務？</h1></div>
    <span class="page-status">{{ store.services.length }} 項服務</span>
  </header>

  <!-- 承接首頁輸入的需求：讓使用者看到自己說的話有被接住 -->
  <p v-if="submittedNeed && !unmatched" class="need-echo" data-testid="need-echo" role="status">
    你說「{{ submittedNeed }}」<span v-if="matchReason" class="muted">——{{ matchReason }}</span>，
    已為你選好下方服務，確認資料後就能送出。
  </p>
  <p v-else-if="submittedNeed" class="need-echo warn" data-testid="need-unmatched" role="status">
    你說「{{ submittedNeed }}」——我還無法對應到現有服務，請從下方挑一項，或改個說法再試。
  </p>

  <div class="service-layout">
    <div class="service-main">
      <form class="service-search" role="search" @submit.prevent>
        <label>
          <span class="search-mark" aria-hidden="true">搜</span>
          <span class="visually-hidden">搜尋服務</span>
          <input v-model="search" type="search" placeholder="輸入服務、需求或合作夥伴" />
        </label>
        <button class="button primary" type="button" aria-label="語音搜尋尚未啟用">語音</button>
      </form>

      <section v-if="store.services.length" class="panel" aria-labelledby="common-services">
        <div class="section-title-row"><h2 id="common-services">我的常用服務</h2><button class="text-button" type="button">編輯</button></div>
        <div class="quick-grid">
          <button v-for="(service, index) in store.services.slice(0, 5)" :key="service.id" class="quick-service" type="button" @click="chooseService(service.id)">
            <span class="service-glyph" :data-hue="index % 4" aria-hidden="true">{{ service.glyph }}</span><strong>{{ service.name }}</strong>
          </button>
        </div>
      </section>

      <section class="context-banner" aria-labelledby="ai-suggestion">
        <div><p class="eyebrow">AI 情境建議</p><h2 id="ai-suggestion">週末適合處理冷氣清洗</h2><p>依高溫預報、你的待辦與附近可預約時段整理。</p></div>
        <div class="context-score"><strong>3</strong><span>個可預約時段</span></div>
      </section>

      <section class="panel catalog-panel" aria-labelledby="all-services">
        <div class="section-title-row"><h2 id="all-services">所有服務</h2><span class="muted">{{ visibleServices.length }} 項結果</span></div>
        <p v-if="store.catalogStatus === 'loading'" class="muted" role="status">服務目錄載入中…</p>
        <p v-else-if="store.catalogStatus === 'unavailable'" class="muted" role="status">目前無法取得服務目錄，請確認後端服務是否啟動。</p>
        <template v-for="category in categories" :key="category">
          <div v-if="visibleServices.some((service) => service.category === category)" class="catalog-group">
            <h3>{{ category }}</h3>
            <div class="catalog-grid">
              <button
                v-for="(service, index) in visibleServices.filter((item) => item.category === category)"
                :key="service.id"
                class="catalog-service"
                :class="{ 'is-selected': store.selectedServiceId === service.id }"
                type="button"
                data-testid="service-card"
                :data-service-id="service.id"
                :aria-pressed="store.selectedServiceId === service.id"
                @click="chooseService(service.id)"
              >
                <span class="service-glyph" :data-hue="index % 4" aria-hidden="true">{{ service.glyph }}</span><strong>{{ service.name }}</strong>
              </button>
            </div>
          </div>
        </template>
      </section>
    </div>

    <aside class="panel service-detail" aria-live="polite">
      <template v-if="store.selectedService">
        <span class="detail-brand">{{ store.selectedService.partner }}</span>
        <h2>{{ store.selectedService.name }}</h2>
        <p class="detail-copy">{{ store.selectedService.summary }}</p>
        <ServiceIntakeForm v-if="selectedForm" :form="selectedForm" :answers="store.selectedAnswers" :errors="errors" @answer="setAnswer" />
        <dl class="summary-list">
          <div><dt>商品／服務</dt><dd>NT$ {{ store.pricing.baseAmount.toLocaleString('zh-TW') }}</dd></div>
          <div v-if="store.pricing.couponDiscount"><dt>優惠券</dt><dd>− NT$ {{ store.pricing.couponDiscount }}</dd></div>
          <div v-if="store.pricing.pointDiscount"><dt>OPENPOINT 折抵</dt><dd>− NT$ {{ store.pricing.pointDiscount }}</dd></div>
          <div v-if="store.pricing.paymentDiscount"><dt>支付加碼</dt><dd>− NT$ {{ store.pricing.paymentDiscount }}</dd></div>
          <div><dt>應付金額</dt><dd>{{ store.pricing.baseAmount ? `NT$ ${store.pricing.finalAmount.toLocaleString('zh-TW')}` : '依訂位結果' }}</dd></div>
          <div><dt>串接方式</dt><dd>統一服務 API</dd></div>
        </dl>
        <button class="button primary full" type="button" data-testid="continue-service" @click="continueWithService">{{ selectedForm?.actionLabel ?? '繼續安排' }}</button>
      </template>
      <div v-else class="empty-state"><span aria-hidden="true">＋</span><h2>選擇一項服務</h2><p>這裡會先顯示合作夥伴、價格與送出內容。</p></div>
    </aside>
  </div>

  <ConfirmDialog
    :open="dialogOpen"
    :title="`確認${store.selectedService?.name ?? '服務'}`"
    :description="`將由 ${store.selectedService?.partner ?? '合作夥伴'} 接收需求，送出後可在訂單頁追蹤。`"
    :amount="store.pricing.finalAmount"
    :details="selectedForm ? summarizeServiceAnswers(selectedForm, store.selectedAnswers) : []"
    :data-use="selectedForm?.dataUse"
    @cancel="dialogOpen = false"
    @confirm="confirmOrder"
  />
</template>
