// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

const MANAGER = { role: 'manager' as const, accountId: null, displayName: '社區管理者' }

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/**
 * 公告以外的社區端點回空資料;公告本身由 platformStub 的有狀態替身處理
 * (seed:「公設保養通知」;POST 空標題回 422)。
 * `/api/v1/platform/communities` 沒有 stub,依後端
 * core/communities/repository.py 的 list_available 形狀以 extra 覆寫。
 */
function stubCommunityPages(extra?: (url: string, init?: RequestInit) => Response | undefined) {
  return stubCatalogFetch((url, init) => {
    const custom = extra?.(url, init)
    if (custom) return custom
    if (url.endsWith('/api/v1/platform/communities')) {
      return json({ data: [
        {
          id: 'community-sunshine', name: '陽光社區', address: '臺中市西屯區臺灣大道三段99號',
          workspaceId: 'workspace-community-sunshine',
          membership: { role: 'resident', status: 'active', isDefault: true },
          joinRequestPending: false,
        },
        {
          id: 'community-greenfield', name: '綠園社區', address: '臺中市西屯區福星路168號',
          workspaceId: 'workspace-community-greenfield',
          membership: null, joinRequestPending: false,
        },
      ] })
    }
    if (url.includes('/community/campaigns') && !init?.method) return json({ data: [] })
    if (url.includes('/community/my-participation')) return json({ data: [] })
    if (url.includes('/community/joint-services') && !init?.method) return json({ data: [] })
    if (url.endsWith('/api/v1/support/queue')) return json({ data: [] })
    return undefined
  })
}

describe('community announcements', () => {
  it('shows the seeded announcement on the resident community page', async () => {
    stubCommunityPages()
    const { wrapper } = await mountApp('/user/community')

    const panel = wrapper.get('[data-testid="community-announcements"]')
    expect(panel.text()).toContain('社區公告')
    expect(panel.text()).toContain('陽光社區')
    const item = wrapper.get('[data-testid="announcement-item"]')
    expect(item.text()).toContain('公設保養通知')

    // details 展開後看得到內容
    await item.get('summary').trigger('click')
    expect(item.text()).toContain('電梯輪流停機')
  })

  it('lets the manager publish an announcement and prepends it to the list', async () => {
    stubCommunityPages()
    const { wrapper } = await mountApp('/community', { identity: MANAGER })

    await wrapper.get('[data-testid="announcement-title"]').setValue('中秋節活動')
    await wrapper.get('[data-testid="announcement-body"]').setValue('9/25 晚上 6 點中庭烤肉，歡迎住戶報名。')
    await wrapper.get('[data-testid="announcement-panel"] form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-testid="announcement-notice"]').text()).toContain('已發布「中秋節活動」')
    const items = wrapper.findAll('[data-testid="manager-announcement-item"]')
    expect(items.length).toBeGreaterThanOrEqual(2)
    // 新公告 prepend 在最前面,seed 公告仍在
    expect(items[0]!.text()).toContain('中秋節活動')
    expect(items.map((item) => item.text()).join('\n')).toContain('公設保養通知')
  })

  it('shows the backend 422 error when the title is blank', async () => {
    stubCommunityPages()
    const { wrapper } = await mountApp('/community', { identity: MANAGER })

    await wrapper.get('[data-testid="announcement-title"]').setValue('')
    await wrapper.get('[data-testid="announcement-body"]').setValue('內容有,但沒有標題')
    await wrapper.get('[data-testid="announcement-panel"] form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-testid="announcement-error"]').text()).toContain('公告標題與內容不可空白')
    expect(wrapper.find('[data-testid="announcement-notice"]').exists()).toBe(false)
  })
})
