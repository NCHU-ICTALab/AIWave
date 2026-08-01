# AIWave M0～M3 測試與操作手冊

> 更新：2026-07-30。所有服務由操作者自行啟動；自動化測試不會留下背景程序。本文件只
> 證明 M0～M3，不把 legacy Hero、舊 MCP 或尚未取得正式資料的服務入口算成新架構閉環。

## 1. 一次性驗收

在專案根目錄使用 Bash：

```bash
uv sync --dev
uv run python -m openapi_spec_validator contracts/vendor-openapi.yaml
uv run pytest -q

cd web/app
npm install
npm test
npm run typecheck
npm run build
cd ../..

bash -n run.sh
git diff --check
```

2026-07-30 的 M0～M3 收尾基線為後端 350 項、前端 21 個測試檔／143 項、Partner
OpenAPI validator、Vue typecheck／production build 與 `bash -n run.sh` 全部通過。每次交付仍
以當下終端機的新結果為準；數量增加本身不代表完成，測試覆蓋範圍才是證據。

## 2. 手動啟動

請依序在四個 Bash 終端機執行：

```bash
# 終端機 1：現行 Partner fake
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
export VENDOR_FAKE_PORT="8020"
export PARTNER_FAKE_API_KEY="aiwave-partner"
uv run python -m fake_upstreams.partner_app
```

```bash
# 終端機 2：legacy Vendor fake（既有 LifeTask 相容流程）
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
export VENDOR_FAKE_PORT="8021"
uv run python -m fake_upstreams.vendor_app
```

```bash
# 終端機 3：Platform API
export PROVIDER_MODE="standard"
export PARTNER_MODE="fake"
export PARTNER_FAKE_URL="http://127.0.0.1:8020"
export PARTNER_API_KEY="aiwave-partner"
export VENDOR_MODE="fake"
export VENDOR_FAKE_URL="http://127.0.0.1:8021"
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
export DEMO_RESET_ENABLED="true"
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000
```

```bash
# 終端機 4：Vue
cd web/app
npm run dev
```

先確認 `http://127.0.0.1:8020/healthz`、`http://127.0.0.1:8021/healthz` 與
`http://127.0.0.1:8000/healthz`，再開前端終端機顯示的網址。

## 3. 身分、角色與 Workspace（M1）

固定 Demo bearer：

| token | 預期入口與隔離 |
| --- | --- |
| `aiwave` | 小圓的 personal workspace |
| `aiwave-chen` | 陳伯伯的 personal workspace |
| `aiwave-vivian` | Vivian 的 personal workspace |
| `aiwave-new` | 無訂單、無點數歷史的新會員 |
| `aiwave-partner` | 王子水電 partner workspace |
| `aiwave-partner-duskin` | DUSKIN 樂清 partner workspace |
| `aiwave-manager` | 核准社區的 community-manager workspace |
| `aiwave-admin` | platform-operator Demo 管理入口 |

驗收重點：

1. 新會員的首頁、點數與訂單皆為空，不得看到小圓資料。
2. 兩個合作方的工作量與案件互相隔離。
3. Group 只有名稱與成員，不出現家庭／朋友／社區 type。
4. Community 可透過申請＋管理者核准，或邀請碼加入；同一會員可加入多個 Community 並設定
   預設 Community。
5. 把 `X-Account-Id` 或 `X-Role` 加在 request 上不能取得另一身分；權限只由 Bearer principal
   決定。

自動證據集中於：

```bash
uv run pytest -q \
  tests/test_access_workspaces.py \
  tests/test_groups.py \
  tests/test_communities.py \
  tests/test_platform_access_api.py
```

## 4. 交易、點數、通知與行事曆（M2）

Platform API 文件位於 `http://127.0.0.1:8000/docs`。可以使用 `Bearer aiwave` 驗證：

- TaskDraft 建立、版本式修改與狀態轉移。
- Booking／CommerceOrder 的 domain-specific payload 與 StatusEvent。
- 正式 reschedule request，而不是直接覆寫廠商預約時間。
- DemoPaymentAdapter 的成功、失敗、取消與退款。
- 同一 Demo points ledger 的取得、折抵、退款、沖銷與到期。
- 持久化通知的 read/unread、scope、deep link、quiet hours。
- 訂單、任務、提醒、Group、Community、手動及週期事件的 Calendar projection。

