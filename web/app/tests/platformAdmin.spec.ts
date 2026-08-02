// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Identity } from '@/stores/session'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

const ADMIN: Identity = {
  role: 'admin',
  accountId: null,
  displayName: '社區小統平台營運者',
  accessToken: 'aiwave-admin',
}

/**
 * `/api/v1/admin/demo-personas` 不在 `/api/v1/platform/` 前綴下,platformStub
 * 的路徑守衛擋不到它,因此用 extra 供應 personas(形狀鏡射後端契約)。
 */
const DEMO_PERSONAS = [
  {
    membershipId: 'membership-member-xiaoyuan', accountId: 'acct-1',
    displayName: '林小圓', role: 'member', demoWorkspaceId: 'demo-default',
    workspace: { id: 'ws-1', kind: 'personal', ownerRef: 'acct-1', name: '林小圓的個人空間' },
  },
  {
    membershipId: 'membership-partner-prince-electric', accountId: 'acct-p',
    displayName: '王子水電人員', role: 'partner_staff', demoWorkspaceId: 'demo-default',
    workspace: { id: 'ws-p', kind: 'partner', ownerRef: 'vendor-prince-electric', name: '王子水電' },
  },
]

function personasExtra(url: string): Response | undefined {
  if (String(url).split('?')[0]!.endsWith('/api/v1/admin/demo-personas')) {
    return new Response(JSON.stringify({ data: DEMO_PERSONAS }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  return undefined
}

describe('platform admin workspace (aiwave-admin)', () => {
  beforeEach(() => {
    globalThis.localStorage?.clear()
  })

  it('shows catalog health for all 12 providers', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/platform', { identity: ADMIN })

    const rows = wrapper.findAll('[data-provider-row]')
    expect(rows).toHaveLength(12)
    expect(wrapper.get('[data-testid="catalog-health-table"]').text()).toContain('partner-demo-v5')
    // 誠實資料標示
    expect(wrapper.text()).toContain('展示資料（partner-demo-v5）')
  })

  it('reports the sync result after re-syncing the catalog', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/platform', { identity: ADMIN })

    await wrapper.get('[data-testid="sync-catalog"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="sync-result"]').text()).toContain('ok')
  })

  it('resets the demo only after explicit confirmation', async () => {
    const fetcher = stubCatalogFetch()
    const resetCalls = () =>
      fetcher.mock.calls.filter(([input]) => String(input).includes('/api/v1/platform/demo/reset'))

    const { wrapper } = await mountApp('/platform', { identity: ADMIN })

    await wrapper.get('[data-testid="reset-demo"]').trigger('click')
    // 只是打開確認 dialog,還沒送出
    expect(resetCalls()).toHaveLength(0)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)

    await wrapper.get('[data-testid="confirm-reset"]').trigger('click')
    await flushPromises()

    expect(resetCalls()).toHaveLength(1)
    expect(wrapper.get('[data-testid="reset-result"]').text()).toContain('ready')
  })

  it('lists demo personas and resets a personal workspace only after confirmation', async () => {
    const fetcher = stubCatalogFetch(personasExtra)
    const personaResetCalls = () =>
      fetcher.mock.calls.filter(([input]) =>
        String(input).includes('/api/v1/platform/admin/workspaces/membership-member-xiaoyuan/reset'))

    const { wrapper } = await mountApp('/platform', { identity: ADMIN })

    const personalRow = wrapper.get('[data-persona-row="membership-member-xiaoyuan"]')
    expect(personalRow.text()).toContain('林小圓')
    expect(personalRow.text()).toContain('personal')
    expect(personalRow.find('[data-testid="reset-persona-membership-member-xiaoyuan"]').exists()).toBe(true)

    // 非個人 workspace 不顯示重置按鈕(422 防護在後端,前端根本不給入口)
    const partnerRow = wrapper.get('[data-persona-row="membership-partner-prince-electric"]')
    expect(partnerRow.find('button').exists()).toBe(false)

    await personalRow.get('[data-testid="reset-persona-membership-member-xiaoyuan"]').trigger('click')
    // 只是打開 ConfirmDialog,還沒送出
    expect(personaResetCalls()).toHaveLength(0)
    const confirmButton = document.body.querySelector<HTMLButtonElement>('[data-testid="confirm-action"]')
    expect(confirmButton).not.toBeNull()
    confirmButton!.click()
    await flushPromises()

    expect(personaResetCalls()).toHaveLength(1)
    expect(wrapper.get('[data-testid="persona-reset-result"]').text()).toContain('已重置「林小圓」')
  })

  it('shows fake upstream health with a seed-consistency badge', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/platform', { identity: ADMIN })

    const section = wrapper.get('[data-testid="upstream-health"]')
    expect(section.text()).toContain('partner-demo-v5')
    expect(wrapper.get('[data-testid="upstream-consistent"]').text()).toContain('一致 ✓')
  })

  it('reports an injected one-shot timeout fault', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/platform', { identity: ADMIN })

    await wrapper.get('[data-testid="inject-timeout"]').trigger('click')
    await flushPromises()

    const result = wrapper.get('[data-testid="fault-result"]').text()
    expect(result).toContain('已注入 timeout')
    expect(result).toContain('一次性 fault')
  })
})
