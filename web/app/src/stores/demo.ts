import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { createServiceCatalogClient, type CatalogService, type ServiceCatalogClient } from '@/api/serviceCatalogClient'
import {
  emptyQuote,
  validateServiceAnswers,
  type ServiceAnswers,
  type ServiceAnswer,
  type ServiceFormDefinition,
  type ServiceQuote,
} from '@/domain/serviceIntake'

export type DemoService = CatalogService

export type CatalogStatus = 'idle' | 'loading' | 'ready' | 'unavailable'

export const useDemoStore = defineStore('demo', () => {
  // 服務目錄與題組定義一律來自後端（單一事實來源，ADR-0002）
  const services = ref<DemoService[]>([])
  const forms = ref<Record<string, ServiceFormDefinition>>({})
  const catalogStatus = ref<CatalogStatus>('idle')
  let client: ServiceCatalogClient | null = null

  const selectedServiceId = ref<string | null>(null)
  const serviceAnswers = ref<Record<string, ServiceAnswers>>({})
  const pricing = ref<ServiceQuote>(emptyQuote)
  const dismissedRecommendationIds = ref<string[]>([])
  const lastDismissedRecommendationId = ref<string | null>(null)
  const recommendationDismissed = computed(() => dismissedRecommendationIds.value.length > 0)

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

  async function setServiceAnswer(fieldId: string, value: ServiceAnswer) {
    if (!selectedServiceId.value) return
    serviceAnswers.value[selectedServiceId.value] = { ...selectedAnswers.value, [fieldId]: value }
    await refreshQuote()
  }

  async function submitSelectedService() {
    if (!selectedService.value) return null
    const form = selectedForm.value
    if (!form || Object.keys(validateServiceAnswers(form, selectedAnswers.value)).length) return null
    return useClient().submit(selectedService.value.id, selectedAnswers.value)
  }

  function dismissRecommendation(id: string) {
    if (!dismissedRecommendationIds.value.includes(id)) {
      dismissedRecommendationIds.value = [...dismissedRecommendationIds.value, id]
    }
    lastDismissedRecommendationId.value = id
  }

  function undoDismissRecommendation(id = lastDismissedRecommendationId.value) {
    if (!id) return
    dismissedRecommendationIds.value = dismissedRecommendationIds.value.filter((item) => item !== id)
    if (lastDismissedRecommendationId.value === id) lastDismissedRecommendationId.value = null
  }

  function resetDemo() {
    selectedServiceId.value = null
    serviceAnswers.value = {}
    pricing.value = emptyQuote
    dismissedRecommendationIds.value = []
    lastDismissedRecommendationId.value = null
  }

  return {
    catalogStatus,
    dismissRecommendation,
    dismissedRecommendationIds,
    forms,
    getServiceForm,
    lastDismissedRecommendationId,
    loadCatalog,
    loadServiceForm,
    pricing,
    recommendationDismissed,
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
    submitSelectedService,
    undoDismissRecommendation,
  }
})
