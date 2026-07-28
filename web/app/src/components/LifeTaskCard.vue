<script setup lang="ts">
import type { LifeTask } from '@/api/lifeTaskClient'

defineProps<{ task: LifeTask; busy?: boolean }>()
const emit = defineEmits<{ choose: [itemId: string, vendorId: string] }>()

const money = (value: number | null | undefined) => `NT$ ${Number(value ?? 0).toLocaleString('zh-TW')}`
</script>

<template>
  <article class="life-task-card" data-testid="life-task-card" :data-status="task.status">
    <header class="life-task-head">
      <div>
        <p class="eyebrow">跨服務生活任務</p>
        <h2>爸媽來訪前的住家整理</h2>
        <p class="row-meta">{{ task.id }}・{{ task.statusLabel }}</p>
      </div>
      <span class="status" :data-status="task.status">{{ task.statusLabel }}</span>
    </header>

    <p v-if="task.lastError" class="result-notice" role="alert">
      上次送出沒有完整完成：{{ task.lastError }}。可安全重試，不會重複建單。
    </p>

    <dl class="task-facts">
      <div><dt>日期</dt><dd>{{ task.scheduledDate ?? '待確認' }}</dd></div>
      <div><dt>地址</dt><dd>{{ task.address?.label ?? '待選擇' }}</dd></div>
      <div><dt>範圍</dt><dd>{{ ({ personal: '我的住家', family: '家庭群組', community: '社區共同需求' } as Record<string, string>)[task.scope ?? ''] ?? '待選擇' }}</dd></div>
    </dl>

    <ol class="task-items">
      <li v-for="item in task.items" :key="item.id" class="task-item">
        <div class="task-item-head">
          <div><strong>{{ item.title }}</strong><p>{{ item.needSummary }}</p></div>
          <span v-if="item.externalInquiryId" class="status">{{ item.status }}</span>
        </div>

        <div v-if="item.candidates.length" class="task-vendors" :aria-label="`${item.title}廠商選擇`">
          <button
            v-for="vendor in item.candidates"
            :key="vendor.vendorId"
            type="button"
            class="task-vendor-option"
            :class="{ selected: vendor.vendorId === item.vendorId }"
            :aria-pressed="vendor.vendorId === item.vendorId"
            :disabled="busy || !['ready', 'needs_details'].includes(task.status)"
            @click="emit('choose', item.id, vendor.vendorId)"
          >
            <span><strong>{{ vendor.vendorName }}</strong><small>★ {{ vendor.rating.toFixed(1) }}・{{ vendor.reasons.find((reason) => reason.code !== 'rating')?.label }}</small></span>
            <span><strong>{{ money(vendor.basePrice) }}</strong><small>展示參考價</small></span>
          </button>
        </div>
        <p v-else-if="item.vendorName" class="task-selected-vendor">
          {{ item.vendorName }}・{{ money(item.basePrice) }}（展示參考價）
        </p>

        <div v-if="item.quotes?.length" class="task-quotes">
          <p class="eyebrow">廠商正式回覆</p>
          <div v-for="quote in item.quotes" :key="quote.id" class="task-quote-row">
            <span>{{ quote.id }}・有效至 {{ quote.validUntil }}</span><strong>{{ money(quote.total) }}</strong>
          </div>
        </div>
        <p v-else-if="item.externalInquiryId" class="muted">案件 {{ item.externalInquiryId }} 已送達，等待廠商回覆報價。</p>
        <p v-if="item.externalOrderId" class="muted">履約訂單 {{ item.externalOrderId }}</p>
        <p v-if="item.syncError" class="result-notice">同步較慢：{{ item.syncError }}</p>
      </li>
    </ol>

    <section v-if="task.estimate" class="task-estimate" aria-labelledby="life-task-estimate-title">
      <div>
        <p id="life-task-estimate-title" class="eyebrow">OPENPOINT 節省試算</p>
        <strong>{{ money(task.estimate.finalAmount) }}</strong>
        <del>{{ money(task.estimate.baseAmount) }}</del>
      </div>
      <p>使用 {{ task.estimate.pointsApplied }} 點，預估省 {{ money(task.estimate.savedAmount) }}</p>
      <small>{{ task.points?.rule }}；點數為競賽展示帳本，非 OPENPOINT 即時餘額。</small>
    </section>

    <details class="reason-details">
      <summary>查看資料使用與執行依據</summary>
      <ul><li v-for="item in task.dataUse" :key="item">{{ item }}</li></ul>
      <p class="muted">廠商排名與點數由規則計算；語言模型只負責理解目標，不決定金額。</p>
    </details>

    <p v-if="task.status === 'ready'" class="source-note muted">
      底部確認鍵會一次建立 {{ task.items.length }} 件廠商諮詢；正式報價回來後仍由你決定是否接受。
    </p>
  </article>
</template>
