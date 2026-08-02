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
    expect(wrapper.find('[data-testid="reachability-map"] a[href*="openstreetmap"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="reachability-map-visual"]').text()).toContain('10 分鐘通勤圈')

    await wrapper.get('[data-testid="reachability-threshold"]').setValue('15')
    await flushPromises()
    expect(wrapper.get('[data-testid="reachable-location-list"]').text()).toContain('DUSKIN')
    expect(wrapper.findAll('[data-testid="reachable-service-card"]')).toHaveLength(6)

    await wrapper.get('[data-testid="reachability-mode"]').setValue('scooter')
    await flushPromises()
    const requests = fetcher.mock.calls.map(([url]) => String(url)).filter((url) => url.includes('/reachability/area'))
    expect(requests.at(-1)).toContain('travelMode=scooter')
    expect(requests.at(-1)).toContain('thresholdMinutes=15')
    expect(wrapper.text()).toContain('非即時路況')
  })

  // 迴歸:曾經因為「後端種子本來就是 isDemo: true」被當成離線條件,
  // 造成永遠丟掉 API 結果、改用本地虛擬地圖並謊稱「後端未啟動」。
  it('renders the API locations themselves and never claims the backend is offline', async () => {
    stubCatalogFetch()
    const { wrapper, router } = await mountApp('/user/life-circle')
    await flushPromises()

    expect(wrapper.find('[data-testid="reachability-offline-demo"]').exists()).toBe(false)
    const listText = wrapper.get('[data-testid="reachable-location-list"]').text()
    // API 回的四個信義區據點都要真的出現(含使用者要求「附近一定有小七」)
    for (const name of ['王子水電', '7-ELEVEN 線上購物中心', '7-ELEVEN 交貨便', '康是美']) {
      expect(listText).toContain(name)
    }
    expect(wrapper.findAll('[data-testid="reachable-location-list"] li')).toHaveLength(4)
    expect(wrapper.findAll('[data-testid="reachable-service-card"]')).toHaveLength(4)
    // 每個服務卡的連結都必須命中真的路由,不能落到 catch-all(等於 404)
    for (const link of wrapper.findAll('[data-testid="reachable-service-card"] a')) {
      const resolved = router.resolve(String(link.attributes('href')))
      expect(resolved.matched.length).toBeGreaterThan(0)
      expect(resolved.matched.some((record) => record.path.includes('pathMatch'))).toBe(false)
    }
    // 標記不能全部塌在起點:每個據點都要有自己的座標
    const markers = wrapper.findAll('[data-testid="reachability-map-visual"] .reachability-location-marker circle')
    expect(markers).toHaveLength(4)
    const positions = new Set(markers.map((marker) => `${marker.attributes('cx')},${marker.attributes('cy')}`))
    expect(positions.size).toBe(4)
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
