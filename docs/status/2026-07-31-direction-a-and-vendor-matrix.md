# 2026-07-31 方向 A 11 項完成矩陣與廠商完成矩陣

> 依產品負責人本輪指示產出;方向 A 的 11 項以 `design-system/aiwave/pages/index.html` 清單為準,
> 廠商名單以《廠商and表單.md》為準(2026-07-31 拍板:兩層制、一品牌一 Provider、
> 照片上傳延後、叫車陳列/售票做非劃位)。
> 驗收證據:後端 pytest 全套 exit 0(含 tests/test_m4_scenarios.py 13 條)、
> 前端 vitest 29 檔/182 tests、vue-tsc、production build、
> 實站 Playwright(四服務全啟動,15 頁 × 390/1440px 零 console error/零水平溢出,
> 住・修繕預約 E2E 取得真實 booking id)。

## 一、方向 A 11 項完成矩陣

| # | 原型項目 | 正式 Vue | API/資料來源 | 測試證據 |
| --- | --- | --- | --- | --- |
| 1 | 公開首頁 | `/`(HomePublicView):價值主張、六場景、右上登入 | 靜態文案(無個人資料) | loginAndAccess.spec、實站截圖 |
| 2 | 登入 | LoginView:帳密卡(驗證錯誤示範)+ Demo 快速登入(住戶×4/12 家合作方/管理者/營運者) | `/insights/accounts`、access seed | loginAndAccess.spec |
| 3 | Dashboard | TodayView:大數字 KPI(點數/消費)、待處理 badge、AI 入口、推薦(單則不感興趣+復原)、近期行程卡+通知未讀 | insights/today、`/platform/points`、`/platform/calendar/events`、`/platform/notifications` | todayInsights.spec(13 條) |
| 4 | 服務探索與詳情 | ServicesView 兩層制(12 tier-1 卡+各場景 tier-2 陳列)+ ProviderDetailView(據點/價目/取消規則/狀態預覽) | `/platform/catalog/providers`、`/catalog/listings`、`/catalog/providers/{id}` | servicesExplore.spec、providerDetail.spec |
| 5 | 表單/店家/時段 | BookingWizardView:TaskDraft 驅動、據點→方案→真實時段→11 個 domain 欄位組→試算→DemoPayment;`?draft=` 續填、409 誠實重載、重複提交保護 | `/platform/task-drafts*`、`/quotes`、`/payments`、`/catalog/availability` | bookingWizard.spec(6 條)、實站 E2E |
| 6 | 訂單詳情與時間軸 | OrderDetailView:per-domain 狀態名、StatusEvent 時間軸、取消(退款+沖銷)、改期(重查時段)、重付 | `/platform/bookings*`、`/commerce-orders*` | orderDetail.spec |
| 7 | Calendar | CalendarView:月/週/列表、來源篩選、手動事件、projection 原則(訂單改期導回訂單頁) | `/platform/calendar/events` | calendarView.spec(8 條) |
| 8 | Group | CommunityBoardView 群組區(自行命名/邀請碼/改名/離開;M1 起有) | `/groups*` | communityGroupBuy.spec |
| 9 | Community | 住戶:公告列表+加入申請+預設社區;管理者:加入審核+發布公告 | `/platform/communities*`、`/communities/{id}/announcements`(本輪新增) | communityAnnouncements.spec、test_communities.py |
| 10 | Provider Workspace | VendorView:案件 inbox、合法狀態轉移、查看需求(details 個資最小化)、本週時段+編輯(標準接入 409 誠實顯示) | `/platform/bookings`(partner)、`/provider/availability`、`/provider/snapshot` | vendorPlatformBookings.spec(6 條) |
| 11 | aiwave-admin | PlatformView:Demo workspaces(單一 persona 重置)、fake upstream 健康+timeout/503 注入/清除(後端代理,key 不出後端)、Partner onboarding 誠實展示、目錄健康/sync/整體 reset | `/admin/demo-personas`、`/platform/admin/workspaces/{id}/reset`、`/admin/upstream-health`、`/admin/upstream-faults`、`/catalog/health` | platformAdmin.spec(7 條)、test_m4_scenarios |

原型與正式版的刻意差異(誠實原則):admin 的「匿名廠商審核動線」原型是純前端戲法,
正式版以誠實展示表呈現(申請/審核/發 key 屬後續里程碑);Dashboard「合作推薦・廣告」
badge 未做——現有推薦全為規則式個人化,無推廣型資料來源,不硬造。

## 二、廠商完成矩陣(兩層制)

### tier-1 可交易 Provider(12 家;`partner-demo-v5`,各自 Partner API key,fake upstream 收件)

| 場景 | Provider | 代表服務(domain) | 表單依據(廠商and表單.md) |
| --- | --- | --- | --- |
| 食 | 21PLUS(21 系列;店型=方案) | 訂位(dining_reservation)+21TOGO 外帶(food_delivery) | 食 B 型訂位/C 型外帶 |
| 食 | foodomo | 熱食/生活用品外送(food_delivery) | 食 C 型外帶外送 |
| 醫 | 康是美 | 處方箋門市領藥(pharmacy_pickup;慢箋/一般、本人/代領、辨識人工確認) | 醫 完整欄位(照片上傳延後) |
| 住 | 王子水電 | 修繕到府檢測/急件(home_repair;報修主項/屋齡坪數選填) | 住 C 型修繕 |
| 住 | DUSKIN 樂清 | 全室清潔/冷氣清洗/計時家事(home_cleaning) | 住 A/B 型 |
| 行 | 速邁樂加油站 | 精緻洗車預約(car_wash;車牌/車種) | 行 A 型(名單指出的差異化切入) |
| 行 | 黑貓宅急便 | 宅配到府收件(shipping_pickup) | — |
| 行 | 7-ELEVEN 交貨便 | 店到店寄件常溫/冷凍(c2c_shipping) | 預 3 C2C 寄件單 |
| 預 | 7-ELEVEN 線上購物中心 | i 預購(ec_preorder;取貨方式+溫層/發票選填) | 預 1/2 |
| 預 | iOPEN Mall | 商城購物(ec_preorder) | 預 1 |
| 樂 | 統一渡假村 | 訂房/溫泉湯屋(resort_booking;馬武督/谷關雙館) | 樂 C 訂房型 |
| 樂 | ibon 售票 | 景點門票/交通票券(ticket_purchase;非劃位) | 樂 B 非劃位型(劃位型列後續) |

### tier-2 目錄陳列(34 品牌;`core/catalog/listing.py`,`GET /catalog/listings`,誠實標示不可下單)

食:7-ELEVEN、星巴克、Mister Donut、COLD STONE、Semeur 聖娜、午茶風光、和食上都、
統一生機、聖德科斯、德記洋行(B2B)、南聯(B2B)、萬家福、樂家康、Mia C'bon、統一武藏野(B2B)
/ 醫:統一藥品、千禧之愛 / 住:MUJI、好鄰居基金會、太子物業 /
行:**ibon 叫車(合作車隊;note 誠實說明官方為機台流程)**、統一精工設備(B2B)、
捷盟、統昶、大智通、捷盛(企業物流)、統一東京(B 端) /
預:賣貨便、i划算、博客來、icash、金財通 / 樂:統一獅、夢時代、DREAM PLAZA、
BEING spa/sport/fit、蘭陽藝文、夢公園、ibon 保險 / 支援型:統一資訊、首阜、
統一期貨、統一綜合證券、統義玻璃(整組陳列)。

名單覆蓋檢查:《廠商and表單.md》第一部分所有品牌均在 tier-1 或 tier-2;無自創品牌。
