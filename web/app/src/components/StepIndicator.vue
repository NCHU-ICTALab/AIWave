<script setup lang="ts">
// 分步指示器:已完成的步驟可點回去修改,未到的步驟不可跳。
defineProps<{ steps: Array<{ id: string; label: string }>; current: number }>()
const emit = defineEmits<{ select: [index: number] }>()
</script>

<template>
  <nav class="step-indicator" aria-label="預約步驟">
    <ol>
      <li v-for="(step, index) in steps" :key="step.id">
        <button
          type="button"
          class="step-chip"
          :aria-current="index === current ? 'step' : undefined"
          :disabled="index > current"
          :data-state="index < current ? 'done' : index === current ? 'current' : 'todo'"
          @click="index < current && emit('select', index)"
        >
          <span class="step-num" aria-hidden="true">{{ index + 1 }}</span>
          <span class="step-label">{{ step.label }}</span>
        </button>
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.step-indicator ol {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0 0 1rem;
  padding: 0;
  list-style: none;
}

.step-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  min-height: 44px;
  padding: 0 0.85rem;
  border: var(--border-chunky) solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--ink);
  font-weight: 700;
  box-shadow: 4px 4px 0 var(--ink);
  cursor: pointer;
}

.step-chip[data-state='current'] {
  background: var(--cta);
}

.step-chip[data-state='done'] {
  background: var(--surface-2);
}

.step-chip:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  box-shadow: none;
}

.step-num {
  display: grid;
  place-items: center;
  width: 1.5rem;
  height: 1.5rem;
  border: 2px solid var(--ink);
  border-radius: 50%;
  font-size: 0.8rem;
}
</style>
