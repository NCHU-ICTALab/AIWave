import { chromium } from 'playwright'

const baseUrl = process.env.ASSISTANT_AUDIT_BASE_URL ?? 'http://127.0.0.1:5173'
const viewports = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'desktop', width: 1440, height: 900 },
]

const browser = await chromium.launch()
const failures = []

for (const viewport of viewports) {
  const context = await browser.newContext({ viewport })
  await context.addInitScript(() => {
    localStorage.setItem('life-ai.identity', JSON.stringify({
      role: 'user',
      accountId: 'scroll-audit-user',
      displayName: '版面測試住戶',
    }))
  })
  const page = await context.newPage()
  let chatStartRequests = 0
  page.on('request', (request) => {
    if (request.url().endsWith('/api/chat/start')) chatStartRequests += 1
  })
  await page.route('**/api/chat/start', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      session_id: 'scroll-audit-session',
      service_name: '居家清潔',
      reply: '請問需要清潔哪個空間？',
      question: { id: 'space', topicId: 1, label: '清潔空間', required: true, options: [{ label: '整屋', value: 'all' }] },
      done: false,
      progress: { answered: 0, total: 4 },
      trace: [],
    }),
  }))
  await page.route('**/api/v1/insights/*/summary', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ data: {
      accountId: 'scroll-audit-user', totalOrders: 1, completedOrders: 1, openOrders: 0,
      cancelledOrders: 0, distinctServices: 1, totalSpend: 1200, earnedPoints: 12,
      firstActivity: '2026-07-01', lastActivity: '2026-07-20', source: 'audit',
      services: [{ serviceId: 'service-cleaning', serviceName: '居家清潔', count: 1, lastUsedOn: '2026-07-20', daysSinceLast: 7, totalAmount: 1200 }],
    } }),
  }))
  await page.route('**/api/v1/insights/*/recommendations?*', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ data: [] }),
  }))
  await page.route('**/api/v1/today/*', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ data: [{
      id: 'audit-suggestion', kind: 'suggestion', title: '安排居家清潔', detail: '距離上次清潔已有一週。',
      actionLabel: '安排服務', actionRoute: '/user/services/cleaning', source: 'audit', score: 10,
      evidence: [{ serviceName: '居家清潔', occurredOn: '2026-07-20' }], computedBy: 'rules',
    }] }),
  }))

  await page.goto(`${baseUrl}/user/assistant?service=service-cleaning`, { waitUntil: 'networkidle' })
  await page.locator('[data-testid="assistant-workspace"]').waitFor()
  await page.locator('.message-list').evaluate((list) => {
    for (let index = 0; index < 28; index += 1) {
      const message = document.createElement('div')
      message.className = `message ${index % 2 ? 'from-user' : 'from-assistant'}`
      message.innerHTML = `<span>${index % 2 ? '你' : '生活管家'}</span><p>這是用來驗證長對話捲動行為的第 ${index + 1} 則訊息，內容刻意保留一定長度。</p>`
      list.append(message)
    }
  })

  const before = await page.evaluate(() => {
    const list = document.querySelector('.message-list')
    const composer = document.querySelector('[data-testid="assistant-composer"]')
    const composerRect = composer.getBoundingClientRect()
    return {
      viewportHeight: innerHeight,
      composerTop: composerRect.top,
      composerBottom: composerRect.bottom,
      listClientHeight: list.clientHeight,
      listScrollHeight: list.scrollHeight,
      documentScrollHeight: document.documentElement.scrollHeight,
    }
  })

  if (before.composerBottom > before.viewportHeight + 1) {
    failures.push(`${viewport.name}: composer 在 viewport 下方 (${Math.round(before.composerBottom)} > ${before.viewportHeight})`)
  }
  if (before.listScrollHeight <= before.listClientHeight) {
    failures.push(`${viewport.name}: 訊息列沒有形成內部 overflow (${before.listScrollHeight} <= ${before.listClientHeight})`)
  }

  const list = page.locator('.message-list')
  await list.evaluate((element) => { element.scrollTop = 0 })
  await list.hover()
  await page.mouse.wheel(0, 420)
  await page.waitForTimeout(100)
  const afterWheel = await list.evaluate((element) => element.scrollTop)
  if (afterWheel <= 0) failures.push(`${viewport.name}: 滑鼠停在訊息區時 wheel 沒有捲動訊息列`)

  const startCountBeforeLanding = chatStartRequests
  await page.goto(`${baseUrl}/user/assistant`, { waitUntil: 'networkidle' })
  const landingTitle = await page.locator('main h1').textContent()
  if (landingTitle?.trim() !== '今天想處理什麼？') {
    failures.push(`${viewport.name}: 通用生活管家標題錯誤（${landingTitle?.trim() || '空白'}）`)
  }
  if (chatStartRequests !== startCountBeforeLanding) {
    failures.push(`${viewport.name}: 通用生活管家仍呼叫特定服務 chat/start`)
  }

  await page.goto(`${baseUrl}/user`, { waitUntil: 'networkidle' })
  const homeSpacing = await page.evaluate(() => {
    const briefing = document.querySelector('[data-home-section="recommendations"]')
    if (!briefing) throw new Error('找不到首頁推薦區塊')
    const source = briefing.querySelector('.source-note')
    const lastItem = briefing.querySelector('.briefing-item:last-child')
    if (!source || !lastItem) throw new Error('首頁推薦區塊缺少來源或建議卡')
    const nextPanel = briefing.nextElementSibling?.querySelector('.panel') ?? briefing.nextElementSibling
    if (!nextPanel) throw new Error('首頁推薦區塊後缺少下一個功能區')
    return {
      sourceGap: source.getBoundingClientRect().top - lastItem.getBoundingClientRect().bottom,
      panelGap: nextPanel.getBoundingClientRect().top - briefing.getBoundingClientRect().bottom,
    }
  })
  if (homeSpacing.sourceGap < 12) failures.push(`${viewport.name}: 來源文字與建議卡間距過小（${Math.round(homeSpacing.sourceGap)}px）`)
  if (homeSpacing.panelGap < 16) failures.push(`${viewport.name}: 首頁兩個大面板間距過小（${Math.round(homeSpacing.panelGap)}px）`)

  await context.close()
}

await browser.close()

if (failures.length) {
  console.error(failures.join('\n'))
  process.exitCode = 1
} else {
  console.log('聊天滾動、通用生活管家入口與首頁區塊間距皆通過。')
}
