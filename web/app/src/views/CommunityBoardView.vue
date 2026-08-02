<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { createCommunityClient, type Campaign } from '@/api/communityClient'
import { createGroupClient, type MemberGroup } from '@/api/groupClient'
import { backendAnswered, request } from '@/api/http'
import { createJointServiceClient, type JointServiceCampaign } from '@/api/jointServiceClient'
import { listCommunityAnnouncements, type CommunityAnnouncement } from '@/api/platformClient'
import { useSessionStore } from '@/stores/session'

/**
 * 住戶端的社區頁：社區是我所屬的範圍，不是另一種身分（ADR-0003）。
 *
 * `groupBuyOnly` 給免費社區用：團購是免費方案唯一開放的功能，所以公告、群組與
 * 共同需求收起來，但跟團／看自己跟的團必須留著——把整頁擋掉會連免費方案的核心
 * 價值一起擋掉。
 */
const props = withDefaults(defineProps<{ groupBuyOnly?: boolean }>(), { groupBuyOnly: false })
const session = useSessionStore()
const client = createCommunityClient()
const jointClient = createJointServiceClient({ accountId: session.accountId })
const groupClient = createGroupClient({ accountId: session.accountId })

const open = ref<Campaign[]>([])
const mine = ref<Campaign[]>([])
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
/**
 * 後端有沒有回應,決定我們可以講哪一句話。有 HTTP 狀態碼(401、403、500)就代表
 * 服務在跑,叫使用者去啟動一個已經在跑的服務只會蓋掉真正的原因——王小明的公告
 * 403 就是這樣被誤讀成「存取不到後端」的。
 */
const boardBackendAnswered = ref(false)
const acting = ref<number | null>(null)
const error = ref('')
const quantities = reactive<Record<number, number>>({})
const jointCampaigns = ref<JointServiceCampaign[]>([])
const jointActing = ref<number | null>(null)
const jointConsent = reactive<Record<number, boolean>>({})
const groups = ref<MemberGroup[]>([])
const groupMode = ref<'closed' | 'create' | 'join'>('closed')
const groupActing = ref(false)
const groupFeedback = ref('')
const leaveConfirmId = ref<string | null>(null)
const editingGroupId = ref<string | null>(null)
const renameValue = ref('')
const createGroupForm = reactive({ name: '' })
const inviteCode = ref('')
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
    const [openCampaigns, myCampaigns, sharedServices, memberGroups] = await Promise.all([
      client.listOpen(),
      session.accountId ? client.myParticipation(session.accountId) : Promise.resolve([]),
      session.accountId ? jointClient.residentList() : Promise.resolve([]),
      session.accountId ? groupClient.list() : Promise.resolve([]),
    ])
    open.value = openCampaigns
    mine.value = myCampaigns
    jointCampaigns.value = sharedServices
    groups.value = memberGroups
    status.value = 'ready'
  } catch (reason) {
    boardBackendAnswered.value = backendAnswered(reason)
    status.value = 'unavailable'
  }
}

function upsertGroup(group: MemberGroup) {
  const index = groups.value.findIndex((item) => item.id === group.id)
  if (index >= 0) groups.value[index] = group
  else groups.value = [group, ...groups.value]
}

async function createGroup() {
  groupActing.value = true
  error.value = ''
  groupFeedback.value = ''
  try {
    const group = await groupClient.create({
      name: createGroupForm.name,
      display_name: session.displayName,
    })
    upsertGroup(group)
    groupFeedback.value = `已建立「${group.name}」，可把邀請碼 ${group.inviteCode} 分享給成員。`
    createGroupForm.name = ''
    groupMode.value = 'closed'
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '群組未建立，請稍後再試。'
  } finally {
    groupActing.value = false
  }
}

async function joinGroup() {
  groupActing.value = true
  error.value = ''
  groupFeedback.value = ''
  try {
    const group = await groupClient.join({ invite_code: inviteCode.value, display_name: session.displayName })
    upsertGroup(group)
    groupFeedback.value = `已加入「${group.name}」。`
    inviteCode.value = ''
    groupMode.value = 'closed'
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '無法加入群組，請檢查邀請碼。'
  } finally {
    groupActing.value = false
  }
}

function startRename(group: MemberGroup) {
  editingGroupId.value = group.id
  renameValue.value = group.name
}

async function renameGroup(group: MemberGroup) {
  groupActing.value = true
  error.value = ''
  try {
    upsertGroup(await groupClient.rename(group.id, renameValue.value))
    editingGroupId.value = null
    groupFeedback.value = '群組名稱已更新。'
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '群組名稱未更新。'
  } finally {
    groupActing.value = false
  }
}

