/**
 * Demo 自動駕駛：用 Playwright 以固定節奏走完九幕簡報走查，畫面交給 OBS 錄。
 *
 * 這支腳本只負責「操作」與「節奏」，不負責錄影，也不產生聲音——旁白後製配。
 * 之所以要自動駕駛，是因為手動重錄一次要五分鐘且每次節奏都不一樣；自動化之後
 * 單幕重錄只要幾十秒，而且第 N 次跑出來的畫面和第 1 次一模一樣。
 *
 * 兩條硬限制決定了整支腳本的寫法（改動前請先讀）：
 *
 * 1. `CommunityDemoService` 的狀態是模組內記憶體（`web/app/src/services/communityDemoService.ts`），
 *    **整頁重載就會洗回 seed**。所以開場之後一律走 SPA 內部導覽，全程只有一次 `goto`。
 * 2. `DemoRoleSwitcher` 只在 `/demo/*` 路徑渲染。所以主線必須待在 `/demo/*`，
 *    換角色只能用畫面右上的切換器，不能改 localStorage 再重載（那會連帶觸發第 1 點）。
 *
 * 用法（在 web/app 下）：
 *
 *   node tools/demo-drive.mjs --list          列出九幕
 *   node tools/demo-drive.mjs                 完整走一次
 *   node tools/demo-drive.mjs --only=6        只錄第 6 幕（前 5 幕會無停頓快轉補狀態）
 *   node tools/demo-drive.mjs --from=5 --to=7 錄第 5～7 幕
 *   node tools/demo-drive.mjs --pace=1.4      整體放慢 40%
 *   node tools/demo-drive.mjs --countdown=5   每個錄製段開始前倒數，給你按 OBS
 *   node tools/demo-drive.mjs --slate         幕與幕之間顯示場記板（彩排用，正式錄請關）
 *   node tools/demo-drive.mjs --video         另外讓 Playwright 存一份 webm 當備援的備援
 *
 * 只需要 Vite dev server（`npm run dev`）。九幕走的是前端 Demo 資料，
 * 不需要後端、不需要 LLM、不需要網路——這正是它適合當斷網備援的原因。
 */
import { chromium } from 'playwright'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const argv = new Map(
  process.argv.slice(2).map((raw) => {
    const [key, value] = raw.replace(/^--/, '').split('=')
    return [key, value ?? 'true']
  }),
)

const BASE = process.env.DEMO_BASE_URL ?? 'http://127.0.0.1:5173'
// 預設節奏是給「有人在旁白」的錄影用的，所以比機器能跑的速度慢得多。
const PACE = Number(argv.get('pace') ?? 2.6)
// 每一幕跑完會補到 `budget` 秒，確保旁白放得下，也讓成品總長 = 預算總和（可預測、好剪）。
// `--nofill` 關掉這個補時，只用於快速驗證腳本跑不跑得通。
const FILL = !argv.has('nofill')
const COUNTDOWN = Number(argv.get('countdown') ?? 0)
const SLATE = argv.has('slate')
const VIDEO = argv.has('video')
const [WIDTH, HEIGHT] = (argv.get('size') ?? '1280x720').split('x').map(Number)

const REPO_TMP = fileURLToPath(new URL('../../../tmp/', import.meta.url))

/** 目前是否在「錄製段」。快轉補狀態時為 false，所有純節奏停頓都會被跳過。 */
let recording = true

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/** 純節奏停頓：只在錄製時生效。等待畫面狀態一律用 locator，不要用這個。 */
const beat = (ms = 700) => (recording ? wait(Math.round(ms * PACE)) : Promise.resolve())

// ── 給鏡頭看的動作 ────────────────────────────────────────────────────────────

/** 捲到定位並停一下。錄影時觀眾需要時間把視線移過去，機器不需要。 */
async function spotlight(page, selector, hold = 900) {
  const target = page.locator(selector).first()
  await target.waitFor({ state: 'visible' })
  await target.scrollIntoViewIfNeeded()
  await beat(320)
  if (recording) await target.hover({ trial: false }).catch(() => {})
  await beat(hold)
}

/** 逐字輸入。一次貼上在畫面上像 bug，逐字打才看得出是「使用者在講話」。 */
async function humanType(page, selector, text) {
  const field = page.locator(selector).first()
  await field.waitFor({ state: 'visible' })
  await field.scrollIntoViewIfNeeded()
  await field.click()
  await beat(220)
  await field.fill('')
  if (recording) {
    await field.pressSequentially(text, { delay: Math.round(55 * PACE) })
  } else {
    await field.fill(text)
  }
  await beat(360)
}

