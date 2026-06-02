# Proposal: Bringing Smokey's Proactive-Assistant Capabilities into Firehouse

**Status:** Draft for review · **Author:** design pass · **Scope:** design + phased plan only (no implementation in this PR)

## Context

Firehouse and Smokey are sibling projects. Smokey (Kevin's single-user, microservices assistant) was partly seeded from Odysseus/Firehouse, but it grew several capabilities Firehouse lacks. This proposal ports the genuinely-new ones into Firehouse **without** adopting Smokey's architecture — Firehouse stays a layered, multi-user, owner-scoped monolith (`static/ → app.py → routes/ → src/ → services/ + mcp_servers/ → core/`). Everything below is scoped to that model and to the existing building blocks: `src/event_bus.py`, `src/task_scheduler.py`, `src/bg_jobs.py`, `core/database.py` (SQLAlchemy + `EncryptedText`), ChromaDB, the agent tool loop, the built-in MCP servers, and the ntfy/browser/email notification channels already used by notes/tasks.

### What we are NOT porting (already in Firehouse)
Chat, agent loop, memory, deep research, Cookbook hardware-fit serving, email triage, model comparison, calendar (CalDAV), skills, self-update/ops. Smokey borrowed these from Firehouse; re-porting adds nothing.

### What this proposal covers (the new capabilities)
1. **Proactive Awareness Loop** — synthesize context, evaluate triggers, push proactive notifications.
2. **Entity + Relationship Store** — structured people/facts/relationships graph with confidence scoring.
3. **Home Assistant Control** — read/control the smart home via a new integration + agent tools.
4. **Calendar-Aware Proactivity** — availability, wake-time inference, evening check-ins.
5. **Also folded in ("anything we missed"):** a **Risk-Tier Action Policy** for gating agent actions, and **Outcome Tracking** (a feedback loop that makes proactivity self-correcting). Statistical pattern-learning is noted as a future extension, not in scope here.

### Cross-cutting principles
- **Owner-scoping is mandatory.** Every new table gets an `owner` column and uses `owner_filter` (`src/auth_helpers.py`). Each feature needs `*_owner_scope`/`*_isolation` regression tests, like the rest of the app.
- **Per-user privileges.** New capabilities are gated by new privilege keys (`core/auth.py` `DEFAULT_PRIVILEGES`), default-off for the powerful ones (awareness push, home control).
- **Secrets via `EncryptedText`.** Home Assistant tokens and any integration creds are Fernet-encrypted at rest (`data/.app_key`), like email passwords.
- **Reuse, don't rebuild.** Awareness rides the existing scheduler/event-bus; entities extend `services/memory/`; notifications reuse the notes/tasks ntfy plumbing; home control is an MCP server like `email_server.py`.
- **Prompt-injection safety.** All ingested signals (calendar text, emails, HA state, web) flow through `untrusted_context_message` (`src/prompt_security.py`) — they are data, never instructions.

---

## Feature 1 — Proactive Awareness Loop

**Goal:** Move Firehouse from purely reactive (user asks → agent answers) to proactive (assistant notices something worth surfacing and reaches out), the way Smokey's `awareness` service does (signal ingestion → snapshot synthesis → trigger evaluation → ntfy push → outcome tracking).

### Where it lives
- **New subsystem:** `services/awareness/` (`service.py`, `signals.py`, `triggers.py`, `snapshot.py`, `outcomes.py`) — mirrors Smokey's `awareness/domain` but as plain modules, not a separate process.
- **Driver:** the existing in-process scheduler (`src/task_scheduler.py`) runs an `awareness_tick` on an interval (default 15 min, configurable, per-user). No new process; it's another scheduled job, started in `app.py` lifespan next to the task runner.
- **Events:** subscribe to `src/event_bus.py` so signals can also be event-driven (`email_received`, `calendar_event_soon`, `chat_created`).
- **Notifications:** reuse the notes/tasks notification path (ntfy / browser / email channels) — no new transport.

### Data model (`core/database.py`)
- `AwarenessSignal` — `id, owner, kind (calendar|email|memory|system|custom), payload(JSON), salience(float), created_at, expires_at`. Short-lived raw inputs.
- `AwarenessTrigger` — `id, owner, name, description, condition(JSON or expr), channel, enabled, risk_tier, cooldown_seconds, last_fired_at`. User- or agent-defined rules.
- `AwarenessNotification` — `id, owner, trigger_id, title, body, channel, status(sent|suppressed|failed), created_at` + outcome fields (see Feature 5).

### Flow (each tick, per user)
1. **Collect signals** from registered sources (calendar lookahead, unread/urgent email summary, memory "follow-ups", system events). Each source is small and pluggable.
2. **Synthesize a snapshot** — a compact, LLM-summarized "state of the world right now" (uses the utility model via `endpoint_resolver`), cached so repeat ticks are cheap.
3. **Evaluate triggers** against the snapshot — cheap rule checks first; only escalate to an LLM judgment for fuzzy triggers ("anything I should know before my 3pm?"). Respect per-trigger `cooldown` + a global per-user rate limit to prevent spam.
4. **Notify** via the chosen channel; record an `AwarenessNotification`.
5. (Feature 5) **Track outcome** for self-correction.

### API (`routes/awareness_routes.py`)
- `GET/POST/PATCH/DELETE /api/awareness/triggers` — manage triggers (owner-scoped, privilege `can_use_awareness`).
- `GET /api/awareness/notifications` — history/feed.
- `POST /api/awareness/tick` — admin/manual run for testing.
- `GET /api/awareness/snapshot` — current synthesized snapshot (debug/UI).

### Agent tools (`src/agent_tools.py` + section in `agent_loop.py`)
- `manage_awareness` (create/list/edit/delete triggers, e.g. "ping me 30 min before any calendar event tagged #focus").
- Awareness can also *start a chat/task* via the existing `create_session`/`manage_tasks` plumbing when a trigger warrants action, not just a notification.

### UI (`static/js/`)
- New `awareness.js` panel: trigger list + editor, notification feed, snapshot preview, enable/disable. Reuses the modal/section patterns. Sidebar entry + `/awareness` route.

### Security / safety
- Default privilege **off**; opt-in. Per-user rate limit + per-trigger cooldown. All ingested signal text wrapped as untrusted. High-risk trigger *actions* (vs. notifications) go through the Risk-Tier Policy (Feature 5).

### Tests
`tests/test_awareness_triggers.py` (evaluation + cooldown), `tests/test_awareness_owner_scope.py` (isolation), `tests/test_awareness_ratelimit.py`.

---

## Feature 2 — Entity + Relationship Store (with confidence)

**Goal:** Upgrade Firehouse's flat fact memory into a structured graph of **people / places / projects / orgs**, each with attributed **facts** that carry **confidence**, plus typed **relationships** between entities — Smokey's `memory` entity store + Beta-distribution confidence (ADR-009).

### Where it lives
- Extends `services/memory/` with `entities.py`, `entity_extractor.py`, `confidence.py`; vectors via the existing ChromaDB client (`src/chroma_client.py`, new `firehouse_entities` collection).
- Bridges to existing **Contacts** (`routes/contacts_routes.py`): a person-entity can link to a CardDAV contact rather than duplicating it.

### Data model (`core/database.py`)
- `Entity` — `id, owner, type(person|place|project|org|thing), name, aliases(JSON), contact_id?(link), created_at, updated_at`.
- `EntityFact` — `id, owner, entity_id, text, category, source(chat|email|manual|inferred), confidence(float 0–1), alpha, beta (Beta params), uses, created_at`. Confidence updates via Beta(α,β) as corroborating/contradicting evidence arrives (cheap, well-understood; ADR-009).
- `EntityRelationship` — `id, owner, src_entity_id, dst_entity_id, type(works_with|manages|spouse|member_of|located_in|...), confidence, created_at`.

### Logic
- **Extraction:** extend the existing background memory extractor (`services/memory/memory_extractor.py`) to also emit entity/relationship candidates, reusing its dedup + audit + ">50% deletion safety net" patterns.
- **Confidence:** new fact → prior Beta(1,1); each confirmation bumps α, each contradiction bumps β; surfaced confidence = α/(α+β). Audit/consolidation already exists; we extend it to merge entities and decay stale facts.
- **Recall:** hybrid keyword+vector over entities feeds the chat context preface (`chat_processor.build_context_preface`) and the agent — "who is Sam?" pulls the entity card + high-confidence facts + relationships.

### API (`routes/entity_routes.py`) + Agent tools
- `GET/POST/PATCH/DELETE /api/entities`, `/api/entities/{id}/facts`, `/api/entities/{id}/relationships`.
- Agent tool `manage_entity` (add/link/relate/list); `resolve_contact` (existing) gains entity awareness.

### UI
Extend the existing **Brain/Memory** modal (`static/js/memory.js`) with an entity inspector: entity cards with type badges, fact list with **confidence bars**, relationship links (clickable `[Name](#entity-<id>)` anchors, following Firehouse's anchor convention).

### Migration / compatibility
Existing flat memories stay as-is; entities are additive. A one-time optional backfill can promote obvious person-facts into entities (admin-triggered, reversible).

### Tests
`tests/test_entity_store.py`, `tests/test_entity_confidence.py` (Beta math), `tests/test_entity_owner_scope.py`, `tests/test_entity_extraction.py`.

---

## Feature 3 — Home Assistant Control

**Goal:** Let the agent read smart-home state and control devices (lights, scenes, alarm, climate), as Smokey does via `integration-hub`.

### Where it lives
- **New built-in MCP server:** `mcp_servers/homeassistant_server.py` (pattern: `email_server.py`). This is the cleanest fit — it exposes tools to the agent and reuses the MCP manager, auto-connect, and per-tool enable/disable already in `src/mcp_manager.py`.
- Thin service `services/homeassistant/service.py` wrapping the HA REST/WebSocket API (`httpx`).

### Config & secrets
- `HomeAssistantConfig` row (or settings entry) per owner: `base_url`, `token` (**`EncryptedText`**), `enabled`, allowed-domains/entities allowlist. Configured in Settings UI; never hardcoded.

### Agent tools (via MCP)
- `ha_list_entities` (filtered by allowlist), `ha_get_state`, `ha_call_service` (e.g. `light.turn_on`), `ha_set_alarm`. Each call is owner-scoped and checked against the allowlist.

### Security / safety (this is the highest-risk feature)
- Privilege `can_control_home` (default **off**, admin-grantable).
- **Allowlist required** — no blanket control; the agent can only touch entities/domains the user explicitly enabled.
- Every state-changing call (`ha_call_service`, alarm) is classified **high risk** and runs through the Risk-Tier Policy (Feature 5): confirmation required unless the user pre-authorized that action class.
- HA state ingested into context is untrusted data.

### UI
Settings → Integrations → Home Assistant: URL + token + "Test connection" + entity allowlist picker. Optional small dashboard card (favorite entities) — phase 2.

### Tests
`tests/test_homeassistant_adapter.py` (mock HA API; assert exact service-call payloads — Smokey's "adapter field-name" discipline is worth adopting here), `tests/test_homeassistant_allowlist.py`, `tests/test_homeassistant_owner_scope.py`.

---

## Feature 4 — Calendar-Aware Proactivity

**Goal:** Turn the existing CalDAV calendar from a passive store into a source of proactive intelligence — availability analysis, wake-time inference, pre-event nudges, evening/morning check-ins (Smokey's `availability_analyzer`, `wake_time_inferrer`, `evening_checkpoint`).

### Where it lives
- Analyzers in `services/awareness/calendar_intel.py` (depends on Feature 1's loop) reading via existing `src/caldav_sync.py` / `routes/calendar_routes.py`.
- Registers built-in awareness **signal sources** and **trigger templates** rather than new infrastructure.

### Capabilities
- **Availability analysis** — find free/busy windows; answer "when am I free this week?" and feed scheduling.
- **Wake-time inference** — infer a daily wake/active window from calendar history + interaction times; used to time morning check-ins so they don't fire at 3am.
- **Pre-event nudges** — ntfy N minutes before events (configurable per tag/calendar), with travel/prep context.
- **Evening/morning check-in** — a daily synthesized brief ("tomorrow you have X; 2 unread urgent emails; reminder Y is due"), delivered on the user's schedule.

### Integration
These are **awareness triggers + signal sources** (Feature 1) plus a couple of pure analyzers. No new tables beyond Feature 1; check-in preferences live in user prefs (`routes/prefs_routes.py`). Agent tool `manage_calendar` (existing) gains an `availability` action.

### Tests
`tests/test_availability_analyzer.py`, `tests/test_wake_time_inferrer.py`, `tests/test_calendar_checkin.py`.

---

## Feature 5 — Risk-Tier Action Policy + Outcome Tracking ("anything we missed")

Two small but high-leverage pieces that make the above safe and self-improving.

### 5a. Risk-Tier Action Policy
**Goal:** Classify agent/awareness actions by risk and gate accordingly (Smokey ADR-010). Firehouse has privileges (can/can't) but no graduated *per-action* risk model — important once the agent can control the home and act proactively.

- **Where:** `src/policy.py` + a hook in the agent tool dispatch (`src/agent_tools.py` / `agent_loop.py`).
- **Model:** each tool/action maps to a tier — `low` (read-only: search, list), `medium` (writes to user data: create doc, add memory), `high` (outward/irreversible: send email, control home, bulk delete, spend). Tiers are data-driven and overridable per user.
- **Gating:** `low` auto-runs; `medium` runs but is logged; `high` requires confirmation **unless** the user pre-authorized that action class (a standing grant) — surfaced in chat as an accept/deny, and for proactive (no-user-present) runs, high-risk actions are deferred to a notification asking for approval.
- **Tests:** `tests/test_policy_tiers.py`, `tests/test_policy_high_risk_confirmation.py`.

### 5b. Outcome Tracking (feedback loop)
**Goal:** Make proactivity self-correcting (Smokey's `outcome_tracker`). Each proactive notification can be marked useful/not (one-tap in the feed, or inferred from whether the user acted). Stored on `AwarenessNotification`; trigger salience/thresholds adjust over time (reuse the Beta-confidence machinery from Feature 2). Prevents notification fatigue.
- **Tests:** `tests/test_awareness_outcomes.py`.

> **Deferred (not in scope):** full statistical pattern-learning / skill-distillation as a service (Smokey ADR-008). Firehouse already has skills + teacher escalation; revisit after the above lands.

---

## Phased Rollout

Ordered by dependency and risk. Each phase is independently shippable (small, focused PRs per Firehouse `CONTRIBUTING.md`), with `pytest` + `py_compile` + `node --check` per change.

### Phase 0 — Foundations (enables everything)
- DB models + migrations for awareness + entities (additive, owner-scoped).
- New privilege keys (default-off): `can_use_awareness`, `can_control_home`.
- `src/policy.py` risk-tier scaffold (tiers defined, enforcement behind a flag).
- **Deliverable:** schema + policy skeleton + tests. No behavior change yet.

### Phase 1 — Entity + Relationship Store (Feature 2)
- Extend memory extractor; confidence math; entity API + `manage_entity` tool; Brain-modal entity inspector.
- Lowest external risk, immediately useful, and feeds later context. **Recommended first user-visible feature.**

### Phase 2 — Awareness Loop core (Feature 1)
- Scheduler tick + signal/snapshot/trigger pipeline; trigger CRUD API + `manage_awareness` tool; notification feed UI; reuse ntfy.
- Wire Outcome Tracking (5b) in from the start.

### Phase 3 — Calendar-Aware Proactivity (Feature 4)
- Availability analyzer, wake-time inference, pre-event nudges, daily check-in — all as awareness signal sources/triggers on top of Phase 2.

### Phase 4 — Home Assistant Control (Feature 3) + full Risk-Tier enforcement (5a)
- MCP server + service + encrypted config + allowlist + Settings UI.
- Turn on Risk-Tier confirmation for `high` actions (gates HA + outward actions). Highest risk, so it ships last behind the now-proven policy layer.

### Phase 5 — Polish
- Dashboards, outcome-driven trigger tuning, optional memory→entity backfill, docs.

---

## Decisions (review feedback)
1. **Notification channel default — DECIDED: ntfy** (bundled), user-configurable per trigger.
2. **Awareness LLM cost — DECIDED.** Cost-control stack: **utility model only**, **change-detection cache** (skip LLM when inputs are unchanged), **opt-in gating** (only users with `can_use_awareness` and ≥1 enabled trigger), **rule-first triggers** (LLM only for fuzzy ones), and **active-window gating** (no off-hours polling).
   - **Interval:** exposed as a per-user **Settings** option, **default 15 min**.
   - **Token budget:** the per-user daily budget mechanism is **built but unlimited by default** (admins opt in to a ceiling); when a ceiling is set and exceeded, the loop falls back to rule-only triggers for the rest of the day and logs it.
3. **Entity backfill — DECIDED: start clean.** No auto-promotion of existing flat memories; an optional admin-triggered backfill may be added later.
4. **Home Assistant transport — DECIDED: REST first, then WebSocket.** Ship REST in Phase 4; add the WebSocket state stream (real-time triggers) in Phase 5. Design the HA service so the transport is swappable behind the port.
5. **Multi-user — DECIDED: adhere to Firehouse.** All features are per-user and owner-scoped (not global/single-user), consistent with the rest of the app.

## Non-goals
- No microservices split, NATS, Qdrant, or separate observability stack — Firehouse stays a monolith with ChromaDB + SQLite.
- No change to existing chat/agent/memory behavior for users who don't opt in.

## Implementation status & operating flags

Backend shipped across Phases 0–5 (all opt-in; `main` unaffected until enabled):

| Phase | What | How to turn on |
|---|---|---|
| 0 | Schema, privileges, risk-policy skeleton | — (inert) |
| 1 | Entity + relationship store (`/api/entities`) | privilege `can_manage_memory` |
| 2 | Awareness loop (triggers, ticks, notifications, outcomes) | `FIREHOUSE_AWARENESS=1` + privilege `can_use_awareness` + ≥1 enabled trigger |
| 3 | Calendar signals feeding the snapshot | (part of awareness) |
| 4 | Home Assistant control (`/api/homeassistant/*`) | privilege `can_control_home` + configured/enabled HA + allowlist |
| 5 | Outcome-driven trigger auto-pause | (part of awareness) |

**Environment flags**
- `FIREHOUSE_AWARENESS` (default off) — runs the background awareness tick loop.
- `FIREHOUSE_RISK_POLICY` (default off) — enforces HIGH-risk confirmation (e.g. `ha_call_service` needs `confirm=true`).

**Settings keys**
- `awareness_interval_seconds` (default 900) — tick cadence.
- `awareness_daily_notification_limit` (default 0 = unlimited) — per-user/day cap.
- `reminder_channel` (existing) — also used for awareness notifications (ntfy/browser/email).

**Privileges (default off):** `can_use_awareness`, `can_control_home`.

**Still open (front-end + enhancements):** the vanilla-JS UI panels (awareness triggers + notification feed, entity inspector in the Brain modal, Home Assistant settings), the optional `homeassistant` MCP server + HA WebSocket state stream, LLM snapshot synthesis + fuzzy-trigger judge, and the optional memory→entity backfill. These were intentionally not built blind — they need a session that can run the app to verify behavior.
