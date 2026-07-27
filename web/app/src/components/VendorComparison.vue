<script setup lang="ts">
/**
 * 服務媒合比較（FR-S-04）。
 *
 * 命題要求「列 2-3 家比較**可改選**」，所以這裡不是一個推薦結論，而是一張比較表：
 * 第一名標為建議，但每一家都看得到理由與代價，使用者隨時能挑別家。
 *
 * 兩個誠實性設計：
 * - `reasons` 逐條顯示加分依據，推薦不是黑箱分數（同 ADR-0011）。
 * - `concerns` 明白寫出不符合的條件，不藏起來讓使用者事後才發現。
 */
import type { MatchResult, VendorMatch } from '@/api/assistantClient'

defineProps<{ result: MatchResult }>()
const emit = defineEmits<{ choose: [vendorId: string] }>()

const currency = (value: number) => `NT$ ${value.toLocaleString('zh-TW')}`

/**
 * 評價已經以數字＋則數獨立呈現，理由清單再列一次「評價 4.4（903 則）」是重複資訊，
 * 會把真正的差異（可加急、在預算內）淹沒。解釋性不受影響——評分本身就在畫面上。
 */
const reasonsOf = (vendor: VendorMatch) => vendor.reasons.filter((reason) => reason.code !== 'rating')
</script>

<template>
  <div class="vendor-compare" data-testid="vendor-comparison">
    <p class="vendor-criteria muted">
      依
      <template v-if="result.region">{{ result.region.county_name }}{{ result.region.district_name }}・</template>
      <template v-if="result.criteria.budget">預算 {{ currency(result.criteria.budget) }} 內・</template>
      <template v-if="result.criteria.urgent">需加急・</template>
      評價媒合
    </p>

    <ul class="vendor-list">
      <li
        v-for="(vendor, index) in result.vendors"
        :key="vendor.vendorId"
        class="vendor-card"
        :class="{ recommended: index === 0 }"
        data-testid="vendor-card"
      >
        <div class="vendor-head">
          <div class="vendor-name">
            <h4>{{ vendor.vendorName }}</h4>
            <span v-if="index === 0" class="badge primary" data-testid="vendor-recommended">建議</span>
          </div>
          <p class="vendor-price">
            <strong>{{ vendor.basePrice > 0 ? currency(vendor.basePrice) : '免服務費' }}</strong>
            <span class="muted">參考價</span>
          </p>
        </div>

        <p class="vendor-intro muted">{{ vendor.intro }}</p>

        <p class="vendor-rating">
          <!-- 評分不只用星號顏色表達，數字與則數都要讀得到（不倚賴顏色傳達資訊） -->
          <span aria-hidden="true">★</span>
          <strong>{{ vendor.rating.toFixed(1) }}</strong>
          <span class="muted">（{{ vendor.reviewCount.toLocaleString('zh-TW') }} 則評價）</span>
        </p>

        <ul class="vendor-reasons">
          <li v-for="reason in reasonsOf(vendor)" :key="reason.code" data-testid="vendor-reason">
            <span aria-hidden="true">✓</span>{{ reason.label }}
          </li>
          <li v-for="concern in vendor.concerns" :key="concern" class="concern" data-testid="vendor-concern">
            <span aria-hidden="true">！</span>{{ concern }}
          </li>
        </ul>

        <p class="vendor-slots muted">可服務時段：{{ vendor.slotLabels.join('、') }}</p>

        <button
          class="button"
          :class="{ primary: index === 0 }"
          type="button"
          data-testid="vendor-choose"
          @click="emit('choose', vendor.vendorId)"
        >
          選這家
        </button>
      </li>
    </ul>

    <p class="muted source-note">
      報價、評價與時段為競賽建置資料，非各品牌實際營業數據；排序由規則算出，非語言模型生成。
    </p>
  </div>
</template>
