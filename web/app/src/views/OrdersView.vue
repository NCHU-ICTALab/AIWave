<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { createAiInquiryClient } from '@/api/aiInquiryClient'
import { useDemoStore } from '@/stores/demo'

const store = useDemoStore()
const syncStatus = ref<'loading' | 'synced' | 'unavailable'>('loading')

onMounted(async () => {
  try {
    const inquiries = await createAiInquiryClient().listInquiries()
    for (const inquiry of inquiries) store.recordAiInquiry(inquiry.id)
    syncStatus.value = 'synced'
  } catch {
    syncStatus.value = 'unavailable'
  }
})
</script>

<template>
  <header class="page-heading"><div><p class="eyebrow">Order center</p><h1>訂單與任務</h1></div><span class="page-status">{{ syncStatus === 'synced' ? '已同步後端諮詢紀錄' : syncStatus === 'loading' ? '同步中…' : '離線種子模式' }}</span></header>
  <div class="grid">
    <section class="panel span-8" aria-labelledby="active-orders">
      <h2 id="active-orders">進行中的訂單</h2>
      <div v-if="store.orders.length">
        <article v-for="(order, index) in store.orders" :key="order.id" class="order-row">
          <span class="row-index">{{ String(index + 1).padStart(2, '0') }}</span>
          <div><strong>{{ order.service.name }}</strong><div class="row-meta">{{ order.id }} · {{ order.service.partner }} · NT$ {{ order.amount.toLocaleString('zh-TW') }}</div></div>
          <span class="status">{{ order.status }}</span>
        </article>
      </div>
      <div v-else class="empty-state compact"><h3>還沒有任何委託</h3><p>在首頁描述你的需求，或直接挑一項服務——送出後進度都會顯示在這裡。</p><RouterLink class="button primary inline" to="/user">回首頁描述需求</RouterLink></div>
    </section>
    <section class="panel span-4" aria-labelledby="order-timeline"><h2 id="order-timeline">接下來</h2><ol class="timeline"><li><div><strong>需求已建立</strong><p>平台保留完整請求紀錄</p></div></li><li><div><strong>等待夥伴回覆</strong><p>不論廠商 API 格式，前台維持一致</p></div></li><li><div><strong>確認排程</strong><p>異常時可轉人工處理</p></div></li></ol></section>
  </div>
</template>