async function leaveGroup(group: MemberGroup) {
  groupActing.value = true
  error.value = ''
  try {
    await groupClient.leave(group.id)
    groups.value = groups.value.filter((item) => item.id !== group.id)
    leaveConfirmId.value = null
    groupFeedback.value = `已離開「${group.name}」。`
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '暫時無法離開群組。'
  } finally {
    groupActing.value = false
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

// ── 社區公告:獨立載入,失敗只影響這個 panel ──
interface MemberCommunity {
  id: string
  name: string
  membership?: { role: string; status: string; isDefault: boolean } | null
  isDefault?: boolean
}

const announcements = ref<CommunityAnnouncement[]>([])
const announcementCommunity = ref<MemberCommunity | null>(null)
const announcementStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const announcementBackendAnswered = ref(false)

/** 取會員社區:優先 default,其次第一個有 membership 的,最後第一個。 */
function pickCommunity(rows: MemberCommunity[]): MemberCommunity | null {
  const joined = rows.filter((row) => row.membership?.status === 'active' || row.isDefault)
  const pool = joined.length ? joined : rows
  return pool.find((row) => row.membership?.isDefault || row.isDefault) ?? pool[0] ?? null
}

async function loadAnnouncements() {
  announcementStatus.value = 'loading'
  try {
    const rows = await request<MemberCommunity[]>('/api/v1/platform/communities')
    const community = pickCommunity(Array.isArray(rows) ? rows : [])
    if (!community) {
      announcementCommunity.value = null
      announcements.value = []
      announcementStatus.value = 'ready'
      return
    }
    announcementCommunity.value = community
    const loaded = await listCommunityAnnouncements(community.id)
    announcements.value = Array.isArray(loaded) ? loaded : []
    announcementStatus.value = 'ready'
  } catch (reason) {
    announcementBackendAnswered.value = backendAnswered(reason)
    announcementStatus.value = 'unavailable'
  }
}

const announcementDate = (value: string) => (value ?? '').replace('T', ' ').slice(0, 16)

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

onMounted(() => {
  void load()
  void loadAnnouncements()
})
</script>

<template>
  <header v-if="!props.groupBuyOnly" class="page-heading">
    <div><p class="eyebrow">GROUPS & COMMUNITY</p><h1>群組與社區</h1></div>
    <span class="page-status">{{ groups.length }} 個群組</span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>
  <p v-if="status === 'unavailable'" class="panel muted" role="status" :data-backend-answered="String(boardBackendAnswered)">
    {{ boardBackendAnswered
      ? '後端有回應但無法提供社區資訊（可能是登入憑證已失效），請重新登入再試。'
      : '目前連不上後端服務，請確認 API 是否已啟動。' }}
  </p>

  <!-- 社區公告:管理者發布,住戶(社區成員)可讀 -->
  <section v-if="!props.groupBuyOnly" class="panel" data-testid="community-announcements" aria-labelledby="announcements-title">
    <div class="section-title-row">
      <div>
        <p class="eyebrow">COMMUNITY NEWS</p>
        <h2 id="announcements-title">社區公告</h2>
      </div>
      <span v-if="announcementCommunity" class="page-status">{{ announcementCommunity.name }}</span>
    </div>
    <p v-if="announcementStatus === 'loading'" class="muted" role="status">正在載入社區公告…</p>
    <p v-else-if="announcementStatus === 'unavailable'" class="muted" role="status" :data-backend-answered="String(announcementBackendAnswered)">
      {{ announcementBackendAnswered
        ? '後端有回應但沒有給你這個社區的公告（可能你還不是社區成員，或憑證已失效）；其他社區功能不受影響。'
        : '目前連不上後端服務，請確認 API 是否已啟動；其他社區功能不受影響。' }}
    </p>
    <template v-else>
      <p v-if="!announcementCommunity" class="muted">你目前不屬於任何社區，加入社區後才會看到公告。</p>
      <p v-else-if="!announcements.length" class="muted">目前沒有公告。</p>
      <ul v-else class="plain-list announcement-list">
        <li v-for="item in announcements" :key="item.id" data-testid="announcement-item">
          <details class="reason-details">
            <summary>
              <strong>{{ item.title }}</strong>
              <span class="muted">・{{ announcementDate(item.publishedAt) }}</span>
            </summary>
            <p>{{ item.body }}</p>
          </details>
        </li>
      </ul>
    </template>
  </section>

  <section v-if="status === 'ready' && !props.groupBuyOnly" class="panel group-hub" data-testid="my-groups" aria-labelledby="my-groups-title">
    <div class="section-title-row">
      <div>
        <p class="eyebrow">MY GROUPS</p>
        <h2 id="my-groups-title">我的群組</h2>
      </div>
      <span class="page-status">{{ groups.length }} 個</span>
    </div>
    <p class="muted">群組用途由你和成員自行決定；社區則是另一個獨立範圍。只有成員能看到群組內的共享內容。</p>
    <div class="group-hub-actions">
      <button class="button primary" type="button" data-testid="open-create-group"
        :disabled="!session.accountId" @click="groupMode = groupMode === 'create' ? 'closed' : 'create'">
        建立群組
      </button>
      <button class="button" type="button" data-testid="open-join-group"
        :disabled="!session.accountId" @click="groupMode = groupMode === 'join' ? 'closed' : 'join'">
        使用邀請碼加入
      </button>
    </div>
    <p v-if="!session.accountId" class="muted">請先使用既有 Demo 住戶，或完成新帳號註冊後再建立群組。</p>

    <form v-if="groupMode === 'create'" class="group-inline-form" @submit.prevent="createGroup">
      <label class="field">群組名稱
        <input v-model="createGroupForm.name" data-testid="group-name" required minlength="2" maxlength="40"
          autocomplete="off" placeholder="例如：我們家、週末讀書會" />
      </label>
      <div class="group-form-actions">
        <button class="button primary" type="submit" data-testid="create-group" :disabled="groupActing || createGroupForm.name.trim().length < 2">
          {{ groupActing ? '建立中…' : '建立並取得邀請碼' }}
        </button>
        <button class="button ghost" type="button" @click="groupMode = 'closed'">取消</button>
      </div>
    </form>

    <form v-if="groupMode === 'join'" class="group-inline-form" @submit.prevent="joinGroup">
      <label class="field">邀請碼
        <input v-model="inviteCode" data-testid="invite-code" required autocomplete="off"
          autocapitalize="characters" placeholder="例如 HOME-7284" />
      </label>
      <p class="muted">加入後，你會成為該群組成員；共享資料仍依每項功能的同意設定處理。</p>
      <div class="group-form-actions">
        <button class="button primary" type="submit" data-testid="join-group" :disabled="groupActing || !inviteCode.trim()">
          {{ groupActing ? '加入中…' : '確認加入' }}
        </button>
        <button class="button ghost" type="button" @click="groupMode = 'closed'">取消</button>
      </div>
    </form>

    <p v-if="groupFeedback" class="feedback-inline" role="status">{{ groupFeedback }}</p>
    <p v-if="session.accountId && !groups.length" class="empty-state">你還沒有群組。建立一個群組，或向管理者索取邀請碼。</p>

    <div class="member-group-grid">
      <details v-for="group in groups" :key="group.id" class="member-group-card">
        <summary>
          <span><strong>{{ group.name }}</strong><small>{{ group.members.length }} 位成員</small></span>
          <span class="status">{{ group.myRoleLabel }}</span>
        </summary>
        <div class="member-group-body">
          <div class="invite-code-row">
            <span>邀請碼</span><strong>{{ group.inviteCode }}</strong>
          </div>
          <ul class="group-member-list" :aria-label="`${group.name}成員`">
            <li v-for="member in group.members" :key="member.accountId">
              <span>{{ member.displayName }}</span><span class="muted">{{ member.roleLabel }}</span>
            </li>
          </ul>

          <form v-if="editingGroupId === group.id" class="group-rename-form" @submit.prevent="renameGroup(group)">
            <label class="field">新的群組名稱
              <input v-model="renameValue" required minlength="2" maxlength="40" />
            </label>
            <div class="group-form-actions">
              <button class="button primary" type="submit" :disabled="groupActing || renameValue.trim().length < 2">儲存名稱</button>
              <button class="button ghost" type="button" @click="editingGroupId = null">取消</button>
            </div>
          </form>
          <div v-else class="group-card-actions">
            <button v-if="group.myRole === 'admin'" class="button" type="button" @click="startRename(group)">修改名稱</button>
            <button v-if="group.myRole === 'member' || group.members.length === 1" class="button danger" type="button"
              @click="leaveConfirmId = group.id">
              {{ group.members.length === 1 ? '刪除群組' : '離開群組' }}
            </button>
          </div>
          <div v-if="leaveConfirmId === group.id" class="group-leave-confirm" role="alert">
            <p>確定要{{ group.members.length === 1 ? '刪除這個群組' : '離開這個群組' }}嗎？共享內容將不再出現在你的帳號。</p>
            <div class="group-form-actions">
              <button class="button danger" type="button" :disabled="groupActing" @click="leaveGroup(group)">確定</button>
              <button class="button ghost" type="button" @click="leaveConfirmId = null">保留群組</button>
            </div>
          </div>
        </div>
      </details>
    </div>
  </section>

  <section v-if="status === 'ready' && !props.groupBuyOnly" class="panel group-demand-panel" aria-labelledby="joint-demand-title">
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
