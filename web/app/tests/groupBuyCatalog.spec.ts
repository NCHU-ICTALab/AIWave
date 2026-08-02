// @vitest-environment happy-dom

import { flushPromises } from '@vue/test-utils'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'

import { GROUP_BUY_CATALOG } from '@/data/groupBuyCatalog'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp, NEW_USER } from './fixtures/mountApp'

describe('community group-buy catalog', () => {
  it('browses products and carries a selected product into the editable opening flow', async () => {
    stubCatalogFetch()
    const { wrapper, router, session } = await mountApp('/user/community/group-buys', { identity: NEW_USER })
    await flushPromises()

    expect(wrapper.get('[data-testid="group-buy-catalog"]').text()).toContain('商品列表')
    expect(wrapper.findAll('[data-testid="open-group-from-list"]').length).toBeGreaterThan(3)

    await wrapper.find('[data-testid="open-group-from-list"]').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('community-group-buy-open'))
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('community-group-buy-open')
    expect(wrapper.get('[data-testid="group-buy-open-page"]').text()).toContain('可編輯')
    const selectedName = (wrapper.get('[data-testid="open-group-name"]').element as HTMLInputElement).value

    await wrapper.get('form.group-buy-open-form').trigger('submit')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('community-group-buy'))
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('community-group-buy')
    expect(session.role).toBe('user')
    expect(wrapper.get('h1').text()).toContain(selectedName)
    expect(wrapper.find('[data-testid="join-group-buy"]').exists()).toBe(true)
  })

  // 商品照一律是本地檔案：外站 CDN（momo/PXGo…）會隨機連線重置，一斷線每張卡就退成 emoji，等於沒有圖。
  // 通路商品照是一次下載後 commit 進 public/group-buy/，出處記在同資料夾的 README.md。
  it('商品照與備援插畫都是本地檔案，且檔案真的存在', () => {
    const withImage = GROUP_BUY_CATALOG.filter((item) => item.imageUrl)
    expect(withImage.length).toBeGreaterThanOrEqual(8)

    for (const item of withImage) {
      // 這條就是防線：只要有人把 imageUrl 換回 https://... 的外站圖床就會紅
      expect(item.imageUrl, `${item.name} 的商品照必須是本地路徑`).toMatch(/^\/group-buy\/[a-z0-9-]+\.(jpg|png|svg)$/)
      expect(existsSync(resolve(process.cwd(), `public${item.imageUrl}`)), `缺少商品照：${item.imageUrl}`).toBe(true)

      // 商品照掛掉時要退回自繪 SVG，而不是直接掉到裸 emoji
      expect(item.fallbackImageUrl, `${item.name} 缺少備援插畫`).toMatch(/^\/group-buy\/[a-z0-9-]+\.svg$/)
      expect(existsSync(resolve(process.cwd(), `public${item.fallbackImageUrl}`)), `缺少備援插畫：${item.fallbackImageUrl}`).toBe(true)
      expect(item.fallbackImageUrl).not.toBe(item.imageUrl)

      // 真實商品必須留下原商品頁，出處才誠實
      expect(item.sourceUrl, `${item.name} 缺少原商品頁連結`).toMatch(/^https:\/\//)
    }
  })

  it('商品照的出處逐張記錄在 public/group-buy/README.md', () => {
    const provenance = readFileSync(resolve(process.cwd(), 'public/group-buy/README.md'), 'utf-8')
    for (const item of GROUP_BUY_CATALOG.filter((entry) => entry.imageUrl)) {
      const fileName = item.imageUrl!.split('/').pop()!
      expect(provenance, `README.md 沒有記錄 ${fileName} 的出處`).toContain(fileName)
      expect(provenance, `README.md 沒有記錄 ${fileName} 的商品頁`).toContain(item.sourceUrl!)
    }
  })

  it('每張商品卡都有圖片或 emoji 備援，且無障礙名稱就是商品名', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/community/group-buys', { identity: NEW_USER })
    await flushPromises()

    const cards = wrapper.findAll('.group-buy-product-card')
    expect(cards.length).toBeGreaterThanOrEqual(GROUP_BUY_CATALOG.length)

    for (const card of cards) {
      const art = card.get('.group-buy-product-art')
      const image = art.find('img')
      if (image.exists()) {
        expect(image.attributes('src')).toMatch(/^\/group-buy\//)
        expect(image.attributes('loading')).toBe('lazy')
        // 商品名已經是卡片標題（h3）＋無障礙名稱，圖片重複同一份資訊，因此標記為裝飾性
        expect(image.attributes('alt')).toBe('')
        expect(image.attributes('aria-hidden')).toBe('true')
      } else {
        // 記錄在案的備援：emoji，且對輔助科技隱藏
        expect(art.get('span').attributes('aria-hidden')).toBe('true')
        expect(art.text().trim().length).toBeGreaterThan(0)
      }

      const labelledBy = card.attributes('aria-labelledby')
      expect(labelledBy).toBeTruthy()
      const heading = card.get(`#${labelledBy}`)
      expect(heading.element.tagName).toBe('H3')
      expect(heading.text().trim().length).toBeGreaterThan(0)
      expect(card.text()).toContain(heading.text())
    }
  })
})
