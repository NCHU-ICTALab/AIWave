// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Identity } from '@/stores/session'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

/** M4 合作方 Demo 帳號:王子水電(與 core/access seed 的固定 Bearer 一致)。 */
const PARTNER: Identity = {
  role: 'partner',
  accountId: 'vendor-prince-electric',
  displayName: '王子水電人員',
  accessToken: 'aiwave-partner',
}

/**
 * 透過 fetch stub 的 task-drafts submit 造一筆 booking(和會員端走同一條路),
 * 再依 `transitions` 依序推進狀態。回傳 booking id。
 */
async function seedBooking(transitions: string[] = []): Promise<string> {
  const createdResponse = await fetch('/api/v1/platform/task-drafts', {
    method: 'POST',
    body: JSON.stringify({
      domain_type: 'home_repair',
      values: {
        offering_id: 'off-prince-electric-repair',
        location_id: 'loc-prince-electric-01',
        slot_id: 'slot-prince-electric-1',
        starts_at: '2026-08-01T09:00:00+08:00',
        ends_at: '2026-08-01T11:00:00+08:00',
      },
    }),
  })
  const draft = ((await createdResponse.json()) as { data: { id: string; version: number } }).data

  const submitResponse = await fetch(`/api/v1/platform/task-drafts/${draft.id}/submit`, {
    method: 'POST',
    body: JSON.stringify({ expected_version: draft.version }),
  })
  const submitted = ((await submitResponse.json()) as {
    data: { booking: { id: string; version: number } }
  }).data

  let version = submitted.booking.version
  for (const status of transitions) {
    const transitionResponse = await fetch(
      `/api/v1/platform/bookings/${submitted.booking.id}/transition`,
      { method: 'POST', body: JSON.stringify({ expected_version: version, status }) },
    )
    version = ((await transitionResponse.json()) as { data: { version: number } }).data.version
  }
  return submitted.booking.id
}

describe('vendor platform bookings (M4)', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
    stubCatalogFetch()
  })

  it('lists the platform booking as awaiting acceptance', async () => {
    const bookingId = await seedBooking()
    const { wrapper } = await mountApp('/partner', { identity: PARTNER })

    expect(wrapper.get('[data-testid="provider-settlement"]').text()).toContain('非正式費率')
    const row = wrapper.get(`[data-platform-booking="${bookingId}"]`)
    expect(row.text()).toContain(bookingId)
    expect(row.text()).toContain('待接單')
    expect(row.find(`[data-testid="booking-transition-${bookingId}"]`).text()).toBe('確認接單')
  })

  it('moves the booking to confirmed after accepting, and tells the vendor the member side is synced', async () => {
    const bookingId = await seedBooking()
    const { wrapper } = await mountApp('/partner', { identity: PARTNER })

    await wrapper.get(`[data-testid="booking-transition-${bookingId}"]`).trigger('click')
    await flushPromises()

    const row = wrapper.get(`[data-platform-booking="${bookingId}"]`)
    expect(row.text()).toContain('已預約')
    // 下一步是「開始服務」,不再是「確認接單」
    expect(row.get(`[data-testid="booking-transition-${bookingId}"]`).text()).toBe('開始服務')
    expect(wrapper.get('[data-testid="platform-toast"]').text()).toContain('會員端進度/通知/行事曆同步更新')
  })

  it('shows no transition button on a completed booking', async () => {
    const bookingId = await seedBooking(['confirmed', 'in_service', 'completed'])
    const { wrapper } = await mountApp('/partner', { identity: PARTNER })

    const row = wrapper.get(`[data-platform-booking="${bookingId}"]`)
    expect(row.text()).toContain('已完成')
    expect(row.find(`[data-testid="booking-transition-${bookingId}"]`).exists()).toBe(false)
  })

  it('expands 查看需求 with localized fulfilment fields and the data-minimization note', async () => {
    // stub 的 submit 不會把 domain required 欄位存進 booking.details,
    // 因此用 extra 覆寫 GET /platform/bookings 回帶 details,驗證前端 render 邏輯。
    const detailBooking = {
      id: 'booking-with-details',
      providerId: 'vendor-prince-electric',
      locationId: 'loc-prince-electric-01',
      offeringId: 'off-prince-electric-repair',
      resourceId: null,
      slotId: 'slot-prince-electric-1',
      startsAt: '2026-08-01T09:00:00+08:00',
      endsAt: '2026-08-01T11:00:00+08:00',
      status: 'pending_provider',
      version: 1,
      details: {
        problem: '陽台排水口阻塞,下雨積水',
        address: '台北市信義區莊敬路 55 號 2 樓',
        phone: '0966-123-456',
        custom_flag: '社區需在管理室換證',
      },
      events: [],
      providerSync: { syncStatus: 'synced', lastError: null },
    }
    stubCatalogFetch((url, init) => {
      const method = (init?.method ?? 'GET').toUpperCase()
      if (method === 'GET' && String(url).split('?')[0]!.endsWith('/api/v1/platform/bookings')) {
        return new Response(JSON.stringify({ data: [detailBooking] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return undefined
    })
    const { wrapper } = await mountApp('/partner', { identity: PARTNER })

    const details = wrapper.get('[data-testid="booking-details-booking-with-details"]')
    expect(details.text()).toContain('查看需求')
    expect(details.text()).toContain('問題描述')
    expect(details.text()).toContain('陽台排水口阻塞,下雨積水')
    expect(details.text()).toContain('服務地址')
    expect(details.text()).toContain('聯絡電話')
    // 未知鍵原樣顯示,不假裝認得
    expect(details.text()).toContain('custom_flag')
    expect(details.text()).toContain('個資最小化:僅顯示履約必要資料')
  })

  it('shows 此案件無補充需求資料 when a booking carries no details', async () => {
    const bookingId = await seedBooking()
    const { wrapper } = await mountApp('/partner', { identity: PARTNER })

    expect(wrapper.get(`[data-testid="booking-details-${bookingId}"]`).text())
      .toContain('此案件無補充需求資料')
  })

  it('surfaces the honest 409 when a standard-integration provider tries to edit availability', async () => {
    const { wrapper } = await mountApp('/partner', { identity: PARTNER })

    // 可服務時段 panel 由 GET /provider/availability 供資料
    const panel = wrapper.get('[data-testid="provider-availability"]')
    expect(panel.text()).toContain('本週可服務時段')

    await wrapper.get('[data-testid="edit-availability"]').trigger('click')
    await wrapper.get('[data-testid="availability-form"]').trigger('submit')
    await flushPromises()

    // 王子水電是標準接入:後端回 409 是規格的正確行為,前端誠實顯示而非假裝成功
    expect(wrapper.get('[data-testid="availability-error"]').text())
      .toContain('availability 由廠商系統維護')
  })
})
