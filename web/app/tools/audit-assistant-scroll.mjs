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

  await context.close()
}

await browser.close()

if (failures.length) {
  console.error(failures.join('\n'))
  process.exitCode = 1
} else {
  console.log('聊天 composer 保持可見，訊息列可直接用滾輪內捲。')
}
