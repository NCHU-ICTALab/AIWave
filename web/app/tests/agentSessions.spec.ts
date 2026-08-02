// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { mountApp } from './fixtures/mountApp'
import { stubCatalogFetch } from './fixtures/catalogClient'

describe('Agent Session lifecycle', () => {
  it('creates, renames, archives, and restores a selected conversation', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/assistant')
    const history = wrapper.get('[data-testid="agent-session-history"]')

    await history.get('[data-testid="new-agent-session"]').trigger('click')
    await flushPromises()
    expect(history.find('[data-testid="new-agent-session"]').exists()).toBe(true)
    expect(history.text()).toContain('新對話')

    await history.get('[data-testid="rename-agent-session"]').trigger('click')
    await history.get('#agent-session-title').setValue('爸媽週末安排')
    await history.get('.session-rename').trigger('submit')
    await flushPromises()
    expect(history.text()).toContain('爸媽週末安排')

    await history.get('[data-testid="archive-agent-session"]').trigger('click')
    await flushPromises()
    expect(history.text()).toContain('顯示已封存')

    await history.get('.text-link').trigger('click')
    await flushPromises()
    expect(history.text()).toContain('已封存・點擊恢復')
    await history.get('.session-history-list.archived .session-history-item').trigger('click')
    await flushPromises()
    expect(history.text()).toContain('爸媽週末安排')
  })
})
