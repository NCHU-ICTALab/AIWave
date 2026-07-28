<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { createCommunityClient, type Campaign, type PurchaseOrder } from '@/api/communityClient'
import { createJointServiceClient, type JointProposal, type JointServiceCampaign } from '@/api/jointServiceClient'
import { createSupportClient, type SupportTicket } from '@/api/supportClient'
import { useSessionStore } from '@/stores/session'

/** 管委會工作台：開團、看跟團狀況、結單並產出給廠商的採購彙總。 */
const client = createCommunityClient()
const supportClient = createSupportClient()
const jointClient = createJointServiceClient()
const session = useSessionStore()

const campaigns = ref<Campaign[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const acting = ref<number | null>(null)
const error = ref('')
const purchaseOrder = ref<PurchaseOrder | null>(null)
const creating = ref(false)
const supportQueue = ref<SupportTicket[]>([])
const supportStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const supportActing = ref<string | null>(null)
const confirmingStart = ref<string | null>(null)
const confirmingResolve = ref<string | null>(null)
const resolutionNotes = reactive<Record<string, string>>({})
const supportNotice = ref('')
const jointCampaigns = ref<JointServiceCampaign[]>([])
const jointStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const jointActing = ref<number | null>(null)
const confirmingProposal = ref<string | null>(null)
const jointNotice = ref('')
const jointDraftTitle = ref('九月社區冷氣聯合服務')
const confirmingJointAction = ref<{ id: number; action: 'publish' | 'prepare' } | null>(null)

const draft = reactive({ title: '', item_name: '', unit_price: 0, min_quantity: 10, pickup: '社區管理室' })
const currency = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`
const eventLabel = (type: string) => ({
  'joint_service.proposals_ready': '方案已備妥', 'joint_service.assigned': '方案已指派',
  'joint_service.started': '廠商已開工', 'joint_service.completed': '服務已完成',
}[type] ?? type)
const priorityLabel = (priority: SupportTicket['priority']) => ({ high: '高優先', medium: '中優先', normal: '一般' })[priority]
const deadline = (value: string) => new Intl.DateTimeFormat('zh-TW', {
  month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
}).format(new Date(value))
const slaLabel = (ticket: SupportTicket) => {
  const due = new Date(ticket.dueAt).getTime()
  const started = ticket.events.find((event) => event.type === 'support.in_progress')
  if (started) return new Date(started.occurred_at).getTime() <= due ? '已在期限內接手' : '逾期接手'
  return ticket.asOf && new Date(ticket.asOf).getTime() > due ? '已逾期' : ticket.statusLabel
}

async function load() {
  try {
    campaigns.value = await client.listAll()
    status.value = 'ready'
    void loadSupport()
    void loadJointServices()
  } catch {
    status.value = 'unavailable'
  }
}

async function loadJointServices() {
  jointStatus.value = 'loading'
  try {
    jointCampaigns.value = await jointClient.managerList()
    jointStatus.value = 'ready'
  } catch {
    jointStatus.value = 'unavailable'
  }
}

async function assignProposal(campaign: JointServiceCampaign, proposal: JointProposal) {
  jointActing.value = campaign.id
  error.value = ''
  try {
    const updated = await jointClient.assign(campaign.id, proposal.id)
    jointCampaigns.value = jointCampaigns.value.map((item) => item.id === updated.id ? updated : item)
    jointNotice.value = `已指派「${proposal.vendorName}」，廠商工作台已收到同一筆標準工單。`
    confirmingProposal.value = null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '方案指派未完成，請稍後再試。'
  } finally {
    jointActing.value = null
  }
}

async function createJointDraft() {
  if (!jointDraftTitle.value.trim()) return
  try {
    const created = await jointClient.create(jointDraftTitle.value.trim())
    jointCampaigns.value = [created, ...jointCampaigns.value]
    jointNotice.value = 'AI 草稿已建立；預覽內容後仍需人工確認才會發布。'
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '草稿建立失敗。'
  }
}

async function advanceJoint(campaign: JointServiceCampaign, action: 'publish' | 'prepare') {
  jointActing.value = campaign.id
  try {
    const updated = action === 'publish'
      ? await jointClient.publish(campaign.id)
      : await jointClient.prepareProposals(campaign.id)
    jointCampaigns.value = jointCampaigns.value.map((item) => item.id === updated.id ? updated : item)
    jointNotice.value = action === 'publish' ? '已發布，住戶現在可匿名回覆需求。' : '已截止募集並產生兩案比較。'
    confirmingJointAction.value = null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '聯合服務狀態更新失敗。'
  } finally {
    jointActing.value = null
  }
}

async function loadSupport() {
  supportStatus.value = 'loading'
  try {
    supportQueue.value = await supportClient.queue()
    supportStatus.value = 'ready'
  } catch {
    supportStatus.value = 'unavailable'
  }
}

function replaceSupport(updated: SupportTicket) {
  supportQueue.value = updated.status === 'resolved'
    ? supportQueue.value.filter((ticket) => ticket.id !== updated.id)
    : supportQueue.value.map((ticket) => ticket.id === updated.id ? updated : ticket)
}

async function startSupport(ticket: SupportTicket) {
  supportActing.value = ticket.id
  error.value = ''
  try {
    replaceSupport(await supportClient.start(ticket.id))
    supportNotice.value = `${ticket.id} 已由 ${session.displayName} 接手。`
    confirmingStart.value = null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '客服工單目前無法接手，請稍後再試。'
  } finally {
    supportActing.value = null
  }
}

async function resolveSupport(ticket: SupportTicket) {
  const note = (resolutionNotes[ticket.id] ?? '').trim()
  if (!note) return
  supportActing.value = ticket.id
  error.value = ''
  try {
    replaceSupport(await supportClient.resolve(ticket.id, note))
    supportNotice.value = `${ticket.id} 已結案，處理結果已回到住戶訂單。`
    confirmingResolve.value = null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '客服工單目前無法結案，請稍後再試。'
  } finally {
    supportActing.value = null
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
    <div><p class="eyebrow">社區管理</p><h1>社區營運中心</h1></div>
    <span class="page-status">{{ campaigns.filter((item) => item.status === 'open').length }} 檔收單中</span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>
  <p v-if="status === 'unavailable'" class="panel muted" role="status">
    無法取得團購資料，請確認後端服務是否啟動。
  </p>

  <section v-if="jointStatus !== 'unavailable'" class="panel joint-hero" data-testid="joint-service-hero" aria-label="社區聯合服務管理">
    <p v-if="jointStatus === 'loading'" class="muted" role="status">正在彙整社區需求與合作方案…</p>
    <template v-for="campaign in jointCampaigns" :key="campaign.id">
      <div class="section-heading">
        <div>
          <p class="eyebrow">社區聯合服務 Hero</p>
          <h2>{{ campaign.title }}</h2>
          <p>{{ campaign.draft.notification }}</p>
        </div>
        <span class="status" :data-status="campaign.status">{{ campaign.statusLabel }}</span>
      </div>

      <p class="data-notice" role="note"><strong>資料說明：</strong>{{ campaign.dataNotice }}</p>
      <div class="copilot-draft">
        <div><p class="eyebrow">AI Copilot 草稿</p><p>{{ campaign.draft.generatedBy }}</p><p class="muted">{{ campaign.draft.serviceContext }}</p></div>
        <ul v-if="campaign.draft.questionnaire?.length" class="plain-list"><li v-for="question in campaign.draft.questionnaire" :key="question">{{ question }}</li></ul>
      </div>
      <p v-if="jointNotice" class="recommendation-feedback" role="status">{{ jointNotice }}</p>

      <div class="joint-metrics" aria-label="匿名需求摘要">
        <div><span>已表達需求</span><strong>{{ campaign.demand.householdCount }} 戶</strong></div>
        <div><span>待清洗設備</span><strong>{{ campaign.demand.unitCount }} 台</strong></div>
        <div><span>最多數時段</span><strong>{{ campaign.demand.timePreferences?.[0]?.label }}</strong></div>
        <div><span>個資保護</span><strong>匿名聚合</strong></div>
      </div>

      <details class="reason-details">
        <summary>查看需求證據與 AI 草稿</summary>
        <div class="evidence-grid">
          <div>
            <h3>需求怎麼算</h3>
            <ul class="plain-list">
              <li v-for="item in campaign.demand.equipment" :key="item.label">{{ item.label }} {{ item.count }} 台</li>
              <li v-for="item in campaign.demand.timePreferences" :key="item.label">{{ item.label }} {{ item.households }} 戶</li>
            </ul>
          </div>
          <div>
            <h3>需廠商確認</h3>
            <ul class="plain-list"><li v-for="item in campaign.demand.specialRequirements" :key="item">{{ item }}</li></ul>
            <p class="muted">{{ campaign.demand.privacy }}</p>
          </div>
        </div>
      </details>

      <div v-if="campaign.status === 'draft'" class="inline-confirm">
        <p>草稿尚未對住戶公開。請先核對服務名稱與資料題目，再確認發布。</p>
        <button class="button" type="button" @click="confirmingJointAction = { id: campaign.id, action: 'publish' }">預覽發布</button>
        <div v-if="confirmingJointAction?.id === campaign.id && confirmingJointAction.action === 'publish'" role="group" aria-label="確認發布聯合服務">
          <p>確認發布「{{ campaign.title }}」並開始募集匿名需求？</p>
          <button class="button primary" type="button" @click="advanceJoint(campaign, 'publish')">確認發布</button>
        </div>
      </div>
      <div v-if="campaign.status === 'collecting'" class="inline-confirm">
        <p>目前已彙整 {{ campaign.demand.householdCount }} 戶／{{ campaign.demand.unitCount }} 台；至少一戶才能截止並產生方案。</p>
        <button class="button" type="button" :disabled="campaign.demand.householdCount < 1" @click="confirmingJointAction = { id: campaign.id, action: 'prepare' }">預覽截止募集</button>
        <div v-if="confirmingJointAction?.id === campaign.id && confirmingJointAction.action === 'prepare'" role="group" aria-label="確認截止需求募集">
          <p>確認停止收件並依匿名彙總產生兩案比較？</p>
          <button class="button primary" type="button" @click="advanceJoint(campaign, 'prepare')">確認截止並產生方案</button>
        </div>
      </div>

      <p v-if="campaign.status === 'proposal_review'" class="comparison-method">
        條件符合度：住戶時段 40%＋價格 30%＋特殊需求涵蓋 30%；分數只協助比較，最終由管委會決定。
      </p>
      <div v-if="campaign.status === 'proposal_review'" class="proposal-grid" aria-label="合作方案比較">
        <article v-for="proposal in campaign.proposals" :key="proposal.id" class="proposal-card" :class="{ recommended: proposal.id === 'proposal-care' }">
          <div class="proposal-head">
            <div><span class="badge primary">{{ proposal.badge }}</span><h3>{{ proposal.vendorName }}</h3></div>
            <div class="proposal-score" :aria-label="`條件符合度 ${proposal.score} 分`"><strong>{{ proposal.score }}</strong><span>／100</span></div>
          </div>
          <p class="source-note">{{ proposal.sourceLabel }}</p>
          <dl class="quote-breakdown">
            <div v-for="item in proposal.items" :key="item.name"><dt>{{ item.name }}</dt><dd>{{ currency(item.amount) }}</dd></div>
            <div class="quote-sum"><dt>合計</dt><dd>{{ currency(proposal.total) }}</dd></div>
          </dl>
          <p><strong>可服務：</strong>{{ proposal.availableSlots.join('、') }}</p>
          <ul class="decision-list">
            <li v-for="item in proposal.strengths" :key="item"><span aria-hidden="true">✓</span>{{ item }}</li>
            <li v-for="item in proposal.concerns" :key="item" class="concern"><span aria-hidden="true">!</span>{{ item }}</li>
          </ul>
          <button class="button" type="button" :data-testid="`choose-${proposal.id}`" @click="confirmingProposal = proposal.id">
            選擇這個方案
          </button>
          <div v-if="confirmingProposal === proposal.id" class="inline-confirm" role="group" :aria-label="`確認指派 ${proposal.vendorName}`">
            <p>確認指派「{{ proposal.vendorName }}」？總額 {{ currency(proposal.total) }}，確認後廠商會收到工單。</p>
            <div class="button-row">
              <button class="button primary" type="button" :data-testid="`confirm-${proposal.id}`" :disabled="jointActing === campaign.id" @click="assignProposal(campaign, proposal)">確認指派</button>
              <button class="button" type="button" @click="confirmingProposal = null">返回比較</button>
            </div>
          </div>
        </article>
      </div>

      <div v-else class="assigned-summary">
        <div><p class="eyebrow">已選方案</p><h3>{{ campaign.selectedProposal?.vendorName }}</h3><p>{{ campaign.selectedProposal ? currency(campaign.selectedProposal.total) : '' }}</p></div>
        <ol class="event-timeline">
          <li v-for="event in campaign.events" :key="`${event.type}-${event.occurredAt}`"><strong>{{ eventLabel(event.type) }}</strong><span>{{ event.detail }}</span></li>
        </ol>
      </div>
    </template>
    <form class="joint-draft-form" @submit.prevent="createJointDraft">
      <label for="joint-draft-title">建立下一檔 AI 草稿</label>
      <div class="button-row"><input id="joint-draft-title" v-model="jointDraftTitle" type="text" /><button class="button" type="submit">建立草稿</button></div>
      <p class="muted">只建立草稿，不會直接通知住戶。</p>
    </form>
  </section>
  <div v-else class="error-state" role="status">
    <strong>聯合服務暫時無法載入</strong><p>客服與團購仍可使用。</p><button class="button" type="button" @click="loadJointServices">重新載入</button>
  </div>

  <section v-if="status === 'ready'" class="panel support-queue-panel" aria-labelledby="support-queue-title">
    <div class="section-heading">
      <div><p class="eyebrow">住戶異常</p><h2 id="support-queue-title">客服待處理</h2></div>
      <span class="page-status">{{ supportQueue.length }} 件</span>
    </div>
    <p v-if="supportNotice" class="recommendation-feedback" role="status">{{ supportNotice }}</p>
    <p v-if="supportStatus === 'loading'" class="muted" role="status">正在取得客服工單…</p>
    <div v-else-if="supportStatus === 'unavailable'" class="error-state" role="alert">
      <strong>客服佇列暫時無法載入</strong>
      <p>團購功能仍可使用；可以只重試客服資料。</p>
      <button class="button" type="button" @click="loadSupport">重新載入客服</button>
    </div>
    <p v-else-if="!supportQueue.length" class="muted">目前沒有待處理的住戶問題。</p>
    <div v-else class="support-queue-grid">
      <article v-for="ticket in supportQueue" :key="ticket.id" class="support-queue-card">
        <div class="support-ticket-head">
          <div><strong>{{ ticket.categoryLabel }}</strong><div class="row-meta">{{ ticket.id }}・{{ ticket.subjectId }}</div></div>
          <span class="status warn">{{ priorityLabel(ticket.priority) }}</span>
        </div>
        <p>{{ ticket.issueText }}</p>
        <p :class="slaLabel(ticket).includes('逾期') ? 'need-error' : 'muted'">
          處理期限 {{ deadline(ticket.dueAt) }}・{{ slaLabel(ticket) }}
        </p>

        <div v-if="ticket.status === 'open'">
          <button class="button primary" type="button" :data-testid="`support-start-${ticket.id}`"
            @click="confirmingStart = ticket.id">接手處理</button>
          <div v-if="confirmingStart === ticket.id" class="inline-confirm" role="group" aria-label="確認接手客服工單">
            <p>確認由「{{ session.displayName }}」接手 {{ ticket.id }}？住戶會看到處理中狀態。</p>
            <div class="button-row">
              <button class="button primary" type="button" :data-testid="`support-start-confirm-${ticket.id}`"
                :disabled="supportActing === ticket.id" @click="startSupport(ticket)">確認接手</button>
              <button class="button" type="button" @click="confirmingStart = null">取消</button>
            </div>
          </div>
        </div>

        <div v-else-if="ticket.status === 'in_progress'" class="support-resolution">
          <label :for="`resolution-${ticket.id}`">處理結果</label>
          <textarea :id="`resolution-${ticket.id}`" v-model="resolutionNotes[ticket.id]" rows="2"
            :data-testid="`support-resolution-${ticket.id}`" placeholder="例如：已重新安排 14:00 到場" />
          <button class="button" type="button" :data-testid="`support-resolve-${ticket.id}`"
            :disabled="!(resolutionNotes[ticket.id] ?? '').trim()" @click="confirmingResolve = ticket.id">預覽結案</button>
          <div v-if="confirmingResolve === ticket.id" class="inline-confirm" role="group" aria-label="確認完成客服工單">
            <p>將以「{{ resolutionNotes[ticket.id] }}」通知住戶並完成工單。</p>
            <div class="button-row">
              <button class="button primary" type="button" :data-testid="`support-resolve-confirm-${ticket.id}`"
                :disabled="supportActing === ticket.id" @click="resolveSupport(ticket)">確認結案</button>
              <button class="button" type="button" @click="confirmingResolve = null">返回修改</button>
            </div>
          </div>
        </div>
      </article>
    </div>
  </section>

  <div v-if="status === 'ready'" class="grid">
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