所有交易寫入都帶 `Idempotency-Key`；版本式更新另帶 `expectedVersion`。重送同一 payload 應
回放同一結果，換 payload 應衝突，不得建立第二筆或重複扣點。

```bash
uv run pytest -q \
  tests/test_task_drafts.py \
  tests/test_fulfillment_core.py \
  tests/test_points_and_payment.py \
  tests/test_notifications_calendar.py \
  tests/test_platform_core_api.py
```

## 5. Partner API 與三種接入（M3）

```bash
curl --fail --silent --show-error \
  -H "Authorization: Bearer aiwave-partner" \
  http://127.0.0.1:8020/partner/v1/catalog

curl --fail --silent --show-error \
  -H "Authorization: Bearer aiwave-partner" \
  http://127.0.0.1:8020/partner/v1/availability

curl --fail --silent --show-error \
  -H "Authorization: Bearer aiwave-partner" \
  http://127.0.0.1:8020/partner/v1/snapshot
```

`StandardProviderConnector` 呼叫現行 Partner OpenAPI；`ExistingVendorAdapterConnector` 明確
轉換 legacy API 差異；`WorkbenchProviderConnector` 讓沒有 API 的廠商透過同一 connector
邊界持久化 catalog、availability 與 bookings。只有後端的 `PROVIDER_MODE` 可以切換。

故障注入、state unknown 與 malformed response 指令見
[fake upstream 手冊](../../fake_upstreams/README.md)。自動測試實際走過 after-commit 504 →
查詢／同 key 重試 → 單一遠端 booking：

```bash
uv run pytest -q \
  tests/test_partner_api_contract.py \
  tests/test_vendor_platform_integration.py \
  tests/test_demo_reset.py
```

## 6. 協調式 reset

平台營運者重設 M0～M3 的平台與 Partner fake：

```bash
curl --fail --silent --show-error \
  -X POST \
  -H "Authorization: Bearer aiwave-admin" \
  http://127.0.0.1:8000/api/v1/platform/demo/reset
```

legacy Vendor fake 是相容服務，另行重設：

```bash
curl --fail --silent --show-error \
  -X POST \
  -H "X-Fake-Control-Key: local-demo-key" \
  http://127.0.0.1:8021/__fake__/reset
```

成功後 Platform 與 Partner snapshot 的 seed version 應為 `partner-demo-v5`，舊 remote ID 不得
繼續被輪詢成 404；reset 回應的 `catalog` 欄位會回報目錄投影重新同步結果。

## 7. M4 六場景後端閉環驗證

fake upstream（8020，`partner-demo-v5`）涵蓋六場景多 Provider；平台啟動時自動同步目錄投影
（`CATALOG_SYNC_ON_STARTUP`，預設開），也可手動：

```bash
# 同步與健康檢查（operator）
curl -s -X POST -H "Authorization: Bearer aiwave-admin" \
  http://127.0.0.1:8000/api/v1/platform/catalog/sync
curl -s -H "Authorization: Bearer aiwave-admin" \
  http://127.0.0.1:8000/api/v1/platform/catalog/health

# 會員探索(六場景)與時段
curl -s -H "Authorization: Bearer aiwave" \
  "http://127.0.0.1:8000/api/v1/platform/catalog/providers?scene=home"
curl -s -H "Authorization: Bearer aiwave" \
  "http://127.0.0.1:8000/api/v1/platform/catalog/availability?providerId=vendor-prince-electric&offeringId=off-prince-electric-repair"
```

六場景端到端閉環（含取消/退款/點數沖銷/付款失敗恢復/狀態未知重試/隔離與 IDOR）由
自動測試實際走過：

```bash
uv run pytest -q tests/test_m4_scenarios.py
```

瀏覽器手動走查（方向 A UI，四個服務都啟動後）：

