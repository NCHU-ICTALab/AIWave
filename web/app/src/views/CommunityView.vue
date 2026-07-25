<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { createCommunityClient, type Campaign, type PurchaseOrder } from '@/api/communityClient'

/** 管委會工作台：開團、看跟團狀況、結單並產出給廠商的採購彙總。 */
const client = createCommunityClient()

const campaigns = ref<Campaign[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const acting = ref<number | null>(null)
const error = ref('')
const purchaseOrder = ref<PurchaseOrder | null>(null)
const creating = ref(false)

const draft = reactive({ title: '', item_name: '', unit_price: 0, min_quantity: 10, pickup: '社區管理室' })
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`

async function load() {
  try {
    campaigns.value = await client.listAll()
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
  }
}

async function createCampaign() {
  if (!draft.title.trim() || !draft.item_name.trim() || draft.unit_price <= 0) {
    error.value = '請填寫團購名稱、品項與單價。'
    return
  }
  creating.value = true
  error.value = ''
  try {
    await client.create({ ...draft, unit_price: Number(draft.unit_price), min_quantity: Number(draft.min_quantity) })
    Object.assign(draft, { title: '', item_name: '', unit_price: 0, min_quantity: 10, pickup: '社區管理室' })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '開團未完成，請稍後再試。'
  } finally {
    creating.value = false
  }
}

async function close(campaign: Campaign) {
  acting.value = campaign.id
  error.value = ''
  try {
    const result = await client.close(campaign.id)
    purchaseOrder.value = result.purchaseOrder
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '結單未完成，請稍後再試。'
  } finally {
    acting.value = null
  }
}

onMounted(load)
</script>

<template>
  <header class="page-heading">
    <div><p class="eyebrow">社區管理</p><h1>團購管理</h1></div>
    <span class="page-status">{{ campaigns.filter((item) => item.status === 'open').length }} 檔收單中</span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>
  <p v-if="status === 'unavailable'" class="panel muted" role="status">
    無法取得團購資料，請確認後端服務是否啟動。
  </p>

  <div v-else class="grid">
    <section class="panel span-7" aria-labelledby="campaign-list">
      <h2 id="campaign-list">目前團購</h2>
      <p v-if="!campaigns.length" class="muted">還沒有開過團，右側可以建立第一檔。</p>

      <article v-for="campaign in campaigns" :key="campaign.id" class="inquiry-card" :data-campaign-id="campaign.id">
        <div class="inquiry-head">
          <div>
            <strong>{{ campaign.itemName }}</strong>
            <div class="row-meta">{{ campaign.title }}・{{ currency(campaign.unitPrice) }}／{{ campaign.unit }}</div>
          </div>
          <span class="status" :data-status="campaign.status">{{ campaign.statusLabel }}</span>
        </div>

        <div class="metric-row">
          <div class="metric"><span>跟團戶數</span><strong>{{ campaign.householdCount }}</strong></div>
          <div class="metric"><span>總數量</span><strong>{{ campaign.totalQuantity }}</strong></div>
          <div class="metric"><span>金額</span><strong>{{ currency(campaign.totalAmount) }}</strong></div>
          <div class="metric"><span>成團門檻</span><strong>{{ campaign.reachedMinimum ? '已達標' : `差 ${campaign.minQuantity - campaign.totalQuantity}` }}</strong></div>
        </div>

        <ul v-if="campaign.joins.length" class="plain-list" :data-joins-for="campaign.id">
          <li v-for="join in campaign.joins" :key="join.account_id">
            <strong>{{ join.display_name }}</strong> {{ join.quantity }} {{ campaign.unit }}
          </li>
        </ul>
        <p v-else class="muted">還沒有住戶跟團。</p>

        <button
          v-if="campaign.status === 'open'"
          class="button primary"
          type="button"
          :data-testid="`close-${campaign.id}`"
          :disabled="acting === campaign.id"
          @click="close(campaign)"
        >{{ acting === campaign.id ? '結單中…' : '結單並彙總給廠商' }}</button>
      </article>
    </section>

    <aside class="panel span-5" aria-labelledby="new-campaign">
      <h2 id="new-campaign">開一檔新團購</h2>
      <div class="campaign-form">
        <label class="field">團購名稱
          <input v-model="draft.title" type="text" data-testid="campaign-title" placeholder="例如：八月社區團購" />
        </label>
        <label class="field">品項
          <input v-model="draft.item_name" type="text" data-testid="campaign-item" placeholder="例如：愛文芒果 5 斤" />
        </label>
        <label class="field">單價
          <input v-model.number="draft.unit_price" type="number" min="0" data-testid="campaign-price" />
        </label>
        <label class="field">成團門檻
          <input v-model.number="draft.min_quantity" type="number" min="1" data-testid="campaign-min" />
        </label>
        <label class="field">取貨方式
          <input v-model="draft.pickup" type="text" />
        </label>
        <button class="button primary full" type="button" data-testid="create-campaign" :disabled="creating" @click="createCampaign">
          {{ creating ? '建立中…' : '開團' }}
        </button>
      </div>

      <div v-if="purchaseOrder" class="quote-box" data-testid="purchase-order">
        <p class="eyebrow">給廠商的採購單</p>
        <dl class="summary-list compact">
          <div><dt>品項</dt><dd>{{ purchaseOrder.itemName }}</dd></div>
          <div><dt>總數量</dt><dd>{{ purchaseOrder.totalQuantity }}</dd></div>
          <div><dt>戶數</dt><dd>{{ purchaseOrder.householdCount }}</dd></div>
          <div><dt>金額</dt><dd><strong>{{ currency(purchaseOrder.totalAmount) }}</strong></dd></div>
        </dl>
        <ul class="plain-list">
          <li v-for="household in purchaseOrder.households" :key="household.name">
            {{ household.name }} × {{ household.quantity }}
          </li>
        </ul>
      </div>
    </aside>
  </div>
</template>
