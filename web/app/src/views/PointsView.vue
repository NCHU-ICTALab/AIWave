<script setup lang="ts">
// 版面比照核准原型 design-system/aiwave/pages/points.html:
// 可用點數 KPI → 兌換優惠(以真實 restock plan 取代;後端無兌換 offer API)→ 點數明細。
// 資料仍走現有 API(pointsClient wallet + lifestyleClient restockPlan),不新增假資料。
import { computed, onMounted, ref } from 'vue'

import { createLifestyleClient, type RestockPlan } from '@/api/lifestyleClient'
import { createPointsClient, type PointsEntry, type PointsWallet } from '@/api/pointsClient'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const lifestyle = createLifestyleClient()
const points = createPointsClient()
const plan = ref<RestockPlan | null>(null)
const wallet = ref<PointsWallet | null>(null)
const loading = ref(false)
const error = ref('')

const entryTypeLabels: Record<PointsEntry['type'], string> = {
  earn: '取得',
  redeem: '折抵',
  refund: '退款',
  reverse: '沖銷',
  expire: '到期',
}

function money(value: number) {
  return `NT$ ${new Intl.NumberFormat('zh-TW').format(value)}`
}

function pointsNumber(value: number) {
  return new Intl.NumberFormat('zh-TW').format(value)
}

function entryDate(entry: PointsEntry) {
  if (!entry.createdAt) return '—'
  const parsed = new Date(entry.createdAt)
  if (Number.isNaN(parsed.getTime())) return '—'
  return `${parsed.getMonth() + 1}/${parsed.getDate()}`
}

function entryAmount(entry: PointsEntry) {
  if (entry.amount > 0) return `+${pointsNumber(entry.amount)}`
  if (entry.amount < 0) return `−${pointsNumber(Math.abs(entry.amount))}`
  return '0'
}

/** 新到舊排序;fixture/後端若缺 createdAt 就維持原順序,不臆造時間。 */
const sortedEntries = computed(() => {
  const entries = wallet.value?.entries ?? []
  return [...entries].sort((a, b) => (b.createdAt ?? '').localeCompare(a.createdAt ?? ''))
})

/** 到期提示只在後端帳本真的帶 expiresAt 時顯示;沒有就誠實不顯示。 */
const expiryNote = computed(() => {
  const candidates = (wallet.value?.entries ?? [])
    .filter((entry) => entry.expiresAt && entry.amount > 0)
    .sort((a, b) => (a.expiresAt ?? '').localeCompare(b.expiresAt ?? ''))
  const soonest = candidates[0]
  if (!soonest?.expiresAt) return ''
  const parsed = new Date(soonest.expiresAt)
  if (Number.isNaN(parsed.getTime())) return ''
  return `其中 ${pointsNumber(soonest.amount)} 點將於 ${parsed.getMonth() + 1}/${parsed.getDate()} 到期，建議優先使用`
})

