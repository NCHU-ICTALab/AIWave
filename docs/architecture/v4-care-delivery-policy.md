# v4 關懷送達政策（未進主 Demo 設定頁）

競賽版只展示站內 CareMessage，不向會員暴露完整偏好設定。正式版的政策先以
`core/proactive_care/policy.py` 固化並測試，避免日後把「候選」直接當成「送達」。

規則如下：

- `quiet`、`balanced`、`caring` 三種模式，預設頻率分別為每類 30 天 1 次、7 天 1 次、24 小時 3 次。
- 類別可覆寫為 `off`、`low`、`normal`、`high`；交易通知使用獨立計數，不受一般關懷頻率限制。
- `push`／`email` 受安靜時段影響；目前 Demo 的 `in_app` 卡片不經此設定頁。
- 資料來源只接受公共日曆、會員明確授權資料與明確標示的 Demo event；背景定位與購買推論會被拒絕。

證據：`tests/test_v4_care_policy.py`。政策本身不寫資料庫，未來偏好 API 接入時由應用服務負責保存與套用。
