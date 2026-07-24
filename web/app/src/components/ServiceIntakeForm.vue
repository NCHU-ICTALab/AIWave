<script setup lang="ts">
import { isFieldVisible, type ServiceAnswers, type ServiceField, type ServiceFormDefinition } from '@/domain/serviceIntake'

const props = defineProps<{ form: ServiceFormDefinition; answers: ServiceAnswers; errors: Record<string, string> }>()
const emit = defineEmits<{ answer: [fieldId: string, value: string | number] }>()

function fieldValue(fieldId: string) {
  return props.answers[fieldId] ?? ''
}

function update(field: ServiceField, event: Event) {
  const target = event.target as HTMLInputElement | HTMLSelectElement
  emit('answer', field.id, field.type === 1 && field.numberOnly && target.value !== '' ? Number(target.value) : target.value)
}
</script>

<template>
  <form class="intake-form" novalidate @submit.prevent>
    <div v-for="field in form.fields" v-show="isFieldVisible(field, answers)" :key="field.id" class="field-group">
      <label :for="`field-${field.id}`">{{ field.label }}<span v-if="field.required">（必填）</span></label>
      <select
        v-if="field.type === 3"
        :id="`field-${field.id}`"
        :value="fieldValue(field.id)"
        :data-field-id="field.id"
        :required="field.required"
        :aria-required="field.required"
        :aria-invalid="Boolean(errors[field.id])"
        :aria-describedby="errors[field.id] ? `error-${field.id}` : field.hint ? `hint-${field.id}` : undefined"
        @change="update(field, $event)"
      >
        <option value="">請選擇</option>
        <option v-for="option in field.options" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <textarea
        v-else-if="field.type === 2 || field.type === 7"
        :id="`field-${field.id}`"
        :value="fieldValue(field.id)"
        :data-field-id="field.id"
        :required="field.required"
        :aria-required="field.required"
        :aria-invalid="Boolean(errors[field.id])"
        :aria-describedby="errors[field.id] ? `error-${field.id}` : field.hint ? `hint-${field.id}` : undefined"
        rows="3"
        @input="update(field, $event)"
      />
      <input
        v-else
        :id="`field-${field.id}`"
        :value="fieldValue(field.id)"
        :data-field-id="field.id"
        :type="field.type === 9 ? 'date' : field.numberOnly ? 'number' : 'text'"
        :min="field.type === 9 ? field.minDate : field.min"
        :max="field.type === 9 ? field.maxDate : field.max"
        :required="field.required"
        :aria-required="field.required"
        :aria-invalid="Boolean(errors[field.id])"
        :aria-describedby="errors[field.id] ? `error-${field.id}` : field.hint ? `hint-${field.id}` : undefined"
        @input="update(field, $event)"
      />
      <p v-if="errors[field.id]" :id="`error-${field.id}`" class="field-error" role="alert">{{ errors[field.id] }}</p>
      <p v-else-if="field.hint" :id="`hint-${field.id}`" class="field-hint">{{ field.hint }}</p>
    </div>
  </form>
</template>
