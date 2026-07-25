<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { createCommunityClient, type Campaign } from '@/api/communityClient'
import { useSessionStore } from '@/stores/session'

/** 住戶端的社區頁：社區是我所屬的範圍，不是另一種身分（ADR-0003）。 */
const session = useSessionStore()
const client = createCommunityClient()

const open = ref<Campaign[]>([])
const mine = ref<Campaign[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const acting = ref<number | null>(null)
const error = ref('')
const quantities = reactive<Record<number, number>>({})

const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`
const joinedIds = computed(() => new Set(mine.value.map((campaign) => campaign.id)))

function quantityFor(id: number) {
  if (!quantities[id]) quantities[id] = 1
  return quantities[id]
}

async function load() {
  try {
    const [openCampaigns, myCampaigns] = await Promise.all([
      client.listOpen(),
      session.accountId ? client.myParticipation(session.accountId) : Promise.resolve([]),
    ])
    open.value = openCampaigns
    mine.value = myCampaigns
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
  }
}

async function join(campaign: Campaign) {
  if (!session.accountId) {
    error.value = '新帳號還沒有住戶資料，請改用既有帳號登入後再跟團。'
    return
  }
  acting.value = campaign.id
  error.value = ''
  try {
    await client.join(campaign.id, session.accountId, session.identity?.displayName ?? '住戶', quantityFor(campaign.id))
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '跟團未完成，請稍後再試。'
  } finally {
    acting.value = null
  }
}

onMounted(load)
</script>

<template>
  <header class="page-heading">
    <div><p class="eyebrow">我的社區</p><h1>社區團購</h1></div>
    <span class="page-status">{{ open.length }} 檔進行中</span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>
  <p v-if="status === 'unavailable'" class="panel muted" role="status">
    無法取得社區資訊，請確認後端服務是否啟動。
  </p>

  <div v-else-if="status === 'ready'" class="grid">
    <section class="panel span-8" aria-labelledby="open-campaigns">
      <h2 id="open-campaigns">可以參加的團購</h2>
      <p v-if="!open.length" class="muted">目前社區沒有進行中的團購。</p>

      <article v-for="campaign in open" :key="campaign.id" class="inquiry-card" :data-campaign-id="campaign.id">
        <div class="inquiry-head">
          <div>
            <strong>{{ campaign.itemName }}</strong>
            <div class="row-meta">{{ campaign.title }}・{{ currency(campaign.unitPrice) }}／{{ campaign.unit }}</div>
          </div>
          <span class="status">{{ campaign.statusLabel }}</span>
        </div>

        <div class="metric-row">
          <div class="metric"><span>已跟團</span><strong>{{ campaign.householdCount }} 戶</strong></div>
          <div class="metric"><span>總數量</span><strong>{{ campaign.totalQuantity }} {{ campaign.unit }}</strong></div>
        </div>
        <p class="muted">
          成團門檻 {{ campaign.minQuantity }} {{ campaign.unit }}——
          <template v-if="campaign.reachedMinimum">已達標 ✓</template>
          <template v-else>還差 {{ campaign.minQuantity - campaign.totalQuantity }} {{ campaign.unit }}</template>
          <span v-if="campaign.pickup">・{{ campaign.pickup }}取貨</span>
        </p>

        <p v-if="joinedIds.has(campaign.id)" class="feedback-inline" role="status" :data-joined="campaign.id">
          你已跟團 {{ mine.find((item) => item.id === campaign.id)?.myQuantity }} {{ campaign.unit }}，可再調整數量。
        </p>

        <div class="quote-form">
          <label class="field">數量
            <input v-model.number="quantities[campaign.id]" type="number" min="1"
                   :data-quantity-for="campaign.id" :placeholder="String(quantityFor(campaign.id))" />
          </label>
          <button
            class="button primary"
            type="button"
            :data-testid="`join-${campaign.id}`"
            :disabled="acting === campaign.id"
            @click="join(campaign)"
          >{{ acting === campaign.id ? '處理中…' : joinedIds.has(campaign.id) ? '更新數量' : '我要跟團' }}</button>
        </div>
      </article>
    </section>

    <aside class="panel span-4" aria-labelledby="my-participation">
      <h2 id="my-participation">我跟的團</h2>
      <p v-if="!mine.length" class="muted">還沒有跟過團。</p>
      <div v-for="campaign in mine" :key="campaign.id" class="queue-row">
        <div>
          <strong>{{ campaign.itemName }}</strong>
          <div class="row-meta">
            {{ campaign.myQuantity }} {{ campaign.unit }}・{{ currency((campaign.myQuantity ?? 0) * campaign.unitPrice) }}
          </div>
        </div>
        <span class="status" :data-status="campaign.status">{{ campaign.statusLabel }}</span>
      </div>
    </aside>
  </div>
</template>
