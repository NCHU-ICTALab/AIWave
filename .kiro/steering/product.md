# AIWave Product Steering

## Product definition

AIWave is a personal-member-centered life-service operating system and AI life butler. It connects service discovery, OPENPOINT demo scenarios, TaskDraft planning, bounded approval, Provider fulfillment, notifications, calendar projection, local life context, and completion outcomes.

The public positioning is:

> AIWave notices relevant life context and, after the member agrees, carries the work through to fulfillment.

## Product principles

1. **Demo-first, evidence-honest.** Distinguish current capability, planned work, Demo data, reasonable inference, and facts requiring official or interview validation.
2. **Foundation before innovation.** Demonstrate manual service, points, orders, Provider fulfillment, notifications, and calendar before Agent features.
3. **Natural conversation, deterministic effects.** The LLM may understand, plan, clarify, and explain naturally. The platform owns capability existence, dates, Providers, inventory, prices, points, permissions, grants, status transitions, and idempotency.
4. **Member control.** The member can edit, pause, remove, compare, switch to manual UI, or decline. External effects require a bounded ExecutionGrant.
5. **One platform state.** Manual Web, Agent, Provider workbench, and future MCP operate on the same TaskDraft, Booking/Order, StatusEvent, points, notification, and calendar state.
6. **Helpful before commercial.** Proactive messages provide useful context first. Products and services appear only after the member opens the guide and asks for help preparing.
7. **Completion over engagement.** The north-star metric is life-task completion, not chat count, dwell time, push clicks, or gamification.

## v4 Demo priorities

- Product FAQ with citations and a safe navigation action.
- Venue-based 10-minute life circle using the HNBK International Convention Center address supplied by the product owner.
- Manual booking with Demo OPENPOINT redemption and cross-page state synchronization.
- Natural multi-turn Agent with editable task package and one bounded grant.
- Provider acceptance and fulfillment feedback.
- Short Zhongyuan life-guide scenario ending at an executable recommendation, not a second checkout.
- Life outcome, one Steam-style achievement unlock, Demo reward, and completion-triggered Provider fee projection.

## Boundaries

- The member remains the authorization principal. A beneficiary does not become a joint account holder.
- New chat sessions do not inherit old conversation text and do not delete existing drafts or orders.
- Do not build background location tracking, unverified navigation, secret shopping carts, or fear-based promotion.
- Do not claim official OPENPOINT issuance, brand sponsorship, Provider rates, or live partner APIs without evidence.
- Do not copy or paraphrase third-party life-guide articles without permission.
- Achievement unlocks are delight microinteractions, not XP, levels, streaks, leaderboards, or an economy.

## Source of truth

Read in this order:

1. `docs/specs/15-agreed-product-and-platform-direction.md`
2. `docs/specs/16-proactive-life-butler-and-commercial-loop.md`
3. `docs/specs/17-conversational-agent-session-and-llm-wiki.md`
4. `CONTEXT.md`
5. Current-state and testing evidence under `docs/status/` and `docs/testing/`

Writing a feature into a spec never proves that it has been implemented.