async function loadPlan() {
  if (!session.accountId || session.isNewUser) return
  loading.value = true
  error.value = ''
  try {
    const [loadedPlan, loadedWallet] = await Promise.all([
      lifestyle.restockPlan(session.accountId),
      points.wallet(),
    ])
    plan.value = loadedPlan
    wallet.value = loadedWallet
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
    <h1>點數兌換</h1>
    <p class="page-lead">Demo points ledger：展示用可重置帳本，非真實 OPENPOINT 餘額。</p>

    <div v-if="loading" class="panel state-panel" role="status">正在整理點數與優惠方案…</div>

    <div v-else-if="error" class="panel state-panel" role="alert">
      <h2>目前讀不到點數方案</h2>
      <p>{{ error }}</p>
      <button class="button" type="button" @click="loadPlan">再試一次</button>
    </div>

    <div v-else-if="!session.accountId || session.isNewUser" class="panel state-panel" data-testid="empty-points-wallet">
      <h2>使用服務後，點數與優惠會整理在這裡</h2>
      <p class="muted">這個新帳號尚無消費與點數紀錄，不會顯示其他會員的資料。</p>
      <RouterLink class="button primary" to="/user/services">開始找服務</RouterLink>
    </div>

    <template v-else-if="plan && wallet">
      <section class="panel" aria-labelledby="balance-title">
        <h2 id="balance-title">可用點數</h2>
        <div class="balance-grid">
          <div class="kpi">
            <p class="points-balance" data-testid="points-balance">
              <strong>{{ pointsNumber(wallet.balance) }}</strong>
              <span>點</span>
            </p>
            <span class="kpi-label">可用點數（Demo 帳本）</span>
            <span v-if="expiryNote" class="kpi-note">{{ expiryNote }}</span>
          </div>
          <div class="balance-side">
            <p>折抵比率：1 點 = NT$1，付款時可直接折抵。</p>
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
          </div>
        </div>
        <p class="demo-note">資料來源：{{ wallet.label }}（Demo points ledger，可於會員中心重置，非真實 OPENPOINT）。</p>
      </section>

      <section class="panel" data-testid="best-offer" aria-labelledby="offer-title">
        <div class="section-title-row">
          <h2 id="offer-title">省錢方案</h2>
          <span class="status">省下 {{ money(plan.bestOffer.savedAmount) }}</span>
        </div>
        <div class="offer-card">
          <h3>{{ plan.recommendation.title }}</h3>
          <p>{{ plan.recommendation.reasonText }}</p>
          <p class="offer-cost">
            試算後 {{ money(plan.bestOffer.finalAmount) }}
            <del>{{ money(plan.bestOffer.baseAmount) }}</del>
          </p>
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
        </div>
        <p class="demo-note">金額由確定性規則計算；下單前仍會再次顯示完整明細並要求確認。</p>
      </section>

      <section class="panel" aria-labelledby="ledger-title">
        <h2 id="ledger-title">點數明細</h2>
        <div v-if="sortedEntries.length" class="table-wrap">
          <table class="ledger-table">
            <caption>依時間新到舊排序（Demo points ledger）</caption>
            <thead>
              <tr>
                <th scope="col">日期</th>
                <th scope="col">類型</th>
                <th scope="col">說明</th>
                <th scope="col">點數</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in sortedEntries" :key="entry.id">
                <td>{{ entryDate(entry) }}</td>
                <td>
                  <span class="badge" :data-entry-type="entry.type">{{ entryTypeLabels[entry.type] ?? entry.type }}</span>
                </td>
                <td>{{ entry.description }}</td>
                <td :class="entry.amount > 0 ? 'ledger-amount-plus' : 'ledger-amount-minus'">
                  {{ entryAmount(entry) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted" data-testid="empty-ledger">目前沒有點數異動紀錄。</p>
      </section>
    </template>
  </section>
</template>

<style scoped>
/* 寬度與卡片間距沿用全域 .member-page;此頁為單欄 card 堆疊(比照原型)。 */
.points-page h1 { margin-bottom: 0; }
.page-lead { margin: 0 0 .25rem; color: var(--muted); }

.balance-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 1rem; align-items: center; }
.kpi { display: grid; gap: .2rem; }
.kpi-label { color: var(--muted); font-size: .82rem; font-weight: 700; }
.kpi-note { color: var(--ink); font-size: .85rem; font-weight: 750; }
.balance-side p { margin: 0 0 .6rem; }
.wallet-list { display: grid; gap: .4rem; margin: 0; }
.wallet-list div { display: flex; justify-content: space-between; gap: 1rem; padding-top: .4rem; border-top: 1px solid var(--line); }
.wallet-list dt { color: var(--muted); }
.wallet-list dd { margin: 0; font-weight: 800; text-align: right; }

.offer-card { display: flex; flex-direction: column; gap: 6px; border: 2px solid var(--ink); border-radius: 16px; padding: 14px 16px; background: var(--surface); }
.offer-card h3 { margin: 0; }
.offer-card p { margin: 0; }
.offer-cost { font-weight: 900; }
.offer-cost del { margin-left: .4rem; color: var(--muted); font-weight: 600; }
.applied-list { margin: .2rem 0 0; padding-left: 1.2rem; }
.offer-card .button-row { margin-top: .4rem; }

.table-wrap { overflow-x: auto; }
.ledger-table { width: 100%; border-collapse: collapse; }
.ledger-table caption { padding-bottom: .5rem; color: var(--muted); font-size: .8rem; text-align: left; }
.ledger-table th, .ledger-table td { padding: .5rem .6rem; border-bottom: 2px solid var(--line); text-align: left; vertical-align: top; }
.ledger-table th { color: var(--muted); font-size: .85rem; }
.ledger-amount-plus { color: var(--primary); font-weight: 800; white-space: nowrap; }
.ledger-amount-minus { font-weight: 800; white-space: nowrap; }

.badge { display: inline-flex; align-items: center; padding: .1rem .55rem; border: 2px solid var(--ink); border-radius: 999px; background: var(--surface-2); font-size: .75rem; font-weight: 800; white-space: nowrap; }
.badge[data-entry-type='earn'] { background: var(--mint); }
.badge[data-entry-type='redeem'] { background: var(--lilac); }
.badge[data-entry-type='refund'] { background: var(--blue); }
.badge[data-entry-type='reverse'] { background: var(--surface-2); }
.badge[data-entry-type='expire'] { background: var(--peach); }

.demo-note { margin: .9rem 0 0; color: var(--muted); font-size: .8rem; }
.state-panel { display: grid; gap: .5rem; justify-items: start; }

@media (max-width: 700px) {
  .balance-grid { grid-template-columns: 1fr; }
}
</style>
