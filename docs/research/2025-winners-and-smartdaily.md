# 2025 優勝作品與智生活相鄰產品研究

> 研究日期：2026-07-28  
> 用途：支撐競賽策略與產品邊界；不是功能 backlog。  
> 策略結論見[競賽策略與奪冠證據](../strategy/competition-winning-strategy.md)。

## 1. 研究範圍

核對 2025 年七個不同企業命題組的優勝作品報導，以及智生活官方文章與產品頁。七隊是各組優勝，不是同一個總冠軍，因此本文只歸納跨組反覆出現的模式。

## 2. 七組優勝作品

| 團隊 | 解決方案 | 值得吸收的證據 |
| --- | --- | --- |
| [Cloud Ninjas](https://www.digitimes.com.tw/tech/dt/n/shwnws.asp?CnlID=13&id=721868) | 語音驅動 AI 助理機器人 | 語音、語意與任務調度形成即時流程；系統狀態及 Live Demo 可見 |
| [水獺叩艇](https://www.digitimes.com.tw/tech/dt/n/shwnws.asp?CnlID=13&id=721876) | 金融詐騙偵測 | 使用企業交易／帳戶資料，以 Precision、Recall、F1 與第二層 LLM 分析建立可信度 |
| [板上有名](https://www.digitimes.com.tw/tech/dt/n/shwnws.asp?CnlID=13&id=721866) | AI 機殼設計平台 | 自然語言轉 color、style、shape、material 等結構規格並即時渲染，AI 產生可見結果 |
| [雲科網管](https://www.digitimes.com.tw/tech/dt/n/shwnws.asp?id=0000721874_8C69KEUW6ZUTIW5WEJQW6) | AI 智慧銷售員 | STT、對話 LLM、TTS 與分析 LLM 分工；匯入名單及產品即可啟用，導入方式清楚 |
| [風中凌亂 Aidol](https://www.digitimes.com.tw/tech/dt/n/shwnws.asp?CnlID=13&id=721877) | 智慧偶像娃娃 | 五項易記功能、可控記憶、企業語音素材、完整原型影片與硬體／訂閱／DLC 商業模式 |
| [AWS Hero Song MediCAM](https://www.digitimes.com.tw/tech/dt/n/shwnws.asp?CnlID=13&id=721875) | 醫病溝通平台 | 量化痛點、研華 ICAM、四項功能、RAG、來源與加密、多院區擴展 |
| [去找另一隊復仇](https://www.digitimes.com.tw/tech/dt/n/shwnws.asp?CnlID=13&id=721878) | 急救大師 | 具名災害痛點、四色檢傷、RAG 與傷患記錄，把非專業者帶過高風險流程 |

## 3. 跨組共同模式

1. 先定義使用者痛點及失敗成本，再介紹技術。
2. 把作品濃縮成 3–5 個步驟或功能，評審能重述。
3. 真正使用命題方的資料、設備或 API。
4. AI 改變原流程並產生可見狀態，不只生成文字。
5. 以 RAG、指標、加密、權限、版本或來源建立可信機制。
6. 現場可跑且完成端到端結果。
7. 說得出導入方式、擴展性與誰得到商業價值。

## 4. 智生活研究

[指定文章](https://www.smartdaily.com.tw/col-ai-gov-smart-community-lifestyle-ecosystem/)是智生活自己的產品內容，適合了解其定位與近期功能，不是獨立第三方成效研究。應與[官方產品頁](https://www.smartdaily.com.tw/)及[規模頁](https://www.smartdaily.com.tw/company/10000community/)交叉閱讀。

可確認的產品重點包含：

- 串接住戶、管理室、物業、設備與生活服務。
- 以公告、管理費、包裹、門禁、公設、報修及紀錄交接形成社區營運底座。
- 逐步加入叫車、寄件、到府服務、AI 客服及廠商端 AI 協助。
- 官方宣稱超過一萬個社區、三百萬用戶及 370 家物業合作，顯示社區管理平台已有成熟規模。
- 實際導入重視高齡使用、既有設備、管理員責任、資料留痕及長期維運。

## 5. 對 AIWave 的意義

### 可吸收

- 群組功能必須包含角色、同意、責任、紀錄與交接，不只「一起省錢」。
- 新系統要能從單一 connector 漸進接入，而不是要求社區或廠商整套換掉。
- AI 的執行結果需要被人接住，有狀態、SLA、異常與責任邊界。

### 不應複製

- 不把管理費、門禁、包裹、公告、公設或社區硬體加入核心 roadmap。
- 不以社區管委會或物業作為唯一主要使用者。
- 不把 AI 客服回答問題當成 AIWave 的主要創意。

### 產品關係

```text
智生活類平台：社區基礎設施與管理流程
AIWave：會員生活目標的跨品牌、跨廠商、跨群組執行
```

未來若串接既有社區平台，應以 `CommunityConnector` 讀取經授權的群組、設施、公告與待辦；AIWave 保留任務編排、點數最佳化、廠商媒合、確認及追蹤責任。
