<script setup lang="ts">
// aiwave-admin 工作台:目錄健康、重新同步與 Demo 重置。
// 這頁不在主導覽,由登入頁的「平台營運管理台」進入(ADR-0015)。
// 所有數字都是 fake upstream 的展示資料(partner-demo-v5),不是真實營運指標。
import { onMounted, ref } from 'vue'

import {
  getCatalogHealth,
  getUpstreamHealth,
  injectUpstreamFault,
  listDemoPersonas,
  resetDemo,
  resetPersonaWorkspace,
  syncCatalog,
  type CatalogHealthRow,
  type DemoPersona,
  type UpstreamHealth,
} from '@/api/platformClient'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const healthRows = ref<CatalogHealthRow[]>([])
const healthStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const error = ref('')

const syncing = ref(false)
const syncResult = ref<{ status: string; failed: string[] } | null>(null)

const confirmingReset = ref(false)
const resetting = ref(false)
const resetResult = ref('')

async function loadHealth() {
  healthStatus.value = 'loading'
  error.value = ''
  try {
    healthRows.value = await getCatalogHealth()
    healthStatus.value = 'ready'
  } catch (reason) {
    healthStatus.value = 'unavailable'
    error.value = reason instanceof Error ? reason.message : '無法取得目錄健康狀態。'
  }
}

async function runSync() {
  syncing.value = true
  error.value = ''
  syncResult.value = null
  try {
    const result = await syncCatalog()
    const providers = (result.providers ?? []) as Array<{ providerId?: string; status?: string }>
    // partial / failed 時誠實列出失敗的 provider,不假裝全部成功
    const failed = providers
      .filter((item) => item.status && item.status !== 'synced' && item.status !== 'ok')
      .map((item) => String(item.providerId ?? '未知 provider'))
    syncResult.value = { status: result.status, failed }
    await loadHealth()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '目錄同步失敗。'
  } finally {
    syncing.value = false
  }
}

// ── Demo workspaces(固定 personas) ──

const personas = ref<DemoPersona[]>([])
const personasStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const personaResetTarget = ref<DemoPersona | null>(null)
const resettingPersona = ref(false)
const personaResetResult = ref('')

async function loadPersonas() {
  personasStatus.value = 'loading'
  try {
    personas.value = await listDemoPersonas()
    personasStatus.value = 'ready'
  } catch {
    personasStatus.value = 'unavailable'
  }
}

async function confirmPersonaReset() {
  const target = personaResetTarget.value
  if (!target) return
  resettingPersona.value = true
  error.value = ''
  try {
    await resetPersonaWorkspace(target.membershipId)
    personaResetResult.value = `已重置「${target.displayName}」的個人 workspace,其他 workspace 不受影響。`
    personaResetTarget.value = null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '個人 workspace 重置失敗。'
    personaResetTarget.value = null
  } finally {
    resettingPersona.value = false
  }
}

// ── Fake upstream 健康與故障注入 ──

const upstream = ref<UpstreamHealth | null>(null)
const upstreamStatus = ref<'loading' | 'ready' | 'unavailable'>('loading')
const injecting = ref(false)
const faultResult = ref('')

async function loadUpstream() {
  upstreamStatus.value = 'loading'
  try {
    upstream.value = await getUpstreamHealth()
    upstreamStatus.value = 'ready'
  } catch {
    upstreamStatus.value = 'unavailable'
  }
}

async function runFault(action: 'timeout' | 'http_503' | 'clear') {
  injecting.value = true
  error.value = ''
  faultResult.value = ''
  try {
    await injectUpstreamFault(action)
    faultResult.value =
      action === 'clear'
        ? '已清除故障注入,fake upstream 恢復正常。'
        : `已注入 ${action === 'timeout' ? 'timeout' : 'HTTP 503'}(一次性 fault,下一次建單觸發)。`
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '故障注入操作失敗。'
  } finally {
    injecting.value = false
  }
}

