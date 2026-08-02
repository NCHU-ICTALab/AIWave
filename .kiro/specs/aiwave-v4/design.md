# AIWave v4 Design

> 狀態：已確認設計；待依 `tasks.md` 實作  
> 日期：2026-08-01  
> 本次只建立文件，不自動執行 task 或修改應用程式碼

## 1. Overview

AIWave v4 在既有手動服務、TaskDraft、ExecutionGrant、ProviderConnector、Booking／Order、StatusEvent、points、notifications 與 calendar 上增加五個深模組：

1. 自然對話 Agent 與兩階段工具回合。
2. 可管理的 ConversationSession。
3. 分離的 product-help／life-guide LLM Wiki。
4. 時間可達生活圈與 Provider Service Area。
5. 主動情境、協助式商務、完成成果、成就與結算投影。

所有創新沿用既有交易閉環，不建立平行訂單、點數或履約系統。

## 2. Architecture

```text
Vue Web
├─ Dashboard／Services／Orders／Calendar／Points
├─ Agent workspace＋Session history
├─ Reachability map
└─ Provider／Platform workbench
        │
        ▼
FastAPI Platform API
├─ Conversation application service
├─ Capability Registry
├─ Wiki service
├─ Reachability service
├─ Task package service
├─ Proactive care service
└─ Reward／settlement projections
        │
        ├─ LLM Client（OpenAI-compatible／Bedrock adapter）
        ├─ TaskDraft／Grant／Catalog／Points repositories
        ├─ Booking／Order／StatusEvent
        ├─ ProviderConnector
        ├─ fixed GeoJSON provider
        └─ optional Amazon Location provider
```

HTTP、Agent 與未來 MCP 只呼叫 application services；不直連 DB 或在 LLM prompt 中藏第二套商業邏輯。

## 3. Conversational Agent

### 3.1 Turn pipeline

```text
Message + selected Session
→ assemble bounded context
→ LLM understand/plan
→ validate intent, TaskPatch and proposed actions
→ execute low-risk tools or request Grant
→ return authoritative ToolResults
→ LLM grounded response
→ persist messages, patches, references and audit
```

### 3.2 Turn contract

```text
ConversationTurn
- assistantMessage
- intent: TurnIntent
- taskPatches[]
- proposedActions[]
- clarification?
- citedKnowledge[]
```

The LLM controls wording and interpretation. The platform validates every identifier and action. Account／Role／Workspace are injected from the principal, never accepted from model arguments.

### 3.3 Tool result contract

```text
ToolResult
- actionId
- status: succeeded | needs_confirmation | unavailable | failed | unknown
- facts
- cards
- warnings
- retryPolicy
- auditRef
```

Facts include stable IDs and exact values. Cards render facts directly. The grounded response may compare and explain but cannot override them.

### 3.4 Task patches

```text
TaskPatch
- targetId
- operation: add | update | pause | resume | remove | select
- expectedVersion
- changes
- source: user | agent
```

User values remain higher priority than Agent inference. Patch conflicts require refresh and replan; do not overwrite unrelated subtasks.

## 4. ConversationSession

### 4.1 Data model

```text
ConversationSession
- id
- demoWorkspaceId
- workspaceId
- accountId
- title
- status
- summary
- activeTaskPackageId?
- pendingGrantId?
- createdAt
- updatedAt
- archivedAt?
```

Messages and object references remain session-scoped. Durable TaskDraft、Booking、Order、points、notifications and calendar records remain independent domain objects.

### 4.2 API surface

Planned Platform API:

- `POST /api/v1/platform/agent/sessions`
- `GET /api/v1/platform/agent/sessions`
- `GET /api/v1/platform/agent/sessions/{id}`
- `PATCH /api/v1/platform/agent/sessions/{id}`
- `POST /api/v1/platform/agent/sessions/{id}/archive`
- `POST /api/v1/platform/agent/sessions/{id}/restore`
- explicit delete only after product confirmation

Message and action requests require an explicit selected session. `latest` remains a compatibility fallback, not the product navigation model.

### 4.3 Context assembly

Use a bounded recent-message window plus a structured session summary and current task state. Do not automatically fetch other session transcripts. Cross-session data is limited to explicit member profile values and permission-checked domain facts.

## 5. LLM Wiki

### 5.1 Source tree

```text
docs/knowledge/
├─ life-guides/
└─ product-help/
```

Articles use front matter for id, domain, status, locale, region, app version, review, commercial use, push eligibility, and sources.

### 5.2 Competition loader

1. Classify the question into `life-guide` or `product-help`.
2. Select only `published` articles matching locale／region／app version.
3. Load the complete small corpus for that domain into context.
4. Request the domain-specific output schema.
5. Validate citations and action allowlists.
6. If evidence is absent, answer that no confirmed information is available.

No embedding or vector storage is required for the initial corpus. A future retrieval implementation stays behind the same Wiki interface.

### 5.3 Output isolation

- Life-guide may return `PreparationItem` and allowed actions such as view life circle or create checklist／draft.
- Product-help may return only answer, citations, limitations, and allowlisted navigation actions.
- Product-help cannot produce commerce recommendations.

## 6. Reachability

### 6.1 Two domain decisions

- Time-based Reachability Area: member travels to a Provider／Location.
- Provider Service Area: Provider travels to the member's ServiceLocation.

These filters can coexist in one task package but cannot substitute for each other.

### 6.2 Provider interface

