import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = process.env.UI_AUDIT_BASE_URL ?? 'http://localhost:5173'
const OUT = 'tmp/shots'
mkdirSync(OUT, { recursive: true })

const VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'desktop', width: 1440, height: 900 },
]

// 依身分登入後才看得到的頁面
const IDENTITIES = {
  resident: { role: 'user', accountId: '019a52d3-7f6b-7da3-b48d-9c9e2522d616', displayName: '小圓' },
  manager: { role: 'manager', accountId: null, displayName: '社區管理者' },
  partner: { role: 'partner', accountId: null, displayName: '合作廠商' },
}

const PAGES = [
  { name: '01-login', path: '/login', identity: null },
  { name: '02-home', path: '/user', identity: 'resident' },
  { name: '03-assistant', path: '/user/assistant?service=service-repair', identity: 'resident' },
  // 規劃模式：走真的 LLM，所以這兩頁也順帶驗證規劃器在瀏覽器裡真的跑得通
  { name: '03b-plan-match', path: `/user/assistant?need=${encodeURIComponent('浴室水管漏水，很急，台北市大同區，預算兩千以內')}`, identity: 'resident' },
  { name: '03c-plan-multi', path: `/user/assistant?need=${encodeURIComponent('冷氣不冷想找人洗，順便看看社區這個月有什麼團購')}`, identity: 'resident' },
  { name: '04-services', path: '/user/services/aircon', identity: 'resident' },
  { name: '05-orders', path: '/user/orders', identity: 'resident' },
  { name: '06-community', path: '/user/community', identity: 'resident' },
  { name: '07-manager', path: '/community', identity: 'manager' },
  { name: '08-partner', path: '/partner', identity: 'partner' },
]

const problems = []

const browser = await chromium.launch()
for (const vp of VIEWPORTS) {
  const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()) })

  for (const target of PAGES) {
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
    if (target.identity) {
      await page.evaluate((id) => localStorage.setItem('life-ai.identity', JSON.stringify(id)), IDENTITIES[target.identity])
    } else {
      await page.evaluate(() => localStorage.clear())
    }
    consoleErrors.length = 0
    await page.goto(`${BASE}${target.path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(600)

    // 橫向溢出檢查——這是 RWD 最常見也最明顯的破綻
    const overflow = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      offenders: [...document.querySelectorAll('*')]
        .filter((el) => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
        .slice(0, 5)
        .map((el) => `${el.tagName.toLowerCase()}.${(el.className || '').toString().split(' ')[0]}`),
    }))
    if (overflow.scrollWidth > overflow.clientWidth + 1) {
      problems.push(`[${vp.name}] ${target.name} 橫向溢出 ${overflow.scrollWidth}>${overflow.clientWidth}｜${overflow.offenders.join(', ')}`)
    }

    // 觸控目標過小
    const smallTargets = await page.evaluate(() => [...document.querySelectorAll('button, a, input, select, textarea')]
      // skip-link 等 visually-hidden 元素平時是 1px，聚焦才展開，不列入觸控目標
      .filter((el) => !el.closest('.visually-hidden') && !el.classList.contains('skip-link'))
      .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.height < 44 || r.width < 24) })
      .slice(0, 6)
      .map((el) => { const r = el.getBoundingClientRect(); return `${el.tagName.toLowerCase()}"${(el.textContent || '').trim().slice(0, 12)}" ${Math.round(r.width)}x${Math.round(r.height)}` }))
    if (smallTargets.length) problems.push(`[${vp.name}] ${target.name} 觸控過小：${smallTargets.join(' / ')}`)

    // 文字被擠成窄柱（中文一字一行）。
    // 這類版面錯誤不會造成任何溢出——文字是「擠進去」而不是「撐出去」，
    // 所以溢出檢查一路綠燈，畫面卻幾乎讀不了。實測在 .timeline 上發生過。
    const squeezed = await page.evaluate(() => {
      const results = []
      for (const el of document.querySelectorAll('p, span, strong, li, dd, dt')) {
        const text = (el.textContent || '').trim()
        if (text.length < 6 || el.children.length) continue
        const r = el.getBoundingClientRect()
        if (r.width === 0 || r.height === 0) continue
        const lineHeight = Number.parseFloat(getComputedStyle(el).lineHeight) || 20
        const lines = Math.round(r.height / lineHeight)
        // 行數逼近字元數 ⇒ 每行只放得下一兩個字
        if (lines >= 4 && lines >= text.length * 0.6) {
          results.push(`${el.tagName.toLowerCase()}"${text.slice(0, 10)}" ${Math.round(r.width)}px/${lines}行`)
        }
      }
      return results.slice(0, 5)
    })
    if (squeezed.length) problems.push(`[${vp.name}] ${target.name} 文字被擠成窄柱：${squeezed.join(' / ')}`)

    // 吸頂導覽壓住標題——橫向溢出檢查抓不到這個，但使用者第一眼就會看到被切掉的標題
    const covered = await page.evaluate(() => {
      const bar = [...document.querySelectorAll('body *')]
        .find((el) => ['sticky', 'fixed'].includes(getComputedStyle(el).position) && el.getBoundingClientRect().top <= 0)
      const heading = document.querySelector('main h1')
      if (!bar || !heading) return null
      const barBottom = bar.getBoundingClientRect().bottom
      const top = heading.getBoundingClientRect().top
      return top < barBottom ? { top: Math.round(top), barBottom: Math.round(barBottom) } : null
    })
    if (covered) {
      problems.push(`[${vp.name}] ${target.name} 標題被吸頂導覽蓋住（h1 top ${covered.top} < 導覽底 ${covered.barBottom}）`)
    }

    if (consoleErrors.length) problems.push(`[${vp.name}] ${target.name} console error：${consoleErrors[0].slice(0, 100)}`)

    await page.screenshot({ path: `${OUT}/${vp.name}-${target.name}.png`, fullPage: true })
  }
  await context.close()
}
await browser.close()

console.log(problems.length ? problems.join('\n') : '未發現溢出／觸控／console 問題')
