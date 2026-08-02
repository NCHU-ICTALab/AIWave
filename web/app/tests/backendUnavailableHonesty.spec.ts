// @vitest-environment happy-dom

/**
 * 「後端沒啟動」是一句很貴的話——使用者看到就會去重開一個其實正在跑的 API,
 * 真正的原因(空清單、憑證過期、伺服器錯誤)反而被蓋掉。
 *
 * 這支測試把三種情況釘死:成功但空、後端回錯誤、真的連不上,
 * 只有最後一種可以說「請確認後端是否啟動」。
 */
import { describe, expect, it } from 'vitest'

import { ApiError, backendAnswered } from '@/api/http'
import { InquiryApiError } from '@/api/inquiryLifecycleClient'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

describe('backendAnswered', () => {
  it('treats a real HTTP status as "the backend answered"', () => {
    expect(backendAnswered(new ApiError('平台回應 500', 500))).toBe(true)
    expect(backendAnswered(new InquiryApiError(401, '請提供 Bearer 存取憑證'))).toBe(true)
  })

  it('treats a connection failure as "the backend did not answer"', () => {
    // http 層把 fetch 本身的例外正規化成 status 0
    expect(backendAnswered(new ApiError('無法連線到平台服務', 0))).toBe(false)
    expect(backendAnswered(new TypeError('Failed to fetch'))).toBe(false)
    expect(backendAnswered(null)).toBe(false)
  })
})

describe('orders view backend messaging', () => {
  it('does not blame a stopped backend when it answered 401', async () => {
    stubCatalogFetch((url) => {
      if (url.endsWith('/api/v1/inquiries')) {
        return new Response(JSON.stringify({ detail: '請提供 Bearer 存取憑證' }), { status: 401 })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/orders')

    const notice = wrapper.get('[data-testid="orders-unavailable"]')
    expect(notice.text()).toContain('後端有回應')
    expect(notice.text()).not.toContain('是否啟動')
    expect(notice.attributes('role')).toBe('status')
  })

  it('says the backend is unreachable when the request never got through', async () => {
    stubCatalogFetch((url) => {
      if (url.endsWith('/api/v1/inquiries')) throw new TypeError('Failed to fetch')
      return undefined
    })
    const { wrapper } = await mountApp('/user/orders')

    const notice = wrapper.get('[data-testid="orders-unavailable"]')
    expect(notice.text()).toContain('連不上後端服務')
    expect(notice.attributes('role')).toBe('status')
  })

  it('shows the empty state, not a backend warning, when the list is legitimately empty', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/orders')

    expect(wrapper.find('[data-testid="orders-unavailable"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('還沒有任何委託')
  })
})

describe('community board backend messaging', () => {
  // 王小明的公告是 403（他不是社區成員），舊文案把它講成「請確認後端服務是否啟動」，
  // 使用者於是去重開一個本來就在跑的 API。這條測試把那個誤導釘死。
  it('does not blame a stopped backend when announcements answered 403', async () => {
    stubCatalogFetch((url) => {
      if (url.includes('/announcements')) {
        return new Response(JSON.stringify({ detail: '只有社區成員可以查看公告' }), { status: 403 })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/community')
    const notice = wrapper.get('[data-backend-answered="true"]')

    expect(notice.text()).toContain('後端有回應')
    expect(notice.text()).not.toContain('是否啟動')
    expect(notice.attributes('role')).toBe('status')
  })

  it('says the backend is unreachable only when the request never got through', async () => {
    stubCatalogFetch((url) => {
      if (url.includes('/communities')) throw new TypeError('Failed to fetch')
      return undefined
    })
    const { wrapper } = await mountApp('/user/community')

    expect(wrapper.get('[data-backend-answered="false"]').text()).toContain('連不上後端服務')
  })
})

describe('home overview backend messaging', () => {
  it('separates a malformed 200 payload from a stopped backend', async () => {
    stubCatalogFetch((url) => {
      if (url.includes('/insights/') && url.endsWith('/summary')) {
        return new Response(JSON.stringify({ data: { unexpected: true } }), { status: 200 })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user')
    const notice = wrapper.get('[data-reason]')

    expect(notice.attributes('data-reason')).toBe('malformed')
    expect(notice.text()).toContain('後端有回應')
    expect(notice.text()).not.toContain('是否啟動')
  })

  it('still reports an unreachable backend honestly', async () => {
    stubCatalogFetch((url) => {
      if (url.includes('/insights/')) throw new TypeError('Failed to fetch')
      return undefined
    })
    const { wrapper } = await mountApp('/user')
    const notice = wrapper.get('[data-reason]')

    expect(notice.attributes('data-reason')).toBe('offline')
    expect(notice.text()).toContain('連不上後端服務')
  })
})

describe('login account list backend messaging', () => {
  it('separates an error response from an unreachable backend', async () => {
    stubCatalogFetch((url) => {
      if (url.endsWith('/api/v1/insights/accounts')) return new Response('{}', { status: 500 })
      return undefined
    })
    const { wrapper } = await mountApp('/login', { identity: null })

    const notice = wrapper.get('[data-testid="account-list-unavailable"]')
    expect(notice.text()).toContain('HTTP 500')
    expect(notice.text()).not.toContain('請確認後端是否啟動')
  })

  it('still tells the user to check the backend when it is genuinely unreachable', async () => {
    stubCatalogFetch((url) => {
      if (url.endsWith('/api/v1/insights/accounts')) throw new TypeError('Failed to fetch')
      return undefined
    })
    const { wrapper } = await mountApp('/login', { identity: null })

    expect(wrapper.get('[data-testid="account-list-unavailable"]').text()).toContain('連不上後端服務')
  })
})
