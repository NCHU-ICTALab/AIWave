# AIWave v4 驗收矩陣

這份矩陣是可失敗的自動驗收入口，不用一般聊天文案 snapshot；測試斷言 intent、stable ID、權威 facts、權限與副作用。

## Agent 與 Session

| 矩陣 | 主要證據 | 執行命令 | 目前結果 |
| --- | --- | --- | --- |
| 同義改寫／規劃 | `tests/test_v4_acceptance_matrix.py`、`tests/test_agent_m8.py` | `uv run pytest -q tests/test_v4_acceptance_matrix.py tests/test_agent_m8.py` | PASS |
| 代名詞、省略、修正、反悔、暫停 | `test_context_patch_and_reversal_keep_unrelated_tasks_intact`、`test_task_patches_only_touch_the_stable_target`、M8 pause path | 同上＋`tests/test_agent_v4_contracts.py` | PASS |
| 非交易對話零副作用 | `test_product_help_turn_is_grounded_and_has_no_draft_side_effect` | `uv run pytest -q tests/test_agent_v4_contracts.py` | PASS |
| 新 Session 隔離與舊任務保留 | session lifecycle／M8 isolation tests | 同上 | PASS |
| LLM 失敗安全降級 | `test_ambiguous_laundry_clarifies_and_llm_failure_degrades_honestly` | `uv run pytest -q tests/test_agent_m8.py` | PASS |
| grounded facts／矛盾降級 | grounded second-stage tests | `uv run pytest -q tests/test_agent_v4_contracts.py` | PASS |
| bounded context／ToolResult／Wiki 證據 | orchestrator context tests、`web/app/tests/assistantConversation.spec.ts` | `uv run pytest -q tests/test_agent_v4_contracts.py`；`npm test -- --run tests/assistantConversation.spec.ts`（於 `web/app`） | PASS |

## Wiki、生活圈與商業閉環

| 矩陣 | 主要證據 | 執行命令 | 目前結果 |
| --- | --- | --- | --- |
| Wiki domain／版本／引用／action allowlist／無證據 | `tests/test_v4_wiki.py` | `uv run pytest -q tests/test_v4_wiki.py` | PASS |
| 步行／機車、10／15 分鐘、Catalog location、到府分流與單次定位隱私 | `tests/test_v4_reachability.py`、`web/app/tests/reachability.spec.ts` | `uv run pytest -q tests/test_v4_reachability.py`；`npm test -- --run tests/reachability.spec.ts`（於 `web/app`） | PASS |
| 候選→送達、來源與會員 action | `tests/test_v4_care.py`、`tests/test_v4_care_policy.py` | `uv run pytest -q tests/test_v4_care*.py` | PASS |
| 任務包 OCC／逐項執行／部分失敗／重放 | `tests/test_v4_task_packages.py` | `uv run pytest -q tests/test_v4_task_packages.py` | PASS |
| 完成／成就／Demo reward／fee／沖銷 | `tests/test_v4_outcomes.py` | `uv run pytest -q tests/test_v4_outcomes.py` | PASS |

## Frontend screen evidence

`web/app/tests/reachability.spec.ts`、`wellbeing.spec.ts`、`agentSessions.spec.ts` 與 `assistantConversation.spec.ts` 以固定 route、`data-testid`、文字、action 後重新抓取資料與錯誤狀態驗證畫面行為；Agent 測試另驗證 ToolResult facts、稽核參照、Wiki 引用與更新日。最新前端回歸為 31 個 test files／155 tests，TypeScript 與 production build 皆 PASS；完整命令與後端分批回歸見 [current-state](../status/2026-07-30-current-state-and-gap.md)。本輪環境沒有可用 browser instance，故不把這些測試誤稱為真實瀏覽器走查。

尚未通過的人工項目會保留為 unchecked：正式生活指南來源與審核、會場座標／GeoJSON 人工檢查、真實瀏覽器鍵盤走查、五分鐘實站彩排，以及 AWS／Amazon Location。這些不是用測試綠燈代替的項目。
