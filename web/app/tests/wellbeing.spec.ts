// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { mountApp } from './fixtures/mountApp'
import { stubCatalogFetch } from './fixtures/catalogClient'

describe('wellbeing view', () => {
  it('renders care, editable package, outcome, achievement, and demo reward evidence', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/wellbeing')
    await flushPromises()

    expect(wrapper.get('[data-testid="care-card"]').text()).toContain('中元關懷 Demo 事件')
    expect(wrapper.get('[data-testid="task-package-card"]').text()).toContain('王子水電')
    expect(wrapper.get('[data-testid="outcome-list"]').text()).toContain('booking-stub-1')
    expect(wrapper.get('[data-testid="achievement-list"]').text()).toContain('完成一項生活任務')
    expect(wrapper.get('[data-testid="reward-list"]').text()).toContain('+20 點')
    expect(wrapper.text()).toContain('Provider success fee 不在此顯示')

    await wrapper.get('[data-testid="care-card"] .button.primary').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="life-guide-card"]').text()).toContain('中元普渡準備・競賽 Demo 指南')
    expect(wrapper.get('[data-testid="life-guide-card"]').text()).toContain('Demo 點數估算')
    expect(wrapper.findAll('[data-testid="preparation-item"]')).toHaveLength(3)

    await wrapper.get('[data-testid="prepare-life-guide"]').trigger('click')
    expect(wrapper.text()).toContain('尚未建立訂單')

    await wrapper.get('[data-testid="task-package-card"] .text-button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="task-package-card"]').text()).toContain('paused')
  })
})
