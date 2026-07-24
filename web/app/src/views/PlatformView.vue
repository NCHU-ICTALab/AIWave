<script setup lang="ts">
import { computed } from 'vue'
import { useDemoStore } from '@/stores/demo'

const store = useDemoStore()
const flowLabel = computed(() => ({ draft: '等待社區草稿', published: '需求已送達廠商', quoted: '報價已回流社區', scheduled: '履約事件已排程' })[store.campaignStatus])
</script>

<template>
  <header class="page-heading"><div><p class="eyebrow">Platform operations</p><h1>服務整合平台</h1></div><span class="page-status">9 項服務 · 7 個連接器正常</span></header>
  <div class="grid">
    <section class="panel span-8"><div class="section-title-row"><h2>廠商連接器</h2><button class="button primary" type="button">新增合作服務</button></div><div class="connector-row"><span class="row-index">黑</span><div><strong>黑貓宅急便</strong><div class="row-meta">寄件、物流狀態 · API Adapter</div></div><span class="status">正常</span></div><div class="connector-row"><span class="row-index">商</span><div><strong>iOPEN Mall</strong><div class="row-meta">商城購物、優惠 · API Adapter</div></div><span class="status">正常</span></div><div class="connector-row"><span class="row-index">潔</span><div><strong>在地清潔夥伴</strong><div class="row-meta">清潔服務 · Portal / 人工派單</div></div><span class="status warn">待驗證</span></div></section>
    <aside class="panel span-4"><h2>今日健康度</h2><div class="metric-row"><div class="metric"><span>成功率</span><strong>99.2%</strong></div><div class="metric"><span>平均回應</span><strong>310ms</strong></div><div class="metric"><span>待處理</span><strong>4</strong></div><div class="metric"><span>人工轉接</span><strong>2</strong></div></div></aside>
    <section class="panel span-12"><div class="section-title-row"><h2>統一 API 的價值</h2><span class="status">{{ flowLabel }}</span></div><div class="value-grid"><article><strong>一套規格</strong><p>前台用相同方式搜尋、下單與追蹤所有服務。</p></article><article><strong>彈性轉接</strong><p>有 API、無 API 或人工流程都可包成連接器。</p></article><article><strong>AI 可編排</strong><p>服務能力結構化後，AI 才能安全組合跨廠商任務。</p></article></div></section>
  </div>
</template>
