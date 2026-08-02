<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { DEMO_HOUSEHOLD_ID } from '@/domain/communityDemo'
import { useCommunityDemoStore } from '@/stores/communityDemo'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const demo = useCommunityDemoStore()
const session = useSessionStore()
const dashboard = computed(() => demo.residentDashboard)
const group = computed(() => dashboard.value?.groupBuyHistory.find((item) => item.id === String(route.params.groupBuyId)) ?? null)
const householdId = computed(() => session.accountId ?? DEMO_HOUSEHOLD_ID)
const communityPath = computed(() => route.path.startsWith('/demo') ? '/demo/resident#group-buys' : '/user/community/group-buys')

const selectedVariantId = ref('')
const quantity = ref(1)
const feedback = ref('')
const error = ref('')

const selectedVariant = computed(() => group.value?.variants.find((item) => item.id === selectedVariantId.value) ?? group.value?.variants[0] ?? null)
const myJoin = computed(() => group.value?.joins.find((item) => item.householdId === householdId.value) ?? null)
const money = (value: number) => `NT$ ${value.toLocaleString('zh-TW')}`
const progressWidth = computed(() => group.value ? `${Math.min(100, Math.round((group.value.progressUnits / group.value.thresholdUnits) * 100))}%` : '0%')

const countdown = computed(() => {
  if (!group.value) return ''
  const remaining = new Date(group.value.closeAt).getTime() - new Date('2026-08-02T10:00:00+08:00').getTime()
  const hours = Math.max(0, Math.floor(remaining / (60 * 60 * 1000)))
  const days = Math.floor(hours / 24)
  return days ? `剩 ${days} 天 ${hours % 24} 小時` : `剩 ${hours} 小時`
})

function chooseVariant(id: string) {
  selectedVariantId.value = id
}

function adjustQuantity(delta: number) {
  quantity.value = Math.max(1, quantity.value + delta)
}

function join() {
  if (!group.value || !selectedVariant.value) return
  error.value = ''
  try {
    demo.joinGroupBuy({
      groupBuyId: group.value.id,
      variantId: selectedVariant.value.id,
      quantity: quantity.value,
      householdId: householdId.value,
      displayName: session.displayName === '主委陳建華' ? '王小明' : session.displayName,
      householdLabel: 'A 棟 12F-3',
    })
    feedback.value = `已跟團：${selectedVariant.value.label} × ${quantity.value}，訂單金額 ${money(selectedVariant.value.price * quantity.value)}。`
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '跟團未完成，請稍後再試。'
  }
}

function cancel() {
  if (!group.value) return
  demo.cancelGroupBuy(group.value.id, householdId.value)
  feedback.value = '已取消這筆跟團，截止前仍可重新加入。'
}

watch(group, (value) => {
  if (value && !selectedVariantId.value) selectedVariantId.value = value.variants[0]?.id ?? ''
}, { immediate: true })

onMounted(() => {
  demo.loadResident(householdId.value)
})
</script>

