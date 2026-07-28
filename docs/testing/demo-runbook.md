# AIWave Demo 與測試手冊

> 更新：2026-07-28。所有服務都由操作者自行啟動；自動化測試不會留下背景程序。

## 1. 一次性驗收

在專案根目錄執行：

```bash
uv sync --dev
uv run python -m openapi_spec_validator contracts/vendor-openapi.yaml
uv run pytest -q

cd web/app
npm install
npm test
npm run typecheck
npm run build
```

2026-07-28 完成基線：後端 299 項通過，前端 19 個測試檔／132 項通過，
OpenAPI validator 回報 `OK`，production build 成功。
執行當下應以終端機的新結果為準。

## 2. 手動啟動

請在三個 Bash 終端機分別執行，不要關閉：

```bash
# 終端機 1
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
uv run python -m fake_upstreams.vendor_app
```

```bash
# 終端機 2
export VENDOR_MODE="fake"
export VENDOR_FAKE_URL="http://127.0.0.1:8020"
uv run main.py
```

```bash
# 終端機 3
cd web/app
npm run dev
```

先開 `http://127.0.0.1:8020/healthz`、`http://127.0.0.1:8000/docs`，再開前端終端機顯示的網址。

## 3. 五分鐘 Hero

1. 以會員「小圓」登入，在 AI 輸入：
   `爸媽週六要來，浴室燈壞了、冷氣也很久沒洗，幫我安排一下，OPENPOINT 能省就省。`
2. 確認週六、會員住家與個人範圍；比較王子水電及 DUSKIN 樂清、點數折抵與限制。
3. 只按一次「確認整份安排」，應建立兩個外部諮詢單；首頁與訂單頁都看得到同一 `TASK-`。
4. 登出後分別以王子水電與 DUSKIN 樂清登入。各自在「AI 跨服務案件」提出正式報價。
5. 回會員訂單頁展開同一生活任務，確認全部報價；再回兩個廠商工作台回報開始與完工。
6. 回會員 AI／首頁／訂單，三處都應顯示完成或最新進度。

## 4. 群組加碼

會員進入「會員中心 → 群組共享」，在「社區共同需求」選設備、台數與時段。未勾同意時
按鈕不可送出；勾選後只共享匿名需求。社區管理者看到聚合戶數／設備／時段，不會看到
姓名、電話或門牌，並可比較方案後指派廠商。

## 5. 故障橋段

依 [fake server 手冊](../../fake_upstreams/README.md) 注入下一次 `POST /v1/inquiries` 的 503。
會員確認後應看見上游維護原因與安全重試按鈕；第二次重試完成剩餘案件，已成功的上游編號
維持不變。reset 後 seed 回到 10 品牌、30 據點、120 諮詢與 120 報價。

## 6. MCP 證據

`tests/test_vendor_platform_integration.py::test_external_agents_can_complete_the_same_cross_service_task_over_mcp`
會實際透過 MCP transport 走完：會員 Agent 草稿／設定／確認 → 兩個廠商 Agent 報價 →
會員接受 → 廠商完工 → 會員讀到完成。所有 MCP 寫入工具先回傳 payload-bound、五分鐘有效且
只能使用一次的確認 token。

手動掛載 MCP server：

```bash
export MCP_ROLE="user"
export MCP_ACCOUNT_ID="019a52d3-7f6b-7da3-b48d-9c9e2522d616"
export MCP_DISPLAY_NAME="小圓"
uv run python -m mcp_server.server
```

## 7. 可量化流程基線

這是流程模型，不冒充使用者研究或耗時實驗：

| 指標 | 傳統分散流程最低需求 | AIWave Hero 可重現結果 |
| --- | ---: | ---: |
| 個別服務入口／供應商流程 | 2 | 1 個生活任務 |
| 重複建立的服務案件 | 2 次分開操作 | 1 次確認建立 2 件 |
| 狀態追蹤位置 | 2 個供應商來源 | AI、首頁、單一折疊任務 |
| 點數試算 | 額外人工查詢 | 同一方案內確定性試算 |
| 外部 Agent 可重用能力 | 0（假設無共同契約） | 會員 6 個 LifeTask tools＋廠商 4 個履約 tools |

完成時間與真實轉換率尚未做人員實驗，因此簡報不得填入虛構秒數或百分比。
