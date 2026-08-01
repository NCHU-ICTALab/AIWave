// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

/** 直接對 platform stub 造一筆 booking,行事曆會長出對應的訂單來源事件。 */
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

describe('calendar view', () => {
  beforeEach(() => stubCatalogFetch())

  it('lists booking-sourced events and links them to the order detail', async () => {
    const booking = await createBooking()
    const { wrapper } = await mountApp('/user/calendar')

    const event = wrapper.get('[data-testid="calendar-event"]')
    expect(event.text()).toContain('水電修繕・到府檢測')
    expect(event.text()).toContain('訂單')
    expect(wrapper.get('[data-testid="calendar-order-link"]').attributes('href'))
      .toBe(`/user/orders/${booking.id}`)
  })

  it('adds a manual event and shows it in the list', async () => {
    const { wrapper } = await mountApp('/user/calendar')

    await wrapper.get('[data-testid="calendar-title"]').setValue('回收家具搬運')
    await wrapper.get('[data-testid="calendar-start"]').setValue('2026-08-09T14:00')
    await wrapper.get('[data-testid="calendar-end"]').setValue('2026-08-09T15:00')
    await wrapper.get('form.calendar-form').trigger('submit')
    await flushPromises()

    const events = wrapper.findAll('[data-testid="calendar-event"]')
    expect(events.some((row) => row.text().includes('回收家具搬運') && row.text().includes('手動'))).toBe(true)
  })

  it('switches to the week view and lays the focused week out as 7 day columns', async () => {
    await createBooking()
    const { wrapper } = await mountApp('/user/calendar')

    await wrapper.get('[data-testid="view-week"]').trigger('click')

    expect(wrapper.get('[data-testid="view-week"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[data-testid="view-list"]').attributes('aria-pressed')).toBe('false')
    const columns = wrapper.findAll('[data-testid="week-column"]')
    expect(columns).toHaveLength(7)
    // booking 是 2026-08-01(六);聚焦週為 7/26(日)–8/1(六),事件落在最後一欄
    expect(columns[6]!.text()).toContain('8/1')
    expect(columns[6]!.text()).toContain('水電修繕・到府檢測')
  })

  it('keeps booking events linked to the order detail in the week view', async () => {
    const booking = await createBooking()
    const { wrapper } = await mountApp('/user/calendar')

    await wrapper.get('[data-testid="view-week"]').trigger('click')

    expect(wrapper.get('[data-testid="week-order-link"]').attributes('href'))
      .toBe(`/user/orders/${booking.id}`)
  })

  it('hides a source when its filter is unchecked', async () => {
    await createBooking()
    const { wrapper } = await mountApp('/user/calendar')

    expect(wrapper.findAll('[data-testid="calendar-event"]')).toHaveLength(1)
    await wrapper.get('[data-testid="filter-booking"]').setValue(false)
    expect(wrapper.findAll('[data-testid="calendar-event"]')).toHaveLength(0)
  })
})
