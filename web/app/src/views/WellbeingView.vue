<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  actOnCareMessage,
  getMemberOutcomes,
  listCareMessages,
  listTaskPackages,
  patchTaskPackageItem,
  type CareMessage,
  type MemberOutcomeProjection,
  type TaskPackage,
} from '@/api/platformClient'

const messages = ref<CareMessage[]>([])
const packages = ref<TaskPackage[]>([])
const projection = ref<MemberOutcomeProjection | null>(null)
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const error = ref('')
const guide = ref<NonNullable<CareMessage['guide']> | null>(null)
const prepareNotice = ref('')
const pendingAction = ref('')

const activeMessages = computed(() => messages.value.filter((message) => !['closed', 'ignored', 'snoozed'].includes(message.state)))
const activePackages = computed(() => packages.value.filter((item) => item.status !== 'cancelled'))
const money = (value: number) => `NT$ ${(value ?? 0).toLocaleString('zh-TW')}`
const timeLabel = (value: string | null) => value ? value.replace('T', ' ').slice(0, 16) : '尚未選定時段'
const necessityLabel = (value: string) => ({
  'common-required': '常見必要', optional: '可選', convenience: '便利', 'cooperation-recommendation': '合作推薦（非必要）',
} as Record<string, string>)[value] ?? value

async function load() {
  status.value = 'loading'
  error.value = ''
  try {
    const [loadedMessages, loadedPackages, loadedProjection] = await Promise.all([
      listCareMessages(), listTaskPackages(), getMemberOutcomes(),
    ])
    messages.value = loadedMessages
    packages.value = loadedPackages
    projection.value = loadedProjection
    status.value = 'ready'
  } catch (reason) {
    status.value = 'unavailable'
    error.value = reason instanceof Error ? reason.message : '目前無法載入生活成果。'
  }
}

async function careAction(message: CareMessage, action: 'ignore' | 'snooze' | 'close' | 'open_guide') {
  pendingAction.value = message.id
  prepareNotice.value = ''
  try {
    const result = await actOnCareMessage(message.id, action)
    if (result.guide) guide.value = result.guide
    messages.value = action === 'open_guide'
      ? messages.value.map((item) => item.id === message.id ? result : item)
      : messages.value.filter((item) => item.id !== message.id || !['ignore', 'close'].includes(action))
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '照護訊息目前無法更新。'
  } finally {
    pendingAction.value = ''
  }
}

function prepareLifeGuide() {
  prepareNotice.value = '已整理成王小明的 Demo 準備清單，僅供確認類別與點數估算；尚未建立訂單。'
}

async function patchItem(
  taskPackage: TaskPackage,
  itemId: string,
  operation: 'pause' | 'resume' | 'remove',
) {
  pendingAction.value = itemId
  error.value = ''
  try {
    const updated = await patchTaskPackageItem(taskPackage.id, itemId, {
      expectedVersion: taskPackage.version, operation,
    })
    packages.value = packages.value.map((item) => item.id === updated.id ? updated : item)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '任務包版本已更新，請重新載入。'
  } finally {
    pendingAction.value = ''
  }
}

onMounted(() => { void load() })
</script>