/** 點擊前先 hover 停一下，讓觀眾知道「接下來要按這個」。 */
async function click(page, selector, hold = 520) {
  const target = page.locator(selector).first()
  await target.waitFor({ state: 'visible' })
  await target.scrollIntoViewIfNeeded()
  if (recording) {
    await target.hover().catch(() => {})
    await beat(hold)
  }
  await target.click()
  await beat(420)
}

/** 用畫面右上的切換器換角色；不重載，所以已開的團與跟團紀錄都留著。 */
async function switchRole(page, role) {
  const switcher = page.locator('[data-testid="demo-role-switcher"]')
  await switcher.waitFor({ state: 'visible' })
  await switcher.scrollIntoViewIfNeeded()
  await beat(420)
  await switcher.selectOption(role)
  await page.waitForURL(role === 'manager' ? '**/demo/committee' : '**/demo/resident')
  await beat(700)
}

/** 場記板：彩排時用來對時間，正式錄影不要開。 */
async function slate(page, index, title) {
  if (!SLATE || !recording) return
  await page.evaluate(([n, text]) => {
    const node = document.createElement('div')
    node.textContent = `第 ${n} 幕・${text}`
    node.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:99999', 'display:grid', 'place-items:center',
      'background:rgba(17,17,17,.92)', 'color:#fff', 'font-size:44px', 'font-weight:800',
      'letter-spacing:.06em', 'font-family:system-ui,sans-serif',
    ].join(';')
    node.dataset.slate = 'true'
    document.body.append(node)
  }, [index, title])
  await wait(1100)
  await page.evaluate(() => document.querySelector('[data-slate]')?.remove())
}

// ── 九幕 ─────────────────────────────────────────────────────────────────────
//
// `budget` 是給後製配音抓長度用的秒數預算，不是硬性 timeout。
// 每一幕都必須能在「前面幾幕剛跑完」的狀態下接著跑——單幕重錄靠的就是這個性質。

