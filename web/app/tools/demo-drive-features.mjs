/**
 * 功能導覽自動駕駛：以固定節奏走完 13 段功能展示，畫面交給 OBS 錄。
 *
 * 與 `demo-drive.mjs` 的分工：
 *
 * | | `demo-drive.mjs` | 本檔 |
 * | --- | --- | --- |
 * | 走的線 | 只有 `/demo/*` 前端假資料 | `/user`、`/partner`、`/platform` 真後端 ＋ 壓縮版團購 |
 * | 依賴 | 只要 Vite | Vite ＋ API :8000 ＋ partner fake :8020 ＋ LLM |
 * | 用途 | 斷網備援影片（簡報主打團購） | 系統功能導覽影片 |
 *
 * 兩者都保留：簡報用前者，功能影片用本檔。
 *
 * 設計上與 `demo-drive.mjs` 的三個關鍵差異：
 *
 * 1. **每段自帶 `prepare()`，永遠不錄。** 真後端的狀態在 SQLite，重載是安全的，
 *    所以每一段都能獨立起跑——`--only=9` 不必快轉前八段，直接登入＋導到定位就開錄。
 *    這正好對應「分段錄、各自配音」的工作方式。
 * 2. **有看得見的滑鼠。** Playwright 的合成點擊不會移動系統游標，OBS 錄不到，
 *    所以在頁面注入一個視覺游標：移動有補間、點擊有漣漪與按壓。同時也真的
 *    `page.mouse.move()`，讓 `:hover` 樣式照常觸發（否則畫面會少一層回饋）。
 * 3. **主線用真的導覽列點擊**（`.main-nav a[href=...]`），不是 `goto`。
 *    鏡頭上「游標移到導覽 → 點 → 換頁」比網址列瞬移可信得多。
 *
 * 用法（在 web/app 下）：
 *
 *   node tools/demo-drive-features.mjs --list            列出 13 段與長度
 *   node tools/demo-drive-features.mjs --only=4          只錄第 4 段（自動補齊前置狀態）
 *   node tools/demo-drive-features.mjs --from=4 --to=6   錄核心三段（4→5→6 共用同一筆交易）
 *   node tools/demo-drive-features.mjs --countdown=5     每段開錄前倒數，給你按 OBS
 *   node tools/demo-drive-features.mjs --pace=3.2        再放慢（預設 2.6）
 *   node tools/demo-drive-features.mjs --nocursor        關掉視覺游標
 *   node tools/demo-drive-features.mjs --nofill --pace=0.12   只驗證跑不跑得通（不是錄影用）
 *
 * 前置服務：`uv run main.py`（:8000）、`fake_upstreams`（:8020）、`npm run dev`（:5173）。
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
const PACE = Number(argv.get('pace') ?? 2.6)
const FILL = !argv.has('nofill')
const COUNTDOWN = Number(argv.get('countdown') ?? 0)
const SLATE = argv.has('slate')
const VIDEO = argv.has('video')
const CURSOR = !argv.has('nocursor')
const [WIDTH, HEIGHT] = (argv.get('size') ?? '1280x720').split('x').map(Number)

const REPO_TMP = fileURLToPath(new URL('../../../tmp/', import.meta.url))

/** 主角。行為指紋合併出的三個 Demo 家庭之一，27 筆官方訂單。 */
const XIAOYUAN = '019a52d3-7f6b-7da3-b48d-9c9e2522d616'
/** 第 4 段要預約的服務——第 6 段要用同一家廠商的工作台看到這筆。 */
const BOOKING_BRAND = 'DUSKIN'
const PARTNER_TESTID = 'enter-partner-vendor-duskin'

/** 目前是否在「錄製段」。`prepare()` 期間為 false，所有純節奏停頓都會被跳過。 */
let recording = true

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/** 純節奏停頓：只在錄製時生效。等畫面狀態一律用 locator，不要用這個。 */
const beat = (ms = 700) => (recording ? wait(Math.round(ms * PACE)) : Promise.resolve())

