/**
 * 題組型別與前端驗證。
 *
 * **題組定義本身不在這裡**——它由後端 `/api/v1/services/{id}/form` 提供（單一事實來源，
 * 見 ADR-0002）。本檔只保留：型別、可見性判斷、以及送出前的即時驗證。
 * 後端在收單時會用同一份定義再驗一次，前端這層純粹是為了即時回饋。
 */

export type ServiceAction = 'inquiry' | 'order' | 'reservation' | 'shipment'
export type ServiceAnswer = string | number
export type ServiceAnswers = Record<string, ServiceAnswer>

export interface ServiceOption {
  value: string
  label: string
  /** 官方 pms_topic_option.id，回寫諮詢單時使用。 */
  optionId?: number
}

export interface VisibilityRule {
  fieldId: string
  equals: ServiceAnswer
}

export interface ServiceField {
  id: string
  /** 官方 pms_form_topic.id。 */
  topicId?: number
  label: string
  /** 沿用官方 pms_form_topic.type 代碼。 */
  type: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10
  numberOnly?: boolean
  required?: boolean
  hint?: string
  options?: ServiceOption[]
  min?: number
  max?: number
  minDate?: string
  maxDate?: string
  visibleWhen?: VisibilityRule
}

export interface ServiceFormDefinition {
  serviceId: string
  formId?: number
  action: ServiceAction
  actionLabel: string
  dataUse: string
  fields: ServiceField[]
}

export interface ServiceQuote {
  baseAmount: number
  couponDiscount: number
  pointDiscount: number
  paymentDiscount: number
  finalAmount: number
  ruleSummary: string[]
}

export const emptyQuote: ServiceQuote = {
  baseAmount: 0,
  couponDiscount: 0,
  pointDiscount: 0,
  paymentDiscount: 0,
  finalAmount: 0,
  ruleSummary: [],
}

export function isFieldVisible(field: ServiceField, answers: ServiceAnswers) {
  return !field.visibleWhen || answers[field.visibleWhen.fieldId] === field.visibleWhen.equals
}

export function validateServiceAnswers(form: ServiceFormDefinition, answers: ServiceAnswers) {
  const errors: Record<string, string> = {}
  for (const field of form.fields) {
    if (!isFieldVisible(field, answers)) continue
    const value = answers[field.id]
    if (field.required && (value === undefined || String(value).trim() === '')) {
      errors[field.id] = `請填寫${field.label}`
      continue
    }
    if (field.type === 1 && field.numberOnly && value !== undefined) {
      const number = Number(value)
      if (!Number.isFinite(number)) errors[field.id] = `${field.label}必須是數字`
      else if (field.min !== undefined && number < field.min) errors[field.id] = `${field.label}不可少於 ${field.min}`
      else if (field.max !== undefined && number > field.max) errors[field.id] = `${field.label}不可超過 ${field.max}`
    }
    if (field.type === 3 && value !== undefined && !field.options?.some((option) => option.value === String(value))) {
      errors[field.id] = `${field.label}不是有效選項`
    }
    if (field.type === 9 && value !== undefined) {
      const date = String(value)
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) errors[field.id] = `${field.label}格式不正確`
      else if (field.minDate && date < field.minDate) errors[field.id] = `${field.label}不可早於 ${field.minDate}`
      else if (field.maxDate && date > field.maxDate) errors[field.id] = `${field.label}不可晚於 ${field.maxDate}`
    }
  }
  return errors
}

export function summarizeServiceAnswers(form: ServiceFormDefinition, answers: ServiceAnswers) {
  return form.fields
    .filter((field) => isFieldVisible(field, answers) && answers[field.id] !== undefined && answers[field.id] !== '')
    .map((field) => {
      const value = answers[field.id]
      const optionLabel = field.options?.find((option) => option.value === String(value))?.label
      return { label: field.label, value: optionLabel ?? String(value) }
    })
}
