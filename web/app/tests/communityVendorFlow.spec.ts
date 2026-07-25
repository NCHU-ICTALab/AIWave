// @vitest-environment happy-dom

import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

const ADMIN = { role: 'admin' as const, accountId: null, displayName: '社區管理者' }
const PARTNER = { role: 'partner' as const, accountId: null, displayName: '合作廠商' }

async function confirmDialog() {
  const button = document.querySelector<HTMLButtonElement>('[data-testid="confirm-action"]')
  expect(button).not.toBeNull()
  if (button) await new DOMWrapper(button).trigger('click')
  await flushPromises()
}

describe('community to vendor workflow', () => {
  beforeEach(() => stubCatalogFetch())

  it('publishes a request from the community workspace and reports it as awaiting a quote', async () => {
    const { wrapper } = await mountApp('/admin', { identity: ADMIN, attach: true })

    await wrapper.get('[data-testid="publish-campaign"]').trigger('click')
    expect(document.body.textContent).toContain('確認發送聯合服務需求')
    await confirmDialog()

    // 管理者不會「切換成廠商」——真實產品裡那是另一個身分的工作台
    expect(wrapper.text()).toContain('等待合作廠商回覆報價')
    expect(wrapper.find('a[href="/partner"]').exists()).toBe(false)
  })

  it('shows an empty vendor queue when nothing has been submitted yet', async () => {
    const { wrapper } = await mountApp('/partner', { identity: PARTNER, attach: true })

    expect(wrapper.get('h1').text()).toContain('廠商工作台')
    expect(wrapper.text()).toContain('目前沒有待報價的需求')
  })
})