// ── 視覺游標 ──────────────────────────────────────────────────────────────────
//
// 用 addInitScript 注入，所以每次導覽後都會自己回來。pointer-events:none 確保
// 它永遠不會擋到真正的點擊；aria-hidden 讓它不進無障礙樹（頁面本身的 WCAG 基線
// 是有測試在守的，錄影工具不該把它弄髒）。

const CURSOR_BOOTSTRAP = () => {
  if (window.__demoCursorInstalled) return
  window.__demoCursorInstalled = true

  const install = () => {
    if (!document.body || document.getElementById('demo-cursor')) return
    const style = document.createElement('style')
    style.textContent = `
      #demo-cursor{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;
        pointer-events:none;will-change:transform;transform:translate3d(-200px,-200px,0)}
      #demo-cursor svg{display:block;transition:transform 90ms ease;
        filter:drop-shadow(0 2px 5px rgba(0,0,0,.45))}
      #demo-cursor.is-press svg{transform:scale(.78)}
      .demo-ripple{position:fixed;z-index:2147483646;pointer-events:none;
        width:36px;height:36px;margin:-18px 0 0 -18px;border-radius:50%;
        border:2px solid rgba(37,99,235,.95);background:rgba(37,99,235,.20);
        animation:demo-ripple-out 640ms cubic-bezier(.22,.61,.36,1) forwards}
      @keyframes demo-ripple-out{from{opacity:.95;transform:scale(.28)}
        to{opacity:0;transform:scale(2)}}
    `
    document.head.append(style)
    const node = document.createElement('div')
    node.id = 'demo-cursor'
    node.setAttribute('aria-hidden', 'true')
    node.innerHTML =
      '<svg width="26" height="26" viewBox="0 0 24 24">' +
      '<path d="M4.2 2.1 L12.3 20.4 L14.6 12.9 L21.6 10.4 Z" ' +
      'fill="#ffffff" stroke="#111827" stroke-width="1.5" stroke-linejoin="round"/></svg>'
    document.body.append(node)
  }

  install()
  document.addEventListener('DOMContentLoaded', install)

  window.__demoCursor = {
    moveTo(x, y, duration) {
      install()
      const node = document.getElementById('demo-cursor')
      if (!node) return
      node.style.transition = `transform ${duration}ms cubic-bezier(.22,.61,.36,1)`
      node.style.transform = `translate3d(${x}px,${y}px,0)`
    },
    press(on) {
      document.getElementById('demo-cursor')?.classList.toggle('is-press', Boolean(on))
    },
    ripple(x, y) {
      install()
      const dot = document.createElement('div')
      dot.className = 'demo-ripple'
      dot.style.left = `${x}px`
      dot.style.top = `${y}px`
      document.body.append(dot)
      setTimeout(() => dot.remove(), 680)
    },
  }
}

// ── 給鏡頭看的動作 ────────────────────────────────────────────────────────────

/**
 * 量出元素中心點。捲動之後一定要重新量——smooth scroll 還在跑的時候量到的是舊座標，
 * 游標就會飄到畫面外。
 */
async function centerOf(page, selector) {
  const target = page.locator(selector).first()
  await target.waitFor({ state: 'visible', timeout: 15000 })
  await target.scrollIntoViewIfNeeded()
  await wait(recording ? 160 : 0)
  const box = await target.boundingBox()
  if (!box) throw new Error(`量不到元素位置：${selector}`)
  return { target, x: box.x + box.width / 2, y: box.y + box.height / 2 }
}

/** 把游標移到目標上並停一下。觀眾需要時間把視線跟過去，機器不需要。 */
async function glide(page, selector, hold = 260) {
  const { target, x, y } = await centerOf(page, selector)
  if (!recording) return target
  const duration = Math.round(360 * PACE)
  if (CURSOR) {
    await page.evaluate(([px, py, d]) => window.__demoCursor?.moveTo(px, py, d), [x, y, duration])
  }
  await page.mouse.move(x, y).catch(() => {})
  await wait(duration)
  await beat(hold)
  return target
}

