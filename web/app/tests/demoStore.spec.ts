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
    expect(store.createOrder()?.amount).toBe(599)
  })

  it('does not create a submission that bypasses required form validation', async () => {
    const store = await storeWithCatalog()
    await store.selectService('service-aircon')
    expect(store.createOrder()).toBeNull()
    expect(store.orders.map(({ id }) => id)).toEqual(['TCAT-8842'])
  })

  it('uses distinct landing seams for inquiries, reservations, shipments, and orders', async () => {
    const store = await storeWithCatalog()

    await store.selectService('service-repair')
    await store.setServiceAnswer('repairType', 'plumbing')
    await store.setServiceAnswer('urgency', 'normal')
    expect(store.createInquiry()?.id).toBe('INQ-0725-001')
    expect(store.createOrder()).toBeNull()

    await store.selectService('service-restaurant')
    await store.setServiceAnswer('people', 2)
    await store.setServiceAnswer('date', '2026-07-27')
    await store.setServiceAnswer('slot', 'dinner')
    expect(store.createReservation()?.id).toBe('RSV-0725-001')

    await store.selectService('service-shipping')
    await store.setServiceAnswer('parcelSize', 'small')
    await store.setServiceAnswer('speed', 'normal')
    await store.setServiceAnswer('store', 'qingchuan')
    expect(store.createShipment()?.id).toBe('SHP-0725-001')
  })

  it('carries one community request through vendor quote and assignment', () => {
    const store = useDemoStore()
    expect(store.campaignStatus).toBe('draft')

    store.publishCampaign()
    expect(store.campaignStatus).toBe('published')
    store.submitQuote()
    expect(store.campaignStatus).toBe('quoted')
    store.assignVendor()
    expect(store.campaignStatus).toBe('scheduled')
  })

  it('restores the stable seed state', async () => {
    const store = await storeWithCatalog()
    store.publishCampaign()
    await store.selectService('service-shopping')
    store.createOrder()

    store.resetDemo()

    expect(store.campaignStatus).toBe('draft')
    expect(store.selectedService).toBeNull()
    expect(store.orders.map(({ id }) => id)).toEqual(['TCAT-8842'])
  })
})
