<script setup lang="ts">
import { computed, ref } from 'vue'

import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useDemoStore } from '@/stores/demo'

const store = useDemoStore()
const pendingAction = ref<'publish' | 'assign' | null>(null)
const statusLabel = computed(() => ({ draft: '草稿', published: '等待報價', quoted: '報價待指派', scheduled: '已安排履約' })[store.campaignStatus])

function confirmAction() {
  if (pendingAction.value === 'publish') store.publishCampaign()
  if (pendingAction.value === 'assign') store.assignVendor()
  pendingAction.value = null
}
</script>

<template>
  <header class="page-heading"><div><p class="eyebrow">Community workspace</p><h1>社區服務中心</h1></div><span class="page-status">18 戶已加入</span></header>
  <div class="grid">
    <section class="panel span-8"><p class="eyebrow">Group service</p><div class="section-title-row"><h2>夏季居家清潔聯合服務</h2><span class="status">{{ statusLabel }}</span></div><p class="muted">AI 已將住戶需求整理成統一題組，冷氣、洗衣機與公共區域清潔可合併詢價。</p><div class="metric-row"><div class="metric"><span>目前登記</span><strong>18 戶</strong></div><div class="metric"><span>預估折扣</span><strong>15%</strong></div></div><div class="button-row"><button v-if="store.campaignStatus === 'draft'" class="button primary" type="button" data-testid="publish-campaign" @click="pendingAction = 'publish'">預覽並送廠商詢價</button><button v-else-if="store.campaignStatus === 'quoted'" class="button primary" type="button" data-testid="assign-vendor" @click="pendingAction = 'assign'">預覽報價並指派</button><span v-else-if="store.campaignStatus === 'published'" class="feedback-inline" role="status">已送出詢價，等待合作廠商回覆報價。</span><span v-else class="feedback-inline" role="status">已指派安心清潔，7/27 開始履約。</span><button class="button" type="button">分享至 LINE 群組</button></div></section>
    <aside class="panel span-4"><h2>AI 群組摘要</h2><ul class="plain-list"><li><strong>8 戶</strong>詢問冷氣清洗</li><li><strong>3 戶</strong>需要週末時段</li><li><strong>1 戶</strong>尚未確認機型</li></ul></aside>
    <section class="panel span-12"><div class="section-title-row"><h2>社區待處理事項</h2><span class="status warn">3 項</span></div><div class="queue-row"><span class="row-index">01</span><div><strong>清潔團購需求確認</strong><div class="row-meta">AI 已將 LINE 的 +1 訊息整理成表格</div></div><span class="status">可送出</span></div><div class="queue-row"><span class="row-index">02</span><div><strong>黑貓包裹集中通知</strong><div class="row-meta">通知 5 位住戶領取</div></div><span class="status warn">待確認</span></div></section>
  </div>
  <ConfirmDialog :open="pendingAction !== null" :title="pendingAction === 'assign' ? '確認指派安心清潔' : '確認發送聯合服務需求'" :description="pendingAction === 'assign' ? '將採用 NT$ 27,540 的 18 戶方案，並通知住戶與廠商。' : '將把 AI 草稿中的服務範圍、18 戶需求與截止時間送給合作廠商詢價。'" @cancel="pendingAction = null" @confirm="confirmAction" />
</template>