/** 捲到定位、游標移過去、停著讓觀眾看。 */
async function spotlight(page, selector, hold = 900) {
  await glide(page, selector, hold)
}

/** 點擊：先移過去，按壓＋漣漪，再真的點。 */
async function click(page, selector, hold = 320) {
  const target = await glide(page, selector, hold)
  if (recording) {
    const box = await target.boundingBox()
    if (box && CURSOR) {
      const x = box.x + box.width / 2
      const y = box.y + box.height / 2
      await page.evaluate(([px, py]) => window.__demoCursor?.ripple(px, py), [x, y])
      await page.evaluate(() => window.__demoCursor?.press(true))
    }
    await wait(120)
    if (CURSOR) await page.evaluate(() => window.__demoCursor?.press(false))
  }
  await target.click()
  await beat(420)
  return target
}

/** 逐字輸入。一次貼上在畫面上像 bug，逐字打才看得出是「有人在講話」。 */
async function humanType(page, selector, text) {
  const field = await glide(page, selector, 180)
  await field.click()
  await beat(200)
  await field.fill('')
  if (recording) {
    await field.pressSequentially(text, { delay: Math.round(52 * PACE) })
  } else {
    await field.fill(text)
  }
  await beat(340)
}

/** 元素存在且看得見才做事——用於各頁面的選配區塊，避免種子差異直接讓整段崩掉。 */
async function has(page, selector) {
  const node = page.locator(selector).first()
  if (!(await node.count())) return false
  return node.isVisible().catch(() => false)
}

async function softSpotlight(page, selector, hold = 900) {
  if (await has(page, selector)) await spotlight(page, selector, hold)
}

// ── 導覽與登入 ────────────────────────────────────────────────────────────────

/** 用真的導覽列點過去；沒有那個連結（例如角色不同）才退回 goto。 */
async function goNav(page, path) {
  const link = `.main-nav a[href="${path}"]`
  if (await has(page, link)) {
    await click(page, link)
  } else {
    await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' })
  }
  await page.waitForURL(`**${path}`).catch(() => {})
  await beat(520)
}

/**
 * 登入。`/user` 線的身分存在 localStorage，重載不會掉，所以每段都能自己登入，
 * 這是分段錄製能成立的前提。
 */
async function loginAs(page, kind) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
  await page.locator('[data-testid="account-list"], [data-testid="start-new-user"]')
    .first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => {})

  if (kind === 'member') {
    const option = `[data-account-id="${XIAOYUAN}"]`
    if (await has(page, option)) {
      await click(page, option)
    } else {
      // 帳號清單來自後端；後端沒起來時退回新帳號，讓腳本至少跑得完並在
      // console 留下痕跡（畫面會明顯不同，剪的時候不會誤用）。
      console.warn('  ! 找不到小圓的帳號選項，改用新帳號進入（後端可能沒起來）')
      await click(page, '[data-testid="start-new-user"]')
    }
    await page.waitForURL('**/user**')
  } else if (kind === 'partner') {
    await click(page, `[data-testid="${PARTNER_TESTID}"]`)
    await page.waitForURL('**/partner**')
  } else if (kind === 'platform') {
    await click(page, '[data-testid="enter-admin"]')
    await page.waitForURL('**/platform**')
  } else if (kind === 'community-demo') {
    await click(page, '[data-testid="enter-community-demo-resident"]')
    await page.waitForURL('**/demo/resident')
  }
  await beat(600)
}

/**
 * 把預約精靈走完。第 5、6 段都需要「已經有一筆交易」，所以抽成共用函式：
 * 錄第 4 段時它是主角，錄第 5、6 段時它在 `prepare()` 裡無聲跑完。
 */
