<script setup lang="ts">
import { ref } from 'vue'

import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useDemoStore } from '@/stores/demo'

const store = useDemoStore()
const quoteOpen = ref(false)
function confirmQuote() {
  store.submitQuote()
  quoteOpen.value = false
}
</script>

<template>
  <header class="page-heading"><div><p class="eyebrow">Partner workspace</p><h1>合作廠商工作台</h1></div><span class="page-status">今日 6 筆新需求</span></header>
  <div class="grid">
    <section class="panel span-7"><h2>待辦需求</h2><div class="queue-row"><span class="row-index">01</span><div><strong>夏季居家清潔聯合服務</strong><div class="row-meta">18 戶 · 3 種服務 · 希望週末安排</div></div><button v-if="store.campaignStatus === 'published'" class="button primary" type="button" data-testid="submit-quote" @click="quoteOpen = true">預覽並送出報價</button><span v-else-if="store.campaignStatus === 'quoted'" class="status">報價已送出</span><span v-else-if="store.campaignStatus === 'scheduled'" class="status">已獲指派</span><span v-else class="status warn">等待社區送出</span></div><div class="queue-row"><span class="row-index">02</span><div><strong>公共區域清潔</strong><div class="row-meta">現場評估 · 社區管理者提交</div></div><button class="button" type="button">查看需求</button></div></section>
    <aside class="panel span-5"><p class="eyebrow">AI campaign</p><h2>用一句話產生活動</h2><p class="muted">AI 可依服務欄位生成表單、推播文案與完整流程，再由廠商確認發布。</p><label class="field">活動目標<textarea rows="3">夏季冷氣清洗，社區滿十戶享團購價</textarea></label><button class="button primary full" type="button">產生活動草稿</button></aside>
    <section class="panel span-12"><h2>串接摘要</h2><p>廠商只需對接平台統一規格；驗證、訂單狀態、錯誤處理與前台呈現由平台承接。</p><div class="api-strip"><code>POST /api/v1/orders</code><span>→</span><code>Partner Adapter</code><span>→</span><code>廠商既有流程／人工派單</code></div></section>
  </div>
  <ConfirmDialog :open="quoteOpen" title="確認送出 18 戶清潔報價" description="方案單價 NT$ 1,530，總價 NT$ 27,540，有效期限至 7/26。送出後社區管理者可比較並指派。" :amount="27540" @cancel="quoteOpen = false" @confirm="confirmQuote" />
</template>
