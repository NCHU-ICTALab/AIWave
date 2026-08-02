// @vitest-environment happy-dom

/**
 * 回歸守門:AI 頁(/user/assistant)左側 session 列表必須「限高內捲」,
 * 不能隨著對話變多長成一條。
 *
 * 這裡分兩層驗:
 * 1. DOM——不管幾筆對話,所有項目都待在同一個捲動區 `.session-history-list` 裡,
 *    面板的標題列/動作列仍在,沒有被搬走或吃掉。
 * 2. CSS 契約——SFC 的 scoped style 讀進來直接斷言。happy-dom 不會套用
 *    `<style scoped>`,量 getComputedStyle 只會拿到空值,所以改為對樣式來源做
 *    宣告式檢查(和 accessibilityBaseline.spec.ts 讀 main.css 是同一招)。
 *    重點是「限高 + 自己捲」而不是「限高 + overflow:hidden 裁掉」——後者會讓
 *    「＋ 新對話」「封存對話」被切掉卻仍可被 Tab 聚焦(WCAG 2.4.11 失敗)。
 */

import { flushPromises } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import { stubCatalogFetch } from './fixtures/catalogClient'
import { mountApp } from './fixtures/mountApp'

const SESSION_COUNT = 24

/** 取 SFC 的 scoped style,並拿掉註解(註解裡也會提到 overflow: hidden)。 */
function scopedStyle(file: string): string {
  const source = readFileSync(resolve(process.cwd(), file), 'utf8')
  const match = source.match(/<style scoped>([\s\S]*?)<\/style>/)
  if (!match) throw new Error(`${file} 沒有 <style scoped>`)
  return match[1]!.replace(/\/\*[\s\S]*?\*\//g, '')
}

/** 取出某個選擇器的宣告區塊(scoped style 內沒有巢狀規則,單層 `}` 即可)。 */
function ruleBlock(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(new RegExp(`^[ \\t]*${escaped}\\s*\\{([^}]*)\\}`, 'm'))
  if (!match) throw new Error(`找不到 CSS 規則:${selector}`)
  return match[1]!
}

/** 取出 max-width 媒體查詢的內容。 */
function mediaBlock(css: string, maxWidth: string): string {
  const start = css.indexOf(`@media (max-width: ${maxWidth})`)
  if (start < 0) throw new Error(`找不到斷點:${maxWidth}`)
  let depth = 0
  for (let index = css.indexOf('{', start); index < css.length; index += 1) {
    if (css[index] === '{') depth += 1
    if (css[index] === '}') {
      depth -= 1
      if (depth === 0) return css.slice(start, index)
    }
  }
  throw new Error(`斷點 ${maxWidth} 沒有收尾`)
}

/** 讓 GET /agent/sessions 回一長串對話;其他路由照舊交給 platformStub。 */
function stubManySessions(count: number) {
  stubCatalogFetch((url, init) => {
    if (!url.includes('/api/v1/platform/agent/sessions')) return undefined
    if ((init?.method ?? 'GET') !== 'GET') return undefined
    if (/\/agent\/sessions\/[^?]/.test(url)) return undefined
    const data = Array.from({ length: count }, (_, index) => ({
      id: `agent-${index + 1}`,
      title: `對話 ${index + 1}`,
      status: 'active',
      summary: '',
      pendingGrantId: null,
      archivedAt: null,
      version: 1,
      createdAt: '2026-07-30T10:00:00+08:00',
      updatedAt: '2026-07-30T10:00:00+08:00',
    }))
    return new Response(JSON.stringify({ data }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}

describe('AI 頁 session 列表版面', () => {
  it('把再多的對話都收在同一個捲動清單裡,面板本身不跟著長高', async () => {
    stubManySessions(SESSION_COUNT)
    const { wrapper } = await mountApp('/user/assistant')
    await flushPromises()

    const panel = wrapper.get('[data-testid="agent-session-history"]')
    const list = panel.get('.session-history-list')
    expect(list.findAll('.session-history-item')).toHaveLength(SESSION_COUNT)

    // 每一筆都在捲動區內,而不是直接掛在面板上(否則面板高度會被項目撐開)
    expect(panel.findAll('.session-history-item')).toHaveLength(SESSION_COUNT)
    const directItems = Array.from(panel.element.children)
      .filter((child) => child.classList.contains('session-history-item'))
    expect(directItems).toHaveLength(0)

    // 固定區塊(新對話/重新命名)仍在面板上,沒有被移進捲動區裡跟著捲走
    expect(panel.get('[data-testid="new-agent-session"]').element.closest('.session-history-list')).toBeNull()
    expect(panel.get('[data-testid="rename-agent-session"]').element.closest('.session-history-list')).toBeNull()

    // 清單是原生 button 的清單:role="listitem" 掛在外層 div,按鈕仍是按鈕
    const first = list.get('.session-history-item')
    expect(first.attributes('role')).toBeUndefined()
    expect(first.element.parentElement?.getAttribute('role')).toBe('listitem')
    expect(list.attributes('role')).toBe('list')
    expect(list.attributes('aria-label')).toBe('對話歷史')
  })

  it('元件樣式:清單限高且自行捲動,面板不用 overflow:hidden 裁切', () => {
    const css = scopedStyle('src/components/AgentSessionHistory.vue')

    const listRule = ruleBlock(css, '.session-history-list')
    expect(listRule).toMatch(/overflow-y:\s*auto/)
    expect(listRule).toMatch(/overscroll-behavior:\s*contain/)
    expect(listRule).toMatch(/max-height:\s*\d/) // 有明確上限,不是 none
    expect(listRule).toMatch(/min-height:\s*[\d.]/) // 被壓縮時仍留得下一筆

    const archivedRule = ruleBlock(css, '.session-history-list.archived')
    expect(archivedRule).toMatch(/max-height:\s*\d/)

    // 面板本身是可壓縮的 flex 欄,而不是靠裁切假裝有限高
    const panelRule = ruleBlock(css, '.agent-session-history')
    expect(panelRule).toMatch(/flex-direction:\s*column/)
    expect(panelRule).toMatch(/min-height:\s*0/)
    expect(panelRule).not.toMatch(/overflow:\s*hidden/)
  })

  it('AI 頁樣式:左欄用剩餘高度撐滿,手機斷點改回限高,任何一層都不裁切', () => {
    const css = scopedStyle('src/views/AssistantView.vue')
    // 整份 scoped style 都不該出現把面板裁掉的寫法
    expect(css).not.toMatch(/overflow:\s*hidden/)

    const columnRule = ruleBlock(css, '.assistant-session-column')
    expect(columnRule).toMatch(/flex-direction:\s*column/)
    // 極矮視窗的保險:整欄可捲,不會有按鈕被藏在看不見的地方
    expect(columnRule).toMatch(/overflow-y:\s*auto/)

    const panelRule = ruleBlock(css, '.assistant-session-column :deep(.agent-session-history)')
    expect(panelRule).toMatch(/flex:\s*1 1 auto/)
    expect(panelRule).toMatch(/min-height:\s*0/)

    // 手機單欄時列高不確定,必須改回自身限高,否則又會長成一條
    const mobile = mediaBlock(css, '760px')
    expect(ruleBlock(mobile, '.assistant-session-column :deep(.session-history-list)')).toMatch(/max-height:\s*\d/)
    expect(mobile).not.toMatch(/overflow:\s*hidden/)

    // 能力總覽展開後也要限高內捲,不能把下方對話擠掉
    const capabilityRule = ruleBlock(css, '.assistant-capability-grid')
    expect(capabilityRule).toMatch(/max-height:/)
    expect(capabilityRule).toMatch(/overflow-y:\s*auto/)
  })

  it('能力總覽的標題層級不跳級:h1 → summary 的 h2 → 卡片的 h3', async () => {
    stubCatalogFetch()
    const { wrapper } = await mountApp('/user/assistant')

    expect(wrapper.findAll('h1')).toHaveLength(1)
    const wiki = wrapper.get('[data-testid="assistant-capability-wiki"]')
    expect(wiki.get('summary h2').text()).toBe('我目前能幫你處理什麼？')
    expect(wiki.findAll('.assistant-capability-card h3').length).toBeGreaterThan(0)
    expect(wiki.findAll('.assistant-capability-card h2')).toHaveLength(0)
    // 預設收合,不佔掉對話空間
    expect(wiki.attributes('open')).toBeUndefined()
  })
})
