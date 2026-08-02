# AIWave Repository Structure Steering

## Primary paths

```text
api/                 FastAPI composition and HTTP boundaries
core/                Domain/application modules and repositories
agent/               Existing conversational/form-agent modules
mcp_server/          MCP integration
contracts/           OpenAPI and shared contracts
fake_upstreams/      Independent Demo Provider systems
web/app/             Vue 3 member, Provider, community, and platform UI
tests/               Python tests
docs/specs/          Product and technical specifications
docs/strategy/       Proposal and competition narrative
docs/testing/        Current evidence and Demo runbooks
docs/knowledge/      LLM Wiki source articles and governance
CONTEXT.md           Domain glossary
.kiro/steering/      Always-on project guidance
.kiro/specs/         Kiro requirements/design/tasks artifacts
.kiro/hooks/         Workspace automation hooks
```

## Documentation authority

- `docs/specs/15-agreed-product-and-platform-direction.md` is the overall product baseline.
- Specs 16 and 17 are the more specific v4 sources for proactive life-butler and conversational Agent behavior.
- `CONTEXT.md` defines canonical domain language and must remain free of implementation detail.
- `docs/status/` and current tests are evidence of what exists now.
- `docs/archive/` is historical and must not drive implementation.
- `docs/knowledge/` contains end-user Wiki content, not product requirements.

## Change discipline

- Read a file before changing it.
- Keep one coherent edit per target file, then validate.
- Do not silently rewrite user-owned dirty files.
- Do not touch `Dockerfile`, `docs/architecture/`, or `infra/` unless the user explicitly requests it.
- Do not implement application code when the task is documentation-only.
- Do not create empty feature shells or claim planned work is complete.
- Keep Demo data, production design, and validation-needed assumptions visibly separate.

## Naming

Use canonical terms from `CONTEXT.md`, including:

- Member, Beneficiary, ServiceLocation
- Time-based Reachability Area and Provider Service Area
- LifeContextEvent, CareCandidate, CareMessage
- Contextual Life Guide and PreparationItem
- Conversational Layer and Deterministic Action Layer
- ConversationSession and TurnIntent
- TaskDraft, ExecutionGrant, Provider, Offering, StatusEvent
- LifeOutcome, Achievement Unlock, Demo points ledger

Avoid introducing aliases that make these concepts ambiguous.

## New v4 artifacts

```text
.kiro/specs/aiwave-v4/
├─ requirements.md
├─ design.md
└─ tasks.md

docs/knowledge/
├─ README.md
├─ life-guides/       planned source-reviewed articles
└─ product-help/      planned release-matched FAQ articles
```

Actual Wiki articles remain incomplete until their sources and current product behavior are reviewed.