async function runBookingWizard(page) {
  // 步驟數依 domain 而定（據點→方案→時段→domain 欄位→試算），所以用迴圈推進，
  // 不寫死步數；出現 submit 就是走到最後一步了。
  for (let guard = 0; guard < 10; guard += 1) {
    if (await has(page, '[data-testid="wizard-submit"]')) break

    if (await has(page, '[data-testid="slot-option"]')) {
      await click(page, '[data-testid="slot-option"]')
    }

    // 未填的必填欄位：選項型取第一個，文字型填一段合理的 Demo 內容。
    const radios = page.locator('[data-testid^="field-"][data-testid*="-"] input[type="radio"]')
    const radioCount = await radios.count().catch(() => 0)
    if (radioCount) {
      const first = radios.first()
      if (await first.isVisible().catch(() => false) && !(await first.isChecked().catch(() => true))) {
        await first.check({ force: true }).catch(() => {})
        await beat(260)
      }
    }

    if (!(await has(page, '[data-testid="wizard-next"]'))) break
    const next = page.locator('[data-testid="wizard-next"]').first()
    if (!(await next.isEnabled().catch(() => false))) break
    await click(page, '[data-testid="wizard-next"]')
  }

  if (await has(page, '[data-testid="wizard-submit"]')) {
    await click(page, '[data-testid="wizard-submit"]')
    await page.locator('[data-testid="booking-done"]')
      .first().waitFor({ state: 'visible', timeout: 30000 }).catch(() => {})
  }
}

/** 從服務探索走到 DUSKIN 的預約精靈。 */
async function openBookingWizard(page) {
  await goNav(page, '/user/services')
  const card = page.locator('[data-testid="provider-card"]').filter({ hasText: BOOKING_BRAND }).first()
  if (await card.count()) {
    await card.scrollIntoViewIfNeeded()
    const book = card.locator('[data-testid="provider-book"]').first()
    if (await book.count()) {
      const box = await book.boundingBox()
      if (box && recording && CURSOR) {
        await page.evaluate(([x, y, d]) => window.__demoCursor?.moveTo(x, y, d),
          [box.x + box.width / 2, box.y + box.height / 2, Math.round(360 * PACE)])
        await wait(Math.round(360 * PACE))
      }
      await book.click()
    } else {
      await card.click()
      await click(page, '[data-testid="provider-book"]')
    }
  } else {
    await click(page, '[data-testid="provider-book"]')
  }
  await page.waitForURL('**/user/booking**').catch(() => {})
  await beat(500)
}

/** 場記板：彩排對時間用，正式錄不要開。 */
async function slate(page, index, title) {
  if (!SLATE || !recording) return
  await page.evaluate(([n, text]) => {
    const node = document.createElement('div')
    node.textContent = `第 ${n} 段・${text}`
    node.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:2147483647', 'display:grid', 'place-items:center',
      'background:rgba(17,17,17,.92)', 'color:#fff', 'font-size:44px', 'font-weight:800',
      'letter-spacing:.06em', 'font-family:system-ui,sans-serif',
    ].join(';')
    node.dataset.slate = 'true'
    document.body.append(node)
  }, [index, title])
  await wait(1100)
  await page.evaluate(() => document.querySelector('[data-slate]')?.remove())
}

// ── 13 段 ────────────────────────────────────────────────────────────────────
//
// `budget` 是給配音抓長度的秒數預算，不是硬 timeout；補時只能拉長不能縮短。
// `prepare` 永遠不錄，負責把狀態帶到這一段的起點——這讓每段都能單獨重錄。

