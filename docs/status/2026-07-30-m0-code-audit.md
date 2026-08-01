# M0 程式碼盤點與保護基線

> 盤點日期：2026-07-30
> 依據：[產品與平台定案基線](../specs/15-agreed-product-and-platform-direction.md)
> 原則：舊文件的「完成」不是新架構完成證據；目前工作樹有大量未提交修改，全部視為需保護的使用者工作。

## 工作樹保護

- 開始 M0 時先以 git status --short 盤點 dirty worktree。
- 本輪未執行 git reset、git checkout --、git clean、rebase、commit 或 push。
- 沒有覆寫或丟棄不相關修改；新架構以增量模組、資料庫 migration 與明確 compatibility path 落地。
- contracts/vendor-openapi.yaml 保留既有檔名供工具相容，但內容已是 Partner API v2；舊契約移至 contracts/legacy/。

## 可重現測試基線

| 基線 | 後端 | 前端 | 其他 |
| --- | --- | --- | --- |
| M0 開始前重新驗證 | 309 tests | 20 files／142 tests | OpenAPI valid、production build pass |
| M0～M3 收尾 | 350 tests | 21 files／143 tests | Partner OpenAPI valid、typecheck／build、bash -n run.sh |

命令全部是 Bash，可在不啟動背景服務的情況下重現：

~~~bash
uv run python -m openapi_spec_validator contracts/vendor-openapi.yaml
uv run pytest -q

cd web/app
npm test -- --run
npm run typecheck
npm run build
cd ../..

bash -n run.sh
git diff --check
~~~

數字只表示測試集合規模；M1～M3 是否完成仍由下列程式與針對性測試證明。

## 保留

| 現有資產 | 保留理由 |
| --- | --- |
| core/forms/ 與官方題型資料 | 彈性表單、跳題與驗證仍是正式手動流程的基礎 |
| core/data/ 與官方訂單／地區資料 | 行為與測試證據來源，不重造第二份資料 |
| core/insights/ 與 personalization 規則 | 保留可解釋規則；點數餘額已改讀新 ledger |
| core/services/ application service seam | Web 與既有工具的 Platform API 邊界素材 |
| api.create_app() dependency injection | 可注入 repository、connector、clock 與測試 client |
| Vue 元件、五頁籤與已驗證互動 | 本 goal 不重寫正式視覺，避免在 HTML 原型核准前改方向 |
| legacy Vendor／LifeTask／客服流程 | 仍提供回歸與 compatibility 價值，但不冒充新 Partner API 或 M4 閉環 |

## 重構與新增

| 項目 | 權威實作 | 驗證 |
| --- | --- | --- |
| Account／RoleMembership／Workspace／DemoWorkspace | core/access/、api/platform_access.py | test_access_workspaces.py、test_platform_access_api.py |
| 自行命名 Group | core/groups/、web/app/src/api/groupClient.ts | test_groups.py、前端 member tests |
| 獨立 Community | core/communities/、api/platform_access.py | test_communities.py、test_platform_access_api.py |
| TaskDraft | core/task_drafts/ | test_task_drafts.py、test_platform_core_api.py |
| Booking／Order／StatusEvent／reschedule | core/fulfillment/ | test_fulfillment_core.py、test_platform_core_api.py |
| Demo points ledger 與 payment | core/points/、core/payments/ | test_points_and_payment.py、前端 points tests |
| 通知與 Calendar | core/notifications/、core/calendar/ | test_notifications_calendar.py |
| Partner API 與三種 connector | contracts/vendor-openapi.yaml、core/providers/ | test_partner_api_contract.py、test_vendor_platform_integration.py |
| 獨立 Partner fake | fake_upstreams/partner_app.py | contract、fault、state-unknown、reset tests |
| 協調 reset | core/demo_reset.py、POST /api/v1/platform/demo/reset | test_demo_reset.py |

## 已移除或停止宣稱

- HTTP X-Account-Id／X-Role 不再作為權威身分來源；Platform API 只接受 Bearer principal。
- 前端 Pinia 中的 seed 訂單與「建立成功」已移除，手動服務送件會呼叫後端持久化 API。
- 新會員不再看到舊 persona 的點數、訂單或推薦摘要。
- Group 的 family／couple／dorm／community type 已移除；Community 不再當 Group type。
- 無 handler 的語音、編輯、新增合作服務等按鈕已移除或改成誠實的非互動狀態。
- 寫死的 connector 數量、campaign success 狀態、假常用服務與假訂單不再作為可見完成證據。
- 2026-07-30 前的 P0 完成宣告、MCP map、決策佇列與舊規格已移入日期化封存區。

## Compatibility path，不是新架構完成證據

- fake_upstreams/vendor_app.py 與 core/vendors/：供既有 LifeTask／報價流程使用，手動測試固定在 8021；現行 Partner fake 在 8020。
- mcp_server/：本機 stdio compatibility proxy，只能經 Bearer Platform API 發現及執行工具；
  它不等於未來 mcp==2.0.0 Streamable HTTP Gateway。
- 舊 Community campaign、joint service、客服及 AI Planner：保留可運作部分，但其功能數量不能代替 M4～M10 的正式驗收。

## 明確延後

- 正式廠商、品牌、價目與代表性表單：等產品負責人提供並核准。
- 住、食、預、行、樂、醫的正式服務閉環。
- 公開首頁及兩種 Dashboard HTML 審批與 Vue 視覺重寫。
- Service Registry、TimeResolver、ExecutionGrant 與完整 Agent 接手流程。
- 遠端 MCP v2、LINE、語音、醫療正式流程與正式 AWS 部署。

## 結論

M0 的保護、分類、封存與測試基線已建立。這份盤點只對 M0～M3 的現行程式碼做完成判斷；未列入 M0～M3 的功能維持「保留／相容／延後」，不得因為舊畫面或舊測試存在就宣稱完成。
