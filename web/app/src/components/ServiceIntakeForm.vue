<script setup lang="ts">
import { isFieldVisible, type ContactAnswer, type RegionAnswer, type ServiceAnswer, type ServiceAnswers, type ServiceField, type ServiceFormDefinition } from '@/domain/serviceIntake'

const props = defineProps<{ form: ServiceFormDefinition; answers: ServiceAnswers; errors: Record<string, string> }>()
const emit = defineEmits<{ answer: [fieldId: string, value: ServiceAnswer] }>()

function fieldValue(fieldId: string) {
  return props.answers[fieldId] ?? ''
}

function scalarFieldValue(fieldId: string): string | number {
  const value = fieldValue(fieldId)
  return typeof value === 'object' ? '' : value
}

function update(field: ServiceField, event: Event) {
  const target = event.target as HTMLInputElement | HTMLSelectElement
  emit('answer', field.id, field.type === 1 && field.numberOnly && target.value !== '' ? Number(target.value) : target.value)
}

function updateRegion(field: ServiceField, key: keyof RegionAnswer, event: Event) {
  const current = typeof props.answers[field.id] === 'object' ? props.answers[field.id] as RegionAnswer : { county_name: '', district_name: '' }
  emit('answer', field.id, { ...current, [key]: (event.target as HTMLInputElement).value })
}

function updateContact(field: ServiceField, key: keyof ContactAnswer, event: Event) {
  const current = typeof props.answers[field.id] === 'object' ? props.answers[field.id] as ContactAnswer : { name: '', mobile: '', address: '' }
  emit('answer', field.id, { ...current, [key]: (event.target as HTMLInputElement).value })
}
</script>

<template>
  <form class="intake-form" novalidate @submit.prevent>
    <div v-for="field in form.fields" v-show="isFieldVisible(field, answers)" :key="field.id" class="field-group">
      <label :for="`field-${field.id}`">{{ field.label }}<span v-if="field.required">（必填）</span></label>
      <select
        v-if="field.type === 3"
        :id="`field-${field.id}`"
        :value="scalarFieldValue(field.id)"
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
      <fieldset v-else-if="field.type === 5" class="compound-field" :aria-describedby="errors[field.id] ? `error-${field.id}` : undefined">
        <legend class="visually-hidden">{{ field.label }}</legend>
        <label :for="`field-${field.id}-county`">縣市</label>
        <input :id="`field-${field.id}-county`" :value="(fieldValue(field.id) as RegionAnswer)?.county_name" :aria-invalid="Boolean(errors[field.id])" autocomplete="address-level1" placeholder="例如：臺北市" @input="updateRegion(field, 'county_name', $event)" />
        <label :for="`field-${field.id}-district`">行政區</label>
        <input :id="`field-${field.id}-district`" :value="(fieldValue(field.id) as RegionAnswer)?.district_name" autocomplete="address-level2" placeholder="例如：大同區" @input="updateRegion(field, 'district_name', $event)" />
      </fieldset>
      <fieldset v-else-if="field.type === 8 || field.type === 10" class="compound-field" :aria-describedby="errors[field.id] ? `error-${field.id}` : undefined">
        <legend class="visually-hidden">{{ field.label }}</legend>
        <label :for="`field-${field.id}-name`">姓名</label>
        <input :id="`field-${field.id}-name`" :value="(fieldValue(field.id) as ContactAnswer)?.name" :aria-invalid="Boolean(errors[field.id])" autocomplete="name" @input="updateContact(field, 'name', $event)" />
        <label :for="`field-${field.id}-mobile`">聯絡電話</label>
        <input :id="`field-${field.id}-mobile`" :value="(fieldValue(field.id) as ContactAnswer)?.mobile" type="tel" inputmode="tel" autocomplete="tel" @input="updateContact(field, 'mobile', $event)" />
        <template v-if="field.type === 8">
          <label :for="`field-${field.id}-address`">完整地址</label>
          <input :id="`field-${field.id}-address`" :value="(fieldValue(field.id) as ContactAnswer)?.address" autocomplete="street-address" @input="updateContact(field, 'address', $event)" />
        </template>
      </fieldset>
      <textarea
        v-else-if="field.type === 2 || field.type === 7"
        :id="`field-${field.id}`"
        :value="scalarFieldValue(field.id)"
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
        :value="scalarFieldValue(field.id)"
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
