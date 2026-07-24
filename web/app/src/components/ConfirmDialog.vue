<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{ open: boolean; title: string; description: string; amount?: number; details?: Array<{ label: string; value: string }>; dataUse?: string }>()
const emit = defineEmits<{ cancel: []; confirm: [] }>()
const dialog = ref<HTMLElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
let previousFocus: HTMLElement | null = null

watch(
  () => props.open,
  async (open) => {
    if (open) {
      previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
      await nextTick()
      closeButton.value?.focus()
    } else {
      previousFocus?.focus()
    }
  },
)

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('cancel')
    return
  }
  if (event.key !== 'Tab' || !dialog.value) return
  const focusable = [...dialog.value.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
  const first = focusable[0]
  const last = focusable.at(-1)
  if (!first || !last) return
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-layer" @click.self="$emit('cancel')">
      <section ref="dialog" class="modal-card" role="dialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-description" @keydown="onKeydown">
        <div class="modal-head">
          <div>
            <p class="eyebrow">送出前確認</p>
            <h2 id="confirm-title">{{ title }}</h2>
          </div>
          <button ref="closeButton" class="icon-button" type="button" aria-label="關閉確認視窗" @click="$emit('cancel')">×</button>
        </div>
        <p id="confirm-description" class="muted">{{ description }}</p>
        <dl v-if="details?.length" class="summary-list">
          <div v-for="detail in details" :key="detail.label"><dt>{{ detail.label }}</dt><dd>{{ detail.value }}</dd></div>
        </dl>
        <dl v-if="amount !== undefined" class="summary-list">
          <div><dt>預估金額</dt><dd>NT$ {{ amount.toLocaleString('zh-TW') }}</dd></div>
          <div><dt>付款方式</dt><dd>確認後選擇</dd></div>
        </dl>
        <div v-if="dataUse" class="data-use-note"><strong>資料用途</strong><p>{{ dataUse }}</p></div>
        <div class="modal-actions">
          <button class="button" type="button" @click="$emit('cancel')">返回修改</button>
          <button class="button primary" type="button" data-testid="confirm-action" @click="$emit('confirm')">確認送出</button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