// ── Partner onboarding(誠實展示表) ──
// 12 家 tier-1 Provider 的名稱對照;接入狀態為展示資料,申請/審核/發 key 屬後續里程碑。
const PARTNER_NAMES: Record<string, string> = {
  'vendor-prince-electric': '王子水電',
  'vendor-duskin': 'DUSKIN 樂清',
  'vendor-21plus': '21PLUS',
  'vendor-smile': '速邁樂加油站 Smile',
  'vendor-blackcat': '黑貓宅急便',
  'vendor-cosmed': '康是美',
  'vendor-711-shop': '7-ELEVEN 線上購物中心',
  'vendor-uni-resort': '統一渡假村 Uni Resort',
  'vendor-foodomo': 'foodomo',
  'vendor-711-c2c': '7-ELEVEN 交貨便',
  'vendor-iopenmall': 'iOPEN Mall',
  'vendor-ibon-ticket': 'ibon 售票',
}
const partnerName = (providerId: string) => PARTNER_NAMES[providerId] ?? providerId

async function runReset() {
  resetting.value = true
  error.value = ''
  try {
    const result = await resetDemo()
    resetResult.value = typeof result.status === 'string' ? result.status : 'done'
    confirmingReset.value = false
    await loadHealth()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : 'Demo 重置失敗。'
  } finally {
    resetting.value = false
  }
}

onMounted(() => {
  void loadHealth()
  void loadPersonas()
  void loadUpstream()
})
</script>