const SEGMENTS = [
  {
    title: '登入與四種角色入口',
    budget: 20,
    narration: '一個平台、四種角色：住戶、管委會、合作廠商、平台營運，各自有獨立入口與各自看得到的資料。我們用住戶小圓進入。',
    async prepare(page) {
      await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
    },
    async act(page) {
      await spotlight(page, '[data-testid="account-list"]', 1200)
      await softSpotlight(page, '[data-testid="partner-list"]', 1100)
      await click(page, `[data-account-id="${XIAOYUAN}"]`)
      await page.waitForURL('**/user**')
      await beat(900)
    },
  },
  {
    title: '今日摘要：由官方訂單算出來的',
    budget: 25,
    narration: '首頁不是靜態儀表板。待辦排序的依據是「誰在等誰」，卡在使用者身上的排最前面；每一筆都能點開看到它是從哪筆官方訂單算出來的。',
    async prepare(page) {
      await loginAs(page, 'member')
    },
    async act(page) {
      await spotlight(page, '[data-testid="metric-open"]', 700)
      await softSpotlight(page, '[data-testid="metric-points"]', 700)
      await softSpotlight(page, '[data-testid="metric-spend"]', 700)
      await spotlight(page, '[data-testid="briefing-item"]', 1200)
      await softSpotlight(page, '[data-testid^="briefing-evidence-"]', 1600)
    },
  },
  {
    title: '服務探索：真實品牌的目錄投影',
    budget: 25,
    narration: '六大生活場景、統一集團的真實品牌。目錄是平台自己的投影表，所以廠商系統臨時掛掉也還查得到；但真的要下單時，仍然會回到廠商端現場驗證。',
    async prepare(page) {
      await loginAs(page, 'member')
    },
    async act(page) {
      await goNav(page, '/user/services')
      await spotlight(page, '[data-testid="scene-group"]', 1100)
      await spotlight(page, '[data-testid="provider-card"]', 1200)
      await softSpotlight(page, '[data-testid="listing-note"]', 1500)
    },
  },
  {
    title: '預約精靈：一條完整的交易閉環',
    budget: 60,
    narration: '據點、方案、真實可預約時段、這個服務類型才需要的欄位、試算與點數折抵，最後送單付款。價格一律由目錄決定，前端送什麼上來都不算數。',
    async prepare(page) {
      await loginAs(page, 'member')
    },
    async act(page) {
      await openBookingWizard(page)
      await spotlight(page, '[data-testid="step-title"]', 700)
      await runBookingWizard(page)
      await softSpotlight(page, '[data-testid="quote-summary"]', 1400)
      await softSpotlight(page, '[data-testid="booking-done"]', 1600)
      await softSpotlight(page, '[data-testid="order-id"]', 1400)
    },
  },
  {
    title: '訂單狀態、取消與退款',
    budget: 40,
    narration: '狀態名稱依服務類型而不同——訂位講「店家確認」、宅配講「理貨」。時間軸是真的事件序，取消會連帶全額退款、點數沖銷、行事曆一起取消。',
    async prepare(page) {
      await loginAs(page, 'member')
      await openBookingWizard(page)
      await runBookingWizard(page)
      await goNav(page, '/user/orders')
    },
    async act(page) {
      await spotlight(page, '[data-testid="m4-order-section"]', 900)
      await click(page, '[data-testid="m4-order-row"]')
      await beat(700)
      await softSpotlight(page, '[data-testid="detail-status"]', 1100)
      await spotlight(page, '[data-testid="detail-timeline"]', 1800)
      await softSpotlight(page, '[data-testid="open-reschedule"]', 1200)
    },
  },
  {
    title: '廠商工作台：同一份資料的另一個視角',
    budget: 30,
    narration: '切到 DUSKIN 的廠商工作台。剛剛那筆預約直接出現在這裡——不是兩套系統對帳，是同一份資料的兩個視角。不合法的狀態轉移，按鈕根本不會出現。',
    async prepare(page) {
      await loginAs(page, 'member')
      await openBookingWizard(page)
      await runBookingWizard(page)
      await loginAs(page, 'partner')
    },
    async act(page) {
      await softSpotlight(page, '[data-testid="availability-form"]', 900)
      await spotlight(page, '[data-testid^="booking-details-"]', 1600)
      await softSpotlight(page, '[data-testid^="booking-transition-"]', 1500)
    },
  },
  {
    title: '對話 Agent：理解、拆解、查真目錄',
    budget: 60,
    narration: '用平常講話的方式說一句需求。模型負責理解與拆解，服務存不存在、日期、時段、價格、授權，全部由確定性的平台決定——所以提案的理由永遠可以驗證。',
    async prepare(page) {
      await loginAs(page, 'member')
      await goNav(page, '/user/assistant')
    },
    async act(page) {
      // 用「明天」而不是「這週六」：時段種子只生到近幾天，講太遠的日期畫面會
      // 出現「查無服務」。這是資料邊界，不是模型答不出來。
      await humanType(page, '[data-testid="assistant-composer"] textarea, [data-testid="assistant-composer"] input', '幫我約明天下午洗冷氣')
      await page.keyboard.press('Enter')
      await page.locator('[data-testid="agent-result"], [data-testid="proposal-card"]')
        .first().waitFor({ state: 'visible', timeout: 45000 }).catch(() => {})
      await softSpotlight(page, '[data-testid="agent-stages"]', 1400)
      await softSpotlight(page, '[data-testid="proposal-card"]', 1800)
      await softSpotlight(page, '[data-testid="grant-card"]', 1600)
    },
  },
  {
    title: 'Wiki 引用與誠實邊界',
    budget: 25,
    narration: '知識庫分成生活指南與產品說明兩個互相隔離的域。答案會標出引用來源與更新日期；沒有依據的時候，它會直接說沒有依據，而不是硬湊一篇最像的。',
    async prepare(page) {
      await loginAs(page, 'member')
      await goNav(page, '/user/assistant')
    },
    async act(page) {
      await softSpotlight(page, '[data-testid="assistant-capability-wiki"]', 1200)
      await humanType(page, '[data-testid="assistant-composer"] textarea, [data-testid="assistant-composer"] input', '預約可以取消嗎')
      await page.keyboard.press('Enter')
      await page.locator('[data-testid="agent-result"]')
        .first().waitFor({ state: 'visible', timeout: 45000 }).catch(() => {})
      await spotlight(page, '[data-testid="agent-result"]', 2000)
      await softSpotlight(page, '[data-testid="agent-session-history"]', 1200)
    },
  },
  {
    title: '生活成果與主動關懷',
    budget: 30,
    narration: '北極星指標是生活任務完成率，不是聊天次數。關懷卡會說明它為什麼出現、用了哪些資料；點開指南之後才會進到協助式商務，不是一開口就推銷。',
    async prepare(page) {
      await loginAs(page, 'member')
      await goNav(page, '/user/wellbeing')
    },
    async act(page) {
      await softSpotlight(page, '[data-testid="outcome-list"]', 1200)
      await softSpotlight(page, '[data-testid="achievement-list"]', 1000)
      await softSpotlight(page, '[data-testid="care-card"]', 1600)
      await softSpotlight(page, '[data-testid="life-guide-card"]', 1400)
    },
  },
  {
    title: '點數與行事曆',
    budget: 25,
    narration: '點數是單一帳本，首頁、結帳、退款讀的都是同一份。行事曆把訂單、任務、提醒、社區活動投影在一起，取消訂單它會跟著消失。',
    async prepare(page) {
      await loginAs(page, 'member')
      await goNav(page, '/user/points')
    },
    async act(page) {
      await softSpotlight(page, '[data-testid="points-balance"]', 1300)
      await goNav(page, '/user/calendar')
      await softSpotlight(page, '[data-testid="calendar-title"]', 800)
      await softSpotlight(page, '[data-testid="calendar-event"]', 1600)
    },
  },
  {
    title: '生活圈',
    budget: 25,
    narration: '以會場為起點的時間可達範圍，步行與機車兩種模式。這是固定的示意資料，畫面上直接標明它不是即時路況、也不提供導航。',
    async prepare(page) {
      await loginAs(page, 'member')
      await goNav(page, '/user/life-circle')
    },
    async act(page) {
      await softSpotlight(page, '[data-testid="reachability-map-visual"]', 1500)
      // 這一段目前會落到「後端沒有回傳據點」的誠實降級。畫面完整、標示誠實，
      // 但旁白不能講成「真實店家清單」——見錄製文件的邊界清單。
      await softSpotlight(page, '[data-testid="reachability-offline-demo"]', 1600)
      await softSpotlight(page, '[data-testid="location-privacy-status"]', 1200)
    },
  },
  {
    title: '平台營運：目錄健康與故障注入',
    budget: 20,
    narration: '平台端看得到每個廠商的目錄同步狀態。上游掛掉時它誠實顯示 partial，而不是假裝一切正常——這是可維運性的證據。',
    async prepare(page) {
      await loginAs(page, 'platform')
    },
    async act(page) {
      await spotlight(page, '[data-testid="catalog-health-table"]', 1800)
      await softSpotlight(page, '[data-testid="onboarding-table"]', 1400)
    },
  },
  {
    title: '社區團購：住戶與主委的雙視角',
    budget: 60,
    narration: '最後是簡報的主軸：社區團購。住戶跟團之後，主委的彙總與成交額立刻更新——同樣是一份資料、兩個視角。',
    async prepare(page) {
      await loginAs(page, 'community-demo')
    },
    async act(page) {
      await softSpotlight(page, '[data-testid="resident-group-buy-kpi"]', 900)
      const card = page.locator('[data-testid^="group-buy-card-"]').first()
      if (await card.count()) {
        await card.scrollIntoViewIfNeeded()
        await beat(600)
        await card.locator('a').first().click()
        await page.waitForURL('**/group-buy/**').catch(() => {})
        await softSpotlight(page, '[data-testid="group-progress"]', 1100)
        const variant = page.locator('label.demo-variant-option').first()
        if (await variant.count()) {
          await variant.click()
          await beat(500)
        }
        if (await has(page, '[data-testid="join-group-buy"]')) {
          await click(page, '[data-testid="join-group-buy"]')
          await page.locator('[data-testid="my-group-order"]')
            .first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => {})
          await softSpotlight(page, '[data-testid="my-group-order"]', 1300)
          await softSpotlight(page, '[data-testid="group-progress"]', 1300)
        }
      }
      // 切主委看同一筆
      const switcher = page.locator('[data-testid="demo-role-switcher"]')
      if (await switcher.count()) {
        await switcher.selectOption('manager').catch(() => {})
        await page.waitForURL('**/demo/committee').catch(() => {})
        await beat(700)
        await softSpotlight(page, '[data-testid="committee-household-order"]', 1600)
        await softSpotlight(page, '[data-testid="committee-revenue-kpi"]', 1400)
      }
    },
  },
]