const SCENES = [
  {
    title: '登入與社區首頁',
    budget: 22,
    narration: '王小明打開社區入口：兩件待領包裹、電梯保養公告、報修進度、進行中的團購，全部在同一頁。',
    async act(page) {
      await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
      await spotlight(page, '[data-testid="community-demo-entry"]', 1200)
      await click(page, '[data-testid="enter-community-demo-resident"]')
      await page.waitForURL('**/demo/resident')
      await spotlight(page, '[data-testid="resident-package-kpi"]', 800)
      await spotlight(page, '[data-testid="resident-group-buy-kpi"]', 800)
      await spotlight(page, '[data-testid="resident-announcements"]', 1100)
    },
  },
  {
    title: '問社區・垃圾車幾點來',
    budget: 24,
    narration: '用平常說話的方式問社區規約。答案標出來源，而且這一段不呼叫外部 LLM——是社區自己的 Demo Wiki。',
    async act(page) {
      await spotlight(page, '[data-testid="ask-community-panel"]', 700)
      await humanType(page, '[data-testid="community-query"]', '垃圾車幾點來')
      await click(page, '[data-testid="ask-community"]')
      await page.locator('[data-testid="community-answer"]').first().waitFor({ state: 'visible' })
      await spotlight(page, '[data-testid="community-answer"]', 1800)
    },
  },
  {
    title: '問社區・假日可以裝修嗎',
    budget: 20,
    narration: '換一個更難的問題：平日、週六、週日與國定假日是三組不同規則，答案要能分開講清楚。',
    async act(page) {
      await click(page, '[data-testid="quick-renovation"]')
      await page.locator('[data-testid="community-answer"]').first().waitFor({ state: 'visible' })
      await spotlight(page, '[data-testid="community-answer"]', 1900)
    },
  },
  {
    title: '社區優惠與訂閱回饋',
    budget: 18,
    narration: '冷氣清洗市價 NT$3,800、社區價 NT$3,500。點問號會直接說明這個價差來自管委會的訂閱回饋。',
    async act(page) {
      await spotlight(page, '[data-testid="community-service-offer"]', 1100)
      await click(page, '[data-testid="offer-price-question"]')
      await spotlight(page, '[data-testid="offer-price-explanation"]', 1700)
    },
  },
  {
    title: '主委發布團購',
    budget: 24,
    narration: '切換到主委陳建華。商品條件可以逐欄修改，確認後發布；發布後住戶端讀到的是同一份資料。',
    async act(page) {
      await switchRole(page, 'manager')
      await spotlight(page, '[data-testid="committee-open-kpi"]', 700)
      await spotlight(page, '[data-testid="group-buy-editor"]', 1300)
      await click(page, '[data-testid="publish-dubai-group-buy"]')
      await page.locator('[data-testid="publish-feedback"]').first().waitFor({ state: 'visible' })
      await spotlight(page, '[data-testid="publish-feedback"]', 1200)
    },
  },
  {
    title: '住戶跟團',
    budget: 48,
    narration: '切回住戶。杜拜巧克力已經出現在社區首頁，選六入、按我要 +1，進度從 7/10 變成 8/10。',
    async act(page) {
      await switchRole(page, 'user')
      const card = page.locator('[data-testid^="group-buy-card-"]').filter({ hasText: '巧克力' }).first()
      await card.waitFor({ state: 'visible' })
      await card.scrollIntoViewIfNeeded()
      await beat(800)
      await card.locator('a').first().click()
      await page.waitForURL('**/group-buy/**')
      await spotlight(page, '[data-testid="group-progress"]', 1200)

      // 規格是 radio input，文字在外層 label 上；點 label 才是真人的操作，
      // 也避開 input 被自訂樣式藏起來時點不到的問題。
      const variant = page.locator('label.demo-variant-option').filter({ hasText: '六入' }).first()
      await variant.waitFor({ state: 'visible' })
      if (recording) { await variant.hover().catch(() => {}); await beat(520) }
      await variant.click()
      await beat(520)

      await click(page, '[data-testid="join-group-buy"]')
      await page.locator('[data-testid="my-group-order"]').first().waitFor({ state: 'visible' })
      await spotlight(page, '[data-testid="my-group-order"]', 1400)
      await spotlight(page, '[data-testid="group-progress"]', 1400)
    },
  },
  {
    title: '主委看訂單彙總',
    budget: 24,
    narration: '同一份資料的另一個視角：住戶剛送出的六入 × 1、NT$780，立刻出現在主委的彙總與成交額 KPI。',
    async act(page) {
      await switchRole(page, 'manager')
      await spotlight(page, '[data-testid="committee-household-order"]', 1600)
      await spotlight(page, '[data-testid="chocolate-revenue"]', 1400)
      await spotlight(page, '[data-testid="committee-revenue-kpi"]', 1200)
    },
  },
  {
    title: 'Wiki 管理與未回答問題',
    budget: 18,
    narration: '住戶問過但答不出來的問題會累積成待補充清單——這是社區知識庫會自己長大的地方。',
    async act(page) {
      await spotlight(page, '[data-testid="wiki-management-summary"]', 1600)
      const mark = page.locator('[data-testid^="mark-wiki-"]').first()
      if (await mark.count()) {
        await mark.scrollIntoViewIfNeeded()
        if (recording) { await mark.hover().catch(() => {}); await beat(520) }
        await mark.click()
        await beat(1100)
      }
    },
  },
  {
    title: '訂閱與帳務',
    budget: 28,
    narration: '最後用一張帳務卡收尾：28 戶落在 1–30 戶級距、月費 NT$999、導入期免費試用、本月住戶省下多少、社區淨效益多少。',
    async act(page) {
      await click(page, '[data-testid="subscription-cta"] a')
      await page.waitForURL('**/demo/subscription')
      await spotlight(page, '[data-testid="subscription-pricing"]', 2000)
      await spotlight(page, '[data-testid="commission-rules"]', 1800)
    },
  },
]

// ── 執行 ─────────────────────────────────────────────────────────────────────

if (argv.has('list')) {
  const total = SCENES.reduce((sum, scene) => sum + scene.budget, 0)
  console.log(`九幕走查・預算合計 ${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}\n`)
  SCENES.forEach((scene, index) => {
    console.log(`  ${index + 1}. ${scene.title}（約 ${scene.budget}s）`)
    console.log(`     ${scene.narration}`)
  })
  process.exit(0)
}

const only = argv.has('only') ? Number(argv.get('only')) : null
const from = only ?? Number(argv.get('from') ?? 1)
const to = only ?? Number(argv.get('to') ?? SCENES.length)

if (from < 1 || to > SCENES.length || from > to) {
  console.error(`幕次超出範圍：可用 1–${SCENES.length}`)
  process.exit(1)
}

const contextOptions = {
  viewport: { width: WIDTH, height: HEIGHT },
  locale: 'zh-TW',
  timezoneId: 'Asia/Taipei',
  reducedMotion: 'no-preference',
}
if (VIDEO) {
  mkdirSync(`${REPO_TMP}demo-video`, { recursive: true })
  contextOptions.recordVideo = { dir: `${REPO_TMP}demo-video`, size: { width: WIDTH, height: HEIGHT } }
}

const browser = await chromium.launch({
  headless: false,
  // 移掉「Chrome 正受自動測試軟體控制」的黃色橫幅——它會出現在錄影畫面裡。
  ignoreDefaultArgs: ['--enable-automation'],
  args: [
    `--window-size=${WIDTH},${HEIGHT + 92}`,
    '--window-position=0,0',
    '--no-first-run',
    '--no-default-browser-check',
    '--hide-crash-restore-bubble',
  ],
})
const context = await browser.newContext(contextOptions)
const page = await context.newPage()