<template>
  <section v-if="group" class="demo-page demo-group-detail-page">
    <div class="demo-back-row"><button class="demo-text-button" type="button" @click="router.push(communityPath)">← 回社區首頁</button><span class="demo-kicker">COMMUNITY GROUP BUY</span></div>
    <header class="demo-detail-hero">
      <div>
        <p class="eyebrow">{{ group.supplierType === 'external' ? '外部廠商・成交抽成 3%' : '統一集團商品・免抽成' }}</p>
        <h1>{{ group.name }}</h1>
        <p>{{ group.description }}</p>
      </div>
      <div class="demo-detail-price"><span>市價</span><del>{{ money(group.marketPrice) }}</del><strong>社區價 {{ money(group.variants[0]?.price ?? 0) }} 起</strong></div>
    </header>

    <div class="demo-two-column demo-detail-columns">
      <section class="panel demo-panel" data-testid="group-buy-detail" aria-labelledby="group-buy-detail-title">
        <div class="demo-section-heading"><div><p class="eyebrow">ORDER DETAILS</p><h2 id="group-buy-detail-title">跟團規格</h2></div><span class="status">{{ group.statusLabel }}</span></div>
        <div class="demo-progress-block">
          <div class="demo-progress-label"><span>成團進度</span><strong data-testid="group-progress">{{ group.progressUnits }}/{{ group.thresholdUnits }} 跟團單位</strong></div>
          <div class="demo-progress large" role="progressbar" :aria-valuenow="group.progressUnits" :aria-valuemin="0" :aria-valuemax="group.thresholdUnits"><span :style="{ width: progressWidth }" /></div>
          <div class="demo-progress-note"><span>{{ countdown }}</span><span>預計到貨 {{ group.expectedArrival }}</span></div>
        </div>

        <fieldset class="demo-variant-fieldset">
          <legend>選擇規格</legend>
          <div class="demo-variant-grid">
            <label v-for="variant in group.variants" :key="variant.id" class="demo-variant-option" :class="{ selected: selectedVariantId === variant.id }">
              <input :data-testid="`variant-${variant.id}`" type="radio" name="group-variant" :value="variant.id" :checked="selectedVariantId === variant.id" @change="chooseVariant(variant.id)" />
              <span><strong>{{ variant.label }}</strong><small>{{ money(variant.price) }}</small></span>
            </label>
          </div>
        </fieldset>

        <div class="demo-quantity-row"><span>數量</span><div class="demo-stepper"><button type="button" aria-label="減少數量" @click="adjustQuantity(-1)">−</button><strong data-testid="group-quantity">{{ quantity }}</strong><button type="button" aria-label="增加數量" @click="adjustQuantity(1)">＋</button></div><strong class="demo-line-total">{{ money((selectedVariant?.price ?? 0) * quantity) }}</strong></div>
        <button class="button primary demo-join-button" data-testid="join-group-buy" type="button" :disabled="group.status !== 'open'" @click="join">{{ group.status === 'open' ? '我要 +1' : '目前已結束收單' }}</button>
        <p v-if="feedback" class="demo-success" data-testid="join-feedback" role="status">{{ feedback }}</p>
        <p v-if="error" class="demo-error" role="alert">{{ error }}</p>
        <div v-if="myJoin" class="demo-my-order" data-testid="my-group-order">
          <div><strong>{{ session.displayName }}已跟團</strong><span>A 棟 12F-3・{{ myJoin.variantLabel }} × {{ myJoin.quantity }}</span></div>
          <button v-if="group.status === 'open'" class="button" type="button" data-testid="cancel-group-buy" @click="cancel">截止前取消</button>
        </div>
        <p class="demo-note">成團門檻以「跟團單位」計算；六入 × 1 仍讓進度增加 1，規格彙總會另外記錄六入 1 組。</p>
      </section>

      <aside class="panel demo-panel" aria-labelledby="joined-list-title">
        <div class="demo-section-heading"><div><p class="eyebrow">JOINED HOUSEHOLDS</p><h2 id="joined-list-title">已跟團名單</h2></div><span class="demo-count-badge">{{ group.joins.length }} 戶</span></div>
        <ul v-if="group.joins.length" class="demo-list demo-join-list">
          <li v-for="join in group.joins" :key="join.householdId" :data-testid="`joined-${join.householdId}`"><div><strong>{{ join.displayName }}</strong><span class="demo-meta">{{ join.householdLabel }}</span></div><span>{{ join.variantLabel }} × {{ join.quantity }}</span></li>
        </ul>
        <p v-else class="demo-empty">發布後第一筆跟團會出現在這裡。</p>
        <div class="demo-price-explanation"><strong>為什麼有社區價？</strong><p>管委會以訂閱 AI 智慧社區服務取得平台優惠，價差回饋住戶；外部廠商成交抽成 3%，統一集團商品免抽成。</p></div>
      </aside>
    </div>
  </section>
  <section v-else class="panel demo-empty-page" role="alert"><h1>找不到這檔團購</h1><p>它可能尚未發布，或已被重設為 Demo 初始狀態。</p><RouterLink class="button primary" :to="communityPath">回社區首頁</RouterLink></section>
</template>
