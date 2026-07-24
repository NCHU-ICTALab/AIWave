# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Hackathon entry for 統一資訊's prompt **「AI 生活管家：智慧社區服務需求理解與媒合平台」** (2026 雲湧智生 GenAI hackathon). A LINE/Web life-butler that understands a resident's need in natural language, drives a flexible **留資表單 (lead-capture form / 諮詢單)**, and matches it to service vendors.

**`docs/` is the source-of-truth spec, not just notes.** Start at [docs/README.md](docs/README.md) (index of 7 specs + 4 ADRs). [CONTEXT.md](CONTEXT.md) is the domain glossary; [ideas.md](ideas.md) is decision history. When you change behavior, keep the relevant `docs/specs/*` in sync — several decisions there are load-bearing (see ADRs below).

## Commands

- Install / sync env: `uv sync` (isolated `.venv`, Python 3.13 via uv)
- Run the test server: `uv run main.py` → http://localhost:8000 (reload on, serves `web/chat.html` + the API)
- All tests: `uv run pytest`
- One file / one test: `uv run pytest tests/test_form_engine.py` · `uv run pytest tests/test_form_engine.py::test_skip_ac_type_when_not_choosing_ac` · `-k <expr>`
- Add deps: `uv add <pkg>` (runtime) · `uv add --dev <pkg>` (dev). Never edit the venv with global `pip`.

No linter or type-checker is configured; `pytest` is the only quality gate. The app entry point is `api.app:app` (built by `create_app()`).

## Architecture (the parts that need multiple files to understand)

**Local-first, AWS-portable ([ADR-0004](docs/adr/0004-local-first-aws-portable.md)).** Everything that touches an external service (LLM, persistence) sits behind a `Protocol` interface so the AWS swap changes only the implementation, never the callers. This is the reason for the seams below — respect them.

**`core/` is the only layer that touches data or the LLM.** The FastAPI app and the (future) MCP servers must go through `core`, never re-implement business rules in a transport adapter. Layers:

- **`core/forms/` — the deterministic form engine, the product's核心** ([ADR-0002](docs/adr/0002-shared-form-engine.md)). `models.py` mirrors the official `pms_form / pms_form_group / pms_form_topic / pms_topic_option` schema; topic types are **exactly the official `pms_form_topic.type` codes 1–10** (do not invent new ones — quantity is an option attribute `is_quantity`, dates are type 9). `engine.py`'s `FormSession` does topic sequencing, **skip logic** (`feature.skipLogic`, stored in the official JSONB field — no DDL changes), validation, `is_complete()`, `progress()`, and `to_feedback_content()` which emits the official `answerList` shape. **No LLM in this layer** — it is fully deterministic and unit-tested. `seed_forms.py` holds F1 修繕 / F2 團購 / F3 公設.
- **`core/clients/llm.py` — `LlmClient` Protocol + `OpenAICompatLlm`.** Reality check: locally the LLM is **NCHC's Gemma** (`gemma-4-31B-it`) over an **OpenAI-compatible** endpoint, configured in `.env` (`API_URL`, `API_KEY`, `MODEL`) — *not* Bedrock Claude yet, despite what some specs say. `get_llm()` reads `.env`. Responses often wrap JSON in ```json fences; `_extract_json` tolerates that. To try a stronger model, change `MODEL` in `.env` (the endpoint also serves `gpt-oss-120b` etc.).
- **`core/services/life_services.py` — application boundary.** `LifeServicesService` is what HTTP/MCP call; it owns inquiry business rules.
- **`core/inquiries/repository.py` — `InquiryRepository` Protocol + `SqliteInquiryRepository`.** Local SQLite at `tmp/*.sqlite3`; swappable for RDS/Postgres. Assigns ids like `INQ-YYYYMMDD-NNN` and records `inquiry_events`.
- **`core/data/regions.py`** resolves 口語 place names → official `county_code`/`district_code` from `raw_data/縣市區域範例資料.json` (normalizes 臺→台; adds a few namespaced demo districts because the sample data is a subset).

**`agent/form_agent.py` — the LLM upper layer.** Deliberate split: *questions are templated* (reliable, testable) while *answer extraction is LLM* (the hard 口語→structured-answer step). `interpret()` returns `answer | skip | unclear`; region answers come back as names and are resolved to codes here. Any LLM/parse failure degrades to `unclear` (never crashes the turn).

**`api/app.py` — FastAPI, built by `create_app(repository=, llm_factory=)`** so tests inject a fake LLM + repository. Orchestration loop in `/api/chat/message`: `interpret → submit_answer/skip → next_topic → (summary + await confirm) → persist on confirmation`. Sessions are in-memory. Responses carry `progress` and a `trace` for the UI. `DEMO_TODAY` is a fixed date so relative-date resolution and validation are reproducible regardless of the machine clock.

**`web/chat.html`** is a self-contained vanilla-JS chat harness (no build step) for manual testing. The intended production frontend is React + Vite (decided, not yet built).

## Official data & domain rules that bite

- `raw_data/` holds the official Postgres DDL + sample JSON. **Official tables are zero-modified; all new features are外掛 extension tables.** `order_type` `07` = 商城/團購 in the *actual data* ([ADR-0001](docs/adr/0001-groupbuy-per-household-orders.md)) even though the PDF legend stops at 06.
- **Scope model ([ADR-0003](docs/adr/0003-scope-as-core-attribute.md)):** shared entities carry `owner_scope` (`individual`/`group`); 個人/家庭/社區 are one mechanism (`grp`/`group_member`), not three subsystems. Don't build per-layer duplicates.
- Glossary distinctions to keep straight: **行為指紋** (identity resolution via `member_hash`) ≠ **行為軌跡** (the time-ordered event sequence).

## Environment notes

- `.env` (git-ignored) must define `API_URL`, `API_KEY`, `MODEL`; `core/config.py` loads it by explicit path (dotenv's `find_dotenv()` fails when code is run via stdin/heredoc).
- Windows console is cp950 — Chinese in terminal output may mojibake even though files are UTF-8; wrap stdout (`io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`) in one-off scripts.
- `tmp/` holds the SQLite db and throwaway analysis scripts; not part of the app.