// ── 執行 ─────────────────────────────────────────────────────────────────────

if (argv.has('list')) {
  const total = SEGMENTS.reduce((sum, item) => sum + item.budget, 0)
  console.log(`功能導覽・${SEGMENTS.length} 段・預算合計 ${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}\n`)
  SEGMENTS.forEach((segment, index) => {
    console.log(`  ${index + 1}. ${segment.title}（約 ${segment.budget}s）`)
    console.log(`     ${segment.narration}`)
  })
  process.exit(0)
}

const only = argv.has('only') ? Number(argv.get('only')) : null
const from = only ?? Number(argv.get('from') ?? 1)
const to = only ?? Number(argv.get('to') ?? SEGMENTS.length)

if (!Number.isInteger(from) || !Number.isInteger(to) || from < 1 || to > SEGMENTS.length || from > to) {
  console.error(`段次超出範圍：可用 1–${SEGMENTS.length}`)
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
  // 移掉「Chrome 正受自動測試軟體控制」的黃色橫幅——它會被錄進畫面。
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
if (CURSOR) await context.addInitScript(CURSOR_BOOTSTRAP)
const page = await context.newPage()

const failures = []
page.on('pageerror', (error) => failures.push(`page error: ${String(error).slice(0, 200)}`))
page.on('response', (response) => {
  if (response.status() >= 400 && !response.url().endsWith('/favicon.svg')) {
    failures.push(`${response.status()} ${response.url()}`)
  }
})

console.log(`\n準備錄製第 ${from}–${to} 段。視窗 ${WIDTH}×${HEIGHT}，OBS 請用「視窗擷取」選 Chromium。`)
if (!CURSOR) console.log('（已關閉視覺游標）')

const cues = []
const runStartedAt = Date.now()

for (let index = from - 1; index < to; index += 1) {
  const segment = SEGMENTS[index]

  // 前置永遠不錄：把狀態帶到這一段的起點。
  recording = false
  process.stdout.write(`  · 準備第 ${index + 1} 段…\r`)
  try {
    await segment.prepare(page)
  } catch (error) {
    console.error(`\n第 ${index + 1} 段前置失敗：${String(error).slice(0, 200)}`)
    failures.push(`prepare#${index + 1}: ${String(error).slice(0, 160)}`)
  }
  recording = true
  process.stdout.write(' '.repeat(40) + '\r')

  if (COUNTDOWN > 0) {
    for (let n = COUNTDOWN; n > 0; n -= 1) {
      process.stdout.write(`\r  第 ${index + 1} 段開始倒數 ${n}… `)
      await wait(1000)
    }
    process.stdout.write('\r' + ' '.repeat(40) + '\r')
  }

  await slate(page, index + 1, segment.title)

  const startedAt = Date.now()
  console.log(`  ▶ 第 ${index + 1} 段　${segment.title}`)
  try {
    await segment.act(page)
  } catch (error) {
    console.error(`    × 動作中斷：${String(error).slice(0, 200)}`)
    failures.push(`act#${index + 1}: ${String(error).slice(0, 160)}`)
  }

  // 補到預算：動作通常比旁白短，不補的話配音會追不上畫面。
  if (FILL) {
    const remaining = segment.budget * 1000 - (Date.now() - startedAt)
    if (remaining > 0) await wait(remaining)
  }
  const elapsed = (Date.now() - startedAt) / 1000

  cues.push({
    index: index + 1,
    title: segment.title,
    offset: (startedAt - runStartedAt) / 1000,
    elapsed,
    budget: segment.budget,
    narration: segment.narration,
  })
  const drift = elapsed - segment.budget
  console.log(`    完成 ${elapsed.toFixed(1)}s（預算 ${segment.budget}s，${drift >= 0 ? '+' : ''}${drift.toFixed(1)}s）`)
}

await beat(1200)

const totalElapsed = (Date.now() - runStartedAt) / 1000
const stamp = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

mkdirSync(REPO_TMP, { recursive: true })
writeFileSync(`${REPO_TMP}demo-feature-cues.md`, [
  '# 功能導覽錄影分軌表（自動產生）',
  '',
  `本次錄製第 ${from}–${to} 段，實際總長 ${stamp(totalElapsed)}。`,
  '時間軸以本次錄製起點為 0。分段錄的話，每段各自從 0:00 起算。',
  '',
  '| 段 | 進入時間 | 實長 | 預算 | 旁白 |',
  '| --- | --- | --- | --- | --- |',
  ...cues.map((cue) => `| ${cue.index}. ${cue.title} | ${stamp(cue.offset)} | ${cue.elapsed.toFixed(1)}s | ${cue.budget}s | ${cue.narration} |`),
  '',
].join('\n'), 'utf8')

console.log(`\n總長 ${stamp(totalElapsed)}　分軌表：tmp/demo-feature-cues.md`)

const overruns = cues.filter((cue) => cue.elapsed > cue.budget + 0.5)
if (overruns.length) {
  console.warn('\n下列段的動作比預算久，長度由動作決定（把 budget 調到不小於實長即可消除）：')
  for (const cue of overruns) {
    console.warn(`  · 第 ${cue.index} 段 ${cue.title}：實長 ${cue.elapsed.toFixed(1)}s > 預算 ${cue.budget}s`)
  }
}
if (failures.length) {
  console.error('\n錄製期間偵測到問題（畫面可能有破綻，建議重錄）：')
  for (const failure of [...new Set(failures)].slice(0, 10)) console.error(`  · ${failure}`)
  process.exitCode = 1
}

await context.close()
await browser.close()
if (VIDEO) console.log('Playwright 備份影片：tmp/demo-video/')