const failures = []
page.on('pageerror', (error) => failures.push(`page error: ${String(error).slice(0, 200)}`))
page.on('response', (response) => {
  if (response.status() >= 400 && !response.url().endsWith('/favicon.svg')) {
    failures.push(`${response.status()} ${response.url()}`)
  }
})

const cues = []

// 快轉補狀態：第 6 幕要有東西可跟團，前面五幕就必須真的發生過。
if (from > 1) {
  recording = false
  console.log(`\n快轉補狀態：第 1–${from - 1} 幕（不錄）`)
  for (let index = 0; index < from - 1; index += 1) {
    process.stdout.write(`  · ${SCENES[index].title}\n`)
    await SCENES[index].act(page)
  }
  recording = true
} else {
  // 從第一幕開始時，第一幕自己會 goto，不需要額外準備。
}

console.log(`\n準備錄製第 ${from}–${to} 幕。視窗 ${WIDTH}×${HEIGHT}，OBS 請用「視窗擷取」選 Chromium。`)

const runStartedAt = Date.now()
for (let index = from - 1; index < to; index += 1) {
  const scene = SCENES[index]

  if (COUNTDOWN > 0) {
    for (let n = COUNTDOWN; n > 0; n -= 1) {
      process.stdout.write(`\r  第 ${index + 1} 幕開始倒數 ${n}… `)
      await wait(1000)
    }
    process.stdout.write('\r' + ' '.repeat(40) + '\r')
  }

  await slate(page, index + 1, scene.title)

  const startedAt = Date.now()
  console.log(`  ▶ 第 ${index + 1} 幕　${scene.title}`)
  await scene.act(page)

  // 補到預算。動作本身通常比旁白短，不補的話配音會追不上畫面。
  if (recording && FILL) {
    const remaining = scene.budget * 1000 - (Date.now() - startedAt)
    if (remaining > 0) await wait(remaining)
  }
  const elapsed = (Date.now() - startedAt) / 1000

  cues.push({
    index: index + 1,
    title: scene.title,
    offset: (startedAt - runStartedAt) / 1000,
    elapsed,
    budget: scene.budget,
    narration: scene.narration,
  })
  const drift = elapsed - scene.budget
  console.log(`    完成 ${elapsed.toFixed(1)}s（預算 ${scene.budget}s，${drift >= 0 ? '+' : ''}${drift.toFixed(1)}s）`)
}

await beat(1500)

const totalElapsed = (Date.now() - runStartedAt) / 1000
const stamp = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

mkdirSync(REPO_TMP, { recursive: true })
const cueSheet = [
  '# Demo 錄影分軌表（自動產生）',
  '',
  `本次錄製第 ${from}–${to} 幕，實際總長 ${stamp(totalElapsed)}。`,
  '時間軸以本次錄製起點為 0，配音時直接對這張表。',
  '',
  '| 幕 | 進入時間 | 實長 | 預算 | 旁白 |',
  '| --- | --- | --- | --- | --- |',
  ...cues.map((cue) => `| ${cue.index}. ${cue.title} | ${stamp(cue.offset)} | ${cue.elapsed.toFixed(1)}s | ${cue.budget}s | ${cue.narration} |`),
  '',
].join('\n')
writeFileSync(`${REPO_TMP}demo-cues.md`, cueSheet, 'utf8')

console.log(`\n總長 ${stamp(totalElapsed)}　分軌表：tmp/demo-cues.md`)

// 補時只能把幕拉長、不能縮短。動作比預算久的話「總長 = 預算總和」就不成立，
// 分軌表的進入時間也會跟著飄——所以要講出來，而不是讓它安靜地不準。
const overruns = cues.filter((cue) => cue.elapsed > cue.budget + 0.5)
if (overruns.length) {
  console.warn('\n下列幕的動作比預算久，長度由動作決定（把 budget 調到不小於實長即可消除）：')
  for (const cue of overruns) {
    console.warn(`  · 第 ${cue.index} 幕 ${cue.title}：實長 ${cue.elapsed.toFixed(1)}s > 預算 ${cue.budget}s`)
  }
}
if (failures.length) {
  console.error('\n錄製期間偵測到錯誤（畫面可能有破綻，建議重錄）：')
  for (const failure of [...new Set(failures)].slice(0, 10)) console.error(`  · ${failure}`)
  process.exitCode = 1
}

await context.close()
await browser.close()
if (VIDEO) console.log('Playwright 備份影片：tmp/demo-video/')
