import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useDemoStore } from '@/stores/demo'

import { createFakeCatalogClient } from './fixtures/catalogClient'

async function storeWithCatalog() {
  const store = useDemoStore()
  await store.loadCatalog(createFakeCatalogClient())
  return store
}

describe('demo state machine', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('loads the service catalog from the backend rather than local fixtures', async () => {
    const store = await storeWithCatalog()
    expect(store.catalogStatus).toBe('ready')
    expect(store.services).toHaveLength(9)
  })

  it('falls back safely when the catalog cannot be reached', async () => {
    const store = useDemoStore()
    await store.loadCatalog({
      listServices: () => Promise.reject(new Error('offline')),
      getServiceForm: () => Promise.reject(new Error('offline')),
      quote: () => Promise.reject(new Error('offline')),
      submit: () => Promise.reject(new Error('offline')),
    })
    expect(store.catalogStatus).toBe('unavailable')
    expect(store.services).toEqual([])
  })

  it('calculates discounts through the backend quote API before creating a trackable order', async () => {
    const store = await storeWithCatalog()
    await store.selectService('service-shopping')
    await store.setServiceAnswer('bundle', 'restock')
    await store.setServiceAnswer('coupon', 'apply')
    await store.setServiceAnswer('points', '50')
    await store.setServiceAnswer('delivery', 'store')
    await store.setServiceAnswer('payment', 'card')

    expect(store.pricing).toEqual({
      baseAmount: 699, couponDiscount: 50, pointDiscount: 50, paymentDiscount: 0, finalAmount: 599,
      ruleSummary: ['日用品補貨券 −NT$ 50', 'OPENPOINT 折抵 50 點'],
    })
    const submission = await store.submitSelectedService()
    expect(submission).toMatchObject({ kind: 'order', resource: { id: 'persisted-service-shopping' } })
  })

  it('does not create a submission that bypasses required form validation', async () => {
    const store = await storeWithCatalog()
    await store.selectService('service-aircon')
    expect(await store.submitSelectedService()).toBeNull()
  })

  it('persists non-commerce forms as service requests instead of claiming fulfillment', async () => {
    const store = await storeWithCatalog()

    await store.selectService('service-repair')
    await store.setServiceAnswer('repairType', 'plumbing')
    await store.setServiceAnswer('urgency', 'normal')
    await store.setServiceAnswer('region', { county_name: '臺北市', district_name: '大同區' })
    await store.setServiceAnswer('date', '2026-07-26')
    await store.setServiceAnswer('slot', 'morning')
    await store.setServiceAnswer('contact', { name: '王小明', mobile: '0912345678', address: '臺北市大同區民生西路 1 號' })
    expect(await store.submitSelectedService()).toMatchObject({
      kind: 'service_request', resource: { id: 'persisted-service-repair' },
    })

    await store.selectService('service-restaurant')
    await store.setServiceAnswer('people', 2)
    await store.setServiceAnswer('date', '2026-07-27')
    await store.setServiceAnswer('slot', 'dinner')
    expect(await store.submitSelectedService()).toMatchObject({
      kind: 'service_request', resource: { id: 'persisted-service-restaurant' },
    })

    await store.selectService('service-shipping')
    await store.setServiceAnswer('parcelSize', 'small')
    await store.setServiceAnswer('speed', 'normal')
    await store.setServiceAnswer('store', 'qingchuan')
    expect(await store.submitSelectedService()).toMatchObject({
      kind: 'service_request', resource: { id: 'persisted-service-shipping' },
    })
  })

  it('restores the stable seed state', async () => {
    const store = await storeWithCatalog()
    await store.selectService('service-shopping')
    await store.setServiceAnswer('bundle', 'restock')

    store.resetDemo()

    expect(store.selectedService).toBeNull()
    expect(store.selectedAnswers).toEqual({})
  })
})
