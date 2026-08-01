# 「範圍」做成核心屬性，而非各層各寫一套

產品採雙重心（個人日常＋社區集體），中間還有家庭層。提醒、優惠券、訂單、生活任務等實體在三層都會出現。我們決定：在這些核心實體上加一個 `owner_scope`（`individual` / `group`）欄位，並用一張 `group`（型態：family/couple/dorm/community）＋ `group_member`（帶角色）表承載所有群組共享；而不是為個人／家庭／社區各寫一套功能。

## Considered Options

1. **scope 做成核心屬性（採用）**——家庭層功能幾乎不需新程式（同一機制換個 scope），新增「宿舍」「情侶」等群組型態是零成本；權限判斷集中一處。簡報上「一個機制覆蓋三層」很好講。
2. 只支援 individual/family 兩值——實作更簡，但社區團購的「社區」層與家庭層脫鉤，日後統一要重構。
3. 各層各寫一套——直覺、初期快，但程式量膨脹約三倍，且與「雙重心用 scope 綁定」的定位自相矛盾。

## Consequences

- `resident` 是自然人；群組共享一律透過 `group`／`group_member` 表達。社區管理者＝community 群組的 admin 成員；代辦家人＝family 群組的 caregiver 成員——角色收斂進成員關係，不另立帳號表。
- 查詢「我的東西」＝ `owner_scope='individual' AND resident_id=?` ∪ 我所屬群組的 `group` 資料，需一致的存取層封裝，避免每個功能各自 join。
- 團購（[ADR-0001](0001-groupbuy-per-household-orders.md)）的跟團訂單仍是個人 07 訂單，但掛在 community 群組的團購活動下——scope 與團購模型正交、相容。
- 安心確認、長輩代辦等家庭功能，本質是 family 群組成員間的通知與代操作權限，不需獨立子系統。
