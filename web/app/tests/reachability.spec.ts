// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('reachability view', () => {
  it('keeps mode, threshold, geometry facts, and location list in one state', async () => {
    const fetcher = stubCatalogFetch()
    const { wrapper } = await mountApp('/user/life-circle')
    await flushPromises()

    expect(wrapper.get('[data-testid="reachability-map"]').text()).toContain('步行・10 分鐘')
    expect(wrapper.get('[data-testid="reachable-location-list"]').text()).toContain('王子水電')
    expect(wrapper.get('[data-testid="reachable-service-card"]').text()).toContain('水電修繕')
    expect(wrapper.get('[data-testid="reachable-service-card"] a').attributes('href')).toBe('/user/services/repair')
    expect(wrapper.find('[data-testid="reachability-map-visual"] svg polygon').exists()).toBe(true)
    expect(wrapper.get('[data-testid="reachability-map"]').get('a').attributes('href')).toContain('openstreetmap.org')

    await wrapper.get('[data-testid="reachability-threshold"]').setValue('15')
    await flushPromises()
    expect(wrapper.get('[data-testid="reachable-location-list"]').text()).toContain('DUSKIN')
    expect(wrapper.findAll('[data-testid="reachable-service-card"]')).toHaveLength(2)

    await wrapper.get('[data-testid="reachability-mode"]').setValue('scooter')
    await flushPromises()
    const requests = fetcher.mock.calls.map(([url]) => String(url)).filter((url) => url.includes('/reachability/area'))
    expect(requests.at(-1)).toContain('travelMode=scooter')
    expect(requests.at(-1)).toContain('thresholdMinutes=15')
    expect(wrapper.text()).toContain('非即時路況')
  })

  it('requests a single location only after consent and does not persist coordinates', async () => {
    localStorage.removeItem('aiwave.current-location')
    const previous = Object.getOwnPropertyDescriptor(navigator, 'geolocation')
    let received = false
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition(success: (position: unknown) => void) {
          received = true
          success({ coords: { latitude: 25.033, longitude: 121.565 } })
        },
      },
    })

    try {
      const fetcher = stubCatalogFetch()
      const { wrapper } = await mountApp('/user/life-circle')
      await flushPromises()
      const areaRequestCount = fetcher.mock.calls.filter(([url]) => String(url).includes('/reachability/area')).length

      await wrapper.get('[data-testid="single-use-location"]').trigger('click')
      await flushPromises()

      expect(received).toBe(true)
      expect(wrapper.get('[data-testid="location-privacy-status"]').text()).toContain('單次定位')
      expect(wrapper.get('[data-testid="location-privacy-status"]').text()).toContain('不會保存')
      expect(localStorage.getItem('aiwave.current-location')).toBeNull()
      expect(fetcher.mock.calls.filter(([url]) => String(url).includes('/reachability/area'))).toHaveLength(areaRequestCount)
    } finally {
      if (previous) Object.defineProperty(navigator, 'geolocation', previous)
      else Reflect.deleteProperty(navigator, 'geolocation')
    }
  })
})
