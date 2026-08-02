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
