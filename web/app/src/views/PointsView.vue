<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { createLifestyleClient, type RestockPlan } from '@/api/lifestyleClient'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const lifestyle = createLifestyleClient()
const plan = ref<RestockPlan | null>(null)
const loading = ref(false)
const error = ref('')

function money(value: number) {
  return `NT$ ${new Intl.NumberFormat('zh-TW').format(value)}`
}

async function loadPlan() {
  if (!session.accountId) return
  loading.value = true
  error.value = ''
  try {
    plan.value = await lifestyle.restockPlan(session.accountId)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '暫時無法讀取點數方案'
  } finally {
    loading.value = false
  }
}

onMounted(loadPlan)
</script>

<template>
  <section class="member-page points-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">POINTS & SAVINGS</p>
        <h1>點數兌換</h1>
        <p class="muted">先看可用資源與試算結果，確認後才會前往服務頁。</p>
      </div>
      <span class="page-status">競賽展示錢包</span>
    </header>

    <div v-if="loading" class="panel state-panel" role="status">正在整理點數與優惠方案…</div>

    <div v-else-if="error" class="panel state-panel" role="alert">
      <h2>目前讀不到點數方案</h2>
      <p>{{ error }}</p>
      <button class="button" type="button" @click="loadPlan">再試一次</button>
    </div>

    <div v-else-if="!session.accountId" class="panel state-panel">
      <h2>使用服務後，點數與優惠會整理在這裡</h2>
      <p class="muted">這個新帳號尚無消費與點數紀錄，不會顯示其他會員的資料。</p>
      <RouterLink class="button primary" to="/user/services">開始找服務</RouterLink>
    </div>

    <template v-else-if="plan">
      <div class="points-grid">
        <section class="panel wallet-card" aria-labelledby="wallet-title">
          <p class="eyebrow">AVAILABLE</p>
          <h2 id="wallet-title">目前可用</h2>
          <p class="points-balance" data-testid="points-balance">
            <strong>{{ plan.wallet.openpointBalance }}</strong>
            <span>OPENPOINT</span>
          </p>
          <dl class="wallet-list">
            <div>
              <dt>可用優惠券</dt>
              <dd>{{ plan.wallet.coupon?.label ?? '目前沒有' }}</dd>
            </div>
            <div>
              <dt>建議支付</dt>
              <dd>{{ plan.wallet.payment ?? '付款時再選擇' }}</dd>
            </div>
          </dl>
          <p class="source-note">資料來源：競賽展示錢包，非 OPENPOINT 即時帳戶。</p>
        </section>

        <section class="panel offer-card" data-testid="best-offer" aria-labelledby="offer-title">
          <div class="section-title-row">
            <div>
              <p class="eyebrow">BEST COMBINATION</p>
              <h2 id="offer-title">{{ plan.recommendation.title }}</h2>
            </div>
            <span class="status">省下 {{ money(plan.bestOffer.savedAmount) }}</span>
          </div>
          <p>{{ plan.recommendation.reasonText }}</p>
          <div class="offer-total">
            <span>試算後</span>
            <strong>{{ money(plan.bestOffer.finalAmount) }}</strong>
            <del>{{ money(plan.bestOffer.baseAmount) }}</del>
          </div>
          <ul class="applied-list" aria-label="已套用優惠">
            <li v-for="rule in plan.bestOffer.applied" :key="rule">{{ rule }}</li>
          </ul>
          <div class="button-row">
            <RouterLink
              class="button primary"
              to="/user/services/shopping"
              data-testid="use-best-offer"
            >
              前往使用最佳方案
            </RouterLink>
            <RouterLink class="button secondary" to="/user/assistant?prompt=幫我試算點數怎麼用最划算">
              問 AI 重新試算
            </RouterLink>
          </div>
          <p class="source-note">金額由確定性規則計算；下單前仍會再次顯示完整明細並要求確認。</p>
        </section>
      </div>
    </template>
  </section>
</template>
