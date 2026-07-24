import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { createServiceCatalogClient, type CatalogService, type ServiceCatalogClient } from '@/api/serviceCatalogClient'
import {
  emptyQuote,
  summarizeServiceAnswers,
  validateServiceAnswers,
  type ServiceAnswers,
  type ServiceFormDefinition,
  type ServiceQuote,
} from '@/domain/serviceIntake'

export type DemoService = CatalogService

export interface DemoOrder {
  id: string
  service: DemoService
  amount: number
  status: '已成立' | '待確認' | '已排程'
  action?: 'inquiry' | 'order' | 'reservation' | 'shipment'
  answerSummary?: Array<{ label: string; value: string }>
}

export type CampaignStatus = 'draft' | 'published' | 'quoted' | 'scheduled'
export type CatalogStatus = 'idle' | 'loading' | 'ready' | 'unavailable'

const SEED_SHIPPING: DemoService = {
  id: 'service-shipping', name: '寄件服務', category: '生活支援',
  summary: '黑貓宅急便到店寄件', partner: '黑貓宅急便', glyph: '寄',
}

/** 服務目錄尚未載入（或離線）時，AI 諮詢單仍要顯示得出來。 */
const FALLBACK_REPAIR: DemoService = {
  id: 'service-repair', name: '水電修繕', category: '生活支援',
  summary: '初步判斷並安排到府', partner: '安心修繕', glyph: '修',
}

function seedOrders(): DemoOrder[] {
  return [{ id: 'TCAT-8842', service: SEED_SHIPPING, amount: 130, status: '已排程' }]
}

export const useDemoStore = defineStore('demo', () => {
  // 服務目錄與題組定義一律來自後端（單一事實來源，ADR-0002）
  const services = ref<DemoService[]>([])
  const forms = ref<Record<string, ServiceFormDefinition>>({})
  const catalogStatus = ref<CatalogStatus>('idle')
  let client: ServiceCatalogClient | null = null

  const selectedServiceId = ref<string | null>(null)
  const serviceAnswers = ref<Record<string, ServiceAnswers>>({})
  const pricing = ref<ServiceQuote>(emptyQuote)
  const orders = ref<DemoOrder[]>(seedOrders())
  const recommendationDismissed = ref(false)
  const campaignStatus = ref<CampaignStatus>('draft')

  const selectedService = computed(() => services.value.find(({ id }) => id === selectedServiceId.value) ?? null)
  const selectedForm = computed(() => (selectedServiceId.value ? forms.value[selectedServiceId.value] : undefined))
  const selectedAnswers = computed(() =>
    selectedServiceId.value ? serviceAnswers.value[selectedServiceId.value] ?? {} : {},
  )

  function useClient(override?: ServiceCatalogClient) {
    if (override) client = override
    if (!client) client = createServiceCatalogClient()
    return client
  }

  /** 載入服務目錄；`override` 供測試注入契約。 */
  async function loadCatalog(override?: ServiceCatalogClient) {
    const api = useClient(override)
    catalogStatus.value = 'loading'
    try {
      services.value = await api.listServices()
      catalogStatus.value = 'ready'
    } catch {
      catalogStatus.value = 'unavailable'
    }
  }

  async function loadServiceForm(serviceId: string) {
    if (forms.value[serviceId]) return forms.value[serviceId]
    try {
      const definition = await useClient().getServiceForm(serviceId)
      forms.value = { ...forms.value, [serviceId]: definition }
      return definition
    } catch {
      return undefined
    }
  }

  function getServiceForm(serviceId: string) {
    return forms.value[serviceId]
  }

  async function selectService(id: string) {
    selectedServiceId.value = id
    await loadServiceForm(id)
    await refreshQuote()
  }

  /** 金額一律由後端統一 API 計算，確保 Web／AI／LINE 三邊一致。 */
  async function refreshQuote() {
    const serviceId = selectedServiceId.value
    if (!serviceId) {
      pricing.value = emptyQuote
      return
    }
    try {
      pricing.value = await useClient().quote(serviceId, selectedAnswers.value)
    } catch {
      pricing.value = emptyQuote
    }
  }

  async function setServiceAnswer(fieldId: string, value: string | number) {
    if (!selectedServiceId.value) return
    serviceAnswers.value[selectedServiceId.value] = { ...selectedAnswers.value, [fieldId]: value }
    await refreshQuote()
  }

  function createTypedSubmission(expectedAction: NonNullable<DemoOrder['action']>, prefix: string) {
    if (!selectedService.value) return null
    const form = selectedForm.value
    if (!form || form.action !== expectedAction || Object.keys(validateServiceAnswers(form, selectedAnswers.value)).length) return null
    const idStem = `${prefix}-0725-`
    const sequence = orders.value.filter(({ id }) => id.startsWith(idStem)).length + 1
    const order: DemoOrder = {
      id: `${idStem}${String(sequence).padStart(3, '0')}`,
      service: selectedService.value,
      amount: pricing.value.finalAmount,
      status: form.action === 'inquiry' ? '待確認' : '已成立',
      action: form.action,
      answerSummary: summarizeServiceAnswers(form, selectedAnswers.value),
    }
    orders.value.unshift(order)
    return order
  }

  const createOrder = () => createTypedSubmission('order', 'OP')
  const createInquiry = () => createTypedSubmission('inquiry', 'INQ')
  const createReservation = () => createTypedSubmission('reservation', 'RSV')
  const createShipment = () => createTypedSubmission('shipment', 'SHP')

  function submitSelectedService() {
    const action = selectedForm.value?.action
    if (action === 'inquiry') return createInquiry()
    if (action === 'reservation') return createReservation()
    if (action === 'shipment') return createShipment()
    if (action === 'order') return createOrder()
    return null
  }

  function dismissRecommendation() {
    recommendationDismissed.value = true
  }

  function undoDismissRecommendation() {
    recommendationDismissed.value = false
  }

  function publishCampaign() {
    if (campaignStatus.value === 'draft') campaignStatus.value = 'published'
  }

  function submitQuote() {
    if (campaignStatus.value === 'published') campaignStatus.value = 'quoted'
  }

  function assignVendor() {
    if (campaignStatus.value === 'quoted') campaignStatus.value = 'scheduled'
  }

  function resetDemo() {
    selectedServiceId.value = null
    serviceAnswers.value = {}
    pricing.value = emptyQuote
    orders.value = seedOrders()
    recommendationDismissed.value = false
    campaignStatus.value = 'draft'
  }

  function recordAiInquiry(inquiryId: string) {
    if (orders.value.some(({ id }) => id === inquiryId)) return
    const repairService = services.value.find(({ id }) => id === 'service-repair') ?? FALLBACK_REPAIR
    orders.value.unshift({
      id: inquiryId,
      service: repairService,
      amount: 0,
      status: '待確認',
      action: 'inquiry',
      answerSummary: [{ label: '建立來源', value: 'AI 生活管家＋後端題組引擎' }],
    })
  }

  return {
    assignVendor,
    campaignStatus,
    catalogStatus,
    createInquiry,
    createOrder,
    createReservation,
    createShipment,
    dismissRecommendation,
    forms,
    getServiceForm,
    loadCatalog,
    loadServiceForm,
    orders,
    pricing,
    publishCampaign,
    recommendationDismissed,
    recordAiInquiry,
    refreshQuote,
    resetDemo,
    selectService,
    selectedAnswers,
    selectedForm,
    selectedService,
    selectedServiceId,
    serviceAnswers,
    services,
    setServiceAnswer,
    submitQuote,
    submitSelectedService,
    undoDismissRecommendation,
  }
})
