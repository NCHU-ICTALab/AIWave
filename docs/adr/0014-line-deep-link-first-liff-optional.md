# LINE 以 Web 深層連結為預設，LIFF 為選配增強層

競賽版以 Web 為主要產品與 Demo 介面，因此接入 LINE 不應迫使團隊維護另一套流程，也不應讓 P0 功能依賴 LIFF 初始化成功。LINE Messaging API 本身支援 URI action，可在 Bot 訊息、Flex Message 與 Rich Menu 中讓使用者點擊後開啟指定網址。

我們決定 LINE 的預設 handoff 為：AI Bot 理解意圖後建立短效 `handoff_id`，回傳對應 Web 深層連結；使用者點擊按鈕後，在同一套 RWD Web 中繼續填答或操作。handoff 狀態保存在伺服器端，URL 不攜帶個資、存取憑證或完整表單資料。瀏覽器登入沿用平台既有登入機制。

LIFF 保留為選配 adapter。只有需求明確涉及 LINE Login、LINE 執行環境／使用者資訊、傳送內容回聊天室、分享或關閉 LIFF 視窗時才載入；未載入 LIFF SDK、從外部瀏覽器開啟或 LINE 發生故障時，Web P0 主流程仍可完成。

限制是 Bot 不得在沒有使用者動作時強制跳轉頁面；AI 能決定目的地與按鈕文案，但實際開啟由使用者點擊 URI action 觸發。