<template>
  <main class="member-page wellbeing-page" data-testid="wellbeing-page">
    <header class="page-heading">
      <p class="eyebrow">AIWave v4</p>
      <h1>生活關懷與成果</h1>
      <p class="page-lead">把明確授權的情境、可編輯安排與已完成的結果放在同一頁。</p>
    </header>

    <div class="truth-banner" role="note">
      <strong>資料邊界</strong>
      <span>只使用你的 Demo event 與已建立的案件；不背景追蹤位置、不自動下單，Provider fee 只在合作方結算端顯示。</span>
    </div>

    <p v-if="status === 'loading'" class="panel" role="status">正在整理你的生活資訊…</p>
    <p v-else-if="status === 'unavailable'" class="panel error-state" role="alert">{{ error }}</p>

    <template v-else>
      <section class="panel wellbeing-section" aria-labelledby="care-title">
        <div class="section-title-row">
          <div>
            <p class="eyebrow">明確授權後才送達</p>
            <h2 id="care-title">主動照護</h2>
          </div>
          <span class="status" data-kind="suggestion">Demo event</span>
        </div>
        <p v-if="!activeMessages.length" class="muted">目前沒有待處理的照護訊息。</p>
        <article v-for="message in activeMessages" :key="message.id" class="care-card" data-testid="care-card">
          <div>
            <strong>中元關懷 Demo 事件</strong>
            <p>{{ message.candidate.reason }}</p>
            <small class="source-note">來源：{{ message.candidate.evidence.source }}・不保存背景位置</small>
          </div>
          <div class="button-row care-actions">
            <button class="button primary" type="button" :disabled="pendingAction === message.id" @click="careAction(message, 'open_guide')">查看指南與準備</button>
            <button class="button" type="button" :disabled="pendingAction === message.id" @click="careAction(message, 'snooze')">稍後提醒</button>
            <button class="text-button" type="button" :disabled="pendingAction === message.id" @click="careAction(message, 'ignore')">忽略</button>
          </div>
        </article>
        <section v-if="guide" class="guide-card" data-testid="life-guide-card" aria-labelledby="life-guide-title">
          <header class="guide-card-head"><div><p class="eyebrow">LIFE GUIDE・{{ guide.status === 'published' ? '已發布 Demo' : guide.status }}</p><h3 id="life-guide-title">{{ guide.title ?? '生活指南' }}</h3></div><span class="status">更新 {{ guide.updatedAt ?? 'Demo' }}</span></header>
          <p>{{ guide.message }}</p>
          <p class="source-note">來源：{{ guide.source }}・檢視：{{ guide.reviewedBy ?? 'Demo' }}</p>
          <div v-if="guide.steps?.length" class="guide-steps"><h4>建議步驟</h4><ol><li v-for="step in guide.steps" :key="step.id"><strong>{{ step.title }}</strong><span>{{ step.body }}</span></li></ol></div>
          <div v-if="guide.preparationItems?.length" class="guide-preparation"><div class="section-title-row"><h4>幫我準備：分類清單</h4><strong>{{ guide.pointsEstimate?.label ?? 'Demo 點數估算' }}</strong></div><ul class="preparation-list"><li v-for="item in guide.preparationItems" :key="item.id" data-testid="preparation-item"><div><strong>{{ item.name }}</strong><span>{{ necessityLabel(item.necessity) }}・{{ item.quantityBasis ?? '依情境確認' }}</span><small v-if="item.cooperationLabel">{{ item.cooperationLabel }}</small></div><strong v-if="item.estimatedPoints !== undefined">約 {{ item.estimatedPoints }} 點</strong></li></ul><button class="button primary" type="button" data-testid="prepare-life-guide" @click="prepareLifeGuide">幫我準備（只整理清單）</button><p v-if="prepareNotice" class="feedback-inline" role="status">{{ prepareNotice }}</p></div>
          <ul v-if="guide.warnings?.length" class="guide-warnings"><li v-for="warning in guide.warnings" :key="warning">{{ warning }}</li></ul>
          <p class="truth-banner guide-boundary"><strong>不會自動下單</strong><span>{{ guide.commercialBoundary ?? '只整理清單，不建立交易。' }}</span></p>
        </section>
      </section>

      <section class="panel wellbeing-section" aria-labelledby="packages-title">
        <div class="section-title-row">
          <div>
            <p class="eyebrow">穩定 ID＋版本控制</p>
            <h2 id="packages-title">可編輯任務包</h2>
          </div>
          <RouterLink class="text-link" to="/user/assistant">回到 AI 對話</RouterLink>
        </div>
        <p v-if="!activePackages.length" class="muted">還沒有由情境或 Agent 建立的任務包。</p>
        <article v-for="taskPackage in activePackages" :key="taskPackage.id" class="package-card" data-testid="task-package-card">
          <header class="package-head">
            <div>
              <strong>{{ taskPackage.source.type === 'agent_session' ? 'Agent 生活安排' : '生活安排' }}</strong>
              <p class="muted">狀態：{{ taskPackage.status }}・版本 {{ taskPackage.version }}</p>
            </div>
            <strong>{{ money(taskPackage.totalAmount) }}</strong>
          </header>
          <ul class="package-items">
            <li v-for="item in taskPackage.items" :key="item.id" :class="{ muted: ['paused', 'removed'].includes(item.status) }">
              <div>
                <strong>{{ item.offeringName }}</strong>
                <span class="muted">・{{ item.providerName }}・{{ timeLabel(item.startsAt) }}</span>
                <small class="muted">項目狀態：{{ item.status }}</small>
                <small v-if="item.lastError" class="error-text">{{ item.lastError }}</small>
              </div>
              <div class="package-item-actions">
                <span>{{ money(item.amount) }}</span>
                <button v-if="item.status === 'selected'" class="text-button" type="button" :disabled="pendingAction === item.id" @click="patchItem(taskPackage, item.id, 'pause')">暫緩</button>
                <button v-else-if="item.status === 'paused'" class="text-button" type="button" :disabled="pendingAction === item.id" @click="patchItem(taskPackage, item.id, 'resume')">恢復</button>
                <button v-if="!['removed', 'succeeded', 'submitted'].includes(item.status)" class="text-button danger" type="button" :disabled="pendingAction === item.id" @click="patchItem(taskPackage, item.id, 'remove')">刪除</button>
              </div>
            </li>
          </ul>
          <p class="source-note">只會執行你選中的項目；授權範圍：{{ taskPackage.grantId ?? '尚未產生 bounded grant' }}。</p>
        </article>
      </section>

      <section class="panel wellbeing-section" aria-labelledby="outcomes-title">
        <div class="section-title-row">
          <div>
            <p class="eyebrow">完成後才投影</p>
            <h2 id="outcomes-title">生活成果</h2>
          </div>
          <RouterLink class="text-link" to="/user/points">查看點數帳本</RouterLink>
        </div>
        <div class="outcome-grid">
          <div>
            <h3>完成摘要</h3>
            <p v-if="!projection?.outcomes.length" class="muted">完成預約或訂單後，這裡會出現摘要。</p>
            <ul v-else class="plain-list" data-testid="outcome-list">
              <li v-for="outcome in projection.outcomes" :key="outcome.id">
                <strong>{{ outcome.summary }}</strong>
                <span class="muted">・{{ outcome.status }}・{{ outcome.subjectId }}</span>
              </li>
            </ul>
          </div>
          <div>
            <h3>一次性成就</h3>
            <p v-if="!projection?.achievements.length" class="muted">還沒有解鎖成就。</p>
            <ul v-else class="plain-list" data-testid="achievement-list">
              <li v-for="achievement in projection.achievements" :key="achievement.key">🏁 {{ achievement.title }}</li>
            </ul>
          </div>
          <div>
            <h3>Demo 回饋</h3>
            <p v-if="!projection?.rewards.length" class="muted">完成成果後，符合 Demo 活動上限才會發放。</p>
            <ul v-else class="plain-list" data-testid="reward-list">
              <li v-for="reward in projection.rewards" :key="reward.id">
                <strong>{{ reward.amount > 0 ? '+' : '' }}{{ reward.amount }} 點</strong>
                <span class="muted">・{{ reward.kind === 'reversal' ? '補償沖銷' : '完成回饋' }}</span>
              </li>
            </ul>
          </div>
        </div>
        <p class="source-note">{{ projection?.note }}</p>
      </section>
    </template>
  </main>