1. 登入頁選「林小圓」→ 首頁看點數/待處理/近期行程卡 → 主導覽「服務」。
2. 服務頁頂部「六大生活場景」選一家（例:王子水電）→「預約」進入預約精靈:
   據點 → 方案 → 真實時段 → 需求內容 → 試算(可折點數)→ 確認送出 → Demo 付款。
   中途重新整理:網址帶 `?draft=`,欄位值恢復續填。
3. 「我的訂單」→ 點進詳情看 StatusEvent 時間軸;可取消(自動退款+點數沖銷)、
   申請改期(重新查詢時段)。
4. 首頁「開啟行事曆」→ 訂單行程與手動事件在同一份 projection;取消後行程消失。
5. 登出改選合作廠商(12 家可選,例:王子水電)→ 工作台「平台案件」接單/開始服務/回報完成;
   回會員端看進度、通知與行事曆同步。
6. 登出改選平台營運者 → 目錄健康、重新同步、Demo reset。
前端元件測試(27 檔,含 booking wizard/order detail/calendar/vendor/admin):`cd web/app && npm test`。

Demo partner 帳號（12 家）：`aiwave-partner`（王子水電）、`aiwave-partner-duskin`、
`aiwave-partner-21plus`、`aiwave-partner-smile`、`aiwave-partner-blackcat`、
`aiwave-partner-cosmed`、`aiwave-partner-711shop`、`aiwave-partner-resort`、
`aiwave-partner-foodomo`、`aiwave-partner-711c2c`、`aiwave-partner-iopenmall`、
`aiwave-partner-ibonticket`。tier-2 目錄陳列品牌見
[方向 A 與廠商完成矩陣](../status/2026-07-31-direction-a-and-vendor-matrix.md)。

## 8. M8 Agent 驗證

Agent 全程使用 `.env` 的真實 LLM(NCHC Gemma),沒有 demo 專用路徑;守門
(Service Registry/TimeResolver/ExecutionGrant)完全確定性,LLM 不能繞過。

```bash
# 守門模組與協調器(CI 可重現;協調器測試注入腳本 LLM 作測試替身)
uv run pytest -q tests/test_agent_guardrails.py tests/test_agent_m8.py
```

真 LLM 實站走查(四服務啟動後,登入林小圓 → AI 頁):

1. **單場景**:「浴室的燈不亮了,想找人明天來修」→ 拆解(TimeResolver 回顯絕對日期)
   → 真目錄方案卡(評分/價格/最早可約)→ 選定 → 對話補欄位 → 授權卡(服務商/預算
   上限/時間範圍/有效期)→ 核准並執行 → 訂單連結 → 訂單頁 StatusEvent 時間軸。
2. **跨場景**:「爸媽這週末要來,幫我安排清潔,週六晚上訂四人餐廳」→ 兩個子任務
   逐一選方案補資料 → 一張授權涵蓋兩服務商 → 核准 → 兩筆訂單。
3. **切手動**:選定方案後點「切到手動填寫」→ 預約精靈開同一份草稿(`?draft=`)→
   手動補欄位 → 回 AI 頁說「都填好了」→ 直接進授權(user 值優先於 agent)。

側欄:任一會員頁右下「AI 管家」開側欄,與 AI 頁同一段對話(重新整理不遺失)。
守門邊界(超預算/過期/範圍外/未核准)由 tests/test_agent_guardrails.py 覆蓋;
「先不要」撤回授權不會建立任何訂單。

## 9. 本里程碑不能宣稱的內容

- 尚未取得產品負責人核准資料的正式廠商、價目、服務表單（seed 為可替換展示資料）。
- 六場景的**瀏覽器端手動 UI**（等 HTML 原型核准後於 Vue 整合；後端閉環已完成）。
- 核准後的新版公開首頁與 Dashboard Vue 視覺。
- Agent／手動 TaskDraft 接手的完整產品體驗。
- `mcp==2.0.0` 遠端 Streamable HTTP Gateway。
- LINE、語音、醫療正式流程與正式 AWS 部署。

既有 AI、LifeTask、Community campaign、客服與舊 MCP 測試仍有回歸價值，但不能代替上述後續
里程碑的驗收。