```text
ReachabilityProvider.calculate(
  origin,
  travelMode: pedestrian | scooter,
  thresholdMinutes
) -> ReachabilityArea
```

Implementations:

- `SeededGeoJsonReachabilityProvider`: required Demo behavior.
- `AmazonLocationReachabilityProvider`: optional／production after validation.

The UI receives source, calculatedAt, mode, threshold, geometry, and eligible location IDs. Fixed data must be visibly marked as Demo and must not claim real-time traffic or navigation.

### 6.3 Privacy

Demo uses the venue address supplied by the product owner. Browser geolocation is requested only after a user click, used for the current calculation, and not persisted by default.

## 7. Proactive care and guides

```text
LifeContextEvent
→ CareCandidate
→ preference/delivery policy
→ CareMessage
→ Contextual Life Guide
→ PreparationItem
→ member chooses “幫我準備”
→ Catalog／reachability／TaskDraft
```

Candidate generation and actual delivery are separate auditable events. The competition Demo requires an in-app card, not production push infrastructure.

The Zhongyuan guide is a short main-Demo branch. Typhoon and moving／housewarming remain source-research and authoring tasks.

## 8. Task package and execution

A LifeTaskPackage references source event, beneficiary, ServiceLocation, and existing TaskDraft IDs. Members edit, pause, remove, or replace items before approval.

The platform recalculates totals, schedule conflicts, Provider scope, points and grant bounds. One ExecutionGrant covers only selected items. Execution is per task／Provider; partial failure preserves completed or accepted items and replans failed ones. Idempotency prevents duplicate orders, points, rewards and fees.

## 9. Completion and business projections

```text
StatusEvent completed/delivered
├─ update LifeOutcome
├─ unlock Achievement once
├─ evaluate Demo RewardRule
└─ create ProviderSuccessFee projection once
```

LifeOutcome, Achievement Unlock, Demo OPENPOINT reward, and Provider fee are separate concepts and ledgers/projections.

- Achievement has no monetary value.
- Reward requires an eligible completed event and campaign budget.
- Fee is per completed Booking／Order, not per package.
- Cancellation, failure, and unfulfilled work produce no fee.
- Refund/reversal creates compensating events rather than deleting history.

## 10. UI design

### Agent workspace

- New chat button and session history.
- Natural conversation as the default surface.
- Cards appear only for evidence, choices, drafts, grants, results, and citations.
- Composer stays usable while cards are present.
- Main AI page and global drawer share the explicitly selected session.

### Authority and accessibility

- Cards render stable IDs and backend facts.
- 44px targets, visible focus, keyboard navigation, non-color-only status, 390px／1440px.
- Achievement is non-blocking and announced accessibly without stealing focus.

## 11. Error handling

| Error | Design response |
| --- | --- |
| LLM timeout／invalid structure | Preserve session and tool facts; offer retry; no side effect |
| Wiki lacks evidence | Say no confirmed information; do not use model memory |
| Tool timeout before commit | Mark unavailable/retryable |
| Tool state unknown after commit | Query by idempotency key／snapshot before retry |
| Fact/response conflict | Suppress response and show authoritative card＋safe summary |
| Session conflict | OCC error, reload and reapply intended patch |
| Grant expired／out of scope | Stop and request new confirmation |
| Reachability unavailable | Use reviewed fixed Demo data if allowed and label source |

## 12. Security and privacy

- Principal-bound authorization for every Session, Wiki action, draft, order, Provider and settlement query.
- Wiki and Provider content are untrusted data and cannot override Agent policy.
- No secrets or raw credentials in prompts, traces, documents, `.kiro/`, or logs.
- No background location, hidden memory, hidden purchase, or unauthorized side effect.
- Auditable action proposals, approvals, tool results, retries and state transitions.

## 13. Testing strategy

### Automated

- Semantic paraphrase matrix asserts intent／capability equivalence.
- Multi-turn references, correction, removal, pause and non-transaction paths.
- Session create/list/rename/archive/isolation and new-session blank context.
- Wiki domain isolation, status/version filters, citations, no-evidence fallback, action allowlist.
- Reachability mode/threshold geometry and Provider list consistency.
- Provider Service Area separated from member reachability.
- Grant bounds, partial failure, idempotency, reward/fee once-only and reversals.
- Account／Workspace／Provider isolation.

### Human evaluation

Rate comprehension, context, naturalness, brevity, transparency, and distinction among suggestion／draft／confirmed／executed. Do not snapshot ordinary generated wording.

### Demo acceptance

Follow `docs/testing/v4-five-minute-demo-runbook.md`; all key results must appear on screen without requiring narration to fill a missing implementation.

## 14. Requirement traceability

| Requirement | Design sections |
| --- | --- |
| R1 | 1, 10, 13 |
| R2 | 3, 10, 13 |
| R3 | 3, 11, 12 |
| R4 | 4, 10, 13 |
| R5–R6 | 5, 12, 13 |
| R7 | 7, 12 |
| R8 | 6, 10, 11 |
| R9 | 7, 12 |
| R10 | 3.4, 8, 11 |
| R11 | 9, 11, 13 |
| R12 | 10, 13 |
| R13 | 13 |

## 15. Open validation items

- Confirm exact venue coordinates and manually review fixed GeoJSON.
- Validate Amazon Location IAM, Taiwan coverage, price, latency, and quality.
- Obtain official or licensed sources for all life-guide articles.
- Validate official OPENPOINT activity rules and Provider commercial terms before production claims.
- Establish human naturalness benchmark and target score after the first implementation.
