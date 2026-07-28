# 社區聯合服務 Hero

## 要回答的產品問題

單戶清洗冷氣只是一次委託；社區真正有價值的能力，是把分散需求變成可議價、可比較、可履約追蹤的共同案件。此流程把 18 戶需求聚合成一份標準工單，讓管委會保留決策權，廠商取得可執行資訊。

## 可信資料標示

- 服務分類與題組：平台服務目錄／官方公開素材。
- 18 戶需求、兩案報價、時段與評分：競賽建置資料。
- UI 必須就近顯示「非品牌即時報價」，不得暗示品牌合作、即時庫存或正式承諾。

## 狀態與權限

| 狀態 | 可執行動作 | 執行者 |
|---|---|---|
| `draft` | 預覽、發布 | 管委會 |
| `collecting` | 住戶加入、截止並進入方案比較 | 住戶／管委會 |
| `proposal_review` | 比較、確認指派一案 | 管委會 |
| `assigned` | 查看標準工單、回報開工 | 被指派廠商 |
| `in_progress` | 回報完工與說明 | 被指派廠商 |
| `completed` | 唯讀稽核 | 管委會／廠商 |

每次變更以 compare-and-set 寫入，並留下事件；寫入工具一律需要 Agent 執行前確認。

## Hero 種子

- 社區：晴光社區（競賽單一社區 scope）
- 情境：冷氣聯合清洗
- 證據：18 戶、27 台；以匿名住戶雜湊去重，不把姓名交給 AI。
- 偏好：週六上午為最多數；另顯示其他時段與特殊需求。
- 方案：兩案皆有清洗、材料／防護、社區統籌等分項，並揭露優點與限制。

## 傳輸契約

- Read：`get_joint_service_summary(campaign_id)`、`list_assigned_joint_services`
- Write：`create_joint_service`、`publish_joint_service`、`join_joint_service`、`prepare_joint_service_proposals`、`assign_joint_service_vendor`、`start_joint_service`、`complete_joint_service`
- Web API 使用同一服務，角色與廠商帳號由目前競賽登入 seam 的 header 取得；request body 不接受角色或帳號。廠商讀寫都必須符合方案的 `vendorId`。
