# 地端優先開發，設計為可平滑移植 AWS

開發初期在本地（地端）進行，之後才移植到 AWS serverless。因此本地實作必須刻意採「方便移植」的架構：所有會變成 AWS 託管服務的相依，都藏在介面之後；所有執行單元都容器化；資料與協定選型與 AWS 目標一致。目的是移植時只換「介面實作」與「部署方式」，不動核心商業邏輯。

## 移植對照（本地 → AWS 目標）

| 能力 | 地端實作 | AWS 目標 | 隔離方式 |
| --- | --- | --- | --- |
| 執行單元 | Docker 容器 | Lambda 容器映像／App Runner／ECS | 一律容器化 |
| LLM | Bedrock（可從地端呼叫）或 Anthropic API | Amazon Bedrock（Claude） | `LlmClient` 介面 |
| 語音 STT/TTS | 本地 Whisper／簡易 TTS | Amazon Transcribe／Polly | `SpeechClient` 介面 |
| 資料庫 | 本地 PostgreSQL | Aurora Serverless v2（Postgres 相容） | 純 SQL/ORM，不用專屬語法 |
| 事件/佇列 | 行程內事件匯流排或本地 Redis | EventBridge／SQS | `EventBus` 介面 |
| 物件儲存 | 本地檔案系統 | S3 | `BlobStore` 介面 |
| MCP Server | 獨立行程 | 各自獨立 Lambda／容器 | 標準 MCP 協定，本就是可獨立部署單元 |
| Web/後台 | 本地 dev server | Amplify／CloudFront+S3 | 靜態前端＋API 呼叫 |

## Considered Options

1. **地端優先＋可移植（採用）**——開發迭代快、不燒 AWS 額度、除錯容易；只要守住介面隔離，移植成本可控。
2. 一開始就直接在 AWS serverless 上開發——最貼近最終環境，但迭代慢、除錯繞、燒額度，且冷啟動等問題會干擾早期功能開發。
3. 地端開發但不管移植——最快，但移植時要大改，且官方會問「AWS 架構考量」時無法自圓其說。

## Consequences

- 核心商業邏輯（Agent 編排、題組引擎、業務規則）不得直接相依任何 AWS SDK；一律經介面。
- 選型硬約束：資料庫用 Postgres 相容、避免 AWS 專屬 SQL；訊息/儲存以介面封裝。
- MCP Server 天然是「獨立可部署單元」，與此決策相互加成——MCP 邊界畫得越乾淨，移植越無痛（見 MCP 邊界決策）。
- 簡報「為什麼這樣設計 AWS 架構」的答法：以介面隔離換取「地端快速開發＋雲端無痛部署」，serverless 對應社區/個人流量的尖峰離峰與成本；AWS 細節（DB/runtime/Gateway）待另一輪定案後補於 [01](../specs/01-system-architecture.md)。
