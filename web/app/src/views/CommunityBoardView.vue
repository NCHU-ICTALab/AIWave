<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { createCommunityClient, type Campaign } from '@/api/communityClient'
import { createJointServiceClient, type JointServiceCampaign } from '@/api/jointServiceClient'
import { useSessionStore } from '@/stores/session'

/** 住戶端的社區頁：社區是我所屬的範圍，不是另一種身分（ADR-0003）。 */
const session = useSessionStore()
const client = createCommunityClient()
const jointClient = createJointServiceClient({ accountId: session.accountId })

const open = ref<Campaign[]>([])
const mine = ref<Campaign[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const acting = ref<number | null>(null)
const error = ref('')
const quantities = reactive<Record<number, number>>({})
const jointCampaigns = ref<JointServiceCampaign[]>([])
const jointActing = ref<number | null>(null)
const jointConsent = reactive<Record<number, boolean>>({})
const jointAnswers = reactive<Record<number, {
  units: number; equipment: string; preferredSlot: string; specialRequirement: string
}>>({})

const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`
const joinedIds = computed(() => new Set(mine.value.map((campaign) => campaign.id)))
const collectingJointCampaigns = computed(() => jointCampaigns.value.filter((campaign) => campaign.status === 'collecting'))

function quantityFor(id: number) {
  if (!quantities[id]) quantities[id] = 1
  return quantities[id]
}

function jointAnswerFor(id: number) {
  if (!jointAnswers[id]) {
    jointAnswers[id] = { units: 1, equipment: '分離式冷氣', preferredSlot: '週六上午', specialRequirement: '' }
  }
  return jointAnswers[id]!
}

async function load() {
  try {
    const [openCampaigns, myCampaigns, sharedServices] = await Promise.all([
      client.listOpen(),
      session.accountId ? client.myParticipation(session.accountId) : Promise.resolve([]),
      session.accountId ? jointClient.residentList() : Promise.resolve([]),
    ])
    open.value = openCampaigns
    mine.value = myCampaigns
    jointCampaigns.value = sharedServices
    status.value = 'ready'
  } catch {
    status.value = 'unavailable'
  }
}

async function joinJointService(campaign: JointServiceCampaign) {
  if (!jointConsent[campaign.id]) {
    error.value = '請先確認同意匿名共享設備數量、時段與特殊需求。'
    return
  }
  jointActing.value = campaign.id
  error.value = ''
  try {
    const updated = await jointClient.join(campaign.id, jointAnswerFor(campaign.id))
    jointCampaigns.value = jointCampaigns.value.map((item) => item.id === updated.id ? updated : item)
    jointConsent[campaign.id] = false
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '共同需求未送出，請稍後再試。'
  } finally {
    jointActing.value = null
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

  <section v-if="status === 'ready'" class="panel group-demand-panel" aria-labelledby="joint-demand-title">
    <div class="section-title-row">
      <div><p class="eyebrow">SHARED NEED</p><h2 id="joint-demand-title">社區共同需求</h2></div>
      <span class="page-status">{{ collectingJointCampaigns.length }} 件募集</span>
    </div>
    <p class="muted">你仍是個人會員；這裡只把你同意的需求匿名加入所屬社區，不會分享姓名、電話或門牌。</p>
    <p v-if="!collectingJointCampaigns.length" class="muted">目前沒有正在募集的共同服務。</p>
    <article v-for="campaign in collectingJointCampaigns" :key="campaign.id" class="inquiry-card" data-testid="resident-joint-service">
      <div class="inquiry-head">
        <div><strong>{{ campaign.title }}</strong><div class="row-meta">{{ campaign.draft.notification }}</div></div>
        <span class="status">{{ campaign.statusLabel }}</span>
      </div>
      <p v-if="campaign.myParticipation" class="feedback-inline" role="status">
        已於 {{ new Date(campaign.myParticipation.consentedAt).toLocaleDateString('zh-TW') }} 同意加入：
        {{ campaign.myParticipation.equipment }} {{ campaign.myParticipation.units }} 台・{{ campaign.myParticipation.preferredSlot }}。
      </p>
      <div class="group-demand-form">
        <label class="field">設備型式
          <select v-model="jointAnswerFor(campaign.id).equipment">
            <option>分離式冷氣</option><option>窗型冷氣</option>
          </select>
        </label>
        <label class="field">台數
          <input v-model.number="jointAnswerFor(campaign.id).units" type="number" min="1" />
        </label>
        <label class="field">偏好時段
          <select v-model="jointAnswerFor(campaign.id).preferredSlot">
            <option>週六上午</option><option>週六下午</option><option>平日下午</option>
          </select>
        </label>
        <label class="field">特殊需求（選填）
          <input v-model="jointAnswerFor(campaign.id).specialRequirement" type="text" placeholder="例如：家中有幼兒" />
        </label>
      </div>
      <label class="consent-check">
        <input v-model="jointConsent[campaign.id]" type="checkbox" :data-testid="`joint-consent-${campaign.id}`" />
        我同意將設備型式、台數、偏好時段與特殊需求匿名彙整；不含姓名、電話與門牌。
      </label>
      <button class="button primary" type="button" :data-testid="`join-joint-${campaign.id}`"
        :disabled="jointActing === campaign.id || !jointConsent[campaign.id]" @click="joinJointService(campaign)">
        {{ jointActing === campaign.id ? '送出中…' : campaign.myParticipation ? '更新匿名需求' : '同意並加入需求' }}
      </button>
    </article>
  </section>

  <div v-if="status === 'ready'" class="grid">
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