<template>
  <header class="page-heading">
    <div><p class="eyebrow">社區小統・平台營運</p><h1>平台營運管理台</h1></div>
    <span class="page-status">展示資料（partner-demo-v5）</span>
  </header>

  <p v-if="error" class="need-error" role="alert">{{ error }}</p>

  <div class="grid">
    <section class="panel span-8" aria-labelledby="catalog-health-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Fake upstream 目錄</p>
          <h2 id="catalog-health-title">目錄健康</h2>
        </div>
        <button
          class="button primary"
          type="button"
          data-testid="sync-catalog"
          :disabled="syncing"
          @click="runSync"
        >{{ syncing ? '同步中…' : '重新同步目錄' }}</button>
      </div>
      <p class="data-notice">以下數字為展示資料（partner-demo-v5），來自 fake upstream 的種子目錄。</p>

      <p aria-live="polite" role="status" data-testid="sync-result" :class="syncResult ? 'data-notice' : 'visually-hidden'">
        <template v-if="syncResult">
          同步結果：{{ syncResult.status }}
          <template v-if="syncResult.failed.length">・失敗 provider：{{ syncResult.failed.join('、') }}</template>
        </template>
      </p>

      <p v-if="healthStatus === 'loading'" class="muted" role="status">正在取得目錄健康狀態…</p>
      <template v-else-if="healthStatus === 'unavailable'">
        <p class="result-notice" role="status">無法取得目錄健康狀態，這是真實的連線失敗，不是空目錄。</p>
        <button class="button" type="button" data-testid="health-retry" @click="loadHealth">重試</button>
      </template>
      <div v-else style="overflow-x: auto">
        <table data-testid="catalog-health-table" style="width: 100%; border-collapse: collapse; text-align: left">
          <caption class="visually-hidden">各 provider 的目錄同步狀態與可售量</caption>
          <thead>
            <tr>
              <th scope="col">Provider</th>
              <th scope="col">目錄版本</th>
              <th scope="col">同步時間</th>
              <th scope="col">方案數</th>
              <th scope="col">可預約時段</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in healthRows" :key="row.providerId" :data-provider-row="row.providerId">
              <th scope="row">{{ row.providerId }}</th>
              <td>{{ row.seedVersion }}</td>
              <td>{{ row.syncedAt }}</td>
              <td>{{ row.offerings }}</td>
              <td>{{ row.availableSlots }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!healthRows.length" class="empty-state compact">目前沒有任何 provider 目錄。</p>
      </div>
    </section>

    <aside class="panel span-4" aria-labelledby="admin-scope-title">
      <h2 id="admin-scope-title">這個帳號能做什麼</h2>
      <p class="muted">
        aiwave-admin 只管理固定的 Demo personas 與 fake upstream 的種子目錄：可以重新同步目錄、
        重置整個 Demo 情境。它不是無限制的越權帳號——看不到會員個資，也不能代替廠商或會員操作案件。
      </p>
      <p class="data-notice">本頁所有數字均為展示資料（partner-demo-v5）。</p>
    </aside>

    <section class="panel span-12" aria-labelledby="demo-workspaces-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">固定 Demo personas</p>
          <h2 id="demo-workspaces-title">Demo workspaces</h2>
        </div>
      </div>
      <p class="data-notice">重置只還原該 persona 的個人 workspace 至種子狀態,不影響其他 workspace;非個人 workspace 不提供重置。</p>
      <p aria-live="polite" role="status" data-testid="persona-reset-result" :class="personaResetResult ? 'data-notice' : 'visually-hidden'">
        {{ personaResetResult }}
      </p>

      <p v-if="personasStatus === 'loading'" class="muted" role="status">正在取得 Demo personas…</p>
      <p v-else-if="personasStatus === 'unavailable'" class="result-notice" role="status">
        無法取得 Demo personas，這是真實的連線失敗，不是沒有 persona。
      </p>
      <div v-else style="overflow-x: auto">
        <table data-testid="personas-table" style="width: 100%; border-collapse: collapse; text-align: left">
          <caption class="visually-hidden">固定 Demo personas 與其 workspace</caption>
          <thead>
            <tr>
              <th scope="col">Persona</th>
              <th scope="col">角色</th>
              <th scope="col">Workspace 類型</th>
              <th scope="col">Workspace</th>
              <th scope="col">動作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="persona in personas" :key="persona.membershipId" :data-persona-row="persona.membershipId">
              <th scope="row">{{ persona.displayName }}</th>
              <td>{{ persona.role }}</td>
              <td>{{ persona.workspace.kind }}</td>
              <td>{{ persona.workspace.name }}</td>
              <td>
                <button
                  v-if="persona.workspace.kind === 'personal'"
                  class="button"
                  type="button"
                  :data-testid="`reset-persona-${persona.membershipId}`"
                  :disabled="resettingPersona"
                  @click="personaResetTarget = persona"
                >重置此 workspace</button>
                <span v-else class="muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!personas.length" class="empty-state compact">目前沒有固定 Demo personas。</p>
      </div>

      <ConfirmDialog
        :open="personaResetTarget !== null"
        title="重置此 workspace？"
        :description="`將把「${personaResetTarget?.displayName ?? ''}」的個人 workspace 還原成種子狀態。其他 workspace 不受影響，此動作無法復原。`"
        @cancel="personaResetTarget = null"
        @confirm="confirmPersonaReset"
      />
    </section>

    <section class="panel span-6" aria-labelledby="upstream-health-title" data-testid="upstream-health">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Fake upstream</p>
          <h2 id="upstream-health-title">Fake upstream 健康</h2>
        </div>
        <button class="button" type="button" :disabled="upstreamStatus === 'loading'" @click="loadUpstream">重新整理</button>
      </div>

      <p v-if="upstreamStatus === 'loading'" class="muted" role="status">正在取得 fake upstream 健康狀態…</p>
      <p v-else-if="upstreamStatus === 'unavailable'" class="result-notice" role="status">
        無法取得 fake upstream 健康狀態，這是真實的連線失敗。
      </p>
      <dl v-else-if="upstream" class="summary-list">
        <div><dt>狀態</dt><dd><span class="status" :data-status="upstream.status">{{ upstream.status }}</span></dd></div>
        <div><dt>Upstream seed</dt><dd>{{ upstream.seedVersion ?? '未知' }}</dd></div>
        <div><dt>Platform seeds</dt><dd>{{ upstream.platformSeedVersions.join('、') || '—' }}</dd></div>
        <div>
          <dt>Seed 一致性</dt>
          <dd data-testid="upstream-consistent">
            <span v-if="upstream.consistent" class="status" data-status="completed">一致 ✓</span>
            <span v-else class="status warn">不一致：platform 與 upstream 的 seed 版本不同，請重新同步目錄。</span>
          </dd>
        </div>
      </dl>

      <div class="button-row" style="margin-top: 12px">
        <button class="button" type="button" data-testid="inject-timeout" :disabled="injecting" @click="runFault('timeout')">注入 timeout</button>
        <button class="button" type="button" data-testid="inject-503" :disabled="injecting" @click="runFault('http_503')">注入 503</button>
        <button class="button" type="button" data-testid="clear-fault" :disabled="injecting" @click="runFault('clear')">清除注入</button>
      </div>
      <p aria-live="polite" role="status" data-testid="fault-result" :class="faultResult ? 'data-notice' : 'visually-hidden'">
        {{ faultResult }}
      </p>
      <p class="muted">故障為一次性 fault:只影響下一次建單請求,可在會員端展示重試與降級路徑。</p>
    </section>

    <section class="panel span-6" aria-labelledby="onboarding-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">合作廠商</p>
          <h2 id="onboarding-title">Partner onboarding</h2>
        </div>
      </div>
      <p class="data-notice">接入狀態為展示資料;申請/審核/發 key 流程屬後續里程碑,本頁不提供假審核操作。</p>
      <div style="overflow-x: auto">
        <table data-testid="onboarding-table" style="width: 100%; border-collapse: collapse; text-align: left">
          <caption class="visually-hidden">tier-1 合作廠商接入狀態</caption>
          <thead>
            <tr><th scope="col">廠商</th><th scope="col">Provider ID</th><th scope="col">狀態</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in healthRows" :key="`onboard-${row.providerId}`" :data-onboarding-row="row.providerId">
              <th scope="row">{{ partnerName(row.providerId) }}</th>
              <td>{{ row.providerId }}</td>
              <td><span class="status" data-status="completed">已上線（標準接入）</span></td>
            </tr>
          </tbody>
        </table>
        <p v-if="!healthRows.length" class="empty-state compact">目錄尚未同步,暫無可列出的合作廠商。</p>
      </div>
    </section>

    <section class="panel span-12" aria-labelledby="demo-reset-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Demo 情境</p>
          <h2 id="demo-reset-title">重置整個 Demo</h2>
        </div>
        <button
          class="button"
          type="button"
          data-testid="reset-demo"
          :disabled="resetting"
          @click="confirmingReset = true"
        >重置整個 Demo</button>
      </div>
      <p class="muted">
        清除 Demo 期間產生的草稿、預約、訂單、付款、通知與行事曆，回到種子狀態。展示前排練用；此動作無法復原。
      </p>
      <p aria-live="polite" role="status" data-testid="reset-result" :class="resetResult ? 'data-notice' : 'visually-hidden'">
        <template v-if="resetResult">重置結果：{{ resetResult }}</template>
      </p>

      <div v-if="confirmingReset" class="modal-layer">
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="reset-confirm-title">
          <div class="modal-head"><h3 id="reset-confirm-title">確認重置整個 Demo？</h3></div>
          <p>所有 Demo 期間產生的案件與紀錄都會被清除，回到 partner-demo-v5 種子狀態。此動作無法復原。</p>
          <div class="modal-actions">
            <button
              class="button primary"
              type="button"
              data-testid="confirm-reset"
              :disabled="resetting"
              @click="runReset"
            >{{ resetting ? '重置中…' : '確認重置' }}</button>
            <button class="button" type="button" data-testid="cancel-reset" @click="confirmingReset = false">取消</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
