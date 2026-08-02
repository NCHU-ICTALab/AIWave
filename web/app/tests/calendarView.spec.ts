// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

/** 直接對 platform stub 造一筆 booking,月曆會長出對應的訂單來源事件。 */
async function postJson(url: string, body: unknown) {
  const response = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  expect(response.ok).toBe(true)
  return (await response.json()).data
}

async function createBooking() {
  const draft = await postJson('/api/v1/platform/task-drafts', {
    domain_type: 'home_repair',
    values: {
      offering_id: 'off-prince-electric-repair',
      location_id: 'loc-prince-electric-01',
      slot_id: 'slot-prince-electric-1',
      starts_at: '2026-08-01T09:00:00+08:00',
      ends_at: '2026-08-01T11:00:00+08:00',
    },
  })
  const result = await postJson(`/api/v1/platform/task-drafts/${draft.id}/submit`, {
    expected_version: draft.version,
  })
  return result.booking
}

describe('calendar month view', () => {
  beforeEach(() => stubCatalogFetch())

  it('shows booking events in the primary month view and links to the order detail', async () => {
    const booking = await createBooking()
    const { wrapper } = await mountApp('/user/calendar')

    const event = wrapper.get('[data-testid="calendar-event"]')
    expect(event.text()).toContain('水電修繕・到府檢測')
    expect(wrapper.get('[data-testid="calendar-order-link"]').attributes('href'))
      .toBe(`/user/orders/${booking.id}`)
    expect(wrapper.find('[data-testid="view-week"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="view-list"]').exists()).toBe(false)
  })

  it('adds a manual event to the focused month', async () => {
    const { wrapper } = await mountApp('/user/calendar')

    await wrapper.get('[data-testid="calendar-title"]').setValue('回收家具搬運')
    await wrapper.get('[data-testid="calendar-start"]').setValue('2026-08-09T14:00')
    await wrapper.get('[data-testid="calendar-end"]').setValue('2026-08-09T15:00')
    await wrapper.get('form.calendar-form').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('[data-testid="calendar-event"]').some((item) => item.text().includes('回收家具搬運'))).toBe(true)
  })

  it('navigates to the previous and next month without changing the view mode', async () => {
    const { wrapper } = await mountApp('/user/calendar')

    expect(wrapper.get('[data-testid="calendar-month-label"]').text()).toBe('2026 年 8 月')
    await wrapper.get('[data-testid="calendar-next-month"]').trigger('click')
    expect(wrapper.get('[data-testid="calendar-month-label"]').text()).toBe('2026 年 9 月')
    await wrapper.get('[data-testid="calendar-prev-month"]').trigger('click')
    expect(wrapper.get('[data-testid="calendar-month-label"]').text()).toBe('2026 年 8 月')
  })

  it('shows the fixed Demo holiday and Father’s Day reminder in August', async () => {
    const { wrapper } = await mountApp('/user/calendar')

    expect(wrapper.find('[data-testid="calendar-holiday"]').text()).toContain('父親節')
    expect(wrapper.text()).toContain('固定 Demo 行事曆')
  })

  it('hides a source when its filter is unchecked', async () => {
    await createBooking()
    const { wrapper } = await mountApp('/user/calendar')

    expect(wrapper.findAll('[data-testid="calendar-event"]')).toHaveLength(1)
    await wrapper.get('[data-testid="filter-booking"]').setValue(false)
    expect(wrapper.findAll('[data-testid="calendar-event"]')).toHaveLength(0)
  })
})

/**
 * 「後端回了空清單」與「後端連不上」是兩件事。畫面說錯會讓人以為 API 沒起來,
 * 而實際上後端正回著 200——這裡把兩種說法釘住。
 */
describe('calendar demo fallback honesty', () => {
  it('does not claim the backend is down when it answered 200 with an empty list', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/calendar')

    const notice = wrapper.get('[data-testid="calendar-offline-demo"]')
    expect(notice.attributes('data-reason')).toBe('empty')
    expect(notice.text()).toContain('沒有任何會員事件')
    expect(notice.text()).not.toContain('連不上')
    expect(notice.text()).not.toContain('未啟動')
    expect(notice.attributes('role')).toBe('status')
  })

  it('says the backend is unreachable when the request actually fails', async () => {
    stubCatalogFetch((url) => {
      if (url.includes('/platform/calendar/events')) throw new TypeError('Failed to fetch')
      return undefined
    })
    const { wrapper } = await mountApp('/user/calendar')

    const notice = wrapper.get('[data-testid="calendar-offline-demo"]')
    expect(notice.attributes('data-reason')).toBe('offline')
    expect(notice.text()).toContain('連不上後端')
    expect(notice.attributes('role')).toBe('status')
  })

  it('separates a backend error response from an unreachable backend', async () => {
    stubCatalogFetch((url) => {
      if (url.includes('/platform/calendar/events')) {
        return new Response(JSON.stringify({ detail: '行事曆暫時無法讀取' }), { status: 500 })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/calendar')

    const notice = wrapper.get('[data-testid="calendar-offline-demo"]')
    expect(notice.attributes('data-reason')).toBe('failed')
    expect(notice.text()).toContain('後端有回應')
    expect(notice.text()).toContain('行事曆暫時無法讀取')
  })

  it('reports a failed create instead of faking an offline event when the backend is up', async () => {
    stubCatalogFetch((url, init) => {
      if (url.includes('/platform/calendar/events') && init?.method === 'POST') {
        return new Response(JSON.stringify({ detail: '結束時間必須晚於開始時間' }), { status: 400 })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/user/calendar')

    await wrapper.get('[data-testid="calendar-title"]').setValue('社區大掃除')
    await wrapper.get('[data-testid="calendar-start"]').setValue('2026-08-09T14:00')
    await wrapper.get('[data-testid="calendar-end"]').setValue('2026-08-09T15:00')
    await wrapper.get('form.calendar-form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('結束時間必須晚於開始時間')
    expect(wrapper.findAll('[data-testid="calendar-event"]').some((item) => item.text().includes('社區大掃除'))).toBe(false)
  })
})
