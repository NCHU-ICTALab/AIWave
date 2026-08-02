// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import { COMMUNITY_DEMO_SEED, planForHouseholds, SUBSCRIPTION_TIERS } from '@/data/communityDemoSeed'
import { GROUP_BUY_CATALOG } from '@/data/groupBuyCatalog'
import { DEMO_MANAGER_IDENTITY } from '@/stores/session'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { EXISTING_USER, mountApp, NEW_USER } from './fixtures/mountApp'

describe('community membership and homepage ticker', () => {
  it('shows the accessible ticker with a pause control on the resident home', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user')

    const ticker = wrapper.get('[data-testid="community-ticker"]')
    const toggle = ticker.get('button')
    expect(ticker.get('h2').text()).toBe('社區快訊')
    expect(toggle.attributes('aria-pressed')).toBe('false')

    await toggle.trigger('click')
    expect(toggle.attributes('aria-pressed')).toBe('true')
    expect(toggle.attributes('aria-label')).toContain('繼續')
  })

  it('shows VIP beside a subscribed resident name', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user', {
      identity: { ...EXISTING_USER, communityMembership: 'subscriber' },
    })

    expect(wrapper.get('[data-testid="membership-badge"]').text()).toContain('VIP')
    expect(wrapper.get('[data-testid="membership-badge"]').attributes('href')).toBe('/user/subscription')
  })

  it('limits a free resident community page to group buying and a visible unlock gate', async () => {
    stubCatalogFetch()
    const { wrapper, router } = await mountApp('/user/community', { identity: NEW_USER })

    expect(wrapper.get('[data-testid="community-subscription-gate"]').text()).toContain('免費會員先從團購開始')
    expect(wrapper.get('a[href="/user/community/group-buys"]')).toBeTruthy()
    expect(wrapper.text()).toContain('生活圈地圖與附近服務')

    // 公告、群組與共同需求收起來;團購本身仍然可用,見 communityGroupBuy.spec.ts
    //「lets a free resident still join a group buy」(那裡才有社區 API stub)。
    expect(wrapper.find('[data-testid="community-announcements"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="my-groups"]').exists()).toBe(false)

    await router.push('/user/life-circle')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('life-circle')
    expect(wrapper.find('[data-testid="subscription-lock"]').exists()).toBe(true)
  })

  it('keeps the full community board for a subscribed resident', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/community', { identity: EXISTING_USER })

    expect(wrapper.find('[data-testid="community-subscription-gate"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="community-announcements"]').exists()).toBe(true)
  })

  // 免費住戶要「看得到訂閱換到什麼」,所以首頁的付費區塊照樣渲染真的內容,只是霧面且
  // inert——不是換成一張說明卡片。這條測的就是這個誠實版本的契約:內容在、但真的碰不到。
  it('frosts the real subscriber tools on a free home instead of swapping in placeholder cards', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user', { identity: NEW_USER })

    const lockedFeatures = wrapper.findAll('[data-testid="subscription-lock-card"]').map((card) => card.text())
    for (const feature of ['AI 主動關懷提醒', '近期行程與通知', '會場生活圈', 'AI 管家', '給你的建議']) {
      expect(lockedFeatures.some((text) => text.includes(`${feature}・需要社區訂閱`))).toBe(true)
    }

    // 真的輸入框仍在畫面上(霧面才有東西可看),但整棵子樹 inert,鍵盤與螢幕閱讀器都進不去。
    const needInput = wrapper.get('[data-testid="need-input"]')
    const blurred = needInput.element.closest('.subscription-lock-content') as HTMLElement | null
    expect(blurred).not.toBeNull()
    expect(blurred!.inert).toBe(true)
    expect(blurred!.getAttribute('aria-hidden')).toBe('true')

    // 每一區都要給得出解鎖的去處,否則住戶只會看到一片模糊。
    const cards = wrapper.findAll('[data-testid="subscription-lock-card"]')
    expect(cards.length).toBeGreaterThanOrEqual(5)
    for (const card of cards) {
      expect(card.find('a[href="/user/subscription"]').exists()).toBe(true)
    }
  })

  it('drops every home lock once the community subscribes', async () => {
    stubCatalogFetch()
    const { wrapper, session } = await mountApp('/user', { identity: NEW_USER })
    expect(wrapper.findAll('[data-testid="subscription-lock"]').length).toBeGreaterThan(0)

    session.upgradeMembership()
    await flushPromises()

    expect(wrapper.findAll('[data-testid="subscription-lock"]')).toHaveLength(0)
    expect(wrapper.get('[data-testid="need-input"]').element.closest('.subscription-lock-content')).toBeNull()
  })

  it('compares both plans in a real table and lets a free resident upgrade in the Demo', async () => {
    stubCatalogFetch()
    const { wrapper, session } = await mountApp('/user/subscription', { identity: NEW_USER })

    expect(wrapper.get('[data-testid="current-membership"]').text()).toContain('免費社區')
    expect(wrapper.get('[data-testid="free-plan-card"]').text()).toContain('NT$ 0')

    // 住戶端方案頁與管委會端 /demo/subscription 共用同一份 seed;各寫一次數字的話,
    // 住戶看到的月費隨時可能跟主委看到的對不起來。
    const plan = COMMUNITY_DEMO_SEED.subscription
    const vip = wrapper.get('[data-testid="subscriber-plan-card"]').text()
    expect(vip).toContain('訂閱社區')
    // 月費不是寫死的,是戶數對照級距表算出來的。
    const derived = planForHouseholds(plan.householdCount)
    expect(derived.monthlyFee).not.toBeNull()
    expect(vip).toContain(`NT$ ${derived.monthlyFee!.toLocaleString('zh-TW')}`)
    expect(vip).toContain(derived.sizeLabel)
    expect(vip).toContain(String(plan.householdCount))
    expect(vip).toContain(plan.trialMonths)

    // 比較表用真的 table 結構,螢幕閱讀器才唸得出「哪個功能／哪個方案」。
    const table = wrapper.get('[data-testid="subscription-feature-table"]')
    expect(table.get('caption').text()).toContain('比較')
    expect(table.findAll('thead th').every((cell) => cell.attributes('scope') === 'col')).toBe(true)
    expect(table.findAll('tbody th').every((cell) => cell.attributes('scope') === 'row')).toBe(true)
    // 團購是免費社區唯一開放的功能,其餘一律標示訂閱解鎖。
    const freeCells = table.findAll('tbody tr').map((row) => row.findAll('td')[0]?.text())
    expect(freeCells[0]).toBe('可使用')
    expect(freeCells.slice(1).every((cell) => cell === '訂閱解鎖')).toBe(true)

    await wrapper.get('[data-testid="upgrade-membership"]').trigger('click')
    await flushPromises()

    expect(session.isSubscriber).toBe(true)
    expect(wrapper.get('[data-testid="subscription-feedback"]').attributes('role')).toBe('status')
    expect(wrapper.find('[data-testid="subscription-active"]').exists()).toBe(true)
  })

  // 價目表是「依社區戶數分級」,所以整份級距表必須看得到,而且社區自己的月費要從戶數
  // 對照出來——在畫面上另外寫一次金額,改價時一定會有一頁忘了改。
  it('shows the whole six-tier price list and derives this community fee from its household count', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/subscription', { identity: NEW_USER })

    const table = wrapper.get('[data-testid="subscription-tier-table"]')
    const rows = table.findAll('tbody tr')
    expect(rows).toHaveLength(6)
    expect(SUBSCRIPTION_TIERS).toHaveLength(6)

    rows.forEach((row, index) => {
      const tier = SUBSCRIPTION_TIERS[index]!
      expect(row.get('th').attributes('scope')).toBe('row')
      expect(row.get('th').text()).toBe(tier.sizeLabel)
      const cells = row.findAll('td').map((cell) => cell.text())
      expect(cells[0]).toContain(tier.monthlyFee === null ? '客製報價' : `NT$ ${tier.monthlyFee.toLocaleString('zh-TW')}`)
      expect(cells[1]).toBe(tier.perHouseholdLabel)
    })

    // 最高一級沒有固定價格,型別必須表達「客製報價」而不是假造一個數字。
    expect(SUBSCRIPTION_TIERS[5]!.monthlyFee).toBeNull()

    expect(table.get('caption').text()).toContain('級距')
    expect(table.findAll('thead th').every((cell) => cell.attributes('scope') === 'col')).toBe(true)

    // 目前級距不能只用底色標示,必須有明確文字。
    const plan = COMMUNITY_DEMO_SEED.subscription
    const currentIndex = SUBSCRIPTION_TIERS.findIndex((tier) => tier.id === plan.tier.id)
    const badges = table.findAll('.subscription-tier-badge')
    expect(badges).toHaveLength(1)
    expect(badges[0]!.text()).toBe('目前方案')
    expect(rows[currentIndex]!.text()).toContain('目前方案')
    expect(plan.tier).toEqual(planForHouseholds(plan.householdCount))
  })

  // 住戶看到的月費與管委會帳務頁看到的必須是同一個數字,不然簡報講商模時會自打嘴巴。
  it('quotes the same monthly fee on the resident page and the committee billing page', async () => {
    const plan = COMMUNITY_DEMO_SEED.subscription
    expect(plan.monthlyFee).not.toBeNull()
    const fee = `NT$ ${plan.monthlyFee!.toLocaleString('zh-TW')}`

    stubCatalogFetch()
    const resident = await mountApp('/user/subscription', { identity: NEW_USER })
    expect(resident.wrapper.get('[data-testid="subscriber-plan-card"]').text()).toContain(fee)

    const committee = await mountApp('/demo/subscription', { identity: DEMO_MANAGER_IDENTITY })
    expect(committee.wrapper.get('[data-testid="subscription-pricing"]').text()).toContain(fee)
    expect(committee.wrapper.get('[data-testid="subscription-pricing"]').text()).toContain(plan.tier.sizeLabel)
  })

  // 管委會頁面把「住戶省下 − 月費」這個減法直接印在畫面上,所以淨效益必須真的成立。
  it('keeps the community net benefit equal to savings minus the fee it actually pays', () => {
    const plan = COMMUNITY_DEMO_SEED.subscription
    expect(plan.netBenefit).toBe(plan.residentSavings - (plan.monthlyFee ?? 0))
    expect(plan.householdCount).toBe(COMMUNITY_DEMO_SEED.community.households)
  })

  it.each([
    [1, 'tier-1-30'], [30, 'tier-1-30'], [31, 'tier-31-50'], [50, 'tier-31-50'],
    [51, 'tier-51-100'], [100, 'tier-51-100'], [101, 'tier-101-200'], [200, 'tier-101-200'],
    [201, 'tier-201-500'], [500, 'tier-201-500'], [501, 'tier-500-plus'], [1200, 'tier-500-plus'],
  ])('maps %i households to %s', (households, tierId) => {
    expect(planForHouseholds(households).id).toBe(tierId)
  })

  it('lets an upgraded resident reach the previously locked pages', async () => {
    stubCatalogFetch()
    const { wrapper, router, session } = await mountApp('/user/subscription', { identity: NEW_USER })

    await wrapper.get('[data-testid="upgrade-membership"]').trigger('click')
    await router.push('/user/life-circle')
    await flushPromises()

    expect(session.isSubscriber).toBe(true)
    expect(router.currentRoute.value.name).toBe('life-circle')
  })

  // 商業規則:免費社區只開放團購,其餘住戶功能訂閱解鎖。這條規則散在 router meta 上,
  // 少標一個 subscriberOnly 就會悄悄漏掉一個功能,所以整組一起驗。
  it.each([
    '/user/assistant', '/user/services', '/user/booking', '/user/calendar',
    '/user/life-circle', '/user/wellbeing',
  ])('locks %s behind a frosted overlay for a free resident', async (path) => {
    stubCatalogFetch()
    const { wrapper, router } = await mountApp('/user', { identity: NEW_USER })

    await router.push(path)
    await flushPromises()

    // 不再導走:住戶留在原頁,才看得到訂閱換到什麼。
    expect(router.currentRoute.value.path).toBe(path)
    const lock = wrapper.get('[data-testid="subscription-lock"]')
    expect(lock.get('[data-testid="subscription-lock-card"]').text()).toContain('需要社區訂閱')
    expect(lock.find('a[href="/user/subscription"]').exists()).toBe(true)
  })

  // 霧面只是視覺。內容若沒有真的 inert,螢幕閱讀器照唸、Tab 也照樣跳得進看不見的
  // 按鈕——鎖了個寂寞,還踩到 WCAG 2.4.11(焦點不可見)。
  it('makes the blurred content genuinely inert, not merely blurry', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/assistant', { identity: NEW_USER })

    const locked = wrapper.get('[data-testid="subscription-lock"] .subscription-lock-content')
    expect((locked.element as HTMLElement).inert).toBe(true)
    expect(locked.attributes('aria-hidden')).toBe('true')

    // 解鎖卡片本身必須留在 a11y tree 裡,否則等於整頁對輔具消失。
    const card = wrapper.get('[data-testid="subscription-lock-card"]')
    expect(card.element.closest('[aria-hidden="true"]')).toBeNull()
  })

  it('drops the lock as soon as the community subscribes', async () => {
    stubCatalogFetch()
    const { wrapper, session } = await mountApp('/user/assistant', { identity: NEW_USER })
    expect(wrapper.find('[data-testid="subscription-lock"]').exists()).toBe(true)

    session.upgradeMembership()
    await flushPromises()

    expect(wrapper.find('[data-testid="subscription-lock"]').exists()).toBe(false)
  })

  it.each([
    '/user/community', '/user/community/group-buys', '/user/orders', '/user/subscription',
  ])('keeps %s open to a free resident', async (path) => {
    stubCatalogFetch()
    const { router } = await mountApp('/user', { identity: NEW_USER })

    await router.push(path)
    await flushPromises()

    expect(router.currentRoute.value.path).toBe(path)
  })

  // 跑馬燈的團購推播是從團購目錄算出來的,不是另寫一份文案。手寫文案會跟商品頁的
  // 價格與成團進度漂移,跑馬燈就會說出頁面上不成立的話。
  it('derives its group-buy promotions from the catalog instead of hand-written copy', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user')

    const ticker = wrapper.get('[data-testid="community-ticker"]')
    const promoted = GROUP_BUY_CATALOG
      .filter((item) => item.status === 'open' && item.progressUnits !== undefined)
      .sort((a, b) => (b.progressUnits ?? 0) / b.thresholdUnits - (a.progressUnits ?? 0) / a.thresholdUnits)
      .slice(0, 2)

    expect(promoted).toHaveLength(2)
    for (const item of promoted) {
      const remaining = item.thresholdUnits - (item.progressUnits ?? 0)
      expect(ticker.text()).toContain(item.name)
      expect(ticker.text()).toContain(`NT$ ${item.communityPrice.toLocaleString('zh-TW')}`)
      expect(ticker.text()).toContain(remaining > 0 ? `差 ${remaining} 件成團` : '已達成團門檻')
    }
  })

  it('stops the ticker animation for residents who ask for reduced motion', () => {
    const styles = readFileSync(resolve(process.cwd(), 'src/components/CommunityTicker.vue'), 'utf8')
    const reducedMotion = styles.slice(styles.indexOf('prefers-reduced-motion'))

    expect(reducedMotion).toContain('animation: none')
  })
})
