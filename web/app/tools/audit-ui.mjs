import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = 'http://localhost:5173'
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

    if (consoleErrors.length) problems.push(`[${vp.name}] ${target.name} console error：${consoleErrors[0].slice(0, 100)}`)

    await page.screenshot({ path: `${OUT}/${vp.name}-${target.name}.png`, fullPage: true })
  }
  await context.close()
}
await browser.close()

console.log(problems.length ? problems.join('\n') : '未發現溢出／觸控／console 問題')