</template>

<style scoped>
.wellbeing-page {
  width: min(100%, 72rem);
  gap: var(--space-5, 1.25rem);
}
.page-heading h1 { margin: 0 0 0.35rem; }
.page-lead { margin: 0; color: var(--muted, #666); }
.truth-banner {
  display: flex;
  gap: 0.75rem;
  align-items: baseline;
  padding: 0.85rem 1rem;
  border: 1px solid var(--line, #d6d0c6);
  border-radius: 14px;
  background: var(--surface-2, #f5f2ec);
  line-height: 1.5;
}
.truth-banner strong { white-space: nowrap; }
.wellbeing-section { display: grid; gap: 1rem; }
.care-card, .package-card {
  display: grid;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--line, #d6d0c6);
  border-radius: 16px;
  background: var(--surface, #fff);
}
.care-card p { margin: 0.35rem 0; }
.care-actions { align-items: center; }
.guide-card { display: grid; gap: .85rem; padding: 1rem; border: 2px solid var(--ink); border-radius: 16px; background: var(--yellow, #fde68a); }
.guide-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.guide-card-head h3, .guide-card h4 { margin: 0; }
.guide-card p { margin: 0; }
.guide-steps, .guide-preparation { display: grid; gap: .55rem; padding: .8rem; border: 1px solid var(--line, #d6d0c6); border-radius: 12px; background: var(--surface); }
.guide-steps ol { display: grid; gap: .55rem; margin: 0; padding-left: 1.3rem; }
.guide-steps li { display: grid; gap: .15rem; }
.guide-steps li span, .preparation-list li span, .preparation-list li small { color: var(--muted); font-size: .82rem; }
.preparation-list { display: grid; gap: .45rem; margin: 0; padding: 0; list-style: none; }
.preparation-list li { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding-top: .5rem; border-top: 1px solid var(--line, #e2ddd5); }
.preparation-list li > div { display: grid; gap: .12rem; }
.guide-warnings { display: grid; gap: .25rem; margin: 0; padding-left: 1.25rem; color: var(--danger, #a13d32); font-size: .82rem; }
.guide-boundary { margin: 0; background: var(--surface); }
.package-head, .package-items li {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}
.package-head p { margin: 0.25rem 0 0; }
.package-items { display: grid; gap: 0.5rem; margin: 0; padding: 0; list-style: none; }
.package-items li { padding-top: 0.65rem; border-top: 1px solid var(--line, #e2ddd5); }
.package-items li > div:first-child { min-width: 0; }
.package-items small { display: block; }
.package-item-actions { display: flex; gap: 0.65rem; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.danger, .error-text { color: var(--danger, #a13d32); }
.outcome-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }
.outcome-grid > div { min-width: 0; padding: 0.85rem; border-radius: 14px; background: var(--surface-2, #f5f5f5); }
.outcome-grid h3 { margin: 0 0 0.5rem; }
.plain-list { display: grid; gap: 0.5rem; margin: 0; padding: 0; list-style: none; }
.plain-list li { overflow-wrap: anywhere; }
@media (max-width: 680px) {
  .truth-banner, .package-head, .package-items li, .guide-card-head, .preparation-list li { display: grid; }
  .outcome-grid { grid-template-columns: 1fr; }
  .package-item-actions { justify-content: flex-start; }
}
</style>
