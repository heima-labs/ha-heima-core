# Heima v2.1 — Development Plan

**Spec:** `docs/specs/heima_v2_spec.md` (v2.1.0-draft)
**Branch:** `feat/v2`
**Solo developer:** Stefano — no backward compatibility with v1 required during development.

---

## How to use this document

This file is the single source of truth for development state.
**Any agent (Claude, Codex, or other) starting a new session must:**

1. Read this file in full.
2. Go to [Current State](#current-state) — it tells you exactly where development is and what to do next.
3. Read the relevant Phase section below for deliverables and acceptance criteria.
4. Read the referenced spec section for full contracts and interface definitions.
5. Run `cd /Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component && git status` to verify the branch.

**Do not make architectural decisions not already in the spec.** If something is ambiguous, stop and ask the developer before implementing.

---

## Repository layout

```
custom_components/heima/     ← integration root
  runtime/                   ← engine, domains, analyzers, reactions, behaviors
    domains/                 ← PeopleDomain, OccupancyDomain, CalendarDomain, HouseStateDomain,
                               LightingDomain, HeatingDomain, SecurityDomain (v1 hardcoded DAG)
    analyzers/               ← IBehaviorAnalyzer impls (v1: unregistered, called directly)
    reactions/               ← HeimaReaction impls
    behaviors/               ← HeimaBehavior impls
    normalization/           ← InputNormalizer
    engine.py                ← core evaluation loop (1629 lines — rewrite in v2)
    contracts.py             ← HeimaEvent, ApplyStep, ApplyPlan (78 lines)
    proposal_engine.py       ← ProposalEngine
    event_store.py           ← EventStore
    snapshot.py / snapshot_buffer.py
  coordinator.py             ← HA DataUpdateCoordinator wrapper (647 lines)
  config_flow/               ← Options flow steps
  entities/                  ← HA entity wrappers
  models.py / const.py
tests/                       ← 660 tests (all must pass at end of each phase)
docs/specs/                  ← canonical specs
```

---

## Running tests

```bash
cd /Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component
pytest tests/ -x -q
```

All 660 tests must pass at the **end** of each phase. Tests may be temporarily broken mid-phase.

---

## Architecture non-negotiables

These constraints must never be violated. See spec §16 for rationale.

| # | Rule |
|---|---|
| 1 | No ML libraries. Pure Python stdlib only in all built-in code. |
| 2 | No blocking I/O on the hot path (`infer()`, `detect()`, invariant checks, hysteresis). |
| 3 | HA async patterns: coroutines for I/O, `async_call_later` for off-cycle tasks. |
| 4 | DAG resolved once at startup via `finalize_dag()`. Cycle errors are fatal at load. |
| 5 | `CanonicalState` stays generic key/value. Plugin state namespaced as `plugin_id.key`. |
| 6 | Core domains (People, Occupancy, **Activity**, HouseState) are NOT plugins. Fixed order. |
| 7 | `IInvariantCheck` must not read EventStore or SnapshotStore. O(1) only. |
| 8 | `InferenceSignal` objects are additive hints. They never override user overrides or safety guards. |
| 9 | All persistent stores use HA `Store`. Current Phase D key: `heima_snapshots`. Approval persistence key `heima_inference_approvals` is reserved for Phase F. |
| 10 | Phase A is behavior-preserving: zero observable behavior change, all 660 tests green. |
| 11 | Time is context, not trigger. Evaluation is driven by state changes + 300s fallback. |
| 12 | `Activity.context: dict[str, Any]` is the only forward-compatibility hook on Activity. Keys namespaced by contributor. |
| 13 | Composite activities always require user approval before `ActivityInferenceModule` emits signals. |
| 14 | Recovery state (see `core/runtime_checkpoint_and_power_recovery_spec.md`) is engine context computed pre-DAG, like time (#11) — not a domain, not a plugin, exempt from the previous-cycle CanonicalState rule. Cross-cutting runtime facilities (Scheduler, Manual Hold Manager, Recovery/Checkpoint) sit outside the DAG. |

---

## Phase overview

| Phase | Title | Status | Depends on |
|---|---|---|---|
| A | Plugin Framework | `DONE` | — |
| B | IBehaviorAnalyzer + FindingRouter | `DONE` | A |
| C | IInvariantCheck | `DONE` | A |
| D | InferenceEngine v2 (base) | `DONE` | A |
| E | OutcomeTracker + Feedback Loop | `DONE` | D |
| F | ActivityDomain | `DONE` | A, D |
| G | Role model + product constraints | `DONE` | — |
| H | House State Learning | `DONE` | D, E, G |
| I | Activity Inference and Learning | `DONE` | D, H, F |
| J | Event-Driven Trigger | `DONE` | F |
| K | Installer alert channel + health entity | `DONE` | C |
| L | Auto-discovery config flow | `DONE` | — |
| M | Installation validation | `DONE` | L |
| N | Semantic Policy Suggestions | `DONE` | A |
| O | HouseSnapshot Alignment + Proposal Revocation | `DONE` | N |
| P | Learning Modules D2: Lighting, Room Correlation, Occupancy | `DONE` | D, F |
| Q | AnomalyAnalyzer: Statistical Detection Rules | `DONE` | O, P |
| R | OutcomeTracker Positive Feedback + WeekdayStateModule Consolidation | `DONE` | E, P |
| S | Learning Module Threshold Configurability | `DONE` | R |
| T | Learning Signal Analyzers | `DEFERRED` | P, S |
| U | Physical Light State Awareness | `DONE` | A, Q |
| V | Signal Discovery Pipeline | `DONE` | N, L |
| W | Calendar: day_off and holiday categories | `DONE` | — |
| X | Room Context Model | `DONE` | U, V |
| Y | HouseStateInferenceModule: tiered feature enrichment | `DONE` | X |
| Z | Activity cold start mitigation | `DONE` | S |
| AA | Global drift detection | `DONE` | Y |
| AB | Smart Lighting Automation (Unified) | `PLANNED` | U, X |
| AC | Proposal Review Grouping | `DONE` | H, Y |
| AD | Proposal/Reaction Lifecycle Management | `DONE` | AC, H, Y |
| AE | Camera Privacy Guard & Extensible Entity Actions | `DONE` | AD, MH |
| MH | Manual Hold Framework | `DONE` | AB, AE |
| AF | Policy Editor Framework + Camera Privacy Policy UI | `DONE` | AE, MH |
| AG | Translate Developer Scripts, Docs, and Specs to English | `DONE` | AF |
| AH | Resident Runtime Confirmation & Auto-Apply Promotion | `DONE` | AD, MH, AF |
| AN | Notification Admin UI & Execution Policy Profiles | `DONE` | AH |
| AO | Admin Observability Panel | `DONE` | AH, AN, MH, AC, AD |
| AO8 | Observability Usability & Detail Views | `DONE` | AO |
| AO9 | Entity Impact Inspector | `PLANNED` | AO8 |
| AO10 | Focused Why-Not-Now Evaluation | `PLANNED` | AO8 |
| AP | Notification Delivery Policy | `DONE` | AH, AN, AO |
| AQ | Runtime Checkpoint and Power Recovery | `PLANNED` | AH, MH, AO, AP |

---

## Current State

**Last completed phases:** Phase E — OutcomeTracker + Feedback Loop; Phase F — ActivityDomain; Phase G — Role model + product constraints; Phase H — House State Learning; Phase I — Activity Inference and Learning; Phase J — Event-Driven Trigger; Phase K — Installer alert channel + health entity; Phase L — Auto-discovery config flow; Phase M — Installation validation; Phase N — Semantic Policy Suggestions; Phase O — HouseSnapshot Alignment + Proposal Revocation; Phase P — Learning Modules D2; Phase Q — AnomalyAnalyzer Statistical Detection Rules; Phase R — OutcomeTracker Positive Feedback + WeekdayStateModule Consolidation; Phase S — Learning Module Threshold Configurability; Phase U — Physical Light State Awareness; Phase V — Signal Discovery Pipeline; Phase W — Calendar day_off and holiday categories; Phase X — Room Context Model; Phase Y — HouseStateInferenceModule tiered feature enrichment; Phase Z — Activity cold start mitigation; Phase AA — Global drift detection; Phase AC — Proposal Review Grouping; Phase AD — Proposal/Reaction Lifecycle Management; Phase MH — Manual Hold Framework; Phase AE — Camera Privacy Guard & Extensible Entity Actions; Phase AF — Policy Editor Framework + Camera Privacy Policy UI; Phase AG — Translate Developer Scripts, Docs, and Specs to English; Phase AH — Resident Runtime Confirmation & Auto-Apply Promotion; Phase AN — Notification Admin UI & Execution Policy Profiles; Phase AO — Admin Observability Panel; Phase AO8 — Observability Usability & Detail Views; Phase AP — Notification Delivery Policy.
**Active slice:** Phase AQ — Runtime Checkpoint and Power Recovery, AQ1-AQ8 implemented; AQ8
live-safe and destructive opt-in validation passed, while the full diagnostic tier is blocked by
unrelated live test 074.
**Branch:** `feat/aq-runtime-checkpoint-recovery`.
**Next action:**
Investigate `074_camera_privacy_manual_hold_live.py` scenario C, which reports
`external_on` while expecting `external_off`.

### Phase AO — Admin Observability Panel

- Status: `DONE`.
- Spec source: `docs/specs/core/admin_observability_panel_spec.md`.
- Goal: provide a real Home Assistant admin panel that explains what Heima is doing, why runtime
  decisions apply/skip/block/wait, what is being learned, and which manual holds, runtime
  confirmations, notification routes, and proposal groups are affecting behavior.
- Product boundary:
  - AO is not an Options Flow diagnostic page.
  - AO1-AO6 are read-only except for navigation/deep links to existing configuration surfaces.
  - AO7 is the first slice allowed to introduce mutations, and only through existing backend
    action boundaries.
  - The panel must be domain-agnostic. Domain-specific details may be rendered only from
    structured extensions supplied by the backend.
- Branch: `feat/ao-admin-observability-panel`.
- AO1 initial implementation completed:
  - Added `custom_components/heima/observability.py` with a versioned read-only snapshot contract.
  - Added redaction that preserves local entity IDs while redacting tokens, credentials, auth
    headers, and sensitive strings.
  - Added `custom_components/heima/websocket_api.py` with an HA-admin-only
    `heima/observability/snapshot` websocket command.
  - Registered the websocket API once during integration setup.
  - Added unit coverage in `tests/test_observability.py` for minimal schema, partial snapshots,
    redaction, admin authorization, successful snapshot response, and missing entry errors.
  - Verification:
    - `.venv/bin/python -m pytest tests/test_observability.py -q` — 6 passed.
    - `.venv/bin/ruff check custom_components/heima/observability.py custom_components/heima/websocket_api.py custom_components/heima/__init__.py tests/test_observability.py`
      — passed.
- AO2 initial implementation completed:
  - Added `custom_components/heima/runtime/observability.py` with bounded in-memory runtime
    activity and decision trace buffers.
  - Runtime traces are exposed through the AO snapshot under `recent_events` and
    `decision_traces`; retention metadata is marked as `history_since_last_restart`.
  - The engine records filtered apply-plan outcomes for applied, skipped, and blocked steps.
  - Runtime confirmation occurrences record a `waiting` trace when a request is created and an
    apply/block/skip trace when approved or timeout-applied execution is processed.
  - Added unit coverage in `tests/test_runtime_observability.py` for applied/blocked/skipped
    traces, runtime confirmation waiting/apply traces, and bounded retention.
  - Extended AO snapshot tests to verify propagation of runtime events/traces.
  - Verification:
    - `.venv/bin/python -m pytest tests/test_observability.py tests/test_runtime_observability.py tests/test_reaction_framework.py tests/test_manual_hold_manager.py tests/test_runtime_confirmation.py -q`
      — 68 passed.
    - `.venv/bin/ruff check custom_components/heima/observability.py custom_components/heima/runtime/observability.py custom_components/heima/runtime/engine.py tests/test_observability.py tests/test_runtime_observability.py`
      — passed.
- AO3 initial implementation completed:
  - Added `custom_components/heima/panel.py` to register/unregister the custom HA admin panel.
  - The panel serves local integration-owned frontend assets from `/heima_static`.
  - The panel module URL includes a content-hash query parameter so browser caches refresh when the
    JavaScript asset changes.
  - Added `custom_components/heima/frontend/heima-admin-panel.js` as a read-only web component
    shell with Overview, Runtime Activity, and Health routes.
  - The frontend consumes only the AO websocket snapshot command and handles loading, error,
    empty, partial, and refresh states.
  - Integration setup registers services, websocket API, and admin panel only once; unloading the
    last entry unregisters the panel.
  - Added unit coverage in `tests/test_admin_panel.py` for panel registration, unload, setup
    idempotency, and asset contract.
  - Verification:
    - `.venv/bin/python -m pytest tests/test_admin_panel.py tests/test_observability.py tests/test_runtime_observability.py -q`
      — 15 passed.
    - `.venv/bin/ruff check custom_components/heima/__init__.py custom_components/heima/panel.py tests/test_admin_panel.py`
      — passed.
- AO4 initial implementation completed:
  - Reaction snapshot rows now include latest trace outcome/id and linked active manual hold scopes.
  - Manual hold snapshot rows now include affected reaction IDs and structured links back to
    reactions/source entities when trace data supports that relationship.
  - The custom admin panel now includes read-only `Reactions` and `Holds` sections.
  - The Reaction Inspector shows ID, type, origin, enabled/muted status, effective execution policy,
    latest outcome, latest trace, and linked holds.
  - The Manual Hold Center shows active hold count, pending apply count, scope, reason, release
    policy, age, source entity, and affected reactions.
  - Added/extended unit coverage in `tests/test_observability.py` and `tests/test_admin_panel.py`.
  - Verification:
    - `.venv/bin/python -m pytest tests/test_admin_panel.py tests/test_observability.py tests/test_runtime_observability.py -q`
      — 15 passed.
    - `.venv/bin/ruff check custom_components/heima/observability.py custom_components/heima/__init__.py custom_components/heima/panel.py tests/test_admin_panel.py tests/test_observability.py`
      — passed.
- AO5 initial implementation completed:
  - Runtime confirmation snapshot now exposes pending, recent completed, stale response,
    duplicate occurrence, completed status, completed step count, blocked/failed/skipped reason,
    scheduled timeout, action subscription, and promotion review state.
  - Notification snapshot now resolves `route_targets` through recipients and recipient groups,
    distinguishes actionable routes from text-only routes, and reports unresolved targets.
  - The custom admin panel now includes read-only `Confirmations` and `Notifications` sections.
  - Runtime Confirmation Center shows pending/completed requests, timeout behavior, targets, apply
    result counts, stale responses, and promotion reviews.
  - Notification Routing Inspector shows recipients, groups, resolved `notify.*` services,
    actionable capability, text-only skipped routes, and unresolved targets.
  - Added/extended unit coverage in `tests/test_observability.py` and `tests/test_admin_panel.py`.
  - Verification:
    - `.venv/bin/python -m pytest tests/test_admin_panel.py tests/test_observability.py tests/test_runtime_observability.py -q`
      — 15 passed.
    - `.venv/bin/ruff check custom_components/heima/observability.py tests/test_admin_panel.py tests/test_observability.py`
      — passed.
- AO6 initial implementation completed:
  - Learning snapshot now exposes module rows, module readiness counts, proposal totals, analyzer
    failures, analyzer output errors, and lifecycle monitoring data.
  - Proposal snapshot now exposes backend-source-of-truth review rows, temporal bundles, real
    pending count, visible pending count, suppressed pending count, stale count, type counters,
    follow-up counters, visible examples, and suppressed examples.
  - The custom admin panel now includes read-only `Learning` and `Proposals` sections.
  - Proposal grouping and temporal bundle rendering use backend diagnostics as the source of truth;
    the frontend does not recompute grouping or visibility.
  - Added/extended unit coverage in `tests/test_observability.py` and `tests/test_admin_panel.py`.
  - Verification:
    - `.venv/bin/python -m pytest tests/test_admin_panel.py tests/test_observability.py tests/test_runtime_observability.py -q`
      — 15 passed.
    - `.venv/bin/ruff check custom_components/heima/observability.py tests/test_admin_panel.py tests/test_observability.py`
      — passed.
    - `.venv/bin/ruff format --check custom_components/heima/observability.py tests/test_admin_panel.py tests/test_observability.py`
      — passed.
- AO7 completed:
  - Added an HA-admin-only `heima/observability/action` websocket command.
  - Added the first allowlisted mutation, `clear_manual_hold`, implemented through the existing
    engine manual-hold boundary.
  - Added allowlisted runtime promotion review actions through the existing coordinator
    `async_review_runtime_promotion` boundary.
  - Added runtime confirmation promotion-state reset through the existing coordinator
    `async_reset_runtime_confirmation_promotion_state` boundary.
  - Added proposal review actions through the existing coordinator `async_review_proposal` boundary.
  - Added house-state proposal bundle review through the existing coordinator
    `async_review_house_state_proposal_batch` boundary, including dismiss-similar semantics.
  - Actions validate payload shape, return an updated observability snapshot, await the existing
    backend boundary, and record `admin_action` events in the runtime observability buffer.
  - The custom admin panel now shows an explicit confirmed `Clear` action for parseable manual hold
    scopes, confirmed promotion review/reset actions for pending promotion reviews, and confirmed
    proposal accept/reject/bundle actions for proposal review rows.
  - AO7 remains intentionally narrow: health finding acknowledgements are not implemented because
    the spec excludes acknowledgement from the MVP and no persisted acknowledgement boundary exists.
  - Added/extended unit coverage in `tests/test_observability.py`,
    `tests/test_runtime_observability.py`, and `tests/test_admin_panel.py`.
  - Verification:
    - `.venv/bin/python -m pytest tests/test_observability.py tests/test_runtime_observability.py tests/test_admin_panel.py -q`
      — 26 passed.
    - `.venv/bin/ruff check custom_components/heima/websocket_api.py custom_components/heima/runtime/observability.py tests/test_observability.py tests/test_runtime_observability.py tests/test_admin_panel.py`
      — passed.
    - `.venv/bin/ruff format --check custom_components/heima/websocket_api.py custom_components/heima/runtime/observability.py tests/test_observability.py tests/test_runtime_observability.py tests/test_admin_panel.py`
      — passed.
- AO live validation completed:
  - Added `scripts/live_tests/080_admin_observability_panel_live.py` to validate the AO websocket
    snapshot/action contract against a real Home Assistant instance.
  - Added `080_admin_observability_panel_live.py` to the diagnostic live tier.
  - Fixed `scripts/lib/ha_websocket.py` to support fragmented websocket messages emitted by large
    AO snapshots.
  - Fixed AO runtime-confirmation snapshot normalization so real diagnostics counts
    (`pending`/`recent_completed`) are kept separate from request rows
    (`pending_requests`/`recent_completed_requests`).
  - Verification:
    - `.venv/bin/python -m pytest tests/test_observability.py tests/test_runtime_observability.py tests/test_admin_panel.py -q`
      — 26 passed.
    - `.venv/bin/ruff check custom_components/heima/observability.py scripts/lib/ha_websocket.py scripts/live_tests/080_admin_observability_panel_live.py tests/test_observability.py`
      — passed.
    - `.venv/bin/ruff format --check custom_components/heima/observability.py scripts/lib/ha_websocket.py scripts/live_tests/080_admin_observability_panel_live.py tests/test_observability.py`
      — passed.
    - `scripts/live_tests/080_admin_observability_panel_live.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" ${HA_NON_ADMIN_TOKEN:+--ha-non-admin-token "$HA_NON_ADMIN_TOKEN"}`
      — passed against the local Docker Home Assistant instance.
    - `./scripts/check_all_live.sh --tier diagnostic`
      — passed against the local Docker Home Assistant instance.

#### AO1 — Backend Observability Snapshot Contract

- Deliverables:
  - Define versioned snapshot contracts for `meta`, `health_findings`, `recent_events`,
    `decision_traces`, `reactions`, `manual_holds`, `runtime_confirmations`, `notifications`,
    `learning`, and `proposals`.
  - Build a read-only aggregator that normalizes existing diagnostics into the snapshot contract.
  - Add redaction helpers or reuse existing diagnostic redaction consistently.
  - Add a HA-admin-only websocket/API boundary for retrieving the full snapshot and basic
    projections.
  - Ensure missing internal subsystems produce explicit partial/unavailable sections instead of
    crashing the panel API.
- Tests:
  - unit tests for snapshot schema shape and versioning
  - redaction tests for secrets/tokens/free-form sensitive values
  - authorization tests for admin and non-admin access
  - partial-snapshot tests for missing/disabled subsystems
  - serialization/backward-compatibility tests for unknown/missing sections
- Acceptance criteria:
  - an HA admin can retrieve a redacted snapshot from the API
  - a non-admin receives an authorization error and no partial data
  - existing config-entry diagnostics remain separate and continue to work

#### AO2 — Runtime Activity and Decision Trace Foundation

- Deliverables:
  - Add a bounded in-memory observability event/trace buffer.
  - Emit structured runtime events for reaction match/apply/skip/block/wait/fail outcomes.
  - Link traces to reaction IDs, apply step IDs, manual hold scopes, runtime request IDs, and
    affected entity IDs when available.
  - Add focused "why not now?" projection support for a single reaction without emitting full
    per-reaction non-match traces on every cycle.
  - Mark retention as "history since last restart" in snapshot metadata.
- Tests:
  - trace buffer retention and ordering tests
  - decision trace construction tests for applied, skipped, blocked, waiting, and failed outcomes
  - manual-hold-blocked apply-step tests
  - dependency-blocked apply-step tests
  - focused non-match query tests
- Acceptance criteria:
  - traces explain real runtime outcomes without requiring log inspection
  - trace volume is bounded and does not emit every non-match by default
  - restart volatility is explicit in the snapshot

#### AO3 — Custom HA Admin Panel Shell

- Deliverables:
  - Register and unload a Home Assistant custom panel during integration setup/unload.
  - Serve integration-owned frontend assets.
  - Implement read-only routes for Overview, Runtime Activity, and Health.
  - Consume only the AO snapshot/API contract, not internal engine structures.
  - Add basic frontend error, loading, empty, partial, and unavailable states.
- Tests:
  - panel registration/unload tests
  - websocket/API smoke tests through the panel data boundary
  - frontend build/static asset tests where supported by the project tooling
  - route smoke tests for Overview, Runtime Activity, and Health
- Acceptance criteria:
  - HA admins can open the panel from Home Assistant
  - the first screen answers current engine health, active holds, pending confirmations, recent
    activity, proposal counts, and notification health at a glance
  - non-admin users cannot access panel data through direct API calls

#### AO4 — Reaction and Manual Hold Inspectors

- Deliverables:
  - Implement reaction list/detail projections.
  - Show configured source data, normalized/effective data, generated apply-step shape, effective
    execution policy, runtime-confirmation descriptor status, linked manual hold scopes, and latest
    outcomes.
  - Implement Manual Hold Center with scope, reason, release policy, age, expiration/release trigger,
    source entity, and affected reactions/apply steps.
  - Keep clear-hold behavior out of AO4; only explain whether a hold would be admin-clearable in
    future AO7 actions.
- Tests:
  - reaction inspector projection tests for admin-authored, learned, muted, and broken reactions
  - execution-policy resolution display tests
  - manual hold inspector tests for entity, domain, and reaction scopes
  - read-only enforcement tests
- Acceptance criteria:
  - an admin can inspect why a configured reaction is active, muted, waiting, blocked, or broken
  - an admin can inspect why a manual hold is active and what will release it

#### AO5 — Runtime Confirmation and Notification Inspectors

- Deliverables:
  - Implement Runtime Confirmation Center projections for pending, recent completed, stale response,
    timeout-applied, timeout-skipped, and promotion-review states.
  - Implement Notification Routing Inspector for recipients, groups, routes, concrete `notify.*`
    services, `supports_actions`, unresolved targets, skipped non-actionable routes, and recent
    delivery attempts.
  - Explain the difference between resident approval, admin promotion approval, and proposal
    acceptance.
- Tests:
  - runtime confirmation inspector tests for approve/dismiss/timeout states
  - promotion cooldown/review projection tests
  - notification route resolution tests for recipients, groups, default route targets, and
    non-actionable services
  - live diagnostic test for an actionable and non-actionable notification route
- Acceptance criteria:
  - an admin can see where a runtime confirmation was sent and why some targets were skipped
  - an admin can tell whether a reaction is waiting for resident response, promotion review, or
    normal auto-apply

#### AO6 — Learning and Proposal Transparency

- Deliverables:
  - Implement Learning Monitor projections for learning families, evidence growth, generated
    proposals, suppressed proposals, visible representatives, stale proposals, and accepted/rejected
    history.
  - Implement Proposal Backlog Inspector projections using existing proposal lifecycle and TB
    grouping semantics as the source of truth.
  - Show real pending proposal count, visible representative count, suppressed-by-group count,
    rejected bundle count, and dismissed similar count.
  - Explain what accept representative, reject bundle, dismiss similar, expand, and skip mean before
    the admin acts in existing review surfaces.
- Tests:
  - proposal grouping projection tests using existing TB fixtures
  - representative-vs-real-count tests
  - hidden/suppressed/stale proposal tests
  - live diagnostic test covering proposal review-row counts and top review groups
- Acceptance criteria:
  - the panel explains why a proposal is visible or hidden
  - proposal counts match backend diagnostics and do not rely on frontend recomputation

#### AO7 — Safe Admin Actions

- Deliverables:
  - Add only after AO1-AO6 are stable.
  - Add safe actions through existing backend boundaries:
    - open/edit existing policy or reaction surfaces
    - open proposal review
    - clear admin-clearable manual hold
    - reset runtime confirmation stats
    - review promotion
    - acknowledge non-critical findings
  - Add server-side HA-admin checks and admin audit events for every mutation.
  - Require confirmation for destructive or behavior-changing actions.
- Tests:
  - authorization tests for every action
  - audit event tests
  - action-boundary tests proving frontend does not mutate internal state directly
  - regression tests for existing options-flow/admin action behavior
- Acceptance criteria:
  - mutations are optional, explicit, audited, and reuse existing domain boundaries
  - AO remains an observability panel, not an automation builder

#### AO Live Validation

- Required live tests before closing AO MVP:
  - camera privacy policy decision trace for armed/disarmed alarm transitions
  - manual hold active/release trace
  - runtime confirmation pending/resolved trace
  - notification routing trace with actionable and non-actionable services
  - proposal backlog grouping counts compared with `scripts/proposal_backlog_audit.py`
  - panel API authorization check for admin and non-admin tokens
- Local CI before each AO commit:
  - targeted pytest for the touched AO slice
  - `python3 -m pytest tests/test_options_flow_e2e.py tests/test_runtime_confirmation.py`
    when touching notifications/runtime confirmation projections
  - full local CI before merging AO MVP
  - live diagnostic tier before merging AO MVP
- Status: completed for AO MVP on `feat/ao-admin-observability-panel`; full CI remains required
  before merging the branch after user MVP verification.

### Planned AO Extensions

These extensions are specified in `docs/specs/core/admin_observability_panel_spec.md` and should be
implemented only if we choose to extend the MVP before merging, or as follow-up branches after AO
MVP merge.

#### AO8 — Observability Usability & Detail Views

- Status: `DONE`.
- Goal: make the MVP panel production-usable without adding new mutation types.
- Product boundary:
  - AO8 must not add new mutation types.
  - AO8 must improve the existing AO panel using the existing redacted snapshot, or backend
    projections derived from the same canonical observability data.
  - The frontend may filter local table rows for display, but it must not recompute authoritative
    proposal grouping, entity relationships, or runtime semantics.
- AO8.1 backend detail projections:
  - Add projection helpers for reaction, manual-hold, runtime-confirmation, and proposal/review
    detail rows when the existing snapshot is insufficient.
  - Keep configured metadata, runtime diagnostics, traces, linked holds, linked requests, proposal
    source metadata, and execution-policy data clearly separated.
  - Preserve the existing redaction path for every projection.
  - Tests:
    - unit tests for reaction detail projection completeness
    - unit tests for manual-hold and runtime-confirmation link projection
    - unit tests proving missing diagnostics degrade to explicit unavailable/empty fields
    - redaction regression tests for projection payloads
- AO8.2 frontend detail views and readable layout:
  - Add detail drawer or route for reactions, manual holds, runtime confirmations, and
    proposal/review rows.
  - Improve table layout so long IDs, badges, execution-policy labels, trace IDs, and source
    metadata remain readable on desktop/tablet widths.
  - Show raw redacted JSON only as secondary advanced-debugging material.
  - Tests:
    - frontend/static smoke tests for each detail affordance
    - layout smoke tests covering long reaction IDs and execution-policy labels
    - unit/static tests for graceful empty/unavailable states
- AO8.3 filters, search, copy buttons, and deep links:
  - Add filters/search for reactions, traces/events, holds, confirmations, and proposals.
  - Add copy buttons for reaction IDs, trace IDs, entity IDs, request IDs, hold scopes, and review
    IDs where present.
  - Add stable custom-panel deep links for route plus object ID.
  - Tests:
    - frontend/static tests for filter controls and local row filtering
    - tests proving filters do not change backend counts or grouping semantics
    - smoke tests for copy-button wiring and deep-link route parsing
- AO8.4 redacted snapshot export:
  - Add both download JSON and copy-to-clipboard export actions.
  - Both actions must serialize the exact same redacted snapshot object currently available to the
    panel.
  - Do not expose secrets, tokens, credentials, raw auth headers, or sensitive free-form values.
  - Tests:
    - snapshot export redaction tests for download payloads
    - snapshot export redaction tests for clipboard payloads
    - test proving both export paths use the same serialized redacted object
- AO8.5 house-state resolver diagnostics:
  - Add a top-level `house_state` AO snapshot projection sourced from the existing house-state
    runtime domain diagnostics.
  - Expose `candidate_trace`, `candidate_summary`, and `resolution_trace` without making the
    frontend infer resolver semantics from unrelated runtime fields.
  - Add a House State panel section showing current state/reason, decision action, target state,
    winning reason, active candidates, pending candidate, resolution path, timers, override state,
    and a searchable candidate table.
  - Tests:
    - unit snapshot contract coverage for the projected house-state fields
    - frontend/static smoke coverage for the House State route and candidate search
    - live `080` contract coverage requiring the house-state diagnostics dictionaries
- Live validation:
  - Extend live `080` so at least one real reaction has label/type/origin/source metadata, latest
    trace info where available, linked holds where available, and no unreadable `unknown`-only row.
  - Verify filters/search and at least one detail route against the running HA test instance.
- Acceptance:
  - an admin can inspect one reaction without reading raw JSON
  - an admin can inspect one hold, confirmation, and proposal/review row from the panel
  - high-volume tables can be filtered/searched without changing backend semantics
  - long IDs and badges remain readable
  - download and clipboard export use the same redacted snapshot payload as the panel

#### AO9 — Entity Impact Inspector

- Status: `PLANNED`.
- Goal: let an admin start from an HA entity and see what Heima is doing to or because of it.
- Product boundary:
  - AO9 must be entity-centric, not domain-specific.
  - Lighting and camera privacy must be explained through the same generic entity-impact model.
  - Entity relationships must be backend-derived. The frontend must not infer relationships from
    naming conventions, room labels, localized text, or entity-ID substrings.
- AO9.1 backend entity-impact index:
  - Build an index from apply steps, reaction configs, manual holds, decision traces, runtime
    confirmations, and structured domain metadata.
  - Include security camera privacy sources as structured metadata, for example privacy entity to
    camera source links.
  - Include notification routes only when linked to an entity-bearing request, apply step, trace, or
    policy. Generic notification recipients/groups are not Home Assistant entities.
  - Tests:
    - entity index projection tests for light apply steps
    - entity index projection tests for camera privacy policy entities
    - tests proving notification recipient/group IDs are not indexed as HA entities by themselves
    - redaction tests for entity-impact rows
- AO9.2 entity list/search:
  - Add an `Entities` or `Entity Impact` section.
  - Support search by entity ID and domain.
  - Show concise counts for linked reactions, traces, holds, requests, policies, and pending applies.
  - Tests:
    - frontend/static tests for entity search and empty state
    - unit/static tests for count rendering from backend-provided fields
- AO9.3 entity detail view:
  - Show entity ID, domain, reactions that target or reference the entity, latest Heima trace,
    recent apply steps, active manual holds, pending applies, runtime confirmations, source
    policies/config entries, and last known Heima outcome.
  - Link entity detail rows back to reaction, trace, hold, request, and policy views when available.
  - Tests:
    - detail projection tests for linked reactions/traces/holds/requests/policies
    - frontend/static smoke tests for entity detail navigation
- AO9.4 live validation:
  - Add `081_entity_impact_live.py`.
  - Validate a known camera privacy entity or test-light entity against the running HA test
    instance.
  - Verify that camera privacy and lighting examples are represented through the same generic
    entity-impact shape.
- Acceptance:
  - an admin can search an entity and see linked Heima reactions, holds, traces, requests, and
    policies
  - camera privacy and lighting cases are explained through the same generic model
  - no frontend inference from naming conventions or hardcoded room/domain strings

#### AO10 — Focused Why-Not-Now Evaluation

- Status: `PLANNED`.
- Goal: answer why one selected reaction would apply, wait, block, skip, or be non-evaluable now.
- Product boundary:
  - AO10 is a read-only focused evaluation tool, not a runtime execution path.
  - It must not enqueue apply steps, create runtime confirmation requests, mutate manual holds,
    update proposal lifecycle state, or rebuild unrelated domains as a side effect.
  - Unsupported reaction types must return `not_evaluable` with explicit reasons.
- AO10.1 websocket/API contract and authorization:
  - Add an HA-admin-only read-only websocket query for one reaction ID.
  - Return `reaction_id`, `generated_at`, `outcome`, `reason_codes`, `input_summary`,
    `condition_results`, `guard_results`, `policy_result`, `apply_steps`, and `links`.
  - Return `not_found` for unknown reaction IDs.
  - Tests:
    - authorization tests for admin/non-admin callers
    - not-found and malformed-request tests
    - schema/version compatibility tests for focused results
- AO10.2 focused evaluation hook:
  - Prefer an optional reaction/plugin focused-evaluation hook over a one-off lighting-only
    evaluator.
  - Reuse existing condition, guard, execution-policy, manual-hold, and apply-step validation
    helpers where possible.
  - If only a subset of reaction types is supported in the first slice, unsupported reactions must
    be explicit in API and UI.
  - Tests:
    - supported-reaction focused evaluation tests
    - unsupported-reaction `not_evaluable` tests
    - tests proving reason codes and links point to relevant holds/entities/policies when available
- AO10.3 no-mutation and rate limiting:
  - Enforce default 2 focused evaluations per minute per config entry.
  - If it does not materially complicate implementation, make the limit runtime-configurable
    through normal config entry/options updates without requiring a Home Assistant restart.
  - If runtime configurability adds meaningful complexity, ship the fixed default first and track
    runtime configurability as an AO10 follow-up sub-slice.
  - Record an observability event that an admin ran a focused inspection, without changing runtime
    state.
  - Tests:
    - default rate-limit tests
    - optional runtime-configurable-rate tests if the option is implemented in this slice
    - no-mutation tests proving no apply plan, runtime request, manual hold, proposal lifecycle, or
      options state changes unexpectedly
- AO10.4 frontend integration and live validation:
  - Add a `Why not now?` affordance in reaction detail.
  - Display `would_apply`, `would_wait`, `would_block`, `would_skip`, `not_evaluable`, and
    `not_found` distinctly.
  - Show condition, guard, policy, apply-step, and link sections without raw JSON as the primary
    explanation.
  - Add `082_why_not_now_live.py` for the first supported focused-evaluation path.
  - Tests:
    - frontend/static smoke test for the reaction detail affordance
    - frontend/static tests for `not_evaluable` and rate-limit display states
    - live `082` test against the running HA test instance once at least one supported reaction
      type is wired
- Acceptance:
  - focused query never applies actions or creates runtime confirmation requests
  - unsupported reaction types fail explicitly
  - repeated UI calls are bounded by the configured/default rate limit
  - result links to relevant traces, holds, entities, and policies where available

### Phase AP — Notification Delivery Policy

- Status: `DONE`.
- Spec sources:
  - `docs/specs/core/events_and_notifications_spec.md`
  - `docs/specs/core/notification_admin_ui_spec.md`
  - `docs/specs/core/resident_runtime_confirmation_spec.md`
- Goal: prevent notification storms by separating runtime observability from human push delivery,
  adding audience policy, startup grace, persistence thresholds, aggregation, burst limits, and
  clearer message rendering while keeping actionable runtime confirmations separate and reliable.
- Product boundary:
  - AP governs informational event push delivery.
  - AP must not suppress actionable runtime confirmation requests; those remain governed by AH
    occurrence deduplication, timeout, and `supports_actions`.
  - AP must not infer authorization from notification groups. `admins` and `residents` are routing
    conventions only; HA admin authority remains the authorization boundary.
  - Event bus, diagnostics, and admin observability must retain events even when push delivery is
    suppressed.
- Architecture name:
  - Runtime policy component: **Notification Delivery Policy**.
  - Acceptable implementation class names include `NotificationDeliveryPolicy` or
    `NotificationPolicyEngine`, but diagnostics and docs should use "Notification Delivery Policy".
- Canonical persisted model:
  - `notifications.audience_targets`
  - `notifications.audience_policy`
  - `notifications.persistence_thresholds`
  - `notifications.aggregation`
  - `notifications.startup_notification_grace_s`
- Legacy decision:
  - AP does not need to preserve old domain-specific notification persistence fields such as
    `occupancy_mismatch_persist_s` and `security_mismatch_persist_s` as authoritative fields.
- External model note:
  - AP follows the same separation of concerns used by systems such as Alertmanager/Grafana
    (classify, route, group, time/rate-control, deliver), but keeps a smaller Heima-specific
    audience vocabulary.

#### AP1 — Policy Model And Normalization

- Status: `DONE`.
- Implement normalized notification policy defaults for:
  - `audience_targets`
  - `audience_policy`
  - `persistence_thresholds`
  - `aggregation`
  - `startup_notification_grace_s`
- Define and validate the closed `audience_policy.<family>.push` vocabulary:
  - `disabled`
  - `observability`
  - `admins`
  - `residents`
  - `residents_and_admins`
  - `admins_after_persistence`
  - `residents_and_admins_after_persistence`
  - `residents_and_admins_when_critical_else_admins_after_persistence`
- Required behavior:
  - apply conservative implicit defaults when config is absent or partial
  - reject or sanitize unsupported policy values deterministically
  - never treat `observability` as a recipient, group, or `notify.*` service
  - no fallback from admin-facing policies to residents when admin targets are missing
  - no fallback from resident-facing policies to admins unless the policy explicitly includes
    admins
- Tests:
  - config absent, partial, and explicit defaults
  - invalid `audience_policy` values
  - invalid audience targets
  - `observability` rejected as target
  - old `*_persist_s` fields are not required for normalized AP behavior

#### AP2 — NotificationDeliveryPolicy Core

- Status: `DONE`.
- Add a runtime policy component that accepts an event plus effective notification config and
  returns a structured delivery decision without sending notifications directly.
- Decision outcomes:
  - `deliver`
  - `observability_only`
  - `disabled`
  - `startup_grace`
  - `waiting_persistence`
  - `suppressed_aggregation`
  - `suppressed_category`
  - `suppressed_dedup`
  - `suppressed_rate_limit`
  - `suppressed_burst`
  - `missing_audience_target`
- Required behavior:
  - classify event family/severity
  - resolve audience policy
  - identify security-critical cases
  - preserve event bus/diagnostics regardless of push decision
- Tests:
  - `people.arrive` -> observability only by default
  - `reaction.fired` -> observability only by default
  - `system.config_issue` -> admins by default
  - alarm triggered -> residents + admins
  - armed-away while someone is home -> residents + admins
  - admin target missing -> no resident fallback and diagnostic reason

#### AP3 — Pipeline Integration

- Status: `DONE`.
- Integrate Notification Delivery Policy into `EventsDomain` / notification pipeline.
- Runtime order:
  1. emit event
  2. classify event family and severity
  3. resolve audience policy
  4. apply startup grace for informational push delivery
  5. apply persistence thresholds for mismatch/invariant families
  6. aggregate/collapse related events
  7. apply category gate
  8. apply deduplication, per-key rate limit, and global informational burst limit
  9. resolve audience targets to recipients/groups
  10. resolve recipients to concrete `notify.*` services
  11. apply transport capability filtering
  12. deliver
- Required behavior:
  - event bus still fires for push-suppressed events
  - diagnostics and admin observability still retain push-suppressed events
  - `route_targets` no longer acts as "send everything to residents" for human-facing event
    delivery
  - actionable runtime confirmations bypass AP informational grace/aggregation/rate/burst controls
- Tests:
  - push-suppressed event appears in event stats/observability
  - system event is observable without unconditional push
  - legacy/default `route_targets` does not receive noisy categories by default
  - runtime confirmation actionable path still sends through AH controls

#### AP4 — Persistence State, Aggregation, And Burst Limits

- Status: `DONE`.
- Add bounded runtime state for:
  - mismatch first seen / last seen
  - persistence threshold met/not met
  - aggregation buckets
  - global informational burst windows
- Required behavior:
  - mismatch that resolves before threshold sends no push
  - persistent mismatch sends one collapsed push according to audience policy
  - related `people`, `occupancy`, and invariant events collapse before push delivery
  - global burst limit applies only to informational push notifications
  - security-critical events may bypass informational burst limit but still deduplicate by key or
    occurrence
- Tests:
  - occupancy mismatch resolved before threshold -> no push
  - occupancy mismatch persists -> one admin push
  - three person-arrival events -> no resident notification storm
  - global informational limit defaults to max 2 per 60 seconds
  - event bus/observability are not burst-limited

#### AP5 — Message Rendering

- Status: `DONE`.
- Add resident/admin message rendering rules for AP informational notifications.
- Required behavior:
  - resident text is plain-language and avoids raw UUIDs when labels/display names exist
  - resident text avoids technical wording such as "injected steps" or "invariant violation"
  - admin text may include technical ids but must lead with a readable summary
  - collapsed notifications summarize the condition instead of listing raw event ids
- Tests:
  - reaction label replaces raw reaction id when reaction push is explicitly enabled
  - person slug resolves to display name when available
  - resident-facing rendered text does not contain known reaction UUIDs
  - admin-facing rendered text includes useful technical context without losing readable summary

#### AP6 — Options Flow / Admin UI Controls

- Status: `DONE`.
- Expose guided advanced controls for:
  - audience targets
  - audience policy preset/editing
  - persistence thresholds
  - startup notification grace
  - aggregation and burst limits
- Required behavior:
  - show implicit defaults separately from explicitly saved values
  - validate closed audience policy vocabulary
  - warn before enabling resident push for noisy families (`people`, `occupancy`, `house_state`,
    `reaction`)
  - show unresolved admin/resident audience targets
  - present `route_targets` as generic/legacy fallback, not preferred human-facing routing
- Tests:
  - HA schema serializes
  - round-trip normalized config
  - invalid vocabulary errors
  - `observability` rejected as recipient/group/service
  - noisy resident-facing policy requires explicit confirmation

#### AP7 — Observability And Diagnostics

- Status: `DONE`.
- Extend diagnostics/admin observability with:
  - effective Notification Delivery Policy
  - push delivery decisions and reason codes
  - startup grace active/inactive state
  - persistence pending/met state
  - aggregation bucket summaries
  - burst-suppressed counts
  - unresolved audience targets
- Tests:
  - observability snapshot includes effective policy
  - diagnostics explain why a notification was not pushed
  - unresolved target diagnostics are structured and redacted appropriately

#### AP8 — Live Tests

- Status: `DONE`.
- Add controlled live tests and simulation tooling.
- Required live checks:
  - `reaction.fired` does not push by default
  - `people.arrive` does not push by default
  - admin-only config issue does not push to residents
  - armed-away while someone is home pushes to residents and admins when configured targets exist
  - persistent occupancy mismatch collapses into one admin notification
- Add a diagnostic script that can simulate AP delivery decisions without sending push
  notifications.
- Tests:
  - live test against Docker HA using controlled notify services or fake observable notify endpoint
  - replay test from exported observability/diagnostic snapshots where possible
  - no live test should depend on a real phone receiving a push notification

- Phase AP acceptance:
  - resident push defaults are quiet and do not produce notification storms
  - admin/security-critical push remains available and explainable
  - actionable runtime confirmation behavior remains governed by AH and is not suppressed by AP
  - every suppressed push has an observable reason in diagnostics/admin panel
  - the config model is general and does not rely on old domain-specific persistence fields

### Phase AQ — Runtime Checkpoint and Power Recovery

- Status: `PLANNED`.
- Spec source: `docs/specs/core/runtime_checkpoint_and_power_recovery_spec.md` (Status: Planned —
  not implemented on `main`; approved after three review rounds).
- Also touches: `core/admin_observability_panel_spec.md` (new `recovery` snapshot key),
  `core/event_catalog_spec.md` / `core/security_mismatch_generalization_spec.md` (severity
  vocabulary already unified as part of spec approval, see below), `domains/heating_spec.md`
  (`vacation_curve` checkpoint fields).
- Goal: behave conservatively and explainably when the home loses power, when Home Assistant
  restarts, or when many devices temporarily become unavailable — without ever blindly restoring
  old checkpoint state over current HA state.
- Product boundary:
  - runtime recovery is an explanation/guardrail layer, not a restore engine;
  - recovery state is engine-computed context read pre-DAG (like time), not a domain and not a
    plugin — see CLAUDE.md and Architecture non-negotiable #14;
  - implicit manual holds are never restored from a checkpoint after restart (matches MH's
    existing non-goal);
  - actionable runtime confirmations are explicitly not made restart-safe by this phase (AH's
    existing vNext baseline).
- Pre-work already landed ahead of implementation (approved during spec review, not gated behind
  AQ slices below):
  - `HeimaEvent.severity` is now `EventSeverity = Literal["debug","info","warning","error","critical"]`
    in `custom_components/heima/runtime/contracts.py`.
  - All `severity="warn"` call sites renamed to `"warning"` (`engine.py`, `heating.py`,
    `lighting.py`, `security.py`, plus tests/scripts).
  - `core/event_catalog_spec.md`, `core/admin_observability_panel_spec.md`,
    `core/security_mismatch_generalization_spec.md` severity vocabularies aligned.
  - Verification: `.venv/bin/python -m pytest tests/ -q` — 1800 passed, 3 pre-existing unrelated
    failures in `test_inference_foundation.py` (confirmed present on `main` before this work).

#### AQ1 — Recovery Context Foundation

- Status: `DONE`.
- Build the pre-DAG recovery classification facility (name TBD at implementation time, e.g.
  `RecoveryManager`), computed once per evaluation cycle before the core DAG runs, exposed
  read-only via the `runtime.recovery.*` context namespace.
- Implement the Recovery States state machine (`normal`, `startup_recovery`, `power_recovery`,
  `degraded_recovery`, `recovery_settling`) with entry/exit conditions and
  `critical_entity_unavailable_ratio` (default 0.35), as pure logic with no consumers wired yet —
  no observable behavior change at the end of this slice.
- Tests: state transitions, ratio threshold entry/exit, `recovery_settling` reversion on flapping.
- Implemented:
  - Added `custom_components/heima/runtime/recovery.py` with `RecoveryManager`,
    `RecoveryContext`, `RecoveryConfig`, `RecoveryEvaluationInput`, and `CriticalEntityState`.
  - Engine now computes the recovery context once before the DAG in `async_evaluate()`, with no
    critical entities/startup signal wired yet, so AQ1 does not change runtime behavior.
  - Engine diagnostics expose internal `recovery` and `runtime_context` snapshots for development
    visibility; AO-facing recovery UI remains AQ7.
  - Added `tests/test_recovery_manager.py`.
- Verification:
  - `.venv/bin/python -m pytest tests/test_recovery_manager.py tests/test_observability.py tests/test_event_category_gating.py -q`
    — 38 passed.
  - `.venv/bin/ruff check custom_components/heima/runtime/recovery.py custom_components/heima/runtime/engine.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/python -m mypy custom_components/heima/runtime/recovery.py custom_components/heima/runtime/engine.py --ignore-missing-imports`
    — passed.

#### AQ2 — Runtime Checkpoint Persistence

- Status: `DONE`.
- Implement the checkpoint contract (schema, attribute allowlist, redaction, atomic write, bounded
  size, versioned/tolerant reader) backed by a dedicated HA `Store`.
- Storage decision: use separate store `heima_runtime_checkpoints`, with one latest checkpoint per
  config entry. Do not embed checkpoint state in learning snapshots, approval records, proposal
  lifecycle state, or event storage.
- Implement Checkpoint Write Policy baseline using Runtime Scheduler job
  `recovery.checkpoint.write` (`owner=recovery`) with write-on-change semantics and a 60s default
  cadence. The job is keyed and deduplicated; when it fires, the engine writes and flushes the
  latest checkpoint, then removes the job. Shutdown performs a best-effort immediate checkpoint
  write.
- AQ2 intentionally does not yet classify startup differences, block apply steps, suppress learning,
  or restore heating branch context; those remain AQ3-AQ6.
- Tests: serialization/deserialization, version tolerance, redaction, write debounce/keyed
  replacement, scheduler jobs firing independent of entity churn.
- Implemented:
  - Added `custom_components/heima/runtime/checkpoint_store.py` with `RuntimeCheckpointStore`,
    `RuntimeCheckpoint`, `CheckpointEntityState`, domain attribute allowlist, redaction, bounded
    entity capture, tolerant loading, and redacted diagnostics.
  - Coordinator owns and loads the checkpoint store and injects it into the engine.
  - Engine builds compact runtime checkpoints, captures allowlisted tracked entity states, exposes
    checkpoint diagnostics, schedules keyed checkpoint writes via Runtime Scheduler, and flushes on
    scheduled write/shutdown.
  - Added `tests/test_runtime_checkpoint_store.py`.
- Verification:
  - `.venv/bin/python -m pytest tests/test_runtime_checkpoint_store.py tests/test_recovery_manager.py -q`
    — 14 passed.
  - `.venv/bin/ruff check custom_components/heima/runtime/checkpoint_store.py custom_components/heima/runtime/engine.py custom_components/heima/coordinator.py tests/test_runtime_checkpoint_store.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/runtime/checkpoint_store.py custom_components/heima/runtime/engine.py custom_components/heima/coordinator.py tests/test_runtime_checkpoint_store.py`
    — passed.
  - `.venv/bin/python -m mypy custom_components/heima/runtime/checkpoint_store.py custom_components/heima/runtime/engine.py --ignore-missing-imports`
    — passed.

#### AQ3 — Startup Recovery Wiring

- Status: `DONE`.
- Wire checkpoint load + current-HA-state comparison + difference classification
  (`unknown_during_downtime` / `power_restore_candidate`) into engine startup.
- Enter/exit `startup_recovery` per Startup Entry Conditions / Exit Conditions.
- Tests: startup recovery entry with no checkpoint, with a stale checkpoint, with a checkpoint that
  fails validation; recovery exit after stable critical entities.
- Implemented:
  - Engine now requests `startup_recovery` on the first evaluation cycle only.
  - Engine reads the latest `heima_runtime_checkpoints` checkpoint for the current config entry and
    exposes checkpoint availability, usability, freshness, age, reason, and difference count under
    the reserved `runtime.recovery.*` context namespace.
  - Checkpoint/current HA differences are classified as `power_restore_candidate` for restore-
    plausible actuator domains (`light`, `switch`, `climate`, `cover`, `fan`) and
    `unknown_during_downtime` otherwise. Current HA state remains source of truth; no old
    checkpoint state is restored.
  - Recovery diagnostics include redacted checkpoint status and per-entity difference details.
  - Engine schedules `recovery.stabilization` via Runtime Scheduler using the recovery
    stabilization deadline, so startup recovery can progress without requiring a new HA entity
    change.
  - Added/extended `tests/test_recovery_manager.py` coverage for missing, stale, invalid, and
    changed checkpoints.
- Verification:
  - `.venv/bin/python -m pytest tests/test_recovery_manager.py tests/test_runtime_checkpoint_store.py -q`
    — 18 passed.
  - `.venv/bin/ruff check custom_components/heima/runtime/recovery.py custom_components/heima/runtime/engine.py tests/test_recovery_manager.py tests/test_runtime_checkpoint_store.py`
    — passed.
  - `.venv/bin/ruff format --check tests/test_recovery_manager.py custom_components/heima/runtime/recovery.py custom_components/heima/runtime/engine.py`
    — passed.
  - `.venv/bin/python -m mypy custom_components/heima/runtime/recovery.py custom_components/heima/runtime/engine.py custom_components/heima/runtime/checkpoint_store.py --ignore-missing-imports`
    — passed.

#### AQ4 — Power Recovery Detection

- Status: `DONE`.
- Detect mass unavailable/mass restore while HA stays online; enter/exit `power_recovery` and
  `recovery_settling`.
- Tests: mass unavailable -> `power_recovery`; mass restore -> `recovery_settling`; flapping reverts
  `recovery_settling` back to `power_recovery`.
- Implemented:
  - Engine now uses a recovery-specific critical entity set instead of reusing only
    `tracked_entity_ids()`. The set includes normal trigger entities plus configured climate
    targets, camera privacy switches, camera privacy manual-hold helpers, lighting room/zone
    entities, best-effort room light entities, and configured reaction step targets.
  - The critical set uses stricter HA entity-id detection to avoid accidentally treating arbitrary
    strings with dots as entities.
  - Online mass-unavailable state transitions now enter `power_recovery`; restoration transitions
    to `recovery_settling`; flapping during settling returns to `power_recovery`.
  - Existing Runtime Scheduler stabilization job (`recovery.stabilization`) is reused for online
    power recovery, so recovery can progress without additional entity churn.
  - Added engine-level test coverage for configured target inclusion and
    `power_recovery -> recovery_settling -> power_recovery` flapping.
- Verification:
  - `.venv/bin/python -m pytest tests/test_recovery_manager.py tests/test_runtime_checkpoint_store.py -q`
    — 19 passed.
  - `.venv/bin/ruff check custom_components/heima/runtime/engine.py custom_components/heima/runtime/recovery.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/runtime/engine.py custom_components/heima/runtime/recovery.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/python -m mypy custom_components/heima/runtime/recovery.py custom_components/heima/runtime/engine.py custom_components/heima/runtime/checkpoint_store.py --ignore-missing-imports`
    — passed.

#### AQ5 — Runtime Behavior Gating

- Status: `DONE`.
- Wire `runtime.recovery.*` context consumption into: Learning suppression, Anomaly Detection
  suppression (see Suppressed/Not-automatically-suppressed lists in the spec), Manual Hold gating
  (implicit hold activation skipped during active recovery; classification stays `external`; no
  checkpoint restore of implicit holds), Pending Applies handling, and Reactions/Apply blocking
  (`blocked_by="recovery:<state>"`, with the defined precedence vs. manual-hold blocking).
- Tests: recovery suppresses learning/anomaly; recovery blocks non-critical apply with the correct
  `blocked_by` value; `blocked_by` precedence when both recovery and manual hold would apply;
  recovery does not create implicit manual holds for restore changes.
- Implemented:
  - Snapshot persistence for learning is skipped while recovery is active, preventing unstable
    startup/power snapshots from entering learning history.
  - Invariant/anomaly checks are skipped while recovery is active, preventing recovery conditions
    from being reported as ordinary invariant violations.
  - Apply plans pass through a recovery gate before manual-hold filtering. Unblocked steps are kept
    in diagnostics but marked `blocked_by="recovery:<state>"`; existing blockers are preserved.
    This gives recovery precedence over manual hold when both would block the same step.
  - Pending apply registration is skipped while recovery is active, avoiding stale Heima-owned
    classifications during power restore.
  - Smart-lighting external-change handling and camera privacy implicit manual-hold creation are
    skipped while recovery is active.
  - Runtime confirmation requests are not created while recovery is active; reaction steps remain
    in the plan and are blocked by the recovery gate.
  - Added focused engine tests for learning suppression, invariant suppression, apply/manual-hold
    precedence, implicit hold gating, and runtime-confirmation gating.
- Verification:
  - `.venv/bin/python -m pytest tests/test_recovery_manager.py tests/test_runtime_checkpoint_store.py -q`
    — 24 passed.
  - `.venv/bin/ruff check custom_components/heima/runtime/engine.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/runtime/engine.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/python -m mypy custom_components/heima/runtime/recovery.py custom_components/heima/runtime/engine.py custom_components/heima/runtime/checkpoint_store.py --ignore-missing-imports`
    — passed.

#### AQ6 — Domain-Specific Recovery Behavior

- Status: `DONE`.
- House State: distinguish checkpointed/current/stable state; no `away` inference from sensor
  silence during recovery.
- Security: emit `security.mismatch` with `subtype=security_state_unavailable` when the alarm panel
  is unavailable during recovery; block security-dependent reactions unless explicitly safe.
- Heating: preserve `vacation_curve_start_temp` / `vacation_curve_started_at` across restart instead
  of recapturing; do not reapply heating targets during startup recovery except by the defined
  exceptions.
- Lighting and Switches: no implicit holds from restore changes; label restore-plausible changes
  `power_restore_candidate`; smart-lighting reactions do not reapply scenes until stabilization
  exits.
- Camera Privacy: security-driven privacy enforcement gated on alarm-state availability during
  recovery.
- Vacation Presence Simulation: suspend source-profile learning; skip/delay scheduled events
  observably during recovery.
- Tests: climate/light/camera-privacy state changed during downtime (integration tests); vacation
  curve restore vs. recapture.
- Implementation notes:
  - House-state recovery now keeps an effective/checkpoint-aware state separate from the raw
    computed state, and exposes the recovery decision in `heima_house_state` attributes.
  - `away` inferred only from sensor silence is blocked during active recovery; Heima falls back to
    the previous non-`away` state, then the checkpointed non-`away` state, then `unknown`.
  - Security unavailable during recovery is emitted as `security.mismatch` with
    `subtype=security_state_unavailable`, once per unavailable episode.
  - Heating checkpoints now persist and restore the active `vacation_curve` runtime so restart does
    not recapture the post-restart setpoint as the ramp origin.
  - The AQ5 recovery apply gate already prevents lighting, switch, camera privacy, heating, and
    runtime-confirmation applies from executing while recovery is active, and suppresses implicit
    holds from restore-time state changes.
- Verification:
  - `.venv/bin/python -m pytest tests/test_recovery_manager.py tests/test_runtime_checkpoint_store.py -q`
    — passed.
  - `.venv/bin/ruff check custom_components/heima/runtime/engine.py custom_components/heima/runtime/domains/heating.py custom_components/heima/coordinator.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/runtime/engine.py custom_components/heima/runtime/domains/heating.py custom_components/heima/coordinator.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/python -m mypy custom_components/heima/runtime/recovery.py custom_components/heima/runtime/engine.py custom_components/heima/runtime/domains/heating.py custom_components/heima/runtime/checkpoint_store.py custom_components/heima/coordinator.py --ignore-missing-imports`
    — passed.

#### AQ7 — Observability, Event Catalog and Diagnostics

- Status: `DONE`.
- Add `recovery` as a new top-level key in the AO snapshot (`core/admin_observability_panel_spec.md`),
  sibling to `manual_holds`/`runtime_confirmations`/`notifications`.
- Add the 8 `system.recovery_*` events (Runtime Activity + Event Catalog Additions), with the
  per-event notification routing defined in the spec (Startup Grace Period for
  `system.recovery_startup_started`, immediate admin push for
  `system.recovery_power_outage_suspected`, `degraded_timeout_s`-gated admin push for
  `system.recovery_degraded`).
- Extend the diagnostics payload per the spec's Diagnostics and Support section.
- Read-only admin panel section, following the same pattern as AO's existing read-only sections
  (no new mutation boundary in this slice).
- Tests: AO snapshot includes `recovery`; each event type routes as specified; diagnostics answers
  all 7 questions listed in the spec.
- Implementation notes:
  - Added top-level AO snapshot `recovery` with state, critical entity availability, checkpoint
    status/store details, recovery-blocked apply steps, and recent recovery events.
  - Added a read-only Recovery section to the Heima admin panel.
  - Added runtime lifecycle events for recovery transitions plus checkpoint written/invalid events.
  - Added recovery events to `core/event_catalog_spec.md`.
- Verification:
  - `.venv/bin/python -m pytest tests/test_observability.py tests/test_recovery_manager.py tests/test_runtime_checkpoint_store.py -q`
    — passed.
  - `.venv/bin/ruff check custom_components/heima/observability.py custom_components/heima/runtime/engine.py tests/test_observability.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/observability.py custom_components/heima/runtime/engine.py tests/test_observability.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/python -m mypy custom_components/heima/observability.py custom_components/heima/runtime/engine.py --ignore-missing-imports`
    — passed.
  - `node --check custom_components/heima/frontend/heima-admin-panel.js` — passed.

#### AQ8 — Live Tests and Validation

- Status: `DONE` for live-safe validation and destructive opt-in validation.
- Add a live test script under `scripts/live_tests/` (naming/number per existing convention)
  covering: controlled restart of the HA test container with a valid checkpoint; simulated
  unavailable/available burst for critical entities; observability export contains recovery state,
  lifecycle events, and checkpoint metadata. Stale-checkpoint construction remains a lower-level
  unit-test concern unless a safe live corruption hook is introduced.
- Add destructive AQ checks to a separate opt-in tier in `scripts/check_all_live.sh`; default,
  diagnostic, and `all` tiers must remain non-destructive.
- Implementation notes:
  - Added `scripts/live_tests/085_recovery_observability_live.py`.
  - Added `scripts/live_tests/086_recovery_destructive_live.py`.
  - Updated `scripts/live_tests/080_admin_observability_panel_live.py` so `recovery` is a required
    AO snapshot section.
  - The AQ8 live-safe script is read-only: it validates the observability recovery contract,
    checkpoint metadata shape, recovery-blocked apply step shape, recent recovery event shape, and
    `sensor.heima_health` alignment.
  - Added `--tier destructive` to `scripts/check_all_live.sh`. It requires `--allow-destructive`
    or `ALLOW_DESTRUCTIVE_LIVE=1`, and passes `--docker-container` only when explicitly provided.
  - The destructive AQ script forces a threshold-sized set of recovery critical entities to
    `unavailable`, verifies `power_recovery`, restores original states, verifies stabilization and
    completion, restarts the HA test container, and verifies that checkpoint metadata is available
    after restart.
  - Recovery lifecycle events are now mirrored into `RuntimeObservabilityBuffer`, so the admin
    Recovery view can show the `system.recovery_*` lifecycle instead of only the internal event
    queue.
- Verification:
  - `.venv/bin/python -m pytest tests/test_observability.py tests/test_recovery_manager.py tests/test_runtime_checkpoint_store.py -q`
    — passed.
  - `.venv/bin/ruff check scripts/live_tests/080_admin_observability_panel_live.py scripts/live_tests/085_recovery_observability_live.py custom_components/heima/observability.py custom_components/heima/runtime/engine.py tests/test_observability.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/ruff format --check scripts/live_tests/080_admin_observability_panel_live.py scripts/live_tests/085_recovery_observability_live.py custom_components/heima/observability.py custom_components/heima/runtime/engine.py tests/test_observability.py tests/test_recovery_manager.py`
    — passed.
  - `.venv/bin/python -m mypy custom_components/heima/observability.py custom_components/heima/runtime/engine.py scripts/live_tests/085_recovery_observability_live.py --ignore-missing-imports`
    — passed.
  - `bash -n scripts/check_all_live.sh` — passed.
  - `python3 -m py_compile scripts/live_tests/086_recovery_destructive_live.py` — passed.
  - `.venv/bin/python -m pytest tests/test_recovery_manager.py -q` — passed.
  - `source scripts/.env && scripts/live_tests/085_recovery_observability_live.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"`
    — passed against the local HA test instance.
  - `source scripts/.env && scripts/live_tests/080_admin_observability_panel_live.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"`
    — passed against the local HA test instance.
  - `source scripts/.env && ./scripts/check_all_live.sh --tier destructive --allow-destructive --docker-container "$DEV_CONTAINER_NAME"`
    — passed against the local HA test instance.
  - `source scripts/.env && ./scripts/check_all_live.sh --tier diagnostic`
    — blocked before reaching AQ8 by `074_camera_privacy_manual_hold_live.py`.
  - `source scripts/.env && scripts/live_tests/074_camera_privacy_manual_hold_live.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --timeout-s 120`
    — failed in scenario C: expected manual hold reason `external_off`, observed `external_on`.

- Phase AQ acceptance (from the spec's own Acceptance Criteria):
  - Heima writes compact runtime checkpoints after important runtime changes.
  - After HA restart, Heima enters startup recovery and exposes why.
  - During recovery, non-critical apply steps are blocked with explicit recovery reasons.
  - During recovery, learning and absence-based anomaly rules do not consume unstable snapshots.
  - Power-restore actuator changes do not create implicit manual holds.
  - After stabilization, Heima exits recovery and resumes normal runtime from current HA state.
  - Admin observability shows checkpoint age, recovery state, entity differences, and blocked
    actions.
  - The implementation is covered by unit, integration, and live restart tests.
  - Mandatory merge-to-main procedure (version bump, changelog, `ci_local.sh`) applies before AQ
    lands on `main`, per CLAUDE.md.

### Recent Working Notes

- Recent implementation slice: **Phase AH — Resident Runtime Confirmation & Auto-Apply Promotion**.
  - Spec source: `docs/specs/core/resident_runtime_confirmation_spec.md`, plus supporting
    notification/options/apply-step specs.
  - Goal: allow an already configured reaction to ask residents before applying one runtime
    occurrence, then let a Home Assistant admin promote frequently approved reactions to
    `auto_apply`.
  - Architectural rule: AH may start with one supported reaction family, but the framework must be
    generic. No AH runtime component may be hardcoded to lighting. Every reaction family that wants
    runtime confirmation must opt in through a `RuntimeConfirmationDescriptor`.
  - First supported family: `context_conditioned_lighting_scene`.
  - Long-term product decision: this notification-confirmation model is intended to become
    available to all domains/reaction families, without domain exclusions, once each family
    provides the required descriptor and review/rendering contract.
  - Runtime confirmation is separate from proposal review:
    - resident approval applies or skips one occurrence only
    - promotion is HA-admin-gated and changes stable execution policy
    - notification responses must never create, accept, or edit learning proposals
  - AH1 completed on `feat/ah-runtime-confirmation`:
    - Added optional `ApplyStep.step_id` and `ApplyStep.depends_on`.
    - Added pure runtime confirmation contracts and helpers in
      `custom_components/heima/runtime/runtime_confirmation.py`.
    - Added tests in `tests/test_runtime_confirmation.py`.
    - Verification:
      - `.venv/bin/python -m pytest tests/test_runtime_confirmation.py tests/test_behavior_framework.py tests/test_manual_hold_manager.py -q`
        — 40 passed.
      - `.venv/bin/ruff check custom_components/heima/runtime/contracts.py custom_components/heima/runtime/runtime_confirmation.py tests/test_runtime_confirmation.py`
        — passed.
      - `.venv/bin/ruff format --check custom_components/heima/runtime/contracts.py custom_components/heima/runtime/runtime_confirmation.py tests/test_runtime_confirmation.py`
        — passed.
  - AH2 completed on `feat/ah-runtime-confirmation`:
    - Added `notifications.notification_service_capabilities` normalization/options support.
    - Added provider-neutral `ActionableNotification` / `NotificationAction`.
    - Added actionable routing that filters logical notification targets by `supports_actions`.
    - Added fail-closed behavior for missing actionable routes.
    - Added parser for `mobile_app_notification_action` response payloads, using stable action ids
      plus `request_id` from `action_data.request_id` or `tag`.
  - AH3 started:
    - Added in-memory `RuntimeActionRequestRegistry`.
    - Added occurrence deduplication, terminal resolution, stale response counting, recent
      completed diagnostics, and due-timeout extraction.
  - AH3 completed:
    - Added `RuntimeConfirmationController` as the Home Assistant integration layer for runtime
      requests.
    - Controller subscribes to `mobile_app_notification_action` and dispatches stable
      approve/dismiss action ids.
    - Controller schedules request timeouts with HA `async_call_later`.
    - `on_timeout: skip` resolves the request as `timeout_skipped` and applies nothing.
    - `on_timeout: apply` dispatches to an injected apply handler; AH4 owns the concrete
      pre-apply validation and stored-step execution.
    - Coordinator owns the controller lifecycle and exposes diagnostics.
  - AH4 in progress:
    - Coordinator now wires the runtime confirmation controller to the engine apply handler and the
      existing event pipeline.
    - Engine exposes a generic runtime-confirmation request sink and descriptor registry.
    - `execution_policy.mode: ask_residents` diverts descriptor-supported reaction steps into a
      `RuntimeActionRequest` instead of merging them into the immediate apply plan.
    - Controller can register a request, schedule timeout, send actionable notifications through
      `supports_actions` routes, and fail closed when no actionable route is available.
    - Approved and timeout-applied requests now re-run generic apply filters, manual hold filtering,
      and dependency evaluation before executing stored steps.
  - AH5 started:
    - Added the first concrete `RuntimeConfirmationDescriptor` for
      `context_conditioned_lighting_scene`.
    - The descriptor provides occurrence identity and resident-facing text for mixed lighting
      scenes without adding lighting-specific branches to the runtime confirmation controller.
    - Added configured-reaction edit support for `context_conditioned_lighting_scene`
      `execution_policy.mode`, confirmation timeout, target recipients/groups, default route target
      usage, and timeout behavior.
  - AH6 started:
    - Runtime confirmation outcomes are persisted per reaction under
      `reactions.confirmation_stats`.
    - Explicit approval/dismissal evidence can create a persisted
      `pending_admin_review` promotion review.
    - Timeout outcomes are recorded but excluded from promotion evidence.
    - `dismissed_not_now` promotion state now enforces progressive cooldown and requires fresh
      explicit approvals after the latest promotion dismissal.
    - Pending promotion reviews are revoked when new explicit evidence no longer satisfies
      thresholds.
    - Pending promotion reviews now persist `next_reminder_after` and `reminder_due` according to
      `reminder_interval_days`; AH7 will consume these fields when sending/admin-surfacing
      reminders.
  - AH7 started:
    - Added HA-admin-gated coordinator action boundary for promotion decisions:
      approve auto-apply, dismiss "not now", and disable future prompts.
    - Revoked/non-pending promotion reviews cannot be approved at this boundary.
    - Added options-flow promotion review step that lists pending reviews and invokes the
      coordinator boundary for the three admin decisions.

- Current slice: **Phase AG — Translate Developer Scripts, Docs, and Specs to English** on
  `feat/remove-hardcoded-italian` (2026-07-03).
  - Requirement: no Italian text in developer scripts, operational documentation, or active
    specifications, except explicit localization/fixture exceptions.
  - Runtime/UI code (`config_flow`, `runtime/reactions`) is **out of scope**: its `is_it`
    IT/EN branching is an intentional localization feature, not hardcoded leftover text — see the
    Phase AG spec revision note for why AG1/AG2 were dropped.
  - Allowed exceptions:
    - `custom_components/heima/translations/it.json`, because it is the Italian localization file.
    - Explicit locale fixtures or parser examples that intentionally test Italian inputs, such as
      calendar keyword classification.
    - Archived/RFC documents only if they are explicitly marked as archived historical Italian
      notes; otherwise they should be translated or moved out of the active docs path.
  - Remaining cleanup groups (AG3–AG5):
    - Developer comments/docstrings and script output.
    - Active operational docs (mechanical, AG4a).
    - Active canonical specs (dedicated reviewed sub-slice, AG4b).

- Current slice: **Proposal Temporal Review Bundles** completed and merged into `feat/v2`
  (2026-07-03).
  - Spec source: `docs/specs/learning/proposal_lifecycle_spec.md` §2d and
    `docs/specs/heima_v2_spec.md` house-state review grouping notes.
  - Reason: production audit found 225 pending proposals, 122 already suppressed by
    `review_grouping`, and residual visible noise dominated by adjacent
    `house_state_learned_context` representatives for the same
    `weekday + anyone_home + predicted_state`.
  - Architecture decision:
    - Temporal bundles are a read-time review/UI structure above `review_grouping`.
    - They use only visible representatives from `pending_proposals()`.
    - They do not modify persisted proposal status, `identity_key`, approval identity, or
      `review_grouping`.
    - `reject bundle` rejects only visible representatives; `dismiss similar` is the explicit
      broader rejection that also rejects hidden pending siblings in the same review groups.
  - TB1 — Proposal review bundle model: `DONE`.
    - Added a pure runtime read model for strict adjacent-hour temporal bundles.
    - Unit coverage for adjacency, gaps, context dimensions, fallback fields, and non-house-state
      proposals.
    - Commit: `1464eb6 Add proposal temporal bundle read model`.
  - TB2 — Diagnostics and audit: `DONE`.
    - Proposal diagnostics expose `temporal_bundles`, `temporal_bundle_*`, `review_rows`, and
      `review_row_count`.
    - `scripts/proposal_backlog_audit.py` reports review rows and top temporal bundles.
    - Commit: `9b4a84e Expose proposal temporal bundle diagnostics`.
  - TB3 — Bundle review actions: `DONE`.
    - Added explicit batch actions in `ProposalEngine`.
    - Added coordinator batch review wrapper that records approval decisions for applied
      house-state proposal ids.
    - Commit: `8890d8c Add proposal bundle review actions`.
  - TB4 — Options Flow review UI: `DONE`.
    - Options Flow shows temporal bundle rows instead of individual adjacent representatives.
    - Bundle actions: accept, reject, dismiss similar, expand, skip.
    - Expansion returns the individual representatives to the existing single-proposal flow.
    - Commit: `7e802de Show proposal temporal bundles in options flow`.
  - TB5 — Test and live validation: `DONE`.
    - Local focused tests, ruff, and py_compile passed for TB1-TB4 coverage.
    - `scripts/live_tests/070_proposal_review_grouping_live.py` now validates temporal bundle
      diagnostics and review-row counts.
    - Live validation passed after Docker/HA restart:
      - `scripts/live_tests/070_proposal_review_grouping_live.py` — passed.
      - `./scripts/check_all_live.sh --tier diagnostic` — passed.

- Current slice: **Manual Hold Framework + AE residual work completed** (2026-06-25).
  - Spec source: `docs/specs/core/manual_hold_framework_spec.md`.
  - Reason: AE camera privacy manual hold overlapped with existing smart-lighting manual override,
    `LightingReactionGuardBehavior`, heating manual hold, and the initial unwired
    `EntityReactionGuardBehavior`.
  - Implemented:
    - Added shared `ManualHoldManager` with pending apply provenance and scope-aware holds.
    - Migrated smart-lighting pending apply classification to the manager while preserving
      reaction-owned release policy.
    - Added central manager-backed apply filtering.
    - Adopted camera privacy scopes, `manual_hold_entity`, switch pending apply, switch
      state-change handling, and `privacy_action`.
    - Represented `heima_heating_manual_hold` as a manager-backed domain scope.
    - Removed legacy `EntityReactionGuardBehavior` and `LightingReactionGuardBehavior`.
  - Verification:
    - `.venv/bin/python -m pytest tests/ -q` — 1546 passed.
    - `.venv/bin/ruff check ...` on touched files — passed.
    - `.venv/bin/ruff format --check ...` on touched files — passed after formatting.
    - `scripts/ci_local.sh` not run in this slice.

- Previous slice: **AE initial implementation on `feat/privacy-guard-alarm-states`** (2026-06-15).
  - Spec source: `docs/specs/core/privacy_guard_for_alarm_states.md`.
  - All AE slices completed (AE1-AE5):
    - AE1: Created `EntityReactionGuardBehavior` (generic guard for any entity domain)
    - AE2: Extended `camera_evidence_sources` with `privacy_entity` and `manual_hold_entity` fields
    - AE3: Added `skip_house_states` to `AlarmStateActionReaction`
    - AE4: Added `alarm_night_camera_privacy` semantic rule with `skip_house_states` support
    - AE5: Verification complete — 1541 tests pass, ruff check/format pass, mypy clean
  - Commits: 6092458, 2ac388f, fcd7daf, 2d4995a, fb6e875
- Current slice: post-AD on `feat/v2`.
  - Spec source: `docs/specs/learning/proposal_lifecycle_spec.md` and
    `docs/specs/learning/learning_system_spec.md`.
  - Phase AD goal completed: manage the full lifecycle of accepted learned proposal-backed
    reactions: birth, active monitoring, drift/replacement suggestion, retirement suggestion,
    explicit user review, and restart-safe recovery.
  - Source branch: `feat/ad1-proposal-engine-invariants`.
  - Merge target: `feat/v2`.
  - Final AD commit included in `feat/v2`: `de65adf Complete proposal lifecycle live verification`.
  - Completed AD slices:
    - AD1 — Preserve reviewed proposal identities across proposal refresh/recovery.
    - AD2 — Add proposal lifecycle monitoring store.
    - AD3 — Add proposal lifecycle/reaction-link diagnostics.
    - AD4 — Evaluate house-state lifecycle opportunities from observed runtime events.
    - AD5 — Add accepted-rule lifecycle policy.
    - AD6 — Generate lifecycle review suggestions.
    - AD7 — Apply proposal lifecycle review decisions.
    - AD8 — Add proposal lifecycle recovery tests.
    - AD9a — Add proposal lifecycle diagnostics live probe.
  - AD9 verification cleanup completed:
    - Add `heima.command` seed commands for house-state snapshots/events.
    - Add seeded live test `scripts/live_tests/073_house_state_lifecycle_suggestion.py`.
    - Add `073` to the `seeded_integration` live-test tier and script docs.
    - Clear proposal lifecycle store during learning reset.
    - Keep a single coordinator-owned `ProposalLifecycleStore` instance shared with
      `ProposalEngine`.
    - Update dashboard/house-state test stubs to the current proposal lifecycle contract.
    - Fix mypy issues in lifecycle grouping and lifecycle counts without changing runtime behavior.
  - Verification run after AD9 cleanup:
    - `PATH="/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/.venv/bin:$PATH" bash scripts/ci_local.sh` — 1527 passed, ruff check passed, ruff format passed, mypy clean.
    - `source scripts/.env && ./scripts/check_all_live.sh` — `live_e2e` passed.
    - `source scripts/.env && ./scripts/check_all_live.sh --tier seeded_integration` — passed,
      including `073_house_state_lifecycle_suggestion.py`.
    - `source scripts/.env && ./scripts/check_all_live.sh --tier diagnostic` — passed.
- Current slice: Phase AA complete.
  - `HouseStateInferenceModule.diagnostics()` exposes model first/last snapshot timestamps, model total snapshot count, and approved model entries only.
  - `AnomalyAnalyzer` adds disabled-by-default `learned_model_stale`, evaluating only approved house-state contexts provided by coordinator diagnostics.
  - `sensor.heima_health` attributes expose the house-state model timestamp/count summary.
  - Verification: `pytest tests/test_inference_modules.py::test_house_state_inference_diagnostics_expose_only_approved_model_entries tests/test_anomaly_analyzer_q.py::test_anomaly_analyzer_learned_model_stale_disabled_by_default tests/test_anomaly_analyzer_q.py::test_anomaly_analyzer_learned_model_stale_emits_for_approved_context_drift tests/test_anomaly_analyzer_q.py::test_anomaly_analyzer_learned_model_stale_ignores_stable_distribution tests/test_health_k.py::test_health_sensor_exposes_house_state_model_summary -q`.
  - Full CI: `PATH="/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/.venv/bin:$PATH" bash scripts/ci_local.sh` — 1452 passed; ruff check, ruff format, and informative mypy completed.
- Current slice: Phase AC in progress.
  - Spec source: `docs/specs/learning/proposal_lifecycle_spec.md` §2c.
  - Goal: centralize review grouping in `ProposalEngine` via optional plugin lifecycle hooks.
  - Key invariant: grouping is computed dynamically at query time. Suppressed proposals keep their
    persisted `pending` status; there are no new store fields, no migration, and no derived state
    written back to storage.
  - First plugin: `house_state_learned_context`, grouping by
    `weekday:N:hour_bucket:N:anyone_home:N:state:S` and ranking Rich > Coarse > Minimal, then
    evidence quality.
  - User-facing pending queues and sensors must expose only current group representatives.
    Diagnostics should still expose suppressed siblings with derived review-group metadata.
  - Diagnostic follow-up identified: `house_state` lifecycle ownership is currently represented as
    a disabled learning family because the registry lacks an explicit plugin execution-mode
    contract. Spec draft now requires `LearningPatternPluginDescriptor.execution_mode`; no code
    implementation is authorized until user confirmation.
  - Implementation completed:
    - `ProposalLifecycleHooks` now supports optional `review_grouping`.
    - `ProposalEngine.pending_proposals()` computes visible representatives dynamically.
    - Diagnostics expose derived review group metadata and suppressed counts.
    - `house_state_learned_context` is registered as a lifecycle-only built-in descriptor with
      no enabled analyzer.
    - House-state proposal notifications are batched and sent only for visible representatives.
  - Focused verification:
    - `.venv/bin/python -m pytest tests/test_proposal_engine.py tests/test_learning_plugin_registry.py tests/test_reaction_helpers.py -q` — 97 passed.
    - `.venv/bin/ruff check custom_components/heima/runtime/analyzers/lifecycle.py custom_components/heima/runtime/analyzers/registry.py custom_components/heima/runtime/proposal_engine.py custom_components/heima/coordinator.py tests/test_learning_plugin_registry.py tests/test_proposal_engine.py` — passed.
    - `.venv/bin/ruff format --check custom_components/heima/runtime/analyzers/lifecycle.py custom_components/heima/runtime/analyzers/registry.py custom_components/heima/runtime/proposal_engine.py custom_components/heima/coordinator.py tests/test_learning_plugin_registry.py tests/test_proposal_engine.py` — passed.
- Current slice: Phase Z complete.
  - `options["learning"]["activity_bootstrap_mode"]` enables early composite activity discovery.
  - `ActivityAnalyzer` uses bootstrap thresholds 5 co-occurrences / 2 distinct days only when enabled; default behavior remains 10 / 3.
  - `ActivityProposal.bootstrap` is persisted, shown in review details, copied into approval metadata, and restored from approval records.
  - `ActivityInferenceModule` applies `bootstrap_min_support=5` per bootstrap-approved pattern unless `activity_inference_min_support` is explicitly configured, in which case the explicit user value wins.
  - Verification: `pytest tests/test_activity_analyzer.py tests/test_inference_modules.py tests/test_proposal_engine.py::test_activity_proposal_round_trips_storage tests/test_proposal_engine.py::test_activity_proposal_refreshes_pending_by_identity tests/test_house_state_learning_h4.py::test_review_activity_proposal_records_approved_decision_and_syncs tests/test_options_flow_e2e.py::test_learning_flow_persists_enabled_plugin_families tests/test_options_flow_e2e.py::test_learning_flow_persists_activity_bootstrap_mode tests/test_coordinator_learning_thresholds.py -q`.
  - Verification: `ruff check` on touched runtime/config/test files.
  - Full verification: `PATH=".venv/bin:$PATH" bash scripts/ci_local.sh` passed with 1447 tests.
- Current slice: Phase Y complete.
  - `HouseStateInferenceModule` now builds Rich, Coarse, and Minimal model tiers.
  - Inference selects Rich → Coarse → Minimal with independent support thresholds and diagnostic hit rates.
  - Rich and Minimal tiers use distinct approval-key learning contexts; Coarse preserves existing approval keys.
  - Branch `feat/phase-y-tiered-house-state-inference` has been merged into `feat/v2`.
- Previous slice: Phase X complete.
  - `RoomDeviceContextBuilder` maps configured HA entities to Heima rooms via HA area/device registry.
  - Engine, `InferenceContext`, `HouseSnapshot`, and `HouseStateDomain` consume room-scoped device context.
  - `RoomContextModule` is wired as an approval-gated learning module.
- Cross-cutting fix: local time contract restored for inference snapshots and notifications.
  - Engine inference contexts and newly persisted `HouseSnapshot` records now derive `weekday` and
    `minute_of_day` from HA local time rather than UTC.
  - `HouseSnapshot.from_dict()` re-derives local slots from `ts`, correcting legacy UTC-derived
    snapshot slots when persisted history is loaded.
  - Unusual-hour anomaly rules use circular clock distance, so times around midnight are compared
    correctly (`23:00` vs `01:00` is a 2-hour difference).
  - Arrival, departure, and alarm-disarm unusual-hour baselines are scoped to the same weekday,
    avoiding false positives caused by mixing workday and weekend distributions.
  - Follow-up fix: `alarm_disarm_unusual_hour` is conservative and cluster/local-support based.
    It no longer treats one median hour as the only normal disarm time; morning and evening disarm
    windows may both be valid when each has local support.
  - Follow-up fix: warning-level statistical anomalies remain visible as events, notifications, and
    `sensor.heima_health.last_anomaly`, but they do not put the whole integration into
    `degraded`. `degraded` is reserved for invariant violations, critical anomalies, and engine
    errors.
  - Presence reaction learning and analyzer calendar boundaries now use HA local time. Activity
    distinct-day counts and analyzer week-span checks use the same local calendar contract.
    Elapsed-time comparisons remain UTC-based.
  - House-state proposal and installer anomaly notifications render weekday names and `HH:MM`
    labels instead of raw weekday/hour numbers.
  - Proposal `last seen` dates in the options flow are rendered in HA local time.
  - Runtime reaction diagnostics persist `last_fired_iso` as timezone-aware UTC timestamps.
  - Calendar `today` classification for vacation, WFH, and office events uses the HA local date.
  - HA is the single authoritative timezone source. The unused Heima `timezone` override was
    removed from config flow, models, and docs; persisted legacy values are dropped on save.
- Current slice: Phase U / U1-U3 complete.
  - `LightingDomainResult` now carries `lights_on`, populated from configured room light entities
    by reading current HA physical state (`state == "on"`).
  - Engine writes `lighting.lights_on` into `CanonicalState` during each snapshot computation.
  - `InferenceContext.lights_on` exposes the previous decision snapshot's physical light state to
    learning modules without reordering the engine hot path.
  - `HouseSnapshot.lights_physically_on` is persisted, deserialized, and included in semantic
    snapshot deduplication.
  - Verification: `pytest tests/test_engine_lighting_runtime.py tests/test_inference_engine_wiring.py tests/test_snapshot_migration_o.py -q`.
- Current slice: Phase U / U4 complete.
  - `lights_on_unattended` now triggers from `HouseSnapshot.lights_physically_on` when configured
    `light.*` entities are physically on while nobody is home.
  - `lighting_scene_drift` compares recent `lighting_scenes` with the historical baseline for the
    same `(scene_key, house_state, hour_bucket)` slot.
  - Both rules live in the existing `AnomalyAnalyzer` catalog and use the existing finding path;
    no proposal or secondary analyzer path was added.
  - Phase U is complete.
  - Verification: `pytest tests/test_anomaly_analyzer_q.py -q`.
- Current slice: Phase V / V1 complete.
  - Added dedicated `runtime/signal_discovery.py` with `HAEntityDescriptor`,
    `SignalOptionsPatch`, `SignalSuggestion`, and `SignalDiscoveryAudit`.
  - V1 classifies `sensor.illuminance`, `sensor.carbon_dioxide`, `sensor.humidity`, and
    `media_player.*` into options patches only; it does not touch runtime normalization.
  - V1 maps HA area names to existing Heima room IDs via the spec heuristic and skips unsupported,
    unmapped, duplicate, or already-configured suggestions.
  - V1 limits suggestions to 50 sorted entity IDs per audit run.
  - Verification: `pytest tests/test_signal_discovery.py -q` and
    `ruff check custom_components/heima/runtime/signal_discovery.py tests/test_signal_discovery.py`.
- Current slice: Phase W complete.
  - Calendar categories now distinguish `vacation`, `holiday`, and `day_off`; the keyword
    `"holiday"` moved out of `vacation`.
  - `holiday` and `day_off` suppress `work_candidate` through workday evidence without activating
    `vacation_mode`.
  - Calendar and house-state diagnostics expose `is_day_off_today` and `is_holiday_today`.
  - Verification: `pytest tests/test_calendar_domain.py tests/test_house_state_domain.py tests/test_config_entry_diagnostics_plugins.py tests/test_options_flow_e2e.py -q`.
- Current slice: Phase V / V2 complete.
  - Coordinator now owns `SignalDiscoveryAudit` and `_pending_signal_suggestions`.
  - `_async_evaluate_signal_discovery()` submits pending suggestions to `ProposalEngine` as
    `ReactionProposal(analyzer_id="signal_discovery", reaction_type="signal_discovery")`.
  - Signal discovery proposals use `followup_kind="config_suggestion"` and serialize
    `SignalOptionsPatch` into `suggested_reaction_config`.
  - Existing proposal identities are respected through `proposal_by_identity_key()`.
  - New suggestions fire installer persistent notifications with stable
    `heima_installer_signal_discovery_*` notification IDs.
  - Verification: `pytest tests/test_signal_discovery.py -q`.
- Current slice: Phase V / V3 complete.
  - `heima.approve_proposal` now routes `signal_discovery` proposals through
    `async_review_signal_discovery_proposal()`.
  - Options flow proposal review accepts/rejects signal discovery proposals without writing to
    `options["reactions"]["configured"]` or reaction labels.
  - Follow-up action-configuration path has a defensive signal discovery guard before any reaction
    config write.
  - `SIGNAL_DISCOVERY_ANALYZER_ID` and `SIGNAL_DISCOVERY_REACTION_TYPE` live in `const.py`.
  - Verification: focused signal discovery and options-flow tests.
- Current slice: Phase V / V4 complete.
  - `ProposalEngine.accepted_proposals()` exposes accepted proposals for coordinator-side patch
    application.
  - `SignalOptionsPatch.from_dict()` validates accepted proposal payloads.
  - `apply_signal_options_patch()` performs additive, idempotent options merges for
    `rooms[*].signals` and `rooms[*].learning_sources`.
  - `_async_apply_accepted_signal_patches()` applies at most one accepted signal discovery patch
    per coordinator cycle through `async_update_entry`.
  - Existing options are the idempotency guard; already reflected patches are skipped after restart.
  - Verification: focused signal discovery and proposal-engine tests.
- Current slice: Phase V / V5 complete.
  - Startup and options reload run signal discovery audit and evaluate resulting suggestions.
  - Coordinator builds `HAEntityDescriptor` values from HA entity registry, device registry, area
    registry, and current states.
  - Coordinator subscribes to `EVENT_ENTITY_REGISTRY_UPDATED` and schedules an off-cycle audit via
    `async_call_later(0, ...)`.
  - Added `async_run_signal_discovery()` for explicit/testable audit execution.
  - Phase V is complete; next planned development phase is U (Physical Light State Awareness).
- Current slice: Phase Q complete.
  - Implemented operational rules in Phase Q: 15/17.
  - The remaining lighting rules, `lights_on_unattended` and `lighting_scene_drift`, were completed
    in Phase U after physical light state became available in `HouseSnapshot`.
  - Live coverage: diagnostic tier includes `062_anomaly_rules_live.py`, validating
    `heima.configure_anomaly_rule`, implemented rule IDs, threshold persistence, validation
    errors, and the next `learning_run` path.
- Phase Q / Q4 complete.
  - Q4 scope: `stove_on_unattended`, `oven_on_unattended`, `appliance_unusual_hour` (3 rules only).
  - `lights_on_unattended` and `lighting_scene_drift` were implemented later in Phase U after
    physical light state awareness was added.
  - `appliance_unusual_hour` trigger semantics: option A — triggers only when the appliance activity
    is present in the **current** (latest) snapshot's `detected_activities`. It does not scan for
    "last time the activity was seen active". Consistent with how other rules compare current state
    vs historical baseline.
  - `stove_on_unattended` / `oven_on_unattended`: window-based, `stove_on`/`oven_on` in
    `detected_activities` AND `anyone_home == False` across last `window` snapshots.
    No room mapping (detected_activities has no room granularity). Severity: critical.
    Defaults: window=6, min_observations=2.
  - `appliance_unusual_hour`: appliance set = `washing_machine_running`, `dishwasher_running`,
    `tv_active`, `pc_active` (excludes `stove_on`, `oven_on` — have dedicated rules).
    For each appliance currently active in the latest snapshot, extract hour from current snapshot ts;
    build historical distribution of hours when that activity appeared in `detected_activities`;
    trigger if `|current_hour - median_hour| >= delta_hours`. Defaults: window=1000,
    min_observations=8, delta_hours=4.0. Severity: warning.
- Current slice: Phase Q / Q1 complete.
  - `AnomalyAnalyzer` now uses the existing `AnomalySignal` contract from
    `runtime/plugin_contracts.py`; Q1 does not define a parallel signal type.
  - Q1 defines an `AnomalyRule` catalog for all 17 planned rule IDs and loads rule options from
    `entry.options["anomaly"]["rules"]` on every `analyze()` pass.
  - The first real end-to-end rule is `heating_unresponsive`, using
    `HouseSnapshot.heating_current_temperature` and `heating_setpoint`.
  - `FindingRouter -> coordinator anomaly handler -> installer alert` is validated by tests.
  - `heima.configure_anomaly_rule` remains out of Q1 and is still planned for Q6.
- Current slice: Phase Q / Q3 complete.
  - Heating anomaly rules implemented: `heating_setpoint_outlier`, `heating_unresponsive`,
    `heating_vacation_mismatch`.
  - All rule windows are snapshot counts, not hours.
  - `heating_vacation_mismatch` uses a fixed recent snapshot window, then filters
    `security_state == "armed_away"` inside that window. It skips if fewer than
    `min_observations` armed-away samples exist; it triggers only when all armed-away samples have
    `heating_setpoint > max_away_setpoint_c`.
- Current slice: Phase Q / Q5 security subset complete.
  - Security anomaly rules implemented: `alarm_disarm_unusual_hour`,
    `alarm_expected_not_armed`.
  - `alarm_disarm_unusual_hour` scans consecutive snapshot pairs for transitions from
    `armed_*` to `disarmed`; the latest transition is the candidate and is excluded from the
    baseline.
  - It requires conservative baseline support and compares the current transition against every
    supported per-weekday disarm window, not against a single median hour.
  - `alarm_expected_not_armed` is statistical only: no calendar/work-window context. It filters
    history by the current `(weekday, hour_bucket)` slot, then checks the latest configured number
    of snapshots within that slot are all `disarmed`.
- Current slice: Phase Q / Q5 residual subset complete.
  - Residual Q5 rules implemented: `sensor_activity_drop`, `ghost_activity`, `unusual_stillness`.
  - All three use only `HouseSnapshot` history; no `EventStore`, calendar, or external context.
  - `sensor_activity_drop` measures snapshot-per-hour rate for tracked Heima domain changes, not
    raw sensor event frequency, and compares recent time-based windows to same weekday/hour
    baseline history.
  - `ghost_activity` detects room occupancy while `anyone_home == False`.
  - `unusual_stillness` compares the current unchanged room-occupancy run to the historical 90th
    percentile of occupied stillness runs.
- Current slice: Phase P / P4a complete.
  - P4a registers `LightingPatternModule`, `RoomStateCorrelationModule`, and
    `OccupancyInferenceModule` in the coordinator learning-module lifecycle.
  - `OccupancyInferenceModule.sync_sensorless_rooms()` runs only at startup and options reload,
    not on every analyze cycle. The synced set is computed from rooms with
    `occupancy_mode == "derived"` and no `occupancy_sources`.
  - Engine diagnostics expose registered learning module diagnostics and the last routed
    inference signal buckets.
  - Runtime side effects remain limited to occupancy: `OccupancySignal` is applied by
    `OccupancyDomain` after the engine gathers signals from the base occupancy result.
  - `LightingSignal` is routed and observable but currently ignored by `LightingDomain`.
    `RoomStateCorrelationModule` `HouseStateSignal` is routed and observable but filtered out
    before `HouseStateDomain`; P4b will decide whether and how to consume it.
  - Verification: full `pytest -q` passed with 1270 tests; `mypy custom_components/heima
    --ignore-missing-imports --no-error-summary` passed; targeted `ruff check` passed.
- P4b policy decision:
  - Statistical signals never feed operational domains directly. The only operational path is:
    `LearningModule signal -> analyzer -> ProposalEngine -> admin review -> configured rule/reaction`.
  - `RoomStateCorrelationModule` remains diagnostic-only at runtime. A future
    `HouseStateCorrelationAnalyzer` may turn stable occupied-room patterns into reviewed
    house-state proposals, but raw `room_state_correlation` signals must never enter
    `HouseStateDomain`.
  - `LightingPatternModule` remains diagnostic-only at runtime. A future analyzer may target the
    existing `context_conditioned_lighting_scene` reaction type; this reaction plugin already
    exists and has proposal/review presenters.
  - The anti-feedback gate is human review, not signal strength alone. Correlations observed from
    current house-state or lighting behavior cannot amplify themselves into runtime behavior
    without explicit admin approval.
- Previous slice: Phase P / P3 complete.
  - P3 added `OccupancyInferenceModule` and `OccupancyDomain` consumption of `OccupancySignal`
    for sensorless rooms only.
  - Sensorless room definition: `occupancy_mode == "derived"` and no `occupancy_sources`;
    `learning_sources` and room `signals` do not make a room sensorized for occupancy.
  - P3 implementation constraints: confidence is smoothed as
    `probability * min(1.0, total / 10)`; inference context `anyone_home` is derived as
    `any(context.room_occupancy.values())`; fixed `Importance.SUGGEST`; `ttl_s=300`;
    `min_support=10`; `confidence_threshold=0.70`.
  - `OccupancyDomain` applies accepted signals directly for sensorless rooms, without dwell/max-on
    processing; sensorized rooms and `occupancy_mode=none` ignore all occupancy inference signals.
  - Sparse snapshot contract: `HouseSnapshot.room_occupancy` stores occupied rooms as `True`;
    absence means false. `OccupancyInferenceModule.analyze()` therefore iterates the synced
    `sensorless_rooms` allow-list and reads each room with `room_occupancy.get(room_id, False)`.
    The snapshot recorder must remain sparse.
  - Targeted verification run: `pytest tests/test_learning_modules_p.py
    tests/test_occupancy_inference_domain_p.py -q` passed with 37 tests; occupancy regression
    run passed with 47 tests; `ruff check` on P3 files passed; `mypy custom_components/heima
    --ignore-missing-imports --no-error-summary` passed.
- Previous slice: Phase P / P2 complete.
  - P2 added module-only `RoomStateCorrelationModule`; it is exported from inference modules but
    is not yet registered in the coordinator and is not consumed by `HouseStateDomain`.
  - The module learns `P(house_state | occupied_room_pattern)` from
    `HouseSnapshot.room_occupancy`, using `frozenset[str]` as the occupied-room pattern key.
  - P2 implementation constraints: ignore empty patterns; fixed `Importance.SUGGEST`; raw
    confidence ratio `best_count / total`; `min_support=15`; `confidence_threshold=0.60`.
  - Targeted verification run: `pytest tests/test_learning_modules_p.py -q` passed with 20 tests;
    `ruff check` on P1/P2 files passed; `mypy custom_components/heima
    --ignore-missing-imports --no-error-summary` passed.
- Previous slice: Phase P / P1 complete.
  - P1 added module-only `LightingPatternModule`; it is exported from inference modules but is
    not yet registered in the coordinator and is not consumed by `LightingDomain`.
  - The module learns `P(scene | room_id, house_state, hour_bucket)` from
    `HouseSnapshot.lighting_scenes`.
  - P1 implementation constraints: iterate over room IDs in the model, not
    `context.room_occupancy`; fixed `Importance.SUGGEST`; raw confidence ratio
    `best_count / total`; `min_support=8`; `confidence_threshold=0.65`.
  - Targeted verification run: `pytest tests/test_learning_modules_p.py
    tests/test_inference_foundation.py::test_inference_context_and_signals_are_typed -q` passed
    with 11 tests; `ruff check` on P1 files passed; `mypy custom_components/heima
    --ignore-missing-imports --no-error-summary` passed.
- Previous slice: Phase O complete.
  - O1 replaced `HouseSnapshot.security_armed` with `security_state`, added legacy
    `security_armed` deserialization fallback, updated `semantic_key()`, and updated engine/test
    references.
  - O2 added `heating_current_temperature` to `HouseSnapshot`. The engine records it via
    `HeatingDomain.current_temperature()` from `_record_snapshot_if_changed()`, using
    `climate.ATTR_CURRENT_TEMPERATURE`.
  - O3 added `ProposalEngine.async_withdraw(identity_key)` pending-only revocation. Coordinator
    semantic policy withdrawal uses `rule.rule_id` when a rule is no longer applicable.
  - Targeted verification run: `pytest tests/test_snapshot_migration_o.py
    tests/test_inference_foundation.py tests/test_inference_engine_wiring.py
    tests/test_inference_modules.py tests/test_activity_analyzer.py
    tests/test_heating_runtime.py::test_fixed_target_branch_builds_and_executes_heating_apply_step
    tests/test_proposal_engine.py::test_proposal_engine_async_withdraw_removes_pending_identity
    tests/test_proposal_engine.py::test_proposal_engine_async_withdraw_preserves_accepted_identity
    tests/test_proposal_engine.py::test_proposal_engine_async_withdraw_preserves_rejected_identity
    tests/test_proposal_engine.py::test_proposal_engine_async_withdraw_returns_false_for_missing_identity
    tests/test_semantic_policies_n.py` passed with 87 tests; `ruff check` on touched files
    passed; `mypy custom_components/heima --ignore-missing-imports --no-error-summary` passed.
  - Full regression: `pytest tests/ -q` passed with 1228 tests.
- Previous slice: Phase N complete.
  - N1 added `AlarmStateActionReaction`, normalization, registry support, and focused tests.
  - N2 added `SemanticRule` and `BUILTIN_SEMANTIC_RULES`; rules produce `admin_authored`
    `ReactionProposal`s with stable `identity_key` values and no new `origin` literal.
  - N3 added coordinator evaluation on initialization and options reload. Existing semantic
    proposal identities are skipped so pending/approved/rejected decisions are not reopened;
    installer notifications are sent only for first-time semantic proposals.
  - Important implementation note: current persisted options do not store HA area-expanded light
    entities; light semantic rules only fire when light entities are explicitly present in room or
    lighting room option payloads.
  - Targeted verification run: `pytest tests/test_semantic_policies_n.py
    tests/test_alarm_policy_reaction.py
    tests/test_rebuild_configured_reactions.py::test_alarm_state_action_reaction_built_and_registered`
    passed with 22 tests; `ruff check` on touched files passed; `mypy custom_components/heima
    --ignore-missing-imports --no-error-summary` passed.
- Status: Phase H is complete. Phase I starts with `ActivityProposal` contract and proposal
  plumbing complete. I2 added stable approval keys and readable snapshots for
  `activity_discovered`. I3 added the isolated `ActivityInferenceModule`. I4 adds
  `ActivityAnalyzer(snapshot_store=...)`. I5 wires analyzer/module/review surfaces for
  `activity_discovered`; no Lovelace card or inline notification actions in I5. Phase I is
  complete. Phase J replaces immediate `state_changed` evaluation with classified event-driven
  scheduling, per-class debounce, re-entry protection, bidirectional power-threshold crossing, and
  a 300s periodic fallback. Phase K adds installer-facing anomaly/invariant alerts, a
  `sensor.heima_health` operational surface, and `heima.run_diagnostics` response data. Phase L
  adds rule-based HA entity discovery with installer review in the options flow. Phase M adds an
  informational installation validation report exposed in options flow, diagnostics, and
  `sensor.heima_health` attributes.
- Key design decisions:
  - `SignalRouter.route()` accepts `list[tuple[InferenceSignal, datetime]]` — emission timestamp
    is separate from the signal dataclass (avoids mutating frozen D1 contracts).
  - TTL expiry: `age_s = (now - emit_time).total_seconds() > signal.ttl_s` → dropped.
  - Conflict WARNING threshold: confidence >= 0.60 AND different predicted values.
  - `_importance()` maps: 0.40-0.60 → OBSERVE, 0.60-0.80 → SUGGEST, >0.80 → ASSERT.
  - `ApprovalStore` is intentionally not implemented in Phase D; full implementation belongs to
    Phase H where approvals have concrete proposal lifecycle behavior.
  - WeekdayStateModule/HeatingPreferenceModule precompute their model in `analyze()` so
    `infer()` is a pure dict lookup (< 1ms verified in tests).
  - H3 B2B proposal-first rule supersedes the older pre-B2B transient-application wording in
    spec §10.9/§13: unknown or pending learned house-state contexts generate candidates only;
    approved contexts emit signals; rejected contexts generate no candidate and emit no signal.
  - HouseStateInferenceModule receives approval state through
    `sync_approval_state(approved, rejected)`. `infer()` remains sync and does not touch
    ApprovalStore or ProposalEngine.
  - `ProposalEngine.async_submit_proposal()` is already idempotent by `identity_key`: existing
    matching proposals are refreshed instead of duplicated.
  - H6 consumes only `HouseStateSignal(source_id="house_state_inference")`; the older
    `WeekdayStateModule` is not approval-gated and is therefore intentionally not applied to
    `HouseStateDomain` decisions in Phase H.
  - Phase I will use constructor injection for `ActivityAnalyzer(snapshot_store=...)`.
    Existing analyzers are already constructed with dependencies/policies in the registry, so this
    keeps `IBehaviorAnalyzer.analyze(event_store, snapshot_store=None)` unchanged and lets
    `ActivityAnalyzer.analyze(event_store)` ignore the event store.
  - `activity_context_key()` explicitly tokenizes `activity_name`, so `"Movie Night"` and
    `"movie_night"` map to the same approval key. Primitive patterns are sorted/deduped; activity
    context conditions are canonicalized before JSON hashing.
  - `ActivityInferenceModule` receives approved proposal definitions through
    `sync_approved_proposals(proposals)`. `infer()` stays sync and I/O-free.
  - I4 uses `MAX_PATTERN_SIZE = 2` for pair-only composite discovery; the constant remains
    explicit for a future upgrade to larger patterns.
  - I5 registers `ActivityAnalyzer` directly in the coordinator (Option A), because it depends on
    runtime `SnapshotStore`; the static learning registry remains dependency-free.
  - `heima.approve_proposal` and `heima.override_approval` dispatch through
    `coordinator.async_review_proposal()`, which resolves the proposal by ID and uses the
    proposal's own type as the source of truth.
  - Phase J power threshold crossing triggers on both directions. Activity start and stop are
    both semantically meaningful and must not wait for the 300s fallback.
  - Phase J re-entry follow-up uses the normal class debounce, not a zero-delay immediate run.
  - Phase K installer channel is Home Assistant `persistent_notification`, which is admin-facing
    by default. Configurable `notify.*` installer push routing is deferred.
  - `heima.run_diagnostics` returns HA service response data and also updates
    `sensor.heima_health` attributes.
  - Phase L power-sensor discovery remains generic (`activity_power_candidate`); no fragile name
    heuristics are used to choose stove/oven/appliance bindings.
  - Phase L options flow must show each `DiscoveredBindingCandidate.reason` so the installer can
    understand why the suggestion exists before accepting it.
  - Accepted non-ambiguous Phase L candidates may update concrete bindings. Ambiguous candidates
    are recorded in the discovery review result but do not silently mutate concrete config.
  - Phase M validation is informational, not blocking. It validates structural config coverage and
    snapshot counts only; it must not perform slow HA calls, network I/O, or live entity
    availability checks.
  - Live HA tests against the local Docker lab must run outside the Codex sandbox; sandboxed
    localhost access to `127.0.0.1:8823` can fail even when the lab is healthy.
  - Canonical lighting learning is now `context_conditioned_lighting_scene`; obsolete
    `lighting_scene_schedule` live/seeded checks are not part of the canonical manifests.
  - Cross-domain live tests assert canonical runtime events (`room_signal_threshold`,
    `room_signal_burst`, `actuation`) instead of legacy raw `state_change` growth.
  - Presence live coverage verifies real `presence` event recording. `presence_preheat` proposal
    generation still requires multi-week evidence and is not expected from same-day live cycles.
  - N1 added `AlarmStateActionReaction`, `normalize_alarm_state_action_config()`, registry
    registration for `alarm_state_action`, and focused reaction/rebuild tests.
  - N1 tests run:
    `pytest tests/test_alarm_policy_reaction.py tests/test_rebuild_configured_reactions.py::test_normalize_reaction_options_payload_normalizes_alarm_state_action_steps tests/test_rebuild_configured_reactions.py::test_alarm_state_action_reaction_built_and_registered`;
    `ruff check custom_components/heima/runtime/reactions/alarm_policy.py custom_components/heima/runtime/reactions/_compat.py custom_components/heima/runtime/reactions/__init__.py tests/test_alarm_policy_reaction.py tests/test_rebuild_configured_reactions.py`;
    `mypy custom_components/heima --ignore-missing-imports --no-error-summary`.
- Files read:
  - `custom_components/heima/runtime/engine.py`
  - `custom_components/heima/coordinator.py`
  - `custom_components/heima/runtime/domains/lighting.py`
  - `custom_components/heima/runtime/domains/heating.py`
  - `custom_components/heima/runtime/domains/security.py`
  - `custom_components/heima/runtime/contracts.py`
  - `custom_components/heima/runtime/snapshot.py`
  - `custom_components/heima/runtime/domains/activity_domain.py`
  - `tests/test_activity_domain.py`
  - `custom_components/heima/runtime/activity_detectors/__init__.py`
  - `custom_components/heima/runtime/activity_detectors/power_media.py`
  - `custom_components/heima/runtime/activity_detectors/stove.py`
  - `custom_components/heima/runtime/activity_detectors/oven.py`
  - `custom_components/heima/runtime/activity_detectors/tv.py`
  - `custom_components/heima/runtime/activity_detectors/pc.py`
  - `custom_components/heima/runtime/activity_detectors/washing.py`
  - `custom_components/heima/runtime/activity_detectors/dishwasher.py`
  - `tests/test_activity_detectors.py`
  - `custom_components/heima/runtime/activity_detectors/shower.py`
  - `custom_components/heima/runtime/activity_detectors/config.py`
  - `tests/test_activity_bindings_and_shower.py`
  - `tests/test_activity_engine_wiring.py`
  - `custom_components/heima/runtime/domains/house_state.py`
  - `custom_components/heima/runtime/inference/signals.py`
  - `custom_components/heima/runtime/inference/modules/house_state_inference.py`
  - `custom_components/heima/runtime/inference/modules/weekday_state.py`
  - `tests/test_house_state_domain.py`
  - `custom_components/heima/runtime/proposal_engine.py`
  - `custom_components/heima/runtime/finding_router.py`
  - `custom_components/heima/runtime/analyzers/base.py`
  - `custom_components/heima/runtime/analyzers/registry.py`
  - `custom_components/heima/runtime/plugin_contracts.py`
  - `custom_components/heima/runtime/inference/approval_store.py`
  - `custom_components/heima/runtime/inference/__init__.py`
  - `tests/test_approval_store_contract.py`
  - `custom_components/heima/runtime/inference/modules/activity_inference.py`
  - `custom_components/heima/runtime/inference/modules/__init__.py`
  - `tests/test_inference_modules.py`
  - `custom_components/heima/runtime/analyzers/activity.py`
  - `custom_components/heima/runtime/analyzers/__init__.py`
  - `custom_components/heima/services.py`
  - `custom_components/heima/config_flow/_steps_reactions.py`
  - `tests/test_services_notify_event.py`
  - `tests/test_options_flow_e2e.py`
  - `docs/specs/heima_v2_spec.md`
  - `tests/test_integration_normalization_e2e.py`
  - `custom_components/heima/entities/registry.py`
  - `custom_components/heima/entities/sensor.py`
  - `custom_components/heima/services.py`
  - `custom_components/heima/services.yaml`
  - `custom_components/heima/const.py`
  - `tests/test_health_k.py`
  - `custom_components/heima/config_flow/__init__.py`
  - `custom_components/heima/room_inventory.py`
  - `custom_components/heima/discovery.py`
  - `tests/test_discovery_l.py`
  - `custom_components/heima/validation.py`
  - `tests/test_validation_m.py`
- Files changed:
  - `custom_components/heima/runtime/plugin_contracts.py`
  - `custom_components/heima/runtime/domain_result_bag.py`
  - `custom_components/heima/runtime/dag.py`
  - `custom_components/heima/runtime/domains/lighting.py`
  - `custom_components/heima/runtime/domains/heating.py`
  - `custom_components/heima/runtime/domains/security.py`
  - `custom_components/heima/runtime/engine.py`
  - `custom_components/heima/coordinator.py`
  - `tests/test_domain_plugin_dag.py`
  - `tests/test_calendar_domain.py`
  - `custom_components/heima/runtime/plugin_contracts.py`
  - `custom_components/heima/runtime/finding_router.py`
  - `custom_components/heima/runtime/proposal_engine.py`
  - `custom_components/heima/runtime/analyzers/presence.py`
  - `custom_components/heima/runtime/analyzers/heating.py`
  - `custom_components/heima/runtime/analyzers/anomaly.py`
  - `custom_components/heima/runtime/analyzers/correlation.py`
  - `custom_components/heima/coordinator.py`
  - `tests/test_proposal_engine.py`
  - `custom_components/heima/runtime/invariant_check.py`
  - `custom_components/heima/runtime/invariants/__init__.py`
  - `custom_components/heima/runtime/invariants/presence.py`
  - `custom_components/heima/runtime/invariants/security.py`
  - `custom_components/heima/runtime/invariants/heating.py`
  - `custom_components/heima/runtime/invariants/sensor.py`
  - `custom_components/heima/runtime/domains/occupancy.py`
  - `tests/test_invariant_checks.py`
  - `custom_components/heima/runtime/inference/__init__.py`
  - `custom_components/heima/runtime/inference/base.py`
  - `custom_components/heima/runtime/inference/signals.py`
  - `custom_components/heima/runtime/inference/snapshot_store.py`
  - `tests/test_inference_foundation.py`
  - `custom_components/heima/runtime/domains/activity_domain.py`
  - `tests/test_activity_domain.py`
  - `custom_components/heima/runtime/proposal_engine.py`
  - `custom_components/heima/runtime/finding_router.py`
  - `tests/test_proposal_engine.py`
  - `custom_components/heima/runtime/inference/approval_store.py`
  - `custom_components/heima/runtime/inference/__init__.py`
  - `tests/test_approval_store_contract.py`
  - `custom_components/heima/runtime/inference/modules/activity_inference.py`
  - `custom_components/heima/runtime/inference/modules/__init__.py`
  - `tests/test_inference_modules.py`
  - `custom_components/heima/runtime/analyzers/activity.py`
  - `custom_components/heima/runtime/analyzers/__init__.py`
  - `custom_components/heima/services.py`
  - `custom_components/heima/config_flow/_steps_reactions.py`
  - `tests/test_services_notify_event.py`
  - `tests/test_options_flow_e2e.py`
  - `tests/test_event_driven_trigger.py`
  - `tests/test_integration_normalization_e2e.py`
  - `docs/specs/heima_v2_spec.md`
  - `custom_components/heima/const.py`
  - `custom_components/heima/entities/registry.py`
  - `custom_components/heima/services.yaml`
  - `tests/test_health_k.py`
  - `custom_components/heima/config_flow/__init__.py`
  - `custom_components/heima/coordinator.py`
  - `custom_components/heima/discovery.py`
  - `tests/test_discovery_l.py`
  - `custom_components/heima/validation.py`
  - `tests/test_validation_m.py`
  - `docs/v2_dev_plan.md`
- Phase B implementation notes:
  - `kind="pattern"` (spec §8) is canonical for `ReactionProposal` routing.
  - `kind="proposal"` is not supported.
  - Analyzer outputs must be `BehaviorFinding` objects; bare `ReactionProposal` outputs are not
    accepted by `ProposalEngine`.
  - `FindingRouter` will expose async routing because `ProposalEngine` persistence is async.
- Tests run:
  - `.venv/bin/python -m pytest tests/test_domain_plugin_dag.py -q` — passed, 8 tests.
  - `.venv/bin/python -m pytest tests/test_domain_plugin_dag.py tests/test_engine_lighting_runtime.py tests/test_heating_runtime.py tests/test_security_mismatch_policy.py -q` — passed, 53 tests.
  - `.venv/bin/python -m pytest tests/test_engine_normalization_migration.py tests/test_engine_behavior_error_event.py tests/test_constraints_layer.py tests/test_sensor_entities.py -q` — passed, 23 tests.
  - `.venv/bin/python -m pytest tests/test_proposal_engine.py tests/test_presence_pattern_analyzer.py tests/test_heating_pattern_analyzer.py -q` — passed, 78 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 949 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_invariant_checks.py -q` — passed, 8 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 957 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_inference_foundation.py -q` — passed, 6 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 963 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_activity_domain.py -q` — passed, 12 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1007 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_activity_domain.py tests/test_activity_detectors.py -q` — passed, 38 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1033 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_activity_domain.py tests/test_activity_detectors.py tests/test_activity_bindings_and_shower.py -q` — passed, 47 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1042 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_activity_domain.py tests/test_activity_detectors.py tests/test_activity_bindings_and_shower.py tests/test_activity_engine_wiring.py -q` — passed, 52 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1047 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `source scripts/.env && ./scripts/check_all_live.sh --tier live_e2e` — passed.
  - `source scripts/.env && ./scripts/check_all_live.sh --tier diagnostic` — passed.
  - `source scripts/.env && ./scripts/check_all_live.sh --tier seeded_integration` — passed.
  - `.venv/bin/ruff check` on touched live/runtime scripts — passed.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1188 tests.
- Notes:
  - `tests/test_calendar_domain.py` had a date-dependent month-end failure on 2026-04-30
    (`today.day + 1`); it was fixed with `timedelta(days=1)`.
  - Remediation after spec correction: only `kind="pattern"` is supported for `ReactionProposal`
    routing; `kind="proposal"` was removed from runtime and tests.
  - All registered learning analyzers now return `BehaviorFinding(kind="pattern")` with the
    existing `ReactionProposal` as payload.
  - `ProposalEngine` rejects non-`BehaviorFinding` analyzer outputs instead of accepting legacy
    bare `ReactionProposal` objects.
  - Tests unwrap `finding.payload` explicitly; `BehaviorFinding` has no payload attribute
    delegation.
  - `AnomalyAnalyzer` and `CorrelationAnalyzer` are Phase B placeholders returning no findings.
- H3 tests run:
  - `.venv/bin/python -m pytest tests/test_inference_modules.py tests/test_approval_store_contract.py -q` — passed, 45 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1108 tests.
- H4 tests run:
  - `.venv/bin/python -m pytest tests/test_house_state_learning_h4.py tests/test_inference_modules.py tests/test_learning_reset.py tests/test_services_notify_event.py tests/test_proposal_engine.py -q` — passed, 128 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_house_state_learning_h4.py tests/test_learning_reset.py tests/test_services_notify_event.py tests/test_integration_normalization_e2e.py -q` — passed, 56 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1114 tests.
- H5 tests run:
  - `.venv/bin/python -m pytest tests/test_house_state_learning_h4.py tests/test_services_notify_event.py tests/test_options_flow_e2e.py -q` — passed, 172 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1120 tests.
  - `.venv/bin/python -m pytest tests/test_house_state_domain.py -q` — passed, 16 tests.
  - `.venv/bin/python -m pytest tests/test_inference_engine_wiring.py tests/test_inference_modules.py -q`
    — passed, 38 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_house_state_domain.py tests/test_inference_engine_wiring.py tests/test_inference_modules.py -q`
    — passed, 54 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1125 tests.
  - `.venv/bin/python -m pytest tests/test_proposal_engine.py -q` — passed, 65 tests.
  - `.venv/bin/ruff check custom_components/heima/runtime/proposal_engine.py custom_components/heima/runtime/finding_router.py tests/test_proposal_engine.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/runtime/proposal_engine.py custom_components/heima/runtime/finding_router.py tests/test_proposal_engine.py`
    — passed.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1129 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_approval_store_contract.py -q` — passed, 21 tests.
  - `.venv/bin/python -m pytest tests/test_approval_store_contract.py tests/test_proposal_engine.py -q`
    — passed, 86 tests.
  - `.venv/bin/ruff check custom_components/heima/runtime/inference/approval_store.py custom_components/heima/runtime/inference/__init__.py custom_components/heima/runtime/proposal_engine.py tests/test_approval_store_contract.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/runtime/inference/approval_store.py custom_components/heima/runtime/inference/__init__.py custom_components/heima/runtime/proposal_engine.py tests/test_approval_store_contract.py`
    — passed.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1137 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_inference_modules.py -q` — passed, 43 tests.
  - `.venv/bin/python -m pytest tests/test_inference_modules.py tests/test_approval_store_contract.py -q`
    — passed, 64 tests.
  - `.venv/bin/ruff check custom_components/heima/runtime/inference/modules/activity_inference.py custom_components/heima/runtime/inference/modules/__init__.py custom_components/heima/runtime/inference/__init__.py tests/test_inference_modules.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/runtime/inference/modules/activity_inference.py custom_components/heima/runtime/inference/modules/__init__.py custom_components/heima/runtime/inference/__init__.py tests/test_inference_modules.py`
    — passed.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1148 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_activity_analyzer.py -q` — passed, 9 tests.
  - `.venv/bin/python -m pytest tests/test_activity_analyzer.py tests/test_proposal_engine.py -q`
    — passed, 74 tests.
  - `.venv/bin/ruff check custom_components/heima/runtime/analyzers/activity.py custom_components/heima/runtime/analyzers/__init__.py tests/test_activity_analyzer.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/runtime/analyzers/activity.py custom_components/heima/runtime/analyzers/__init__.py tests/test_activity_analyzer.py`
    — passed.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1157 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_house_state_learning_h4.py tests/test_services_notify_event.py tests/test_options_flow_e2e.py -q`
    — passed, 180 tests.
  - `.venv/bin/python -m pytest tests/test_house_state_learning_h4.py tests/test_services_notify_event.py tests/test_options_flow_e2e.py tests/test_activity_analyzer.py tests/test_inference_modules.py -q`
    — passed, 232 tests.
  - `.venv/bin/ruff check custom_components/heima/coordinator.py custom_components/heima/services.py custom_components/heima/config_flow/_steps_reactions.py tests/test_house_state_learning_h4.py tests/test_services_notify_event.py tests/test_options_flow_e2e.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/coordinator.py custom_components/heima/services.py custom_components/heima/config_flow/_steps_reactions.py tests/test_house_state_learning_h4.py tests/test_services_notify_event.py tests/test_options_flow_e2e.py`
    — passed.
  - `.venv/bin/python -m pytest tests/ -q` — failed, 2 learning-reset stub regressions.
  - `.venv/bin/python -m pytest tests/test_learning_reset.py tests/test_house_state_learning_h4.py -q`
    — passed, 21 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1165 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_event_driven_trigger.py -q` — passed, 8 tests.
  - `.venv/bin/python -m pytest tests/test_event_driven_trigger.py tests/test_learning_reset.py tests/test_activity_engine_wiring.py tests/test_services_notify_event.py -q`
    — passed, 43 tests.
  - `.venv/bin/python -m pytest tests/test_integration_normalization_e2e.py -q`
    — passed, 21 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1173 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_health_k.py tests/test_services_notify_event.py -q`
    — passed, 30 tests.
  - `.venv/bin/python -m pytest tests/test_learning_reset.py tests/test_health_k.py tests/test_services_notify_event.py -q`
    — passed, 36 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1178 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1179 tests.
  - `.venv/bin/ruff check custom_components/heima tests` — passed.
  - `.venv/bin/ruff format --check custom_components/heima tests` — passed.
  - `.venv/bin/python -m pytest tests/test_discovery_l.py tests/test_options_flow_e2e.py::test_rooms_flow_persists_actuation_only_room_with_save_and_close -q`
    — passed, 5 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1183 tests.
  - `.venv/bin/ruff check custom_components/heima/discovery.py custom_components/heima/coordinator.py custom_components/heima/config_flow/__init__.py tests/test_discovery_l.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/discovery.py custom_components/heima/coordinator.py custom_components/heima/config_flow/__init__.py tests/test_discovery_l.py`
    — passed.
  - `.venv/bin/ruff check .` — failed on pre-existing unrelated `scripts/` import-order and
    unused-variable issues.
  - `.venv/bin/ruff format --check .` — failed on pre-existing unrelated `scripts/` formatting
    issues.
  - `.venv/bin/python -m pytest tests/test_validation_m.py tests/test_health_k.py tests/test_discovery_l.py -q`
    — passed, 14 tests.
  - `.venv/bin/python -m pytest tests/ -q` — passed, 1188 tests.
  - `.venv/bin/ruff check custom_components/heima/validation.py custom_components/heima/coordinator.py custom_components/heima/config_flow/__init__.py tests/test_validation_m.py`
    — passed.
  - `.venv/bin/ruff format --check custom_components/heima/validation.py custom_components/heima/coordinator.py custom_components/heima/config_flow/__init__.py tests/test_validation_m.py`
    — passed.
- Next concrete step: discuss the next v2 scope before implementation.
- Phase C implementation notes:
  - `_run_invariant_checks()` runs after `_compute_snapshot()` and before `_build_apply_plan()`.
  - Checks only receive `DecisionSnapshot` and `DomainResultBag`; they must not read EventStore or
    SnapshotStore.
  - `presence_without_occupancy` uses `OccupancyResult.sensorized_room_count` to avoid false
    positives for homes without sensorized rooms.
  - `InvariantViolation` is converted to `HeimaEvent(type=f"anomaly.{anomaly_type}")` after
    per-check debounce.
  - `anomaly.resolved` is emitted only after a previously active invariant clears.
  - Config defaults implemented: `anomaly_enabled=true`,
    `anomaly_sensor_stuck_threshold_s=86400`, `anomaly_heating_empty_threshold_s=1800`,
    `anomaly_notify_on_info=false`, `anomaly_re_emit_interval_s=3600`.
- Open decisions: none.

#### Phase F slice plan

- G1 — ActivityDomain foundation:
  - [x] Add `Activity`, `ActivityResult`, `ActivityDetection`, `ActivityHysteresisState`, and
    `ActivityDomain`.
  - [x] Add `IActivityDetector` protocol.
  - [x] Implement §7.5 hysteresis transitions and canonical keys:
    `activity.active_names`, `activity.candidate_names`, `activity.last_started`.
  - [x] Add tests for all hysteresis transitions, candidate/active result filtering, canonical keys,
    duplicate detector rejection, reset, diagnostics, and composite signal merge.
- G2 — Primitive power/media detectors:
  - [x] Add stove, oven, tv, pc, washing machine, and dishwasher detectors.
  - [x] Keep detector bindings explicit and inactive when unbound.
- G3 — Shower detector and activity bindings config:
  - [x] Add humidity/rate-of-change shower detector.
  - [x] Add `activity_bindings` runtime defaults, normalization, and detector builder.
- G4 — Engine and snapshot wiring:
  - [x] Insert ActivityDomain between OccupancyDomain and HouseStateDomain.
  - [x] Populate `InferenceContext.previous_activity_names` from CanonicalState.
  - [x] Populate `HouseSnapshot.detected_activities` from ActivityResult.

#### Phase D slice plan

- D1 — Inference Foundation:
  - [x] Add `runtime/inference/base.py` with `ILearningModule`, `HeimaLearningModule`, and
    `InferenceContext`.
  - [x] Add `runtime/inference/signals.py` with `Importance`, `InferenceSignal`,
    `HouseStateSignal`, `HeatingSignal`, `LightingSignal`, `ActivitySignal`, and
    `OccupancySignal`.
  - [x] Add `runtime/inference/__init__.py` public exports.
  - [x] Add tests for contracts and typed signal payloads.
- D2 — SnapshotStore:
  - [x] Add `HouseSnapshot` with `detected_activities`.
  - [x] Add `SnapshotStore` persisted with HA Store key `heima_snapshots`.
  - [x] Enforce max 10,000 records, 90-day TTL, and semantic write-on-change deduplication.
  - [x] Add tests for load/save, pruning, TTL, and dedup.
- D3 — Learning Modules + SignalRouter:
  - [x] Add `runtime/inference/modules/weekday_state.py` — `WeekdayStateModule`.
  - [x] Add `runtime/inference/modules/heating_preference.py` — `HeatingPreferenceModule`.
  - [x] Add `runtime/inference/router.py` — `SignalRouter`.
  - [x] Add tests: modules (importance ranges, min support, timing < 1ms), router (grouping,
    expiry, sorting, conflict warning).
- D4 — Engine wiring:
  - [x] Add `_collect_signals()` to `engine.py` — calls `module.infer(context)` for each module.
  - [x] Add `_record_snapshot_if_changed()` to `engine.py` — calls
    `SnapshotStore.async_append_if_changed()`.
  - [x] Add `signals: list[Any] | None = None` stub param to `OccupancyDomain.compute()` (spec §10.8).
    LightingDomain and HeatingDomain already had the param from Phase A.
  - [x] Wire `SignalRouter`, `SnapshotStore`, `WeekdayStateModule`, and
    `HeatingPreferenceModule` in `coordinator.py`.
  - [x] `_cancel_analyze_tick()` called in `async_shutdown()` — verified no lingering timers.

#### Phase A slices 2/3 implementation decision

- Add lightweight result dataclasses for Lighting, Heating, and Security plugin outputs.
- Make each built-in domain satisfy `IDomainPlugin` with `domain_id`, `depends_on`, and
  `compute(canonical_state, domain_results, signals=None)`.
- Preserve existing internal domain methods; plugin `compute()` wrappers should call current logic
  instead of duplicating or rewriting behavior.
- Use explicit runtime bindings/providers supplied by `HeimaEngine` for options, events,
  scheduler callbacks, room config callbacks, and other engine-owned dependencies.
- Keep Activity out of Phase A. The Phase A engine loop remains behavior-preserving and does not
  introduce the future Activity core domain.

**Open blockers:** none.

---

## Phase A — Plugin Framework

**Spec section:** §5 (Plugin Framework), §15 (File Structure — new files + modified files)
**Goal:** introduce `IDomainPlugin`, declarative DAG, and migrate Lighting/Heating/Security to plugins.
No new behavior — pure structural refactor. All 660 tests must be green at end of phase.

### Working slices

1. Contracts + DAG
   - Add `runtime/plugin_contracts.py`, `runtime/domain_result_bag.py`, and `runtime/dag.py`.
   - Add focused tests for topological ordering, cycle detection, and missing dependencies.
2. Built-in plugin compliance
   - Adapt Lighting, Heating, and Security domains to satisfy `IDomainPlugin`.
   - Preserve existing internal logic and public diagnostics.
   - Use explicit runtime bindings rather than hidden globals or ad hoc bag payloads.
3. Engine plugin loop
   - Add plugin registration/finalization to `HeimaEngine`.
   - Replace hardcoded Lighting/Heating/Security evaluation with the resolved plugin loop.
4. Coordinator wiring
   - Register built-in plugins and finalize the DAG during coordinator startup.
   - Preserve reload/reset behavior.
5. Verification and closeout
   - Run focused runtime tests, then the full suite.
   - Update acceptance criteria and Current State.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/plugin_contracts.py` | `IDomainPlugin`, `DomainResultBag`, `IOptionsSchemaProvider` Protocols | §5.1–5.6 |
| `runtime/dag.py` | `resolve_dag(plugins) -> list[IDomainPlugin]` with cycle + missing-dep detection | §5.3 |
| `runtime/domain_result_bag.py` | `DomainResultBag` dataclass | §5.4 |

### Files to modify

| File | Change |
|---|---|
| `runtime/domains/lighting.py` | Add `IDomainPlugin` compliance: `domain_id`, `depends_on`, `compute(canonical_state, domain_results, signals)` wrapping existing logic |
| `runtime/domains/heating.py` | Same as lighting |
| `runtime/domains/security.py` | Same as lighting |
| `runtime/engine.py` | Add `register_plugin()`, `finalize_dag()`, replace hardcoded Lighting/Heating/Security calls with DAG loop |
| `coordinator.py` | Call `register_plugin()` for each built-in plugin, call `finalize_dag()` on init |

### Acceptance criteria

- [x] `resolve_dag()` raises on cycles and missing dependencies
- [x] `LightingDomain`, `HeatingDomain`, `SecurityDomain` satisfy `IDomainPlugin` Protocol
- [x] Engine evaluates plugins via DAG loop (not hardcoded order)
- [x] Core domains (People, Occupancy, HouseState, Calendar) remain untouched
- [x] All existing tests pass
- [x] New tests: DAG cycle detection, missing dependency detection (at least 2 tests each)

---

## Phase B — IBehaviorAnalyzer + FindingRouter

**Spec section:** §8
**Goal:** unify behavior analysis under `IBehaviorAnalyzer`; introduce `FindingRouter`.
**Depends on:** Phase A complete.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/finding_router.py` | `FindingRouter` — routes `BehaviorFinding` by `kind` to `ProposalEngine` or logger | §8.3 |
| `runtime/analyzers/anomaly.py` | `AnomalyAnalyzer(IBehaviorAnalyzer)` | §8.4 |
| `runtime/analyzers/correlation.py` | `CorrelationAnalyzer(IBehaviorAnalyzer)` | §8.4 |

### Files to modify

| File | Change |
|---|---|
| `runtime/plugin_contracts.py` | Add `IBehaviorAnalyzer` Protocol, `BehaviorFinding`, `AnomalySignal` | §8.1–8.2 |
| `runtime/analyzers/presence.py` | Migrate `PresencePatternAnalyzer` to `IBehaviorAnalyzer` |
| `runtime/analyzers/heating.py` | Migrate `HeatingPatternAnalyzer` to `IBehaviorAnalyzer` |
| `coordinator.py` | Register analyzers, wire `FindingRouter` |

### Acceptance criteria

- [x] All existing analyzers satisfy `IBehaviorAnalyzer` Protocol
- [x] `FindingRouter` routes `kind="pattern"` → `ProposalEngine.submit()`
- [x] `FindingRouter` routes `kind="anomaly"` → `AnomalyEngine.submit_statistical()` (spec §8.3)
- [x] `FindingRouter` routes `kind="activity"` → `ProposalEngine.submit()` (stubbed, used in Phase H)
- [x] All existing tests pass

---

## Phase C — IInvariantCheck

**Spec section:** §9
**Goal:** per-cycle structural constraint checks with debounce and resolution events.
**Depends on:** Phase A complete.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/invariant_check.py` | `InvariantCheckState`, debounce loop helper | §9.5 |
| `runtime/invariants/presence.py` | `PresenceWithoutOccupancy` | §9.4 |
| `runtime/invariants/security.py` | `SecurityPresenceMismatch` | §9.4 |
| `runtime/invariants/heating.py` | `HeatingHomeEmpty` | §9.4 |
| `runtime/invariants/sensor.py` | `SensorStuck` | §9.4 |

### Files to modify

| File | Change |
|---|---|
| `runtime/plugin_contracts.py` | Add `IInvariantCheck` Protocol, `InvariantViolation` | §9.2–9.3 |
| `runtime/engine.py` | Add `_run_invariant_checks()` call after all domains computed, before Apply |
| `coordinator.py` | Register built-in invariant checks |

### Acceptance criteria

- [x] Each built-in check: at least 1 test for violation, 1 for resolution, 1 for debounce
- [x] Checks run after all domains computed, before Apply (spec §9 — pre-Apply guard)
- [x] Checks never read EventStore or SnapshotStore (enforce in code review)
- [x] Each `InvariantViolation` is immediately converted to `HeimaEvent(type=f"anomaly.{anomaly_type}")` with debounce per `check_id` (spec §9.3)
- [x] Config defaults implemented: `anomaly_enabled=true`, `anomaly_sensor_stuck_threshold_s=86400`, `anomaly_heating_empty_threshold_s=1800`, `anomaly_notify_on_info=false`, `anomaly_re_emit_interval_s=3600` (spec §9.6)
- [x] All tests pass

---

## Phase D — InferenceEngine v2 (base)

**Spec section:** §10 (InferenceEngine v2)
**Goal:** `SnapshotStore`, `ILearningModule`, `InferenceContext`, per-cycle signal collection.
**Depends on:** Phase A complete.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/inference/__init__.py` | Public API exports | — |
| `runtime/inference/base.py` | `ILearningModule`, `HeimaLearningModule`, `InferenceContext` | §10.4, §10.2 |
| `runtime/inference/signals.py` | `Importance`, `InferenceSignal` hierarchy, `ActivitySignal` | §10.3 |
| `runtime/inference/snapshot_store.py` | `HouseSnapshot` (with `detected_activities`), `SnapshotStore` | §10.1 |
| `runtime/inference/router.py` | `SignalRouter` | §10.7 |
| `runtime/inference/modules/weekday_state.py` | `WeekdayStateModule` | §10.6 |
| `runtime/inference/modules/heating_preference.py` | `HeatingPreferenceModule` | §10.6 |

### Files to modify

| File | Change |
|---|---|
| `runtime/engine.py` | Add `_collect_signals()`, `_record_snapshot_if_changed()` | §10 |
| `runtime/domains/lighting.py` | Add `compute(signals: list[...] = [])` parameter | §10.8 |
| `runtime/domains/heating.py` | Same |
| `runtime/domains/occupancy.py` | Add `compute(signals: list[OccupancySignal] = [])` stub | §10.8 |
| `coordinator.py` | Register learning modules, wire `SignalRouter` |

### Notes

- `RoomStateCorrelationModule` and `LightingPatternModule` are deferred to Phase D2 (post-Phase I).
- `HouseSnapshot.detected_activities` is created empty here; populated in Phase G.
- `InferenceContext.previous_activity_names` is created empty here; populated in Phase G.

### Acceptance criteria

- [x] `SnapshotStore` persists to HA Store key `heima_snapshots`
- [x] `_record_snapshot_if_changed()` only writes on state change (deduplication)
- [x] `WeekdayStateModule` and `HeatingPreferenceModule` return typed signals
- [x] `ILearningModule.infer()` completes in < 1ms (verified via test timing)
- [x] All tests pass — 995 tests (D1–D4 added 335 new tests)

---

## Phase E — OutcomeTracker + Feedback Loop

**Spec section:** §12 (OutcomeTracker)
**Goal:** act→verify loop; degrade reactions that consistently fail.
**Depends on:** Phase D complete.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/outcome_tracker.py` | `OutcomeTracker`, `PendingVerification`, `OutcomeRecord` | §12.2 |

### Files to modify

| File | Change |
|---|---|
| `runtime/reactions/base.py` | Add `outcome_spec: OutcomeSpec | None` field | §12.2 |
| `runtime/engine.py` | Call `OutcomeTracker.check_pending()` after Apply | §12 |
| `proposal_engine.py` | Add `submit()` entry point for tracker-triggered degradation proposals | §12.4 |
| `coordinator.py` | Wire `OutcomeTracker` |

### Slice plan

- [x] E1 — OutcomeTracker foundation:
  - Create `OutcomeTracker`, `OutcomeSpec`, `PendingVerification`, and `OutcomeRecord`.
  - Support registering pending verifications, resolving positive outcomes, resolving timeout
    negatives, tracking consecutive negative streaks, and diagnostics.
  - Keep this slice synchronous, in-memory, and not wired into the engine.
- [x] E2 — Reaction contract:
  - Add default `HeimaReaction.outcome_spec: OutcomeSpec | None` returning `None`.
  - Add `PresencePatternReaction.outcome_spec` with `expected_event_type="presence"` and
    `timeout_s=1800`, matching `EventRecorderBehavior` arrival events with
    `data.transition == "arrive"` for the later E3 matcher.
  - Keep `ConsecutiveStateReaction` out of E2 because its expected event depends on runtime
    configuration and is not hardcodable in the class contract.
  - Keep reaction behavior unchanged when no `outcome_spec` is present.
- [x] E3 — Runtime wiring:
  - Add `OutcomeSpec.match_data` and subset matching against observed `HeimaEvent.data`.
  - Buffer EventRecorderBehavior events for the current evaluation cycle only.
  - Register pending verifications when reaction-originated apply steps are fired.
  - Call `OutcomeTracker.check_pending()` after apply using current cycle observations.
- [x] E4 — Feedback and degradation proposal:
  - Emit at most one degradation `ReactionProposal` after five consecutive negatives until
    user resolution.

### Acceptance criteria

- [x] Positive outcome (entity state matches expected within timeout) → recorded
- [x] Negative outcome (timeout, no match) → degradation proposal emitted
- [x] `check_pending()` is synchronous and completes in O(pending count)
- [x] Tests: positive outcome, negative outcome, timeout policy
- [x] All 1076 tests pass

---

## Phase F — ActivityDomain

**Spec section:** §7 (Activity Layer)
**Goal:** primitive activity detection, hysteresis state machine, `ActivityResult` in DAG.
**Depends on:** Phase A (DomainResultBag) and Phase D (HouseSnapshot.detected_activities).

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/domains/activity_domain.py` | `Activity`, `ActivityResult`, `ActivityDetection`, `ActivityHysteresisState`, `ActivityDomain` | §7.2–7.4 |
| `runtime/activity_detectors/__init__.py` | Exports | — |
| `runtime/activity_detectors/stove.py` | `StoveOnDetector` (power ≥ 200W, candidate 5s, grace 30s) | §7.6 |
| `runtime/activity_detectors/oven.py` | `OvenOnDetector` (power ≥ 500W, candidate 10s, grace 120s) | §7.6 |
| `runtime/activity_detectors/tv.py` | `TvActiveDetector` (media_player + power, candidate 10s, grace 120s) | §7.6 |
| `runtime/activity_detectors/pc.py` | `PcActiveDetector` (power ≥ 50W, candidate 30s, grace 60s) | §7.6 |
| `runtime/activity_detectors/shower.py` | `ShowerRunningDetector` (humidity + rate_of_change, candidate 60s, grace 300s) | §7.6 |
| `runtime/activity_detectors/washing.py` | `WashingMachineDetector` (power ≥ 200W, candidate 60s, grace 300s) | §7.6 |
| `runtime/activity_detectors/dishwasher.py` | `DishwasherDetector` (power ≥ 200W, candidate 60s, grace 300s) | §7.6 |

### Files to modify

| File | Change |
|---|---|
| `runtime/plugin_contracts.py` | Add `IActivityDetector` Protocol | §7.4 |
| `runtime/engine.py` | Insert `ActivityDomain` between OccupancyDomain and HouseStateDomain in core evaluation order; populate `InferenceContext.previous_activity_names` from CanonicalState | §7.3 |
| `runtime/inference/snapshot_store.py` | Populate `HouseSnapshot.detected_activities` from `ActivityResult` | §10.1 |
| `runtime/activity_detectors/config.py`, `const.py` | Add `activity_bindings` defaults and normalization (maps detector names to HA entity IDs) | §7.3 |

### Hysteresis state machine (implement exactly as spec §7.5)

```
absent → candidate  : detector.detect() returns ActivityDetection
candidate → absent  : detect() returns None before candidate_period_s elapsed
candidate → active  : detect() returns non-None AND candidate_period_s elapsed
active → grace      : detect() returns None
grace → active      : detect() returns non-None (signal returned)
grace → absent      : grace_period_s elapsed without signal
```

### CanonicalState keys written by ActivityDomain

- `activity.active_names`: `tuple[str, ...]`
- `activity.candidate_names`: `tuple[str, ...]`
- `activity.last_started`: `str` — ISO-8601 timestamp of most recent `activity.started` event (spec §7.8)

### Acceptance criteria

- [x] All 5 hysteresis transitions tested
- [x] `ActivityResult.active` contains only phase=ACTIVE detectors
- [x] `ActivityResult.candidates` contains only phase=CANDIDATE detectors
- [x] `CanonicalState` keys written correctly each cycle
- [x] `InferenceContext.previous_activity_names` reads from CanonicalState (one-cycle lag)
- [x] `HouseSnapshot.detected_activities` populated
- [x] All tests pass; new tests ≥ 20

---

## Phase G — Role model + product constraints

**Spec section:** New §1.x in `docs/specs/heima_v2_spec.md`
**Goal:** Document the B2B product model and wire approval records with `approved_by` tracking. Prerequisite for Phase H.
**Depends on:** —

### New files to create

None — role model is spec + contract additions only.

### Files to modify

| File | Change |
|---|---|
| `docs/specs/heima_v2_spec.md` | §1.1 Product Model — **done** |
| `runtime/inference/approval_store.py` | Add `approved_by: Literal["resident", "installer"]` to approval record contract |
| `services.yaml` | Add `heima.override_approval(proposal_id, action, installer_override=True)` service definition |

### Acceptance criteria

- [x] §1.1 Product Model in `heima_v2_spec.md`: B2B model, installer role, resident role, HA admin/user mapping, notification routing policy
- [x] `ApprovalStore` approval records include `approved_by: Literal["resident", "installer"]`
- [x] `heima.override_approval` with `installer_override: true` defined in `services.yaml`
- [x] Notification routing policy documented: behavioral proposals → resident; anomalies/invariant violations → installer (implementation in Phase K)
- [x] All existing tests pass — 1084 tests

---

## Phase H — House State Learning

**Spec section:** §13 (House State Learning), §10.9
**Goal:** `HouseStateInferenceModule`, user-approval gate.
**Depends on:** Phases D, E, and G complete.

### Product constraints (from Phase G)

- `ApprovalStore` must store `approved_by: Literal["resident", "installer"]` on every record.
- Proposal notifications route to resident channel only.
- Installer override via `heima.override_approval` service (defined in Phase G).

### Slice plan

- [x] H1 — ApprovalStore and context keys:
  - Implement persistent `ApprovalStore` with HA Store key `heima_inference_approvals`.
  - Require `approved_by` and `context_snapshot` on every `ApprovalRecord`.
  - Add stable `house_state_context_key(...)` with sorted rooms, fixed H1 learning-context
    vocabulary, deterministic context hash, and `state:{predicted_state}` in the key.
  - Add tests for load/save, malformed record rejection, `decision_for()`, room sorting,
    context hash stability, empty context, and mandatory context snapshot.
- [x] H2 — HouseStateInferenceModule:
  - Learn house-state probabilities from snapshots and keep accumulating/analyzing even when
    approval gates block signal emission.
- [x] H3 — Proposal and approval gate:
  - Expose proposal-first learned candidates for unknown/pending contexts.
  - Keep signal emission limited to approved contexts; rejected contexts produce no signal and no
    candidate.
  - Keep ProposalEngine submission out of H3; H4 owns runtime wiring.
- [x] H4 — Engine/coordinator wiring:
  - Load ApprovalStore, register HouseStateInferenceModule, and route approvals through the
    coordinator product-flow layer.
- [x] H5 — Resident approval surface + service:
  - Send `persistent_notification` nudge pointing to resident dashboard when a new
    `house_state_learned_context` proposal is pending (dedup guard: do not re-send for
    already-notified pending proposals).
  - Add `heima.approve_proposal(proposal_id, action)` service in `services.yaml`; handler
    calls `coordinator.async_review_house_state_proposal(..., approved_by="resident")`.
  - Add `house_state_learned_context` review step in config flow options (installer path,
    `approved_by="installer"`).
  - Do not implement a Lovelace card in H5; expose dashboard-ready data through
    `sensor.heima_reaction_proposals` and the `heima.approve_proposal` service.
- [x] H6 — HouseStateDomain signal consumption:
  - Pass routed `HouseStateSignal` buckets from the engine to `HouseStateDomain`.
  - Consume only approved learned house-state signals after manual override, vacation, and
    everyone-away hard guards.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/inference/modules/house_state_inference.py` | `HouseStateInferenceModule` | §13, §10.6 |

### Files to modify

| File | Change |
|---|---|
| `runtime/inference/approval_store.py` | Full implementation with `approved_by` field | §10.9 |
| `runtime/domains/house_state.py` | Consume `HouseStateSignal`; approval gate | §10.9 |
| `config_flow/` | `house_state_learned_context` proposal type review screen |

### Acceptance criteria

- [x] `HouseStateInferenceModule` emits `HouseStateSignal` only for approved patterns
- [x] `ApprovalStore` persists to HA Store key `heima_inference_approvals`
- [x] `ApprovalStore` records include `approved_by` field
- [x] Unapproved signals are ignored by `HouseStateDomain`
- [x] User approval/rejection survives HA restart
- [x] All existing tests pass — 1125 tests

---

## Phase I — Activity Inference and Learning

**Spec section:** §7.7 (ActivityProposal), §10.5 (ActivityInferenceModule)
**Goal:** composite activity discovery; `ActivityAnalyzer`; user-approved `ActivitySignal`.
**Depends on:** Phases D, H, and F complete.

### Slice plan

- [x] I1 — ActivityProposal contract and proposal plumbing:
  - Add `ActivityProposal` support to the shared proposal store.
  - Route `BehaviorFinding(kind="activity")` only when the payload is an `ActivityProposal`.
  - Preserve existing `ReactionProposal` behavior unchanged.
- [x] I2 — Activity approval contract:
  - Add stable activity approval key/snapshot helpers and `activity_discovered` approval records.
- [x] I3 — ActivityInferenceModule:
  - Emit `ActivitySignal` only for approved composite activity proposals with support/confidence.
- [x] I4 — ActivityAnalyzer:
  - Discover composite activity candidates from `SnapshotStore`; use named constants for
    min 10 co-occurrences and min 3 distinct days.
- [x] I5 — Resident/installer review surfaces:
  - Add review and approval wiring for `activity_discovered` proposals.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/analyzers/activity.py` | `ActivityAnalyzer(IBehaviorAnalyzer)` — min 10 co-occurrences across 3+ days | §7.7 |
| `runtime/inference/modules/activity_inference.py` | `ActivityInferenceModule(ILearningModule)` — emits `ActivitySignal` for approved proposals only | §10.5 |

### Files to modify

| File | Change |
|---|---|
| `runtime/proposal_engine.py` | Add `ActivityProposal` dataclass support | §7.7 |
| `runtime/finding_router.py` | Handle `kind="activity"` → `ProposalEngine.submit(ActivityProposal)` | §8.3 |
| `runtime/inference/approval_store.py` | Support `"activity_discovered"` proposal type |
| `runtime/domains/activity_domain.py` | Step 5: merge `ActivitySignal` from `ActivityInferenceModule` into `ActivityResult` | §7.3 |
| `config_flow/` | `activity_discovered` proposal review surface |

### Product constraints (from Phase G)

- `ActivityProposal` approvals must include `approved_by` field, consistent with `ApprovalStore` contract from Phase G.
- Proposal notifications route to resident channel; installer override via `heima.override_approval`.

### Acceptance criteria

- [x] `ActivityAnalyzer` does not emit `ActivityProposal` with < 10 co-occurrences or < 3 distinct days
- [x] `ActivityInferenceModule.infer()` returns `[]` until at least one `ActivityProposal` approved
- [x] Approved composite activity appears in `ActivityResult.active` when signal fired
- [x] Approval survives HA restart (via `ApprovalStore`) with `approved_by` populated
- [x] All existing tests pass; new tests ≥ 15 — 1165 tests

---

## Phase J — Event-Driven Trigger

**Spec section:** §11 (Event-Driven Trigger)
**Goal:** HA `state_changed`-driven evaluation, per-class debounce, 300s periodic fallback.
**Depends on:** Phase F (power threshold binding config).

### Files to modify

| File | Change | Spec ref |
|---|---|---|
| `coordinator.py` | `_on_state_changed()` listener | §11.1 |
| `coordinator.py` | `_classify_entity()` — pattern matching + explicit config | §11.2 |
| `coordinator.py` | Per-class debounce handles (see table below) | §11.3 |
| `coordinator.py` | `_eval_running` guard against re-entrant evaluation | §11.3 |
| `coordinator.py` | Periodic fallback: 300s (reduce from current fixed interval) | §11.4 |
| `coordinator.py` | Power threshold crossing detection (feeds activity detector bindings) | §11.2 |

### Entity class debounce table (implement exactly)

| Class | Debounce |
|---|---|
| `presence` | 5s |
| `motion` | 3s |
| `door_window` | 2s |
| `power_threshold` | 5s |
| `calendar` | 0s |
| `override` | 0s |
| `weather` | 10s |
| environmental sensors | no trigger (read passively) |

### Acceptance criteria

- [x] State change on a classified entity triggers evaluation within debounce window
- [x] Re-entrant evaluation is skipped (guard active)
- [x] Periodic 300s fallback fires even with no state changes
- [x] Environmental sensors do not trigger evaluation
- [x] All existing tests pass; new tests cover debounce timing and re-entrancy guard — 1173 tests

---

## Phase K — Installer alert channel + health entity

**Spec section:** Phase K delivery section in `docs/specs/heima_v2_spec.md`
**Goal:** Route anomaly/invariant violation alerts to installer HA user; expose `sensor.heima_health` for remote monitoring.
**Depends on:** Phase C (IInvariantCheck).

### Files to modify

| File | Change |
|---|---|
| `coordinator.py` | Route `anomaly.*` events to installer notification channel (HA admin user) |
| `entities/` | Add `sensor.heima_health` with state (`ok` / `degraded` / `error`) and diagnostic attributes |
| `services.yaml` | Add `heima.run_diagnostics` service returning structured diagnostic payload |

### Acceptance criteria

- [x] Anomaly/invariant violation events routed to installer channel, not resident channel
- [x] `sensor.heima_health` exposed with overall state and `last_anomaly` attribute
- [x] `heima.run_diagnostics` service call returns structured diagnostic payload
- [x] All existing tests pass — 1179 tests

---

## Phase L — Auto-discovery config flow

**Spec section:** `docs/specs/heima_v2_spec.md` — Phase L
**Goal:** Scan HA entity registry using device classes to suggest bindings; installer confirms in options flow.
**Depends on:** —

### Discovery strategy

Uses HA domain, device classes, area metadata, and device registry metadata — no ML, no NLP, and
no fragile entity-name heuristics for activity type selection:

| HA device class | Heima binding candidate |
|---|---|
| `motion` | motion sensor |
| `door`, `window` | door/window security sensor |
| `occupancy` | presence sensor |
| `humidity` | shower detector |
| `power`, `energy` | generic activity power candidate |
| `media_player` | tv/pc detector |

Power and energy sensors remain generic `activity_power_candidate` suggestions. The installer
chooses stove/oven/appliance-specific bindings later in manual activity configuration.
Each `DiscoveredBindingCandidate.reason` must be shown in the options flow review step.

### Files to modify

| File | Change |
|---|---|
| `config_flow/` | Add auto-discovery step: scan entities, group by device class, present suggestions |
| `coordinator.py` | Add `async_discover_entities()` helper |

### Acceptance criteria

- [x] Discovery step presented before manual binding in options flow
- [x] Suggestions grouped by functional category (presence, security, activity detectors)
- [x] Installer can accept all, reject all, or selectively confirm
- [x] Discovery result feeds into existing binding normalization
- [x] Ambiguous suggestions are recorded but do not silently mutate concrete config
- [x] All existing tests pass — 1183 tests

---

## Phase M — Installation validation

**Spec section:** `docs/specs/heima_v2_spec.md` — Phase M
**Goal:** After config, report what Heima can and cannot do with the current binding set.
**Depends on:** Phase L.

### Validation report covers

- Activities detectable with current bindings vs. activities missing required sensors
- Invariant checks active vs. inactive (missing required entities)
- Learning modules with sufficient data vs. insufficient data
- Validation is informational and non-blocking
- Validation is cheap and stateless: structural config coverage and snapshot counts only; no live
  entity availability checks

### Files to modify

| File | Change |
|---|---|
| `config_flow/` | Add validation summary step at end of options flow |
| `coordinator.py` | Add `async_validate_config() -> ValidationReport` |
| `validation.py` | Add `ValidationReport`, sections, issues, and structural validation builder |

### Acceptance criteria

- [x] Validation report generated from current config
- [x] Missing bindings listed with human-readable description of what is unavailable
- [x] Report accessible via `sensor.heima_health` attributes and via `heima.run_diagnostics`
- [x] Options flow exposes a non-blocking validation summary step
- [x] All existing tests pass — 1188 tests

---

## Phase N — Semantic Policy Suggestions

**Spec section:** §N (Semantic Policy Suggestions)
**Goal:** propose pre-configured `admin_authored` reactions from entity topology; installer reviews in existing config flow.
**Depends on:** Phase A complete.

### Working slices

1. N1 — `AlarmStateActionReaction`:
   - Create `runtime/reactions/alarm_policy.py`.
   - Implement `AlarmStateActionReaction(HeimaReaction)` with `alarm_states`, `steps`, and `_last_fired_state` firing guard.
   - Implement `normalize_alarm_state_action_config()`, `build_alarm_state_action_reaction()`, and `present_alarm_state_action_label()`.
   - Register `RegisteredReactionPlugin` for `"alarm_state_action"` in `runtime/reactions/__init__.py`.
   - Add focused tests: state entry fires once, stays-in-state no repeat, state exit resets, multiple alarm states.
2. N2 — `SemanticRule` + `BUILTIN_SEMANTIC_RULES`:
   - Create `runtime/semantic_policies.py`.
   - Implement `SemanticRule` dataclass with `rule_id`, `description`, `evaluate(options) -> ReactionProposal | None`.
   - Implement the four Phase N built-in rules (see §N.4).
   - Add focused tests: rule returns None when alarm_entity missing, returns None when target entities missing, returns proposal with correct steps when topology complete.
3. N3 — Coordinator wiring:
   - Add `_async_evaluate_semantic_policies()` to `coordinator.py`.
   - Call it from `async_config_entry_first_refresh()` and `async_reload()`.
   - Call `_async_notify_installer_alert()` when a new semantic proposal is submitted for the first time.
   - Add integration test: coordinator submits proposals on first refresh, does not duplicate on reload.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/reactions/alarm_policy.py` | `AlarmStateActionReaction`, builder, normalizer, presenter | §N.3 |
| `runtime/semantic_policies.py` | `SemanticRule` + `BUILTIN_SEMANTIC_RULES` | §N.1, §N.4 |
| `tests/test_semantic_policies_n.py` | Tests for slices N1–N3 | §N |

### Files to modify

| File | Change |
|---|---|
| `runtime/reactions/__init__.py` | Register `alarm_state_action` plugin |
| `coordinator.py` | Add `_async_evaluate_semantic_policies()`, call sites |

### Built-in rules (Phase N)

| Rule ID | Trigger | Action | Required topology |
|---|---|---|---|
| `alarm_away_lights_off` | `armed_away` | `light.turn_off` all light entities | `alarm_entity` + ≥1 light entity |
| `alarm_triggered_lights_on` | `triggered` | `light.turn_on` all light entities | `alarm_entity` + ≥1 light entity |
| `alarm_away_climate_off` | `armed_away` | `climate.set_hvac_mode hvac_mode=off` | `alarm_entity` + ≥1 thermostat entity |
| `alarm_night_climate_sleep` | `armed_night` | `climate.set_preset_mode preset_mode=sleep` | `alarm_entity` + ≥1 thermostat entity |

### Acceptance criteria

- [x] `AlarmStateActionReaction` fires once per state entry, does not repeat while in the same state
- [x] `AlarmStateActionReaction` resets `_last_fired_state` when `security_state` leaves `alarm_states`
- [x] Each built-in rule returns `None` when any required entity is absent
- [x] Each built-in rule returns a valid `ReactionProposal` with correct `suggested_reaction_config` when topology is complete
- [x] Coordinator calls `_async_evaluate_semantic_policies()` on first refresh and reload
- [x] ProposalEngine deduplication prevents re-submission of already-pending/approved proposals
- [x] Installer is notified via `_async_notify_installer_alert()` on first new semantic proposal
- [x] Targeted tests pass; new tests ≥ 15

---

## Phase O — HouseSnapshot Alignment + Proposal Revocation

**Spec section:** Phase O
**Goal:** align HouseSnapshot with the data needed by later phases; add proposal revocation.
**Depends on:** Phase N.

### Working slices

1. O1 — HouseSnapshot `security_state`:
   - Replace `security_armed: bool` with `security_state: str` in `HouseSnapshot`.
   - Add backward-compatible migration in `from_dict()`: if `security_state` is absent, derive it
     from `security_armed` (True → `"armed_away"`, False → `"disarmed"`).
   - Update `HeatingDomain` and any other reference to `security_armed`.
   - Tests: legacy deserialization, round-trip of the new format.
2. O2 — HouseSnapshot `heating_current_temperature`:
   - Add field `heating_current_temperature: float | None` to `HouseSnapshot`.
   - `HeatingDomain` reads `climate.ATTR_CURRENT_TEMPERATURE` and passes it to the snapshot.
   - Tests: field populated when available, None when absent.
3. O3 — `ProposalEngine.async_withdraw`:
   - Add `async_withdraw(identity_key) -> bool` to `ProposalEngine`.
   - Removes only proposals in `pending` status; no-op on approved/rejected.
   - Update `_async_evaluate_semantic_policies()` in the coordinator to call `async_withdraw()` on
     rules that no longer apply.
   - Tests: withdraw pending → True, withdraw approved → False, withdraw absent → False.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `tests/test_snapshot_migration_o.py` | Legacy format migration, new fields | Phase O |

### Files to modify

| File | Change |
|---|---|
| `runtime/inference/snapshot_store.py` | `security_state`, `heating_current_temperature`, `from_dict()` migration |
| `runtime/domains/heating.py` | Reads `current_temperature` attr, passes it to the snapshot |
| `runtime/proposal_engine.py` | `async_withdraw(identity_key)` |
| `coordinator.py` | `_async_evaluate_semantic_policies()`: calls `async_withdraw()` |
| `tests/test_proposal_engine.py` | Extend: test `async_withdraw` |

### Acceptance criteria

- [x] `HouseSnapshot.security_state` is `str`, not `bool`
- [x] Snapshots serialized with `security_armed: bool` deserialize correctly
- [x] `HouseSnapshot.heating_current_temperature` is populated when the climate entity is available
- [x] `ProposalEngine.async_withdraw()` removes only pending proposals, no-op on others
- [x] `_async_evaluate_semantic_policies()` calls `async_withdraw()` for rules that no longer apply
- [x] Full regression tests pass

---

## Phase P — Learning Modules D2: Lighting, Room Correlation, Occupancy

**Spec section:** Phase P
**Goal:** complete Phase D2; add OccupancyInferenceModule.
**Depends on:** Phase D (ILearningModule, SnapshotStore), Phase F (room_occupancy in HouseSnapshot).

### Working slices

1. P1 — `LightingPatternModule`:
   - Implement `ILearningModule` that learns `P(scene | room_id, house_state, hour_bucket)`.
   - Min support 8 snapshots/slot. Emits `LightingSignal(importance=SUGGEST, confidence ≥ 0.65)`.
   - Tests: model building from a snapshot sequence, signal emission, min support respected.
2. P2 — `RoomStateCorrelationModule`:
   - Implement `ILearningModule` that learns `P(house_state | frozenset(occupied_rooms))`.
   - Min support 15 snapshots/pattern. Emits `HouseStateSignal`.
   - Tests: patterns with support < 15 ignored, signal with correct confidence.
3. P3 — `OccupancyInferenceModule` + `OccupancyDomain` consumption:
   - Implement `ILearningModule` that learns `P(room_occupied | room_id, weekday, hour_bucket, anyone_home)`.
   - Min support 10 snapshots/slot. Emits `OccupancySignal` only for rooms without a sensor.
   - `OccupancyDomain.compute()`: for rooms without a sensor, applies `OccupancySignal` if
     confidence ≥ 0.70.
   - Tests: rooms with a sensor ignore the signal, rooms without one apply it.
4. P4 — Coordinator wiring:
   - Register the three new modules in the coordinator.
   - P4a: the modules run in the real cycle and are observable in diagnostics; only
     `OccupancySignal` influences runtime. `LightingSignal` and `RoomStateCorrelationModule`
     remain signal-only.
   - P4b: formalize proposal-gated consumption. `LightingSignal` and the room/house-state
     correlation signal do not enter the domains; future analyzers produce reviewable proposals.
   - Tests: verify the modules are called in the inference cycle, that sensorless-room sync
     happens on startup/options reload, and that signals with no consumer don't cause errors.
   - Verification: `context_conditioned_lighting_scene` exists as a reaction type for future
     lighting proposals. For house-state correlation, the path remains the dedicated
     approval/candidate mechanism, not a direct runtime reaction plugin.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/inference/modules/lighting_pattern.py` | `LightingPatternModule` | Phase P, §10.6 |
| `runtime/inference/modules/occupancy_inference.py` | `OccupancyInferenceModule` | Phase P |
| `tests/test_learning_modules_p.py` | Tests P1–P4 | Phase P |

### Files to modify

| File | Change |
|---|---|
| `runtime/inference/modules/room_state.py` | Implement `RoomStateCorrelationModule` (file exists as a stub) |
| `runtime/domains/occupancy.py` | Consume `OccupancySignal` for rooms without a sensor |
| `coordinator.py` | Register three new modules |

### Acceptance criteria

- [x] `LightingPatternModule` does not emit signals with support < 8 snapshots/slot
- [x] `RoomStateCorrelationModule` does not emit signals for patterns with support < 15
- [x] `OccupancyInferenceModule` emits `OccupancySignal` only for rooms without a sensor
- [x] `OccupancyDomain` applies `OccupancySignal` with confidence ≥ 0.70 for unsensored rooms
- [x] `OccupancyDomain` ignores `OccupancySignal` for rooms with at least one sensor
- [x] P4a registers modules P1-P3 in the coordinator lifecycle
- [x] `sync_sensorless_rooms()` is called on startup/options reload, not in the analyze loop
- [x] `LightingSignal` with no operational consumer is routed/observable and causes no errors
- [x] `RoomStateCorrelationModule` remains observable but does not alter `HouseStateDomain`
- [x] P4b policy: operational statistical signals only via ProposalEngine + admin review
- [x] Verified lighting target: `context_conditioned_lighting_scene` exists
- [x] All existing tests green; new tests ≥ 20

---

## Phase Q — AnomalyAnalyzer: Statistical Detection Rules

**Spec section:** Phase Q
**Goal:** implement `AnomalyAnalyzer` with 15 operational rules configurable in the current v2
scope; keep in the catalog the 2 planned lighting rules for completion in Phase U / physical light
state awareness; `heima.configure_anomaly_rule` service.
**Depends on:** Phase O (security_state, heating_current_temperature), Phase P (snapshot data quality).

### Working slices

1. Q1 — `AnomalyRule` + catalog + infrastructure: `DONE`
   - Define the `AnomalyRule` dataclass with `rule_id`, `enabled`, `severity`, `thresholds`.
   - Define the catalog with default thresholds for all 17 planned rules.
   - Implement loading thresholds from options on every `analyze()`.
   - Implement at least one real rule end-to-end to validate the
     `AnomalyAnalyzer -> FindingRouter -> installer alert` path.
   - The `heima.configure_anomaly_rule` service is out of Q1; it stays in Q6.
2. Q2 — Presence rules (4): `DONE`
   - `arrival_time_outlier`, `departure_time_outlier`, `extended_absence`, `presence_pattern_drift`.
   - `arrival_time_outlier` and `departure_time_outlier` use consecutive transitions
     `anyone_home=False -> True` and `anyone_home=True -> False`; the most recent transition is
     compared against the historical median of previous transitions.
   - `extended_absence` uses the current `anyone_home=False` run and compares it against the 90th
     percentile of historical absence runs.
   - `presence_pattern_drift` compares the recent `anyone_home=True` ratio against the baseline for
     the same `(weekday, hour_bucket)`.
   - Presence anomaly rules are house-state aware: `vacation` snapshots are excluded from normal
     presence baselines, and no presence anomaly is emitted while the current snapshot is in
     `house_state=vacation`.
   - Follow-up audit covered all canonical house states:
     - `vacation` is an expected-absence context and must not produce absence-only anomalies.
     - `away` is still valid input for absence/security/heating rules and is not globally excluded.
     - `guest`, `home`, `working`, `sleeping`, and `relax` remain valid learned/runtime contexts.
   - Tests: each rule covers trigger, insufficient support, normal condition, threshold override,
     and disabled rule.
3. Q3 — Heating rules (3): `DONE`
   - `heating_setpoint_outlier`, `heating_unresponsive`, `heating_vacation_mismatch`.
   - Tests: `heating_unresponsive` uses `heating_current_temperature` from Phase O.
4. Q4 — Activity rules (3): `DONE`
   - `stove_on_unattended`, `oven_on_unattended`, `appliance_unusual_hour`.
   - `lights_on_unattended` and `lighting_scene_drift` completed in Phase U / physical light state
     awareness.
   - `appliance_unusual_hour` triggers only if the activity is active in the last snapshot (option A).
5. Q5 — Security + sensor + cross-domain rules (5): `DONE`
   - `alarm_disarm_unusual_hour`, `alarm_expected_not_armed`, `sensor_activity_drop`, `ghost_activity`, `unusual_stillness`.
   - Security subset `DONE`: `alarm_disarm_unusual_hour`, `alarm_expected_not_armed`.
   - Residual subset `DONE`: `sensor_activity_drop`, `ghost_activity`, `unusual_stillness`.
   - `sensor_activity_drop` and `ghost_activity` are vacation-aware: they ignore `vacation`
     snapshots and do not emit when the current snapshot is in `house_state=vacation`.
   - `lights_on_unattended` is also vacation-aware because vacation presence simulation may
     intentionally leave lights on while no resident is home.
   - Safety-critical unattended appliance rules (`stove_on_unattended`, `oven_on_unattended`) remain
     active during `vacation`.
   - Statistical anomaly alerts are reconciled after each analyzer run. If a previous anomaly type
     is no longer emitted, `_last_anomaly` is cleared and the matching installer persistent
     notification is dismissed.
6. Q6 — `heima.configure_anomaly_rule` service: `DONE`
   - Handler in the coordinator: updates options, takes effect on the next `analyze()`.
   - Tests: threshold override applied, disabled rule doesn't trigger.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `tests/test_anomaly_analyzer_q.py` | Tests Q1–Q6 | Phase Q |

### Files to modify

| File | Change |
|---|---|
| `runtime/analyzers/anomaly.py` | Full implementation (replaces placeholder) |
| `services.yaml` | `heima.configure_anomaly_rule` |
| `coordinator.py` | Service handler, passes updated options to AnomalyAnalyzer |

### Acceptance criteria

- [x] Every rule in Q scope triggers on a snapshot sequence built ad hoc in the test
- [x] Disabled rule produces no findings
- [x] Threshold override via `heima.configure_anomaly_rule` applied on the next `analyze()` pass
- [x] Q1 validates at least one real rule end-to-end through to the installer alert
- [x] `heating_unresponsive` uses `heating_current_temperature` (Phase O prerequisite verified)
- [x] `heating_setpoint_outlier` uses `heating_setpoint` and a snapshot-count window
- [x] `heating_vacation_mismatch` uses `security_state`, `heating_setpoint`, and a strict `>` threshold
- [x] Q2 presence rules use only `HouseSnapshot.anyone_home`, time slots, and consecutive
      transitions
- [x] `alarm_disarm_unusual_hour` uses `security_state` and consecutive `armed_* -> disarmed` transitions
- [x] `alarm_expected_not_armed` uses only statistical patterns from `security_state` in the same slot
- [x] `sensor_activity_drop` does not overlap with `SensorStuck` (snapshot/hour frequency vs absolute timeout)
- [x] `ghost_activity` uses `room_occupancy` + `anyone_home` from `HouseSnapshot`
- [x] `unusual_stillness` uses a run of unchanged `room_occupancy` with `anyone_home == True`
- [x] Q4 activity rules use `HouseSnapshot.detected_activities`; the 2 lighting rules are
      completed in Phase U / physical light state awareness
- [x] `heima.configure_anomaly_rule` merges `entry.options["anomaly"]["rules"][rule_id]` without reload
- [x] All existing tests green; Q tests cover every operational rule, threshold overrides,
      disabled rule, and the end-to-end path to the installer alert

---

## Phase R — OutcomeTracker Positive Feedback + WeekdayStateModule Consolidation

**Spec section:** Phase R
**Goal:** bidirectional feedback loop; downgrade WeekdayStateModule to OBSERVE.
**Depends on:** Phase E (OutcomeTracker base), Phase P (HouseStateInferenceModule + room correlation wired).

### Working slices

1. R1 — OutcomeTracker `positive_streak` + boost:
   - Status: `DONE`.
   - Add `positive_streak: int` per reaction alongside the existing `negative_streak`.
   - After K=10 consecutive positives, call `ProposalEngine.async_boost_confidence(reaction_id, delta=0.05)`.
   - Reset `positive_streak` after the boost (not after the next negative).
   - `positive_streak` resets on every negative outcome.
   - Tests: streak accumulation, boost at K=10, reset, no double-boost within the same cycle.
2. R2 — `ProposalEngine.async_boost_confidence`:
   - Status: `DONE`.
   - Add `async_boost_confidence(reaction_id, delta) -> None`.
   - Increases the confidence of the approved proposal record for `reaction_id`, capped at 1.0.
   - No-op if reaction_id is not found or the proposal is not approved.
   - Tests: boost applied, cap at 1.0, no-op on unknown reaction.
3. R3 — WeekdayStateModule downgrade:
   - Status: `DONE`.
   - Modify `WeekdayStateModule.infer()`: all emitted signals use `importance=Importance.OBSERVE`.
   - Verify that `HouseStateDomain` ignores OBSERVE signals (already defined in §10.3/§10.8).
   - Tests: WeekdayStateModule emits OBSERVE; HouseStateDomain does not consume them.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `tests/test_outcome_tracker_r.py` | Tests R1–R2 | Phase R |
| `tests/test_weekday_consolidation_r.py` | Tests R3 | Phase R |

### Files to modify

| File | Change |
|---|---|
| `runtime/outcome_tracker.py` | `positive_streak`, boost trigger at K=10 |
| `runtime/proposal_engine.py` | `async_boost_confidence(reaction_id, delta)` |
| `runtime/inference/modules/weekday_state.py` | `importance=Importance.OBSERVE` |
| `scripts/live_tests/066_positive_outcome_boost_live.py` | Live E2E for accepted proposal confidence boost |

### Acceptance criteria

- [x] `OutcomeTracker` accumulates `positive_streak` separately from `negative_streak`
- [x] Boost sent to `ProposalEngine` after exactly K=10 consecutive positives
- [x] `positive_streak` reset after the boost, not after the next negative
- [x] No double-boost within the same positive streak cycle
- [x] `async_boost_confidence` capped at 1.0
- [x] `WeekdayStateModule` emits `Importance.OBSERVE` (not `SUGGEST`)
- [x] `HouseStateDomain` does not consume OBSERVE signals (regression test)
- [x] Live E2E: proposal accepted with `target_reaction_id`, 10 positive outcomes, confidence boost and streak reset
- [x] All existing tests green; new tests ≥ 12

---

## Phase S — Learning Module Threshold Configurability

**Spec section:** §10.6 (note "Threshold configurability")
**Goal:** turn each module's `min_support` and `confidence_threshold` into constructor parameters,
passed from `entry.options["learning"]`. No change to default values. No admin UI for thresholds.
**Depends on:** Phase R (operational feedback loop — lets us observe whether the default values are
adequate before making the thresholds configurable).

### Motivation

Households with very different data density (e.g. smart working vs. frequent travel) may have
slots with insufficient support even after months of use. Configurable thresholds allow lowering
`min_support` for low-data environments without changing the code. The auto-tuning policy
(OutcomeTracker-driven) stays out of scope.

### Working slices

0. S0 — Baseline audit (documentation lock):
   - Current hardcoded/default thresholds:
     - `weekday_state`: `min_support=10`, `confidence_threshold=0.40`
     - `heating_preference`: `min_support=10`, `confidence_threshold=0.40`
     - `house_state_inference`: `min_support=3`, `confidence_threshold=0.60`
     - `lighting_pattern`: `min_support=8`, `confidence_threshold=0.65`
     - `room_state_correlation`: `min_support=15`, `confidence_threshold=0.60`
     - `occupancy_inference`: `min_support=10`, `confidence_threshold=0.70`
   - At S0, `house_state_inference`, `lighting_pattern`, `room_state_correlation`, and
     `occupancy_inference` already have constructor parameters and diagnostics for both values.
   - At S0, `weekday_state` and `heating_preference` used module-level `_MIN_SUPPORT` and hardcoded
     `0.40` confidence gates; Phase S adds constructor parameters and diagnostics.

1. S1 — Refactor constructors:
   - `WeekdayStateModule(min_support=10, confidence_threshold=0.40)`
   - `HeatingPreferenceModule(min_support=10, confidence_threshold=0.40)`
   - Keep existing constructor contracts for:
     - `HouseStateInferenceModule(min_support=3, confidence_threshold=0.60)`
     - `LightingPatternModule(min_support=8, confidence_threshold=0.65)`
     - `RoomStateCorrelationModule(min_support=15, confidence_threshold=0.60)`
     - `OccupancyInferenceModule(min_support=10, confidence_threshold=0.70)`
   - All default values unchanged relative to the current hardcoded values.
2. S2 — Read from `learning_config` in the coordinator:
   - Read `entry.options.get("learning", {})` and pass the values to the constructors.
   - Options keys: `{module_id}_min_support`, `{module_id}_confidence_threshold`.
   - If the key doesn't exist in options, use the constructor default.
   - Conservative parsing: missing, non-numeric, `None`, or out-of-range values are ignored and
     leave the module's default active. No UI validation in Phase S.
3. S3 — `diagnostics()` exposes the effective values:
   - Each module adds `min_support` and `confidence_threshold` to its own `diagnostics()`.
   - Allows verifying the active values without accessing options.
   - Modules that already expose these values remain unchanged except for an optional regression test.

### Implementation order

1. Update `WeekdayStateModule` and `HeatingPreferenceModule` first, because they are the only
   modules without constructor-configurable thresholds today.
2. Add a small coordinator helper that extracts per-module numeric thresholds from
   `entry.options["learning"]`, clamps via each module constructor, and keeps defaults when keys are
   missing or invalid.
3. Wire all six module constructors through the helper in `HeimaCoordinator.__init__`.
4. Add/adjust tests:
   - module-level tests proving defaults are unchanged;
   - module-level tests proving custom thresholds affect emission gates;
   - coordinator wiring test proving options are passed to constructors;
   - diagnostics tests proving effective values are visible.
5. Run focused tests first:
   - `pytest tests/test_inference_modules.py tests/test_learning_modules_p.py tests/test_inference_engine_wiring.py -q`
   - then full suite or project standard check before closing Phase S.

### Acceptance criteria

- [x] All modules accept `min_support` and `confidence_threshold` as constructor parameters with unchanged defaults
- [x] The coordinator reads from `entry.options["learning"]` and passes the values to the constructors
- [x] Each module's `diagnostics()` exposes the effective values of `min_support` and `confidence_threshold`
- [x] No observable behavior change with default options
- [x] All existing tests green (no test should change the default values) — 1362 passed

---

## Phase T — Learning Signal Analyzers

**Spec section:** §10 (inference engine — proposal-gated signal consumption)
**Status:** `DEFERRED`
**Goal:** turn mature statistical signals (`LightingSignal`, `HouseStateSignal`) into
`ReactionProposal` via ProposalEngine + admin review. No signal acquires direct operational
authority over the domains.
**Depends on:** Phase P (active, observable learning modules), Phase S (configurable thresholds —
signals must be measurable before promoting them to a proposal).

### Defer rationale

T1 has a fundamental gap: `LightingPatternModule` learns `P(scene_name | room_id, house_state, hour_bucket)`
from snapshots, but the `context_conditioned_lighting_scene` contract requires `entity_steps`
(concrete per-entity actuations). T1 knows the scene name but not the list of entities to
actuate — the resulting proposal would be incomplete and would require the admin to manually
configure the `entity_steps`.

The existing `LightingAnalyzer` (`runtime/analyzers/lighting.py`) already produces complete
proposals with `entity_steps` starting from HA events. T1 would add little differential value.

T2 remains blocked: no `reaction_type` for "house state rule".

Phase T can be reconsidered if:
- a reaction type is introduced that accepts HA scenes by name (e.g. `scene.*`) without requiring
  explicit `entity_steps`; or
- T1 is redesigned as an enrichment of the existing `LightingAnalyzer` rather than as an
  independent analyzer.

---

## Phase U — Physical Light State Awareness

**Goal:** give Heima runtime and historical awareness of light entities physically on in HA,
independent of the scenes Heima manages. Unlocks the resident card (live light state) and
completes the lighting anomaly rules planned in Phase Q.
**Depends on:** Phase A (plugin framework), Phase Q (anomaly catalog already defined).

### Motivation

`HouseSnapshot.lighting_scenes` records Heima's decisions (applied scenes), not the physical state
of the lights. If a resident turns on a light manually and then leaves, Heima has no record of it.
This phase adds a "physical" observation layer for all configured light entities, without
requiring the general `monitored_entities` mechanism (deferred to Plugin API v3+).

### Working slices

1. U1 — `LightingResult.lights_on`:
   - Add `lights_on: dict[str, bool]` (entity_id → is_on) to `LightingResult`.
   - `LightingDomain.compute()` reads `hass.states.get(entity_id).state == "on"` for all
     configured light entities (rooms + lighting_rooms). Entity absent from hass.states → False.
   - Only light entities with domain `light.*` (consistent with `_unique_entities` in semantic_policies).

2. U2 — `CanonicalState` and `InferenceContext`:
   - The engine writes `lighting.lights_on` (serialized dict) to `CanonicalState` after
     evaluating the LightingDomain.
   - `InferenceContext` exposes `lights_on: dict[str, bool]` to the learning modules.

3. U3 — `HouseSnapshot.lights_physically_on`:
   - Add `lights_physically_on: dict[str, bool]` to `HouseSnapshot`.
   - `_record_snapshot_if_changed()` populates the field from `LightingResult.lights_on`.
   - Serialization/deserialization consistent with the snapshot's other dict fields.

4. U4 — Lighting anomaly rules:
   - Implement `lights_on_unattended` and `lighting_scene_drift` in `AnomalyAnalyzer`,
     now that `HouseSnapshot.lights_physically_on` and `lighting_scenes` are available together.
   - `lights_on_unattended`: triggers if, in the last `window` snapshots, at least one entry in
     `lights_physically_on` is True AND `anyone_home == False` for `min_observations` snapshots.
     Defaults: window=6, min_observations=3. Severity: warning.
   - `lighting_scene_drift`: compares the recent scene for `(room_id, house_state, hour_bucket)`
     against the historical baseline from `lighting_scenes`. Pure diagnostic, no proposal.
     Defaults: history_window=1000, min_observations=10, recent_observations=3, baseline_ratio=0.65.
   - Update the Phase Q notes to indicate completion in Phase U.

### Files to modify

| File | Change |
|---|---|
| `runtime/plugin_contracts.py` or `runtime/domains/lighting.py` | Add `lights_on` to `LightingResult` |
| `runtime/domains/lighting.py` | Read physical states in `compute()` |
| `runtime/engine.py` | Write `lighting.lights_on` to `CanonicalState`; populate `InferenceContext` |
| `runtime/inference/snapshot_store.py` | Add `lights_physically_on` to `HouseSnapshot` |
| `runtime/analyzers/anomaly.py` | Implement `lights_on_unattended` and `lighting_scene_drift` |
| `tests/test_anomaly_analyzer_q.py` | Test U4 lighting rules |

### Acceptance criteria

- [x] `LightingResult.lights_on` reflects the physical HA state, not Heima's scenes
- [x] `CanonicalState["lighting.lights_on"]` available after every evaluation cycle
- [x] `HouseSnapshot.lights_physically_on` persisted and readable by the anomaly analyzer
- [x] `lights_on_unattended` triggers when at least one configured light entity is physically
      on while `anyone_home == False`
- [x] `lighting_scene_drift` compares recent scenes vs the historical baseline for slot `(room_id, house_state, hour_bucket)`
- [x] All existing tests green; new tests ≥ 2 (one per lighting rule)

---

## Phase V — Signal Discovery Pipeline

**Spec section:** `docs/specs/learning/signal_discovery_spec.md`
**Goal:** discover useful HA entities already present in the installation, classify them with
rule-based heuristics, and propose additive config patches to the installer. Accepted patches add
room signals or learning sources to existing options; runtime canonicalization remains owned by
`EventCanonicalizer`.
**Depends on:** Phase N (ProposalEngine + installer proposal review), Phase L (auto-discovery
config-flow patterns).

### Scope guardrails

- Signal discovery does not normalize runtime values. It only proposes options patches.
- `EventCanonicalizer` remains the only runtime normalizer for `rooms[*].signals`.
- Discovery runs outside the hot path: coordinator startup and `EVENT_ENTITY_REGISTRY_UPDATED`.
- Accepted `signal_discovery` proposals must not be written to `options["reactions"]["configured"]`.
- v2 supports only built-in rule-based classes: room lux, room CO2, room humidity, and media-player
  learning sources. Plugin classifier APIs and solar/energy packs are deferred to v3.

### Working slices

1. V1 — Inventory and classification:
   - Add `HAEntityDescriptor`, `SignalSuggestion`, and `SignalOptionsPatch`.
   - Implement `SignalDiscoveryAudit.run()` over HA entity registry + current states.
   - Classify supported entities by domain/device_class/unit/area only; no EventStore/history reads.
   - Map HA area names to existing Heima `room_id` values using the spec heuristic.

2. V2 — Proposal submission:
   - Add coordinator storage for `_pending_signal_suggestions`.
   - Submit suggestions to `ProposalEngine` with `analyzer_id = "signal_discovery"` and stable
     `identity_key = "signal_discovery:{entity_id}"`.
   - Reuse installer persistent notifications with deduplication.

3. V3 — Accept routing:
   - Add coordinator review branch for `signal_discovery` proposals.
   - Guard every config-flow proposal acceptance path so signal discovery never writes configured
     reactions or labels.
   - Accept/reject only changes proposal status; options are patched lazily by the coordinator.

4. V4 — Options patch application:
   - Implement `_async_apply_accepted_signal_patches()`.
   - Apply one accepted patch per cycle through `async_update_entry`.
   - Use current options as the idempotency guard: existing `signal_name` or `learning_sources`
     entity_id means skip.

5. V5 — Triggering and tests:
   - Run audit at coordinator startup and schedule audit on `EVENT_ENTITY_REGISTRY_UPDATED`.
   - Add focused tests for classification, room mapping, proposal dedupe, accept routing, options
     patch idempotency, and reload-safe re-application.

### Files to modify

| File | Change |
|---|---|
| `runtime/signal_discovery.py` | Add descriptors, suggestions, patch model, and `SignalDiscoveryAudit` |
| `coordinator.py` | Store pending suggestions, submit proposals, review signal discovery proposals, apply accepted patches, register triggers |
| `config_flow/_steps_reaction_proposals.py` | Short-circuit all signal discovery accept paths before reaction config writes |
| `tests/` | Add unit/integration coverage for V1-V5 behavior |

### Acceptance criteria

- [ ] Supported HA entities are classified only by allowed metadata and mapped to existing Heima rooms
- [ ] Unmapped or unsupported entities are ignored without persistence
- [ ] New signal discovery suggestions are submitted once per stable `identity_key`
- [ ] Accepting a signal discovery proposal never mutates `options["reactions"]["configured"]`
- [ ] Accepted room-signal patches add to `rooms[*].signals` only when that `signal_name` is absent
- [ ] Accepted learning-source patches add to `rooms[*].learning_sources` only when that entity_id is absent
- [ ] Re-running after coordinator restart does not re-apply an already reflected patch
- [ ] Discovery audit is never called from `infer()` or domain evaluation methods
- [ ] All existing tests pass; new tests cover classification, routing, and idempotency

---

## Phase W — Calendar: `day_off` and `holiday` categories

**Spec section:** `docs/specs/domains/calendar_domain_spec.md` (extension)
**Goal:** Add `day_off` and `holiday` as first-class calendar categories to suppress `work_candidate` on
non-vacation rest days, without activating away-from-home semantics.
**Depends on:** —

### Problem

Without these categories, any day without a calendar event defaults to `is_workday=True`. National
holidays and personal days off are treated as workdays. The keyword `"holiday"` currently maps to
`vacation`, forcing `vacation_mode=True` — incorrect semantics for at-home rest days.

### New categories

| Category | Meaning | Effect on work_candidate | Effect on vacation_mode |
|---|---|---|---|
| `day_off` | Personal day off / at-home rest | `is_workday=False` | None (not activated) |
| `holiday` | National / bank holiday | `is_workday=False` | None (not activated) |

### Keyword changes

- `"holiday"` moved from `vacation` → `holiday` category
- `holiday` default keywords: `["festivo", "festa nazionale", "bank holiday", "national holiday", "public holiday", "giorno festivo", "holiday"]`
- `day_off` default keywords: `["giorno libero", "day off", "permesso", "recupero", "riposo"]`
- `"ferie"` remains in `vacation` (multi-day, away-from-home semantics)

### Contract changes

**`CalendarEvent.category`:** extend literal to include `"day_off"` and `"holiday"`.

**`CalendarResult`:** add two fields:
```python
is_day_off_today: bool    # day_off event active or all-day today
is_holiday_today: bool    # holiday event active or all-day today
```

**`DEFAULT_CALENDAR_CATEGORY_PRIORITY`:** `["vacation", "holiday", "day_off", "office", "wfh", "visitor"]`

**Workday evidence chain in `HouseStateDomain`** — updated order:
```
1. is_office_today=True   → is_workday=False, source=calendar_office
2. is_day_off_today=True  → is_workday=False, source=calendar_day_off    ← NEW
3. is_holiday_today=True  → is_workday=False, source=calendar_holiday    ← NEW
4. is_wfh_today=True      → is_workday=True,  source=calendar_wfh
5. workday_entity         → normalized bool,  source=workday_entity
6. default                → is_workday=True,  source=default_true
```

New reason strings: `calendar_day_off`, `calendar_holiday`.

### Working slices

1. W1 — `CalendarDomain`: add categories to literal/enum, add default keywords, add
   `is_day_off_today` and `is_holiday_today` to `CalendarResult`, update classification logic.
2. W2 — `HouseStateDomain`: update workday evidence chain, add new reason strings.
3. W3 — Tests + spec update for `calendar_domain_spec.md`.

### Files to modify

| File | Change |
|---|---|
| `const.py` | Add `day_off`, `holiday` keyword defaults; update category priority |
| `runtime/domains/calendar.py` | Classification logic, `CalendarResult` fields |
| `runtime/domains/house_state.py` | Workday evidence chain |
| `docs/specs/domains/calendar_domain_spec.md` | Reflect new categories and contract |
| `tests/` | New tests for W1–W3 |

### Acceptance criteria

- [x] `is_day_off_today=True` or `is_holiday_today=True` → `work_candidate=False` regardless of `work_window`
- [x] `vacation_mode` not activated by `day_off` or `holiday` events
- [x] `"holiday"` keyword no longer classifies as `vacation`
- [x] Existing `vacation`, `wfh`, `office`, `visitor` behavior unchanged
- [x] All existing tests pass; new tests cover classification and workday chain

---

## Phase X — Room Context Model

Status: DONE on branch `feat/phase-x-room-context`.

**Spec section:** New `docs/specs/learning/room_context_spec.md`
**Goal:** Transform signal model from global boolean aggregates to room-scoped device context vectors,
derived from already-configured entities' HA area assignments. No static room tagging by user.
Semantics emerge from signal composition at runtime.
**Depends on:** Phase U (`lights_physically_on`), Phase V (area registry reading pattern)

### Design rationale

`media_active` is a global OR over all configured media players. Multiple rooms with media players
lose spatial context. A media player used for work in a study produces the same global signal as one
used for leisure in a living room. The fix is not static room labeling (rooms are multi-purpose) but
contextual composition: `media_on=True AND work_activity=True` in the same room → work context, not
relax. `media_on=True AND work_activity=False` → relax evidence.

### Core contract: `RoomDeviceContext`

New file: `custom_components/heima/runtime/room_context.py`

```python
@dataclass(frozen=True)
class RoomDeviceContext:
    room_id: str
    media_on: bool        # any media_active_entity in room active (post-normalization)
    lights_on: bool       # any light entity in room physically on (from lights_physically_on)
    work_activity: bool   # any work_activity_entity in room active (post-normalization)
    pc_active: bool       # pc/workstation entity in room active (best-effort; False if no area)
```

`occupied` is NOT included — already in `room_occupancy`. No duplication.

### Room-entity mapping (X1)

X1 does NOT scan all HA entities. It maps **already-configured** entities to rooms:

```
For each entity_id in options (media_active_entities, work_activity_entities, etc.):
  1. Look up area_id via HA entity registry (entity.area_id) or device registry fallback
     (entity.device_id → device.area_id) — same pattern as room_inventory.py
  2. Find Heima room_id where options["rooms"][room]["area_id"] == area_id
  3. entity_id → room_id
```

Entities without an HA area, or whose area doesn't match any configured Heima room, contribute
only to the existing global aggregates — no change to current behavior.

**Notes:**
- `lights_by_room` uses `lights_physically_on` (already per-entity from Phase U) → aggregate by room
- `pc_active_by_room` uses the same power entity configured for pc detection → area lookup
- Rooms without `area_id` configured in Heima options do not participate in room context

**Registry freshness:** X1 subscribes to `EVENT_ENTITY_REGISTRY_UPDATED` and
`EVENT_AREA_REGISTRY_UPDATED` (same pattern as Phase V / signal_discovery). On event: mark mapping
as stale; rebuild on next coordinator cycle.

**Unavailability:** `unavailable` and `unknown` states for configured entities are already
normalized to `False` by `InputNormalizer` upstream. No separate policy needed in X1.

**Mapping drift:** When a device is reassigned to a different room in HA, old snapshots contain the
entity in the previous room's context. This causes a training data transition window (typically
2–4 weeks) during which RoomContextModule patterns for the old assignment lose support below
`min_support` and new patterns accumulate. Self-correcting; no action required in the model.

### Overlap note

`RoomStateCorrelationModule` (Phase P2) learns `P(house_state | frozenset(occupied_rooms))` —
conditions on occupancy only. `RoomContextModule` (X5) conditions on device state per room in
addition to occupancy. Different feature space, no duplication. `RoomStateCorrelationModule` is
preserved unchanged.

### Working slices

1. X1 — Room-entity mapping layer:
   - `RoomDeviceContextBuilder` in `runtime/room_context.py`
   - Builds `entity_to_room: dict[entity_id, room_id]` at coordinator init and on registry events
   - Computes `media_by_room`, `lights_by_room`, `work_activity_by_room`, `pc_by_room`
   - Writes `CanonicalState["rooms.device_context"]`

2. X2 — `RoomDeviceContext` dataclass + `InferenceContext` extension:
   - `RoomDeviceContext` dataclass in `runtime/room_context.py`
   - `InferenceContext` new field: `room_device_context: dict[str, RoomDeviceContext] = field(default_factory=dict)`
   - Backward compat: empty dict default; existing modules unaffected

3. X3 — `HouseSnapshot` extension:
   - New field: `room_device_context: dict[str, dict]`
   - Serialization/deserialization consistent with existing dict fields
   - Semantic dedup key updated to include room_device_context

4. X4 — Candidate resolver enrichment:
   - `relax_candidate`: if `room_device_context` populated, use room-scoped logic:
     `relax_media = any(ctx.media_on and not ctx.work_activity for ctx in occupied_contexts)`
     replaces global `media_active` for relax evidence.
   - `work_candidate`: if occupied room has `work_activity=True` or `pc_active=True`,
     media in the same room does NOT suppress work evidence.
   - Fallback: if `room_device_context` empty → current behavior unchanged (backward compat).

5. X5 — `RoomContextModule` (ILearningModule):
   - `module_id = "room_context"`
   - Learns: `P(house_state | room_context_pattern, weekday, hour_bucket)`
   - `room_context_pattern = frozenset((room_id, media_on, work_activity) for occupied rooms)`
     (`lights_on` and `pc_active` excluded from pattern key — too noisy / less reliable)
   - `min_support=20` (default), `confidence_threshold=0.65` — configurable via Phase S mechanism
   - Signal: `HouseStateSignal(source_id="room_context", importance=SUGGEST)`
   - Approval-gated: same flow as `HouseStateInferenceModule`
   - Wired in coordinator alongside existing learning modules

### Files to modify / create

| File | Change |
|---|---|
| `runtime/room_context.py` | New: `RoomDeviceContext`, `RoomDeviceContextBuilder` |
| `runtime/inference/base.py` | Add `room_device_context` to `InferenceContext` |
| `runtime/inference/snapshot_store.py` | Add `room_device_context` to `HouseSnapshot` |
| `runtime/domains/house_state.py` | Candidate resolver enrichment (X4) |
| `runtime/inference/modules/room_context.py` | New: `RoomContextModule` |
| `coordinator.py` | Wire builder, subscribe to registry events, register module |
| `docs/specs/learning/room_context_spec.md` | New spec file |
| `tests/` | New tests: mapping, resolver, module (≥ 15) |

### Acceptance criteria

- [x] `RoomDeviceContext` computed correctly from HA area registry for configured entities
- [x] `InferenceContext.room_device_context` populated each cycle
- [x] `HouseSnapshot.room_device_context` persisted and deserialized correctly
- [x] `relax_candidate` uses room-scoped media logic when context available; falls back to global when not
- [x] `work_candidate` not suppressed by media when same occupied room has `work_activity=True`
- [x] `RoomContextModule` emits no signals with support < 20
- [x] Device reassignment or removal causes no runtime error; fallback to global aggregates
- [x] Household with no area mappings: behavior identical to pre-Phase-X
- [x] All existing tests pass; new tests ≥ 15

### Implementation notes

- `runtime/media_activity.py` centralizes the existing media-active semantics so the global
  `HouseStateDomain` path and the room-scoped context path do not diverge.
- `RoomContextModule` reuses the `house_state_learned_context` approval lifecycle with a distinct
  `learning_context.module = "room_context"` key segment.
- The coordinator listens to entity and area registry updates and marks the room-context mapping
  stale; rebuilding happens on the next engine cycle.
- Extensibility decision: do not expose a public room-context plugin API yet. The next step should
  be an internal `RoomContextSignalProvider` interface with entity-to-room mapping still owned only
  by `RoomDeviceContextBuilder`. Keep the explicit dataclass fields as compatibility layer; add
  future signals through an internal extension path before considering a generic public signal model.

---

## Phase Y — HouseStateInferenceModule: tiered feature enrichment

Status: DONE on branch `feat/phase-y-tiered-house-state-inference`.

**Spec section:** `docs/specs/heima_v2_spec.md` §13 (extension)
**Goal:** Enrich `HouseStateInferenceModule` conditioning with room device context using a tiered
fallback strategy to preserve min-support guarantees when feature space is sparse.
**Depends on:** Phase X (`room_device_context` in `HouseSnapshot`)

### Tiered key strategy

Current key: `(weekday, hour_bucket, frozenset(room_occupancy.items()), anyone_home)`

| Tier | Conditioning key | Min support | Active when |
|---|---|---|---|
| Rich | `(weekday, hour_bucket, room_context_signature)` | 15 (default) | `room_device_context` present in snapshot AND support ≥ threshold |
| Coarse | `(weekday, hour_bucket, frozenset(occupied_rooms), anyone_home)` | existing module default (`3`) unless configured | Rich tier insufficient |
| Minimal | `(weekday, hour_bucket, anyone_home)` | 5 (default) | Coarse tier insufficient |

`room_context_signature = frozenset((room_id, media_on, work_activity) for occupied rooms)` —
same definition as `RoomContextModule.room_context_pattern` for consistency.

Snapshots without `room_device_context` populate Coarse and Minimal tiers only.

### Working slices

1. Y1 — Model tiering: `analyze()` builds three independent model dicts from snapshot history.
   Each tier tracks support and confidence independently.

2. Y2 — Tiered inference: `infer()` tries Rich → Coarse → Minimal. Emits signal from the first
   tier with sufficient support and confidence. Signal context dict includes `tier: "rich" | "coarse" | "minimal"`.

3. Y3 — Configurable thresholds: `house_state_inference_rich_min_support` and
   `house_state_inference_minimal_min_support` in `options["learning"]` (Phase S mechanism).

4. Y4 — Diagnostics: `diagnostics()` exposes slot count and hit rate per tier.

### Files to modify

| File | Change |
|---|---|
| `runtime/inference/modules/house_state_inference.py` | Tiered model, tiered inference, diagnostics |
| `tests/` | New tests: tier selection, fallback, diagnostics |

### Acceptance criteria

- [x] Rich tier used when `room_device_context` available and support ≥ threshold
- [x] Coarse fallback when Rich tier insufficient; Minimal fallback when Coarse insufficient
- [x] No signal emitted if all tiers below threshold
- [x] Active tier visible in signal context dict and diagnostics
- [x] Household without Phase X data: behavior identical to pre-Phase-Y (Coarse/Minimal only)
- [x] All existing tests pass

### Implementation notes

- Coarse keeps the pre-Phase-Y approval key shape (`learning_context={}`), preserving existing
  approvals.
- Rich and Minimal use distinct `learning_context.module` values so approval keys cannot collide
  with Coarse or `RoomContextModule`.
- `HouseStateSignal.context["tier"]` exposes the active tier; existing signal construction remains
  backward compatible because the context field defaults to `{}`.
- Follow-up required: generalized as Phase AC. `house_state_learned_context` is the first plugin
  using ProposalEngine review grouping; approval identity remains the exact `context_key`.

---

## Phase Z — Activity cold start mitigation

Status: DONE on branch `feat/phase-z-activity-cold-start`.

**Spec section:** `docs/specs/heima_v2_spec.md` §7.7 (extension)
**Goal:** Reduce the minimum evidence window for composite activity discovery to accelerate first
proposals in data-sparse environments.
**Depends on:** Phase S (threshold configurability)

### Problem

`MIN_COOCCURRENCES=10`, `MIN_DISTINCT_DAYS=3` in `ActivityAnalyzer` → earliest possible first
proposal requires ≥ 3 distinct days with ≥ 10 co-occurrence observations. In practice: 2–4 weeks.
No mitigation exists today.

### Solution: `activity_bootstrap_mode`

New option: `options["learning"]["activity_bootstrap_mode"]: bool` (default `false`, user opt-in).

When enabled:
- `ActivityAnalyzer`: `MIN_COOCCURRENCES=5`, `MIN_DISTINCT_DAYS=2`
- `ActivityInferenceModule`: `min_support=5`
- Proposals generated include `"bootstrap": true` in proposal metadata
- Proposals labeled "(early discovery)" in UI notification surfaces

Bootstrap mode does not auto-disable. The user removes it when they judge the model stable.

### Working slices

1. Z1 — `ActivityAnalyzer`: read `bootstrap_mode` from options; apply lower thresholds when enabled;
   include `bootstrap=True` in proposal metadata.
2. Z2 — `ActivityInferenceModule`: lower `min_support` when bootstrap proposals are approved;
   expose `bootstrap_mode: bool` in diagnostics.
3. Z3 — Options normalization, config flow label, tests.

### Files to modify

| File | Change |
|---|---|
| `runtime/analyzers/activity.py` | Bootstrap threshold branching |
| `runtime/inference/modules/activity_inference.py` | Bootstrap-aware min_support |
| `const.py` | `OPTION_ACTIVITY_BOOTSTRAP_MODE` constant |
| `tests/` | New tests: bootstrap enables lower thresholds; default unchanged |

### Acceptance criteria

- [x] `activity_bootstrap_mode=true` → `MIN_COOCCURRENCES=5`, `MIN_DISTINCT_DAYS=2`
- [x] Default behavior (`mode=false`) unchanged
- [x] Bootstrap proposals include `"bootstrap": true` in metadata
- [x] Diagnostics expose `bootstrap_mode` state
- [x] All existing tests pass

---

## Phase AA — Global drift detection

**Status:** DONE on branch `feat/phase-aa-global-drift-detection`
**Spec section:** Phase AA (new section in `docs/specs/heima_v2_spec.md`)
**Goal:** Detect when learned house_state patterns are globally stale — household behavior has shifted
but the model has not updated to reflect it.
**Depends on:** Phase Y (tiered model with per-tier diagnostics and timestamp exposure)

### New anomaly rule: `learned_model_stale`

Algorithm (run during `AnomalyAnalyzer.analyze()`):

1. Retrieve `HouseStateInferenceModule.diagnostics()` via coordinator-provided summary dict
   (no direct coupling between `AnomalyAnalyzer` and the inference module).
2. For each approved house_state context in the model:
   - `expected_ratio = count_in_model / total_model_snapshots`
   - `recent_ratio = count_in_last_N_snapshots / N` (default `N=500`)
3. Contexts with `expected_ratio ≥ 0.15` are "dominant".
4. Trigger if `≥ min_stale_contexts` dominant contexts have `recent_ratio < expected_ratio × drift_threshold`.
5. Defaults: `N=500`, `drift_threshold=0.50`, `min_stale_contexts=2`.
6. Severity: `warning`. Finding: `learned_model_stale`.

Rule is **disabled by default**. Enable via `heima.configure_anomaly_rule`.

### `HouseStateInferenceModule` diagnostics extension

`diagnostics()` adds:
```python
"model_first_snapshot_ts": str | None   # ISO timestamp of oldest snapshot in model
"model_last_snapshot_ts": str | None    # ISO timestamp of newest snapshot in model
"model_total_snapshots": int            # total snapshots used to build current model
```

Exposed in `sensor.heima_health` attributes.

### Working slices

1. AA1 — `learned_model_stale` rule in `AnomalyAnalyzer`: implement algorithm, read diagnostics
   summary from coordinator, emit `Finding` with severity `warning`.
2. AA2 — `HouseStateInferenceModule.diagnostics()`: add timestamp and count fields; wire to health
   entity attributes.
3. AA3 — Tests: stale trigger (dominant context drops below threshold), no trigger (stable
   distribution), rule disabled by default.

### Files to modify

| File | Change |
|---|---|
| `runtime/analyzers/anomaly.py` | `learned_model_stale` rule |
| `runtime/inference/modules/house_state_inference.py` | Diagnostics timestamp/count fields |
| `coordinator.py` | Pass inference diagnostics summary to `AnomalyAnalyzer` |
| `tests/` | New tests for AA1–AA3 |

### Acceptance criteria

- [x] Rule triggers when ≥ 2 dominant contexts drop below 50% of expected frequency in recent window
- [x] Rule disabled by default; no `Finding` emitted until explicitly enabled
- [x] Model first/last timestamp and snapshot count visible in `sensor.heima_health` attributes
- [x] All existing tests pass

---

## Phase AB — Smart Lighting Automation (Unified)

**Purpose:** Unify `room_darkness_lighting_assist` and `room_contextual_lighting_assist` into a
single `room_smart_lighting_assist` automation type with correct indoor/outdoor lux separation,
adaptive smart turn-off with two-step dim→off, and admin choice of fixed vs. learned timeout.

The two existing types are removed with no migration path (hard cut).

**Dependencies:** U (physical light state awareness), X (room context model)

**Slices:**

1. AB1 — `room_smart_lighting_assist` automation type: config schema, turn-on logic, indoor/outdoor
   lux policy
2. AB2 — Two-step turn-off engine: dim→off with configurable ratio
3. AB3 — Smart timeout engine: fixed and learned modes, fast-exit detection
4. AB4 — Outdoor lux as debounced evaluation trigger
5. AB5 — Room type catalog with default timeouts

---

### AB1 — `room_smart_lighting_assist` automation type

New unified automation type. Replaces both `room_darkness_lighting_assist` and
`room_contextual_lighting_assist` (hard cut — old types removed).

Config schema:

```yaml
type: room_smart_lighting_assist
room_id: studio
indoor_lux_signal: room_lux         # on/off trigger only; never used for modulation
outdoor_lux_signal: outdoor_lux     # optional; if absent, no ambient modulation
lux_on_buckets: [dark, dim]         # indoor lux buckets that allow turn-on
room_type: studio                   # key into default timeout table (AB5) and night-mode defaults
suppress_on_states: [vacation, away] # states that fully suppress lighting
night_mode_states: [sleeping]        # states that use night profile instead of suppressing;
                                     # room_type determines whether sleeping → suppress or night profile
manual_override_window_min: 30      # override window after manual OFF; 0 = rely on presence cycle only
timeout_mode: learned               # "fixed" | "learned"; default "learned"
base_timeout_min: 6                 # installer override; if absent, use room_type default
fast_exit_timeout_s: 60             # timeout when visit classified as fast-exit
dim_brightness_pct: 15              # brightness during dim phase; default 15
dim_ratio: 0.3                      # fraction of effective_timeout spent in dim; default 0.3
profiles: [...]                     # optional; same schema as contextual profiles
entity_steps: [...]                 # used if no profiles configured
```

**Turn-on condition:**

At config load, `effective_suppress_states` is computed once:

```
effective_suppress_states =
    suppress_on_states
    ∪ { s for s in night_mode_states
        if room_type in NIGHT_SUPPRESS_ROOM_TYPES }
```

Turn-on fires when:

```
auto_lighting_enabled
AND NOT manual_override_active
AND presence_detected
AND indoor_lux_bucket in lux_on_buckets
AND house_state NOT IN effective_suppress_states
```

`NOT sleep_mode` is removed. House-state gating replaces it with room-type-aware logic.

Profile re-application (lights already on, context changed):

```
needs_apply
AND NOT manual_on_hold
```

**Manual override — pending-apply detection:**

HA does not reliably propagate `context.parent_id` through light integrations. Primary mechanism:
**pending apply records**. `PendingApply(expected_state, timestamp, ttl=5s,
expected_brightness, expected_color_temp)`. Match is fuzzy: state + brightness ±5 + color_temp ±100K.
`register_pending_apply_for_step(step)` is called by the execution layer after apply-plan
filtering and immediately before `async_call` — NOT inside `evaluate()` — to avoid stale records
for steps blocked by constraints. `issued_context_ids` and `ApplyStep.context_id` are not used.
The execution layer identifies the originating reaction from `ApplyStep.source` (`reaction:<id>`)
using the existing `_reaction_from_step_source(step)` lookup; no dedicated `ApplyStep.reaction_id`
field is required, and the lookup must not be inferred from entity ownership alone.
For `light.turn_off`, `expected_brightness` and `expected_color_temp` remain `None`; many HA
integrations keep stale attributes or remove them after off. If multiple smart-lighting steps target
the same entity inside the TTL window, the latest pending record overwrites the previous one
(`last command wins`).

- **External OFF**: set `manual_override_active = True`. Clears on `manual_override_window_min`
  expiry (default 30 min) OR presence lost → re-detected.
- **External ON**: set `manual_on_hold = True`. Clears **only** on presence lost → re-detected.
- `LightingRecorderBehavior` TTL provenance is NOT used for override detection (diagnostic only).
- Coordinator-level dispatcher routes `STATE_CHANGED` to `handle_external_light_change()` on
  the reaction; reactions do not subscribe to HA events directly.

`NIGHT_SUPPRESS_ROOM_TYPES` (sleeping → suppress):
`camera_da_letto`, `cameretta_bambini`, `studio`, `soggiorno`, `sala_da_pranzo`, `tinello`,
`garage`, `ripostiglio`.

Night-profile rooms (sleeping → night profile, not suppress):
`bagno`, `corridoio`, `ingresso`, `cucina`, `lavanderia`, `generic`.

**Profile selection:**

```
if house_state in night_mode_states:
    use profile where house_states contains sleeping  (night profile)
    fallback: color_temp=2200K, brightness=10%
else:
    use profile matching (house_state, hour_bucket)
    fallback: entity_steps or first profile
```

Brightness: if `outdoor_lux_signal` configured, modulate the active profile brightness by
outdoor lux bucket scale; otherwise use static brightness from profile or entity_steps.

Indoor lux is used only to decide whether to turn on. It is never used for brightness
modulation — doing so would create a feedback loop (light on → indoor lux rises → brightness
reduced → indoor lux falls → brightness raised → oscillation).

**Lux signal roles (invariant):**

| Signal | Role | Trigger evaluation? |
|---|---|---|
| `indoor_lux_signal` | on/off gate | No |
| `outdoor_lux_signal` | brightness modulation scale | Yes (debounced, AB4) |

---

### AB2 — Two-step turn-off engine

Once presence is lost and `effective_timeout` computed (AB3):

- At `t_absence + effective_timeout × (1 − dim_ratio)`: `light.turn_on` at `dim_brightness_pct`
- At `t_absence + effective_timeout`: `light.turn_off`
- If presence re-detected at any point before turn-off: cancel sequence, return to full brightness

`dim_ratio` and `dim_brightness_pct` are per-rule config with defaults (0.3 and 15).

---

### AB3 — Smart timeout engine

**`timeout_mode = fixed`:**

```
effective_timeout = base_timeout_min (configured or room_type default)
fast_exit_threshold = fast_exit_timeout_s × 3
if current_visit_duration < fast_exit_threshold:
    effective_timeout = fast_exit_timeout_s
```

**`timeout_mode = learned`** (default):

Per-room ring buffer of the last 50 visit durations (presence_confirmed → presence_lost).
- p25 of buffer = `fast_exit_threshold`
- Before 20 visits observed: fall back to fixed defaults

```
if current_visit_duration < fast_exit_threshold (p25):
    effective_timeout = fast_exit_timeout_s
else:
    effective_timeout = base_timeout_min
```

Ring buffer size (50) and minimum visits for learning (20) are internal constants, not
user-configurable.

Visit duration tracking: the automation records the timestamp when presence is first confirmed
for a visit and computes duration when presence is lost. Data is held in memory; not persisted
across HA restarts (ring buffer rebuilds over time).

---

### AB4 — Outdoor lux as debounced evaluation trigger

When an `outdoor_lux_signal` state change is received:
- If the corresponding room is currently occupied
- And there is an active `room_smart_lighting_assist` rule with that `outdoor_lux_signal`
- → schedule a lighting evaluation after a 60 s debounce (configurable via
  `outdoor_lux_trigger_debounce_s` in learning options, default 60)

Indoor lux state changes do not trigger lighting evaluation.

This gives `room_smart_lighting_assist` responsive brightness adjustment at dawn/dusk without
relying solely on the 300 s fallback cycle.

---

### AB5 — Room type catalog

Default timeout table:

| room_type | base_timeout_min | fast_exit_timeout_s |
|---|---|---|
| bagno | 2 | 30 |
| cucina | 4 | 45 |
| corridoio | 1 | 15 |
| ingresso | 1 | 15 |
| studio | 6 | 60 |
| soggiorno | 8 | 90 |
| sala_da_pranzo | 6 | 60 |
| tinello | 4 | 45 |
| camera_da_letto | 5 | 60 |
| cameretta_bambini | 5 | 90 |
| lavanderia | 3 | 20 |
| ripostiglio | 1 | 15 |
| garage | 3 | 30 |
| generic | 5 | 45 |

If `room_type` is not specified in the rule config, `generic` defaults apply.

---

### Acceptance criteria

- [ ] `room_smart_lighting_assist` type is accepted by the options flow and reaction engine
- [ ] `room_darkness_lighting_assist` and `room_contextual_lighting_assist` types removed; engine
  raises a clear config error if encountered
- [ ] Turn-on fires when presence + indoor lux bucket match + house_state NOT IN
  effective_suppress_states
- [ ] `effective_suppress_states` = `suppress_on_states` ∪ night_suppress rooms for
  `night_mode_states`; computed at config load
- [ ] NIGHT_SUPPRESS_ROOM_TYPES suppress sleeping correctly; night-profile rooms use night
  profile instead
- [ ] Night profile fallback (color_temp=2200K, brightness=10%) applies when no matching profile
  is defined for the sleeping state
- [ ] Profile selection: night_mode_states → night profile; otherwise (house_state, hour_bucket)
- [ ] Brightness uses outdoor lux scale when `outdoor_lux_signal` configured; static otherwise
- [ ] Indoor lux state changes do not trigger a lighting evaluation cycle
- [ ] Outdoor lux state changes trigger evaluation (debounced 60 s) when room occupied and rule active
- [ ] Two-step turn-off: dim fires at `effective_timeout × (1 − dim_ratio)`, off fires at
  `effective_timeout`; presence during dim cancels and restores brightness
- [ ] `timeout_mode = fixed`: effective timeout = base or fast-exit based on visit duration vs
  `fast_exit_timeout_s × 3`
- [ ] `timeout_mode = learned`: ring buffer per room; p25 used as fast-exit threshold after 20
  visits; fallback to fixed before that
- [ ] All room_type keys in catalog resolve to correct default timeouts and night-mode behavior
- [ ] `STATE_CHANGED` matched via `pending_applies`; heima-owned if within TTL, state matches, and
  brightness/color_temp within tolerance (±5 / ±100 K); consumed after match
- [ ] `light.turn_off` pending records do not verify brightness/color temperature attributes
- [ ] Multiple pending records for the same entity use `last command wins` overwrite semantics
- [ ] `register_pending_apply_for_step(step)` called after apply-plan filtering, immediately before
  `async_call`; not inside `evaluate()` (prevents stale records for constraint-blocked steps)
- [ ] Pending registration uses `ApplyStep.source = "reaction:<id>"` and
  `_reaction_from_step_source(step)`; no entity-only lookup when registering the pending record
- [ ] External OFF (switch, other automation, script, scene): `manual_override_active` set; turn-on
  suppressed until window expires or presence cycle clears it
- [ ] External ON: `manual_on_hold` set; profile re-application suppressed until presence lost → re-detected
- [ ] Manual override window configurable via `manual_override_window_min`; 0 disables timer
- [ ] `LightingRecorderBehavior` TTL path not involved in override detection
- [ ] All existing tests pass

---

## Phase AC — Proposal Review Grouping

Status: IMPLEMENTED, pending full CI, on branch `feat/phase-ac-proposal-review-grouping`.

**Spec section:** `docs/specs/learning/proposal_lifecycle_spec.md` §2c
**Goal:** Add a generalized, query-time review grouping layer to proposal lifecycle so user-facing
review queues show one representative per semantic review group while preserving exact approval
identity and persisted proposal status.
**Depends on:** Phase H (`ApprovalStore`, house-state proposal approval), Phase Y (tiered
house-state inference)

### Design constraints

- Review grouping is owned by `ProposalEngine`, not config flow or individual coordinators.
- Grouping is exported by plugin lifecycle hooks through optional `review_grouping`.
- No persisted fields are added.
- No migration is required.
- No new persisted status is introduced.
- `suppressed_in_review` is derived at query/diagnostics time only.
- Approval and rejection still apply only to the proposal's exact `identity_key`.
- If a representative is rejected, another pending sibling may become representative automatically
  on the next `pending_proposals()` query because grouping is recomputed from current statuses.

### Working slices

1. AC1 — Lifecycle hook contract:
   - Add `ProposalReviewGrouping` dataclass.
   - Add `LifecycleReviewGrouping`.
   - Extend `ProposalLifecycleHooks` with optional `review_grouping`.
   - Preserve unchanged behavior for plugins without `review_grouping`.

2. AC2 — ProposalEngine query-time grouping:
   - Resolve `review_grouping` through lifecycle hooks.
   - Compute representative/suppressed roles dynamically.
   - Make `pending_proposals()` return only current representatives and ungrouped pending proposals.
   - Keep `proposal_by_id()` and persisted proposal records unchanged.

3. AC3 — Diagnostics:
   - Expose per-proposal derived fields:
     - `review_group_key`
     - `review_group_role`
     - `suppressed_by_review_group`
   - Expose per-family summary:
     - `review_groups`
     - `suppressed_in_review_count`

4. AC4 — First plugin hook: `house_state_learned_context`:
   - Register a lifecycle hook for `house_state_learned_context`.
   - Group key:
     `house_state_ctx_group:weekday:N:hour_bucket:N:anyone_home:N:state:S`
   - Derive tier from `context_snapshot.learning_context.module`:
     - `house_state_inference_rich` → Rich
     - `house_state_inference_minimal` → Minimal
     - empty/unknown module for current house-state inference → Coarse fallback
   - Rank Rich > Coarse > Minimal, then confidence, support, total observations, and stable
     `context_key` ordering.

5. AC5 — Review queue and notification verification:
   - Options-flow proposal review uses the filtered `pending_proposals()` view.
   - Proposal sensor pending count uses the filtered user-facing view.
   - Suppressed siblings do not generate user-facing review rows.
   - Existing proposal IDs remain valid for direct lookup.

### Files to modify

| File | Change |
|---|---|
| `runtime/analyzers/lifecycle.py` | Add review grouping contract and house-state hook |
| `runtime/analyzers/registry.py` or plugin registration path | Register `house_state_learned_context` lifecycle hook if needed |
| `runtime/proposal_engine.py` | Query-time grouping, filtered pending view, diagnostics |
| `coordinator.py` | Ensure house-state proposals use lifecycle-aware ProposalEngine path without local dedup |
| `tests/` | ProposalEngine grouping tests; house-state grouping tests |

### Acceptance criteria

- [x] Plugins without `review_grouping` behave exactly as before
- [x] `pending_proposals()` returns at most one pending representative per `(plugin_family, group_key)`
- [x] Suppressed siblings remain persisted as `status="pending"` and are not mutated
- [x] No store schema migration or persisted field is introduced
- [x] Accepted same-or-higher-specificity proposals suppress candidate siblings in the same group
- [x] Higher-specificity siblings remain eligible after a lower-specificity accepted proposal
- [x] Rejected representative no longer suppresses pending siblings; next best sibling becomes visible
- [x] `house_state_learned_context` grouping excludes opaque `ctx` hash and room detail
- [x] `house_state_learned_context` approval records still store only the exact approved `context_key`
- [x] Diagnostics expose review group key, role, and suppressed count without writing them to storage
- [ ] Existing tests pass; new focused tests cover ranking, accepted suppression, rejection recovery,
  and no-op behavior for ungrouped plugins

### Spec revision note: learning plugin execution mode

Status: SPEC DRAFT ONLY — implementation requires explicit user confirmation.

Problem:
- `builtin.house_state_contexts` exists to claim `house_state_learned_context` lifecycle hooks and
  review grouping.
- It should not execute an analyzer.
- Representing it only as `enabled=False` makes diagnostics report `house_state` as a disabled
  learning family, even while house-state proposals are claimed and grouped correctly.

Spec direction:
- Add explicit `LearningPatternPluginDescriptor.execution_mode`.
- Valid values:
  - `analyzer`
  - `lifecycle_only`
  - `admin_authored_only`
- `enabled_plugin_families` and `disabled_plugin_families` apply only to analyzer-mode families.
- Lifecycle-only families must be exposed separately, e.g. `lifecycle_only_plugin_families`.
- `house_state_learned_context` must be registered as lifecycle-only.

Implementation plan, pending approval:
1. Extend `LearningPatternPluginDescriptor` with `execution_mode`, default `analyzer`.
2. Register `builtin.house_state_contexts` with `execution_mode="lifecycle_only"`.
3. Register admin-authored-only plugins without analyzer execution when applicable.
4. Make `LearningPluginRegistry.analyzers()` return only enabled analyzer-mode plugins.
5. Make diagnostics compute:
   - `enabled_plugin_families`
   - `disabled_plugin_families`
   - `lifecycle_only_plugin_families`
   - `admin_authored_only_plugin_families`
6. Keep lifecycle hooks and proposal type ownership available for lifecycle-only descriptors.
7. Update registry/diagnostics tests and dashboard expectations.

---

## Phase AD — Proposal/Reaction Lifecycle Management

Status: DONE. Implemented through AD9 on branch `feat/ad1-proposal-engine-invariants`, then
merged and pushed to `feat/v2`.

**Spec sections:**
- `docs/specs/learning/proposal_lifecycle_spec.md`
- `docs/specs/learning/learning_system_spec.md`

**Goal:** Treat accepted proposal-backed behavior as a full lifecycle rather than a one-way
proposal approval. The lifecycle must cover creation, accepted-rule monitoring, replacement
suggestions, retirement suggestions, explicit user decisions, diagnostics, and restart-safe recovery.

**Depends on:** Phase AC (review grouping), Phase H (approval store), Phase Y (tiered
house-state learned context)

### Design constraints

- Proposal/reaction lifecycle state must remain coherent after Home Assistant restart.
- Accepted/reviewed proposal identity must be preserved; refresh must not silently erase user
  decisions.
- Replacement and retirement must be reviewable proposals, not automatic destructive changes.
- Replacement has priority when a stable alternative exists; retirement is suggested only when no
  replacement candidate is stable enough.
- User-modified reactions become the new user-approved baseline; Heima must not silently overwrite
  them.
- Dependency-unavailable signals are distinct from transient misses and must not automatically retire
  a learned rule.
- Lifecycle diagnostics must show enough state to debug why a rule is confirmed, contradicted,
  missing context, unavailable, replacement-ready, or retirement-ready.

### Working slices

1. AD1 — ProposalEngine invariants and reviewed identity preservation:
   - Preserve reviewed proposal identity across proposal refresh/recovery.
   - Keep exact approval/rejection identity semantics from Phase AC.
   - Ensure accepted proposal records can be associated with configured reactions.

2. AD2 — Proposal lifecycle monitoring store:
   - Add a dedicated lifecycle store for accepted proposal/reaction monitoring state.
   - Store lifecycle records separately from proposal records.
   - Keep lifecycle state restart-safe.

3. AD3 — Reaction-link diagnostics:
   - Expose whether an accepted proposal still has a linked configured reaction.
   - Classify link state so missing/deleted/modified reactions are visible in diagnostics.
   - Avoid hidden lifecycle state divergence when config changes outside the proposal path.

4. AD4 — House-state lifecycle opportunity evaluation:
   - Evaluate accepted house-state learned contexts against observed house-state events.
   - Track confirmation, contradiction, context miss, transient unknown, and dependency unavailable
     outcomes.
   - Use stable aggregation windows rather than single observations.

5. AD5 — Accepted-rule lifecycle policy:
   - Apply lifecycle policy to determine confirmed, replacement candidate, retirement candidate,
     and unavailable states.
   - Prefer replacement over retirement when a stable alternative exists.
   - Treat user-modified reactions as a user-approved baseline rather than as an error to overwrite.

6. AD6 — Lifecycle suggestion generation:
   - Generate reviewable lifecycle suggestions for replacement/retirement decisions.
   - Keep suggestions in the proposal review path instead of performing automatic destructive
     changes.
   - Preserve proposal provenance and target references for user-facing review.

7. AD7 — Lifecycle review decision application:
   - Apply accepted lifecycle decisions to the target proposal/reaction.
   - Preserve rejected/skipped decisions as explicit user feedback.
   - Keep exact-key approval behavior intact.

8. AD8 — Recovery and persistence tests:
   - Add tests proving lifecycle state can be recovered after reload/restart.
   - Verify accepted/reviewed identity and lifecycle records remain coherent.

9. AD9 — Diagnostics and live verification:
   - Add lifecycle diagnostics live probe.
   - Add seeded services for deterministic house-state snapshot/event setup.
   - Add `073_house_state_lifecycle_suggestion.py` seeded live test covering accepted house-state
     proposal -> contradictory observations -> replacement suggestion.
   - Add lifecycle-store clearing to learning reset so live tests and diagnostics start from a clean
     baseline.
   - Update test stubs to the current proposal lifecycle contract.
   - Remove mypy warnings from lifecycle grouping/count code.

### Files modified

| File | Change |
|---|---|
| `runtime/proposal_engine.py` | Lifecycle monitoring/evaluation, lifecycle suggestions, diagnostics, typed lifecycle counts |
| `runtime/proposal_lifecycle_store.py` | Dedicated restart-safe lifecycle store and clear/reset support |
| `runtime/analyzers/lifecycle.py` | Lifecycle hook typing and house-state grouping parsing fix |
| `runtime/analyzers/registry.py` | Lifecycle-only proposal ownership and execution-mode integration |
| `coordinator.py` | Lifecycle store ownership, lifecycle evaluation wiring, seeded test helpers, reset cleanup |
| `services.py` | `heima.command` seed commands for deterministic lifecycle live tests |
| `scripts/check_all_live.sh` | Include lifecycle seeded live test in `seeded_integration` tier |
| `scripts/live_tests/073_house_state_lifecycle_suggestion.py` | New deterministic AD lifecycle replacement live test |
| `scripts/README.md` | Document new live test |
| `tests/` | Proposal lifecycle, recovery, seed command, dashboard/test-stub, and mypy-related coverage |

### Acceptance criteria

- [x] Reviewed proposal identity is preserved across refresh/recovery.
- [x] Lifecycle state is stored separately from proposal records.
- [x] Lifecycle state remains coherent after restart/reload.
- [x] Accepted house-state learned contexts are monitored against runtime observations.
- [x] Replacement suggestions are generated when a stable contradictory state appears.
- [x] Retirement remains reviewable and does not run when a stable replacement exists.
- [x] Dependency-unavailable is distinct from transient unknown and does not auto-retire rules.
- [x] User-facing lifecycle changes go through proposal review.
- [x] Diagnostics expose lifecycle records, reaction-link state, and lifecycle suggestions.
- [x] Learning reset clears proposal lifecycle state.
- [x] Deterministic seeded live test covers the replacement suggestion path.
- [x] Local CI is green with mypy clean.
- [x] Current AD9 cleanup is committed.
- [x] Phase AD branch is merged into `feat/v2`.

### Verification

- `.venv/bin/python -m pytest tests/test_proposal_engine.py tests/test_house_state_learning_h4.py -q` — 126 passed.
- `.venv/bin/mypy custom_components/heima` — success, no issues found in 165 source files.
- `PATH="/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/.venv/bin:$PATH" bash scripts/ci_local.sh` — 1527 passed, ruff check passed, ruff format passed, mypy clean.
- `source scripts/.env && ./scripts/check_all_live.sh` — `live_e2e` passed.
- `source scripts/.env && ./scripts/check_all_live.sh --tier seeded_integration` — passed, including `073_house_state_lifecycle_suggestion.py`.
- `source scripts/.env && ./scripts/check_all_live.sh --tier diagnostic` — passed.

### Current open items

- None for Phase AD.
- Unrelated local untracked files are intentionally outside the AD merge:
  - `DEBUG_HEIMA_STATE.txt`
  - `VIBE.md`
  - `docs/audit/code_quality_audit_plan_2026-06-08.md`

---

## Phase MH — Manual Hold Framework

**Spec:** `docs/specs/core/manual_hold_framework_spec.md`
**Status:** `DONE`
**Depends on:** AB smart-lighting behavior, AE audit
**Branch:** `feat/v2` or a dedicated `feat/manual-hold-framework` branch

### Goal

Replace fragmented manual-hold behavior with one shared runtime framework used by smart lighting,
camera privacy, heating, and future entity automations.

The framework must support:

1. pending-apply provenance to distinguish Heima-owned state changes from external/manual changes;
2. implicit holds from external state changes;
3. explicit holds from configured helper entities;
4. scope-aware blocking for entity, room, reaction, and domain targets;
5. diagnostics explaining active holds and pending applies.

### Slices

1. **MH1 — Core framework skeleton**
   - Add `ManualHoldScope`, `ManualHoldReason`, `ManualHoldState`, `PendingApply`, and
     `ManualHoldManager`.
   - Wire manager into `HeimaEngine` diagnostics.
   - No behavior changes.
   - Acceptance:
     - [x] Unit tests for scope serialization/keying.
     - [x] Unit tests for pending apply match/expiry.
     - [x] Diagnostics expose empty manager state.

2. **MH2 — Smart-lighting migration**
   - Move pending-apply storage and external light-change classification from
     `RoomSmartLightingAssistReaction` into `ManualHoldManager`.
   - Preserve current behavior:
     - external OFF suppresses automatic turn-on;
     - external ON suppresses profile re-application;
     - Heima-owned light changes do not activate hold;
     - release policies stay unchanged.
   - Acceptance:
     - [x] Existing `tests/test_room_smart_lighting_assist_reaction.py` remain green.
     - [x] New manager-level tests cover light pending apply and external classification.

3. **MH3 — Central apply-filter integration**
   - Add manager-backed hold filtering after domain/reaction steps are merged and before execution.
   - Do not overwrite existing `blocked_by`.
   - Keep step blocking visible in diagnostics.
   - Acceptance:
     - [x] Held steps are marked `blocked_by="manual_hold:..."`.
     - [x] Blocked steps are not executed.
     - [x] Pending apply is not registered for blocked steps.

4. **MH4 — AE camera privacy adoption**
   - Register camera privacy scopes from `security.camera_evidence_sources[*].privacy_entity`.
   - Use `manual_hold_entity` as explicit hold source.
   - Register pending apply for `switch.turn_on` and `switch.turn_off` privacy steps.
   - Route state changes for configured `privacy_entity` switches to the manager.
   - Implement `privacy_action` support in semantic policy and options-flow validation.
   - Acceptance:
     - [x] Missing `privacy_action` defaults to `switch.turn_on`.
     - [x] `privacy_action="turn_off"` emits `switch.turn_off`.
     - [x] Invalid `privacy_action` is rejected.
     - [x] Heima-owned switch privacy changes do not activate hold.
     - [x] External/manual switch privacy changes activate entity-scoped hold.
     - [x] `manual_hold_entity` blocks camera privacy actions while on.

5. **MH5 — Heating adoption**
   - Represent `heima_heating_manual_hold` as a domain-scoped explicit hold.
   - Preserve existing heating behavior.
   - Acceptance:
     - [x] Existing heating manual-hold tests remain green.
     - [x] Heating diagnostics expose manager-backed hold state.

6. **MH6 — Cleanup and docs**
   - Remove or refactor `EntityReactionGuardBehavior`.
   - Replace or refactor `LightingReactionGuardBehavior`.
   - Update:
     - `docs/specs/core/manual_hold_framework_spec.md`
     - `docs/specs/core/smart_lighting_assist_spec.md`
     - `docs/specs/core/privacy_guard_for_alarm_states.md`
     - heating docs if touched.
   - Acceptance:
     - [x] No duplicate manual-hold behavior classes remain for migrated automations.
     - [ ] Full local CI passes.

### Current open items

- Full `scripts/ci_local.sh` not run in this slice.

---

## Phase AE — Camera Privacy Guard & Extensible Entity Actions

**Spec:** `docs/specs/core/privacy_guard_for_alarm_states.md`
**Status:** `DONE`
**Depends on:** AD
**Branch:** `feat/v2`

**Spec revision note — 2026-06-25**

Phase AE was initially implemented on `feat/privacy-guard-alarm-states` and merged into `feat/v2`,
but the implementation audit found that camera privacy manual hold is not equivalent to the
smart-lighting manual override contract:

- The initial `EntityReactionGuardBehavior` existed and had unit tests, but was not registered by
  the runtime. It has now been removed in favor of `ManualHoldManager`.
- `manual_hold_entity` is accepted and validated but not consumed by runtime blocking logic.
- `privacy_action` is specified but not implemented; camera privacy proposals currently emit
  `switch.turn_on` only.
- Switch privacy actions do not have pending-apply provenance, so Heima-owned switch changes cannot
  be distinguished from external/manual switch changes.

Resolution implemented:

- Implemented Phase MH — Manual Hold Framework (`docs/specs/core/manual_hold_framework_spec.md`).
- Completed MH4 camera privacy adoption plus `privacy_action` support.

### Goal
Implement a **generic** system to:
1. Block automatic actions on **any entity** when a manual hold is active.
2. Skip reactions based on `house_state` (e.g., `guest`, `vacation`).
3. Generate **automatic proposals** for camera privacy actions (extensible to other use cases).

### Slices

1. **AE1 — `EntityReactionGuardBehavior` (Generic)**
   - Create: `custom_components/heima/runtime/behaviors/entity_reaction_guard.py`
   - Purpose: Block actions on **any entity** (switch, light, cover, etc.) when the corresponding manual hold is active.
   - Contract:
     - Configurable `hold_entity_pattern` (default: `"heima_{domain}_manual_hold"`).
     - Configurable `target_domain` (e.g., `"switch"`, `"light"`, `"cover"`).
   - Logic:
     - If global hold entity (e.g., `heima_switch_manual_hold`) is ON → block all actions for that domain.
     - If per-entity hold (e.g., `heima_switch_manual_hold_{entity_id}`) is ON → block only that entity.
   - Acceptance Criteria:
     - [ ] Blocks actions on `switch.*_privacy` if `heima_switch_manual_hold` or `heima_switch_manual_hold_{entity_id}` is ON.
     - [ ] Works for any domain (`switch`, `light`, `cover`, etc.).
     - [ ] Unit tests: `tests/test_entity_reaction_guard.py`.

2. **AE2 — Extend `camera_evidence_sources` with Optional Fields**
   - Modify: `custom_components/heima/config_flow/_steps_security.py`
   - Add optional fields to `camera_evidence_sources`:
     - `privacy_entity`: `switch.*` (optional).
     - `manual_hold_entity`: `input_boolean.*` (optional, default: global).
   - Acceptance Criteria:
     - [ ] Optional fields do not break existing configurations.
     - [ ] User can configure them via **options flow** (UI).
     - [ ] Validation: `privacy_entity` must be a `switch.*` entity, `manual_hold_entity` must be `input_boolean.*`.

3. **AE3 — house-state filters in `AlarmStateActionReaction`**
   - Modify: `custom_components/heima/runtime/reactions/alarm_policy.py`
   - Add:
     - `skip_house_states: list[str]` field to the reaction contract.
     - `only_house_states: list[str]` field to the reaction contract.
     - Skip logic in `evaluate()` if `only_house_states` is set and `house_state` is not in it.
     - Skip logic in `evaluate()` if `house_state` is in `skip_house_states`.
   - Acceptance Criteria:
     - [ ] Actions are skipped if `house_state` is in `skip_house_states`.
     - [ ] Actions are skipped if `only_house_states` is set and `house_state` is outside it.
     - [ ] All existing `alarm_policy.py` tests still pass.

4. **AE4 — Semantic Policy for Privacy (Generic Helpers)**
   - Modify: `custom_components/heima/runtime/semantic_policies.py`
   - Add:
     - New semantic rule: `alarm_night_camera_privacy`.
     - Generic helper: `_configured_camera_entity_entities(options, field, domain)`.
     - Evaluator: `_camera_privacy_proposal()` using the generic helper.
   - Acceptance Criteria:
     - [ ] Rule generates proposals **only if** `privacy_entity` is configured.
     - [ ] Proposal includes `skip_house_states=["guest", "vacation"]`.
     - [ ] Unit tests: `tests/test_semantic_policies_camera_privacy.py`.

5. **AE5 — Integration and Verification**
   - All **660 existing tests** must pass.
   - New tests:
     - `tests/test_entity_reaction_guard.py` (AE1).
     - `tests/test_alarm_policy_skip_house_states.py` (AE3).
     - `tests/test_semantic_policies_camera_privacy.py` (AE4).
   - Acceptance Criteria:
     - [ ] `PATH=".venv/bin:$PATH" bash scripts/ci_local.sh` — all tests pass.
     - [ ] `ruff check` and `ruff format` pass.
     - [ ] Mypy clean.

### Files to Modify/Create

| # | Action | File | Slice |
|---|--------|------|-------|
| 1 | Create | `custom_components/heima/runtime/behaviors/entity_reaction_guard.py` | AE1 |
| 2 | Modify | `custom_components/heima/runtime/behaviors/__init__.py` | AE1 |
| 3 | Modify | `custom_components/heima/config_flow/_steps_security.py` | AE2 |
| 4 | Modify | `custom_components/heima/runtime/reactions/alarm_policy.py` | AE3 |
| 5 | Modify | `custom_components/heima/runtime/semantic_policies.py` | AE4 |
| 6 | Create | `tests/test_entity_reaction_guard.py` | AE5 |
| 7 | Create/Modify | `tests/test_alarm_policy_skip_house_states.py` | AE5 |
| 8 | Create/Modify | `tests/test_semantic_policies_camera_privacy.py` | AE5 |

### Acceptance Criteria

- [x] `skip_house_states` skips actions for configured house states.
- [x] `only_house_states` allows alarm-state actions to require specific house states.
- [x] Semantic policy generates proposals for camera privacy when `privacy_entity` is configured.
- [x] `privacy_entity` and `manual_hold_entity` validation does not break existing camera source configuration.
- [x] `privacy_entity`-only camera source configuration is accepted.
- [x] `privacy_action` supports `turn_on` and `turn_off` with default `turn_on`.
- [x] `manual_hold_entity` blocks camera privacy actions through the shared manual-hold framework.
- [x] Heima-owned camera privacy switch changes do not activate manual hold.
- [x] External/manual camera privacy switch changes activate manual hold.
- [ ] Full local CI (`scripts/ci_local.sh`) passes after MH + AE completion.

## Phase AF — Policy Editor Framework + Camera Privacy Policy UI

**Status:** `DONE`
**Spec:** `docs/specs/core/camera_privacy_policy_ui_spec.md`
**Framework:** `docs/specs/core/policy_editor_framework_spec.md`
**Branch:** `feat/policy-editor-implementation-plan` (merged into `feat/v2`)
**Depends on:** AE, MH

### Context

AE made camera privacy behavior expressible, but the raw `security.camera_evidence_sources` +
`reactions.configured[*].alarm_state_action` shape is not admin-friendly. The follow-up UI must be
domain-specific, not a generic HA automation clone.

### Scope

- Add a bounded Camera Privacy Policy editor in Options Flow.
- Let admins choose camera, alarm states, house-state filter, and privacy on/off.
- Materialize normal `alarm_state_action` reactions under the hood.
- Preserve existing camera evidence fields and manual hold semantics.
- Keep raw `ApplyStep` fields out of the primary UI.
- Improve wrong-level YAML validation for the existing low-level camera source editor.

### Architecture Decision

- Generalize the authoring method as domain-specific Policy Editors.
- Do not build a generic trigger/condition/action automation editor.
- Future domains/plugins must follow `policy_editor_framework_spec.md`.

### Development Plan

1. **Fix reaction config envelope normalization**
   - Keep `alarm_state_action` runtime normalization focused on builder-consumed fields.
   - Add persisted-config envelope preservation for allowlisted fields on the same configured
     reaction entry.
   - Preserve at least `enabled`, provenance fields, `admin_authored_template_id`,
     `source_template_id`, `source_request`, and policy metadata objects such as
     `camera_privacy_policy`.
   - Add focused tests for `alarm_state_action` metadata survival and `enabled: false` survival.

2. **Build the camera privacy policy materializer**
   - Define the bounded policy-row model described by `camera_privacy_policy_ui_spec.md`.
   - Generate normal `alarm_state_action` configs.
   - Use stable reaction ids and deterministic collision handling.
   - Persist human labels in `reactions.labels`.
   - Preserve unrelated configured reactions and unrelated camera evidence fields.

3. **Build reverse parser and import path**
   - Reconstruct managed policy rows from `camera_privacy_policy` metadata.
   - Detect compatible one-step `alarm_state_action` reactions without metadata as imported rows.
   - Mark imported rows clearly and write metadata on the first editor save.

4. **Add the Options Flow UI**
   - Add a Security-domain entry point: `Camera privacy policies`.
   - Implement list, add, edit, delete, enable, and disable flows.
   - Expose only camera privacy concepts: camera, alarm states, house-state filter, privacy action,
     and manual-hold status.
   - Do not expose raw `target`, `params.entity_id`, service payloads, or arbitrary conditions in
     the primary UI.

5. **Tighten validation**
   - Validate `privacy_entity` as `switch.*`.
   - Validate `manual_hold_entity` as `input_boolean.*`.
   - Validate non-empty alarm-state selections.
   - Validate `only`/`except` house-state filters require at least one house state.
   - Detect duplicate policy slots.
   - Return domain-specific errors for wrong-level YAML/object payloads containing `security` or
     `reactions`.

6. **Verify runtime and live behavior**
   - Confirm generated config rebuilds into `AlarmStateActionReaction`.
   - Confirm manual hold blocks camera privacy switch actions generated by policy rows.
   - Verify representative live scenarios:
     - alarm `disarmed` -> privacy on;
     - alarm `armed_away` -> privacy off regardless of house state;
     - alarm `armed_night` + house state not `guest` -> privacy off;
     - alarm `armed_night` + house state `guest` -> no privacy-off action.

### Acceptance Criteria

- [x] `alarm_state_action` compatibility normalization preserves allowlisted envelope fields.
- [x] `enabled: false` configured reactions remain disabled after normalization.
- [x] Camera privacy policy rows materialize to normal `reactions.configured` entries.
- [x] Generated reactions rebuild through the existing reaction plugin system.
- [x] Policy metadata round-trips through Options Flow edit/save.
- [x] Imported compatible reactions can be adopted without losing runtime behavior.
- [x] Existing camera evidence fields survive policy editor saves.
- [x] Existing unrelated configured reactions survive policy editor saves.
- [x] Manual hold continues to block generated privacy-switch actions.
- [x] Wrong-level camera source payloads produce domain-specific validation errors.
- [x] Focused tests cover create, edit, delete, enable/disable, duplicate detection, metadata
  survival, unrelated-option preservation, and runtime rebuild.

### Current open items

- None for Phase AF.

### Verification

- Code audit confirmed the feature is implemented in the expected layers:
  - Options Flow policy editor in `custom_components/heima/config_flow/_steps_security.py`.
  - Domain-specific materializer/parser in
    `custom_components/heima/config_flow/_camera_privacy_policy.py`.
  - Runtime execution through normal `alarm_state_action` reactions and shared manual-hold
    filtering.
- Focused regression check on 2026-07-03:
  - `.venv/bin/python -m pytest tests/test_camera_privacy_policy_materializer.py tests/test_options_flow_e2e.py tests/test_manual_hold_manager.py tests/test_engine_lighting_runtime.py -k "camera_privacy_policy or camera_privacy"` — 22 passed.
- Live coverage exists for the main AF/AE overlap:
  - `scripts/live_tests/074_camera_privacy_manual_hold_live.py` verifies camera privacy manual
    hold behavior.
  - `scripts/live_tests/075_camera_privacy_policy_editor_live.py` verifies editor import/adopt,
    delete, stale-policy preservation, and options-flow persistence.
  - `scripts/live_tests/076_camera_privacy_policy_runtime_live.py` verifies runtime policy actions,
    including `disarmed -> privacy on` and `armed_night -> privacy off`.
- Runtime follow-up fixes are merged into `feat/v2` via `ad151fb Merge camera privacy runtime
  fixes`; these corrected the security-triggered switch apply path found during production
  debugging.

---

## Phase AG — Translate Developer Scripts, Docs, and Specs to English

**Status:** `DONE`
**Branch:** `feat/remove-hardcoded-italian`
**Depends on:** AF

### Goal

Make English the default language for developer scripts, active operational documentation, and
active specifications, while leaving the runtime IT/EN localization mechanism untouched.

### Spec revision note (2026-07-03)

This phase was originally titled "Remove Hardcoded Italian Text" and included steps AG1 (remove
Italian from product UI/runtime code) and AG2 (update tests accordingly). Investigation found that
the Italian strings targeted by AG1 are **not** hardcoded leftovers: they are one branch of a
deliberate, working runtime IT/EN localization mechanism
(`is_it = language.startswith("it")`, sourced from `self._flow_language()` / the reaction's
configured `language`), used to generate dynamic proposal/reaction review text (interpolated
values, pluralization) that HA's static `translations/it.json` catalog cannot express. The pattern
appears 183 times across 14 files (`_steps_reaction_proposals.py`, `_reaction_helpers.py`,
`config_flow/__init__.py`, `_steps_reactions.py`, `_steps_calendar.py`,
`context_conditioned_lighting.py`, `_room_lighting_base.py`, `lighting_assist.py`,
`signal_assist.py`, `contextual_lighting_assist.py`, `_lighting_review.py`,
`lighting_schedule.py`, `lighting_vacancy_off.py`, `security_presence_simulation.py`). Deleting it
would be a real product regression (loss of Italian localization for dynamic content), not a
cleanup.

**Decision:** AG1 and AG2 are dropped. The `is_it` mechanism is intentional and stays as-is. Phase
AG is rescoped to developer-facing artifacts only: scripts, operational docs, and specs (former
AG3–AG5, renumbered below). No runtime/UI/config-flow code is touched by this phase.

### Scope

- Translate Python comments/docstrings and developer script output to English.
- Translate active operational documentation and active specifications to English, or explicitly
  classify old Italian documents as archived historical notes.
- Use targeted manual review and repository searches during the cleanup; do not add permanent
  language-audit tooling.

### Non-Goals

- Do not touch the `is_it` runtime IT/EN localization mechanism in `config_flow` or
  `runtime/reactions` — it is intentional, not hardcoded leftover text.
- Do not remove the Italian localization file.
- Do not remove Italian keyword support where Heima intentionally parses Italian calendar or
  external-context inputs.
- Do not redesign the options flow UX.
- Do not change reaction semantics, proposal identity, review grouping, or runtime apply behavior.

### Development Plan

1. **AG3 — Translate developer comments, docstrings, and script output**
   - Translate internal comments/docstrings and script messages in:
     - `pyproject.toml`
     - `scripts/generate_debug_dashboard.py`
     - `scripts/lib/dashboard/*.py`
     - `scripts/lib/utils.py`
     - `scripts/live_tests/047_darkness_assist_fire_live.py`
     - `scripts/live_tests/060_lighting_schedule.py`
   - Keep script behavior unchanged.
   - Acceptance:
     - [ ] Developer-facing scripts have English comments, docstrings, and output.
     - [ ] Script tests and live-test syntax checks pass.

2. **AG4a — Translate developer/operational docs (mechanical, low risk)**
   - Translate active operational docs to English:
     - `CLAUDE.md` — full translation; the one exception is the literal instruction "Respond in
       Italian in chat", which is preserved as an explicit directive (expressed in English prose).
       This does not change the chat interaction language, only the instructions file.
     - `docs/v2_dev_plan.md` — residual Italian fragments only (~9 spots, mostly in acceptance-criteria
       bullets of phases already `DONE`). This is a pure language fix, not a rewrite of historical
       content: substance and decisions recorded in those sections are preserved unchanged.
     - `scripts/README.md`
     - `docs/DEVELOPMENT_PLAN.md`
     - `docs/examples/heima_security_presence_panel.yaml`
     - `docs/specs/adapters/external_context_contract.md`
     - `docs/specs/adapters/owm_adapter_spec.md`
     - `docs/specs/adapters/protezione_civile_adapter_spec.md`
     - `docs/specs/user-interfaces/heima_non_admin_dashboard_spec.md`
     - `docs/specs/user-interfaces/heima_view_model_builder_spec.md`
   - No line-by-line semantic review required beyond normal proofreading — these are not contract
     specs, so translation risk is low.
   - Acceptance:
     - [ ] Active operational docs are English.
     - [ ] `CLAUDE.md`'s "respond in Italian in chat" directive is preserved.
     - [ ] `docs/v2_dev_plan.md` historical phase content is unchanged in substance.
     - [ ] Example dashboards do not ship Italian text unless they are explicitly locale-specific.

3. **AG4b — Translate canonical active specs (dedicated reviewed sub-slice)**
   - Highest translation risk: these are normative contracts where a mistranslated field definition,
     threshold, or default can silently change behavior. Treat as its own sub-slice, done after AG3–AG4a
     are merged and green, one file at a time:
     - `docs/specs/heima_v2_spec.md` (highest priority — canonical, currently mixed-language in
       normative sections, e.g. around the `monitored_entities` note, house-state confidence
       thresholds, and the anomaly rule catalog)
     - `docs/specs/core/options_flow_ux_spec.md`
     - `docs/specs/domains/calendar_domain_spec.md`
     - `docs/specs/learning/learning_system_spec.md`
   - After each file: diff the translated version against the original section-by-section to confirm
     no field name, threshold, default value, or contract behavior changed — only the language did.
   - Acceptance:
     - [ ] Each translated spec file has a reviewed diff confirming semantic equivalence.
     - [ ] Active specs are English or have an explicit archival exception.

4. **AG5 — Final verification**
   - Run focused tests during each slice and full local CI at the end.
   - Run relevant live diagnostics only if runtime-facing text changes touch live-test contracts.
   - Perform targeted repository searches as a final manual review aid; do not add a permanent CI
     language gate.
   - Acceptance:
     - [x] `scripts/ci_local.sh` passes (1594 tests, lint, format all green across every commit).
     - [x] Manual repository review finds no Italian text outside the documented exceptions
       (verified via broad-wordlist grep sweeps across every AG-touched file; one missed
       multi-line docstring in `layout.py` found and fixed during this sweep).
     - [x] `047_darkness_assist_fire_live.py` and `060_lighting_schedule.py` had only
       print/error-message text translated, no logic change; verified via `py_compile` and the
       full unit test suite. Not run against a live HA instance in this session (none available);
       documented here as not required since only text changed.

### AG completion summary (2026-07-04)

- AG1/AG2 dropped (see spec revision note above) — `is_it` runtime localization preserved.
- AG3: dev script comments/docstrings/output translated (`pyproject.toml`,
  `scripts/generate_debug_dashboard.py`, `scripts/lib/dashboard/*.py`, `scripts/lib/utils.py`,
  `scripts/live_tests/047_darkness_assist_fire_live.py`,
  `scripts/live_tests/060_lighting_schedule.py`). Dashboard-rendered content (card titles, table
  labels generated via `translate()`) intentionally left in Italian, same category as `is_it`.
- AG4a: `CLAUDE.md`, `docs/v2_dev_plan.md` residual fragments (Phases O–U), `scripts/README.md`,
  `docs/examples/heima_security_presence_panel.yaml`, and the three adapter specs translated.
  `docs/DEVELOPMENT_PLAN.md` marked `SUPERSEDED` instead of translated (describes v1, replaced by
  this document). `heima_non_admin_dashboard_spec.md`'s one hit was an intentional Italian UI-copy
  example, left as-is.
- AG4b: `heima_v2_spec.md`, `options_flow_ux_spec.md`, `calendar_domain_spec.md`,
  `learning_system_spec.md` translated with a numeric-token diff review per file to confirm no
  threshold/contract drift. Calendar keyword lists and `is_it`-example UI text preserved and
  annotated inline as intentional exceptions.
- Commits: `9ed842a` (AG3+AG4a), `9ae6d1c` (AG4b), `af5d058` (AG5 fix).

### Current open items

- Decide whether old audit/RFC documents should be translated or marked as archived historical
  notes. Until that decision is made, the audit allowlist should treat them as temporary
  exceptions, not permanent product policy.

- **Resolved (2026-07-03):** AG1/AG2 were dropped after finding their premise was wrong — see the
  "Spec revision note" at the top of this phase. The `is_it` runtime IT/EN localization mechanism
  is intentional and out of scope for AG.

---

## Phase AH — Resident Runtime Confirmation & Auto-Apply Promotion

**Status:** `PLANNED`
**Depends on:** AD, MH, AF
**Spec source:** `docs/specs/core/resident_runtime_confirmation_spec.md`

### Goal

Add a generic runtime-confirmation layer between configured reactions and apply execution.

For selected reaction families, Heima can ask residents whether to apply a concrete runtime
occurrence. If residents repeatedly approve the same reaction, Heima may create an HA-admin-gated
promotion review that switches that reaction from `ask_residents` to `auto_apply`.

### Scope Guardrails

- Runtime confirmation is not proposal review.
- Runtime approval applies or skips one occurrence only.
- Promotion changes stable execution policy and must be approved in an HA-admin-gated Heima surface.
- Runtime action requests are in-memory only in the first implementation.
- Confirmation statistics and promotion state are persistent.
- The first supported reaction family is `context_conditioned_lighting_scene`.
- The framework must be domain-generic from the first slice:
  - no runtime confirmation component may be lighting-specific
  - every supported family must register a `RuntimeConfirmationDescriptor`
  - future domains must be able to opt in through descriptors, renderers, validators, and
    configuration schema, not through new hardcoded runtime branches
- The intended end state is support for every Heima domain/reaction family that can provide the
  required descriptor and safe resident-facing rendering. No domain is excluded by product policy.

### Development Plan

1. **AH1 — Core runtime confirmation contracts** — `DONE`
   - Add optional `ApplyStep` metadata for `step_id` and `depends_on`.
   - Add runtime models:
     - `ExecutionPolicy`
     - `ConfirmationPolicy`
     - `RuntimeActionRequest`
     - `RuntimeApplyResult`
     - `RuntimeConfirmationDescriptor`
   - Add status transition helpers and first-writer-wins resolution semantics.
   - Add dependency evaluation rules:
     - blocked/failed/skipped dependency skips dependent step
     - list order must not imply dependency
   - Acceptance:
     - [x] Unit tests cover model defaults, status transitions, dependency skipping, and
       `failed` when zero steps apply after an apply trigger.

2. **AH2 — Notification capabilities and actionable routing** — `DONE`
   - Normalize and persist `notifications.notification_service_capabilities`.
   - Add Options Flow support for marking concrete notify services with `supports_actions`.
   - Extend notification routing for actionable requests:
     - resolve recipients/groups through the existing logical model
     - filter services by `supports_actions: true`
     - fail closed with `failure_reason: no_actionable_route` when no actionable service remains
   - Implement provider-neutral actionable notification payload objects.
   - Wire notification action response handling to runtime request ids.
   - Verify the current Home Assistant actionable notification payload shape before implementation.
   - Acceptance:
     - [x] Non-actionable informational notifications continue to use existing routing.
     - [x] Actionable requests never silently downgrade to non-actionable text.
     - [x] Stale/unknown response ids are parsed for registry handling; registry-side stale
       counting started in AH3.

3. **AH3 — In-memory request registry and timeout engine** — `DONE`
   - Add coordinator/runtime-owned in-memory request registry.
   - Deduplicate pending requests by `(reaction_id, occurrence_key)`.
   - Schedule expirations with HA async scheduling.
   - Implement `on_timeout: skip`.
   - Implement `on_timeout: apply`.
   - Ignore stale responses after restart or completion.
   - Acceptance:
     - [x] Duplicate occurrences do not create duplicate pending requests.
     - [x] Timeout skip applies nothing.
     - [x] Timeout apply dispatches to the injected apply handler; AH4 implements the concrete
       pre-apply validation and stored-step processing.
     - [x] Restart behavior foundation is safe: stale/unknown responses are ignored and counted by
       the in-memory registry.

4. **AH4 — Engine apply-path integration**
   - Integrate `execution_policy.mode` into the reaction apply path. `IN PROGRESS`
   - Keep `auto_apply` behavior unchanged. `DONE`
   - For `ask_residents`:
     - store the concrete `ApplyStep` plan. `DONE`
     - send an actionable request. `DONE`
     - do not apply steps immediately. `DONE`
   - Add pre-apply validation:
     - request is still pending and not expired. `DONE`
     - source reaction still exists and is compatible. `PARTIAL`
     - entities/services still exist. `TODO`
     - manual hold and apply filters are evaluated per step. `DONE`
     - dependencies are evaluated after per-step blocking. `DONE`
     - descriptor validators pass. `TODO`
   - Register pending applies only immediately before approved/timeout-applied execution.
   - Acceptance:
     - [x] Manual hold blocks affected steps without blocking unrelated surviving steps.
     - [x] Dependent steps are skipped when prerequisites did not run.
     - [x] If no step applies after an apply trigger, status is `failed`.
     - [x] If the source reaction is disabled while pending, status is `cancelled`.
     - [ ] If the source reaction is structurally changed while pending, status is `cancelled`.
     - [ ] Descriptor validators can veto request creation or approved/timeout-applied execution.

5. **AH5 — First descriptor: context-conditioned lighting scene**
   - Register a `RuntimeConfirmationDescriptor` for `context_conditioned_lighting_scene`. `DONE`
   - Define occurrence key semantics for lighting scene occurrences. `DONE`
   - Render concise resident-facing text for: `DONE`
     - turning lights off
     - setting brightness
     - mixed light-scene changes
   - Add reaction configuration support for `execution_policy.mode`, confirmation timeout, targets,
     and timeout behavior. `DONE`
   - Acceptance:
     - [x] A learned/context-conditioned lighting scene in `ask_residents` creates a runtime
       request instead of applying immediately.
     - [x] Approving applies the stored lighting steps.
     - [x] Dismissing applies nothing.

6. **AH6 — Confirmation statistics and promotion state** — `IN PROGRESS`
   - Persist confirmation stats per reaction:
     - `requested`. `DONE`
     - `approved`. `DONE`
     - `dismissed`. `DONE`
     - `timeout_skipped`. `DONE`
     - `timeout_applied`. `DONE`
     - `failed`. `DONE`
   - Persist promotion review state per reaction. `PARTIAL`
   - Implement promotion eligibility:
     - `min_samples`. `DONE`
     - `min_approval_rate`. `DONE`
     - `min_distinct_days`. `DONE`
     - `min_new_approvals_after_dismissal`. `DONE`
     - `cooldown_schedule_days`. `DONE`
     - `reminder_interval_days`. `DONE`
   - Exclude timeout outcomes from promotion evidence in all cases. `DONE`
   - Revoke `pending_admin_review` when new evidence no longer satisfies thresholds. `DONE`
   - Acceptance:
     - [x] Repeated explicit approvals can create `pending_admin_review`.
     - [x] Explicit dismissals count as negative promotion evidence.
     - [x] Timeout outcomes never count as promotion evidence.
     - [x] Revoked promotion reviews cannot be approved by the AH7 admin action boundary.

7. **AH7 — HA-admin-gated promotion and configuration UI**
   - Add admin UI/options-flow support for:
     - viewing/editing `execution_policy.mode`
     - configuring runtime confirmation targets and timeout behavior
     - viewing confirmation stats in pending promotion reviews. `DONE`
     - viewing pending promotion reviews. `DONE`
     - approving auto-apply. `DONE`
     - dismissing "not now". `DONE`
     - disabling future promotion prompts. `DONE`
     - resetting stats/cooldown. `DONE`
     - reverting promoted `auto_apply` back to `ask_residents`. `DONE`
   - Promotion notifications remain informational only and must not contain a direct approve action.
   - Acceptance:
     - [x] Only HA-admin-gated options-flow UI/coordinator boundary can approve promotion.
     - [x] Sending a promotion notification to a non-admin route grants no approval authority
       because notifications remain informational and expose no action.
     - [x] Admin "not now" starts/increments cooldown.
     - [x] Admin "do not ask again" disables future promotion prompts only for that reaction.

8. **AH8 — Diagnostics, services, and observability**
   - Extend diagnostics with:
     - pending runtime requests. `DONE`
     - recent completed requests. `DONE`
     - counts by status. `DONE`
     - applied/blocked/skipped/failed step counts. `DONE`
     - no-actionable-route failures. `DONE`
     - stale response counts. `DONE`
     - confirmation stats. `DONE`
     - promotion eligibility, cooldowns, and disabled prompts. `DONE`
   - Add debug/service helpers only where needed for tests or live diagnostics. `DONE`
   - Acceptance:
     - [x] Production debug can explain why an action was not applied.
     - [x] Diagnostics distinguish manual-hold blocking from dependency skipping.
     - [x] Diagnostics distinguish runtime request state from proposal review state.

9. **AH9 — Verification and live coverage**
   - Add unit tests for all AH1-AH8 contracts.
   - Add integration tests for options flow, notification routing, engine interception, timeout,
     promotion, diagnostics, and stale responses.
   - Add live tests:
     - ask-residents lighting request
     - approve applies stored steps
     - dismiss applies nothing
     - timeout skip
     - timeout apply
     - no actionable route fails closed
     - duplicate response from multiple devices: first valid response wins
     - manual hold blocks a step and skips dependent steps
     - disabled reaction while pending cancels the request
     - repeated approvals create admin promotion review
     - admin-approved promotion makes later occurrences auto-apply
   - Added read-only diagnostic live coverage:
     - `scripts/live_tests/077_runtime_confirmation_diag_live.py` validates runtime confirmation
       request counters, recent request rows, step result counts, failure reasons, stale responses,
       and persisted confirmation/promotion diagnostics. `DONE`
   - Acceptance:
     - [x] Focused unit/integration tests pass.
     - [x] Runtime confirmation diagnostics have live diagnostic coverage.
     - [x] `scripts/ci_local.sh` passes.
     - [x] Relevant live diagnostic/e2e tiers pass outside the sandbox.
   - Validation:
     - `PATH=".venv/bin:$PATH" bash scripts/ci_local.sh` — passed: 1651 tests,
       coverage 84.34%, ruff check and ruff format check passed; mypy remains informative.
     - `source scripts/.env && ./scripts/check_all_live.sh --tier diagnostic` — passed,
       including `074_camera_privacy_manual_hold_live.py`, `076_camera_privacy_policy_runtime_live.py`,
       and `077_runtime_confirmation_diag_live.py`.

### Expected File Areas

- `custom_components/heima/runtime/contracts.py`
- `custom_components/heima/runtime/engine.py`
- `custom_components/heima/runtime/notifications.py`
- `custom_components/heima/runtime/manual_hold.py`
- `custom_components/heima/runtime/reactions/base.py`
- `custom_components/heima/runtime/reactions/context_conditioned_lighting.py`
- `custom_components/heima/coordinator.py`
- `custom_components/heima/config_flow/`
- `custom_components/heima/options_migration.py`
- `custom_components/heima/diagnostics.py`
- `custom_components/heima/translations/en.json`
- `custom_components/heima/translations/it.json`
- `tests/`
- `scripts/live_tests/`

### Acceptance Criteria

- [ ] Existing reactions without `execution_policy` keep current `auto_apply` behavior.
- [ ] `ask_residents` is supported through descriptors, not per-domain runtime branches.
- [ ] First supported family is `context_conditioned_lighting_scene`.
- [ ] The architecture is ready for every domain/reaction family to opt in later.
- [ ] Runtime confirmation requests never enter the proposal backlog.
- [ ] Promotion review is HA-admin-gated and persistent.
- [ ] Runtime requests are in-memory only and restart-safe by ignoring stale responses.
- [ ] Manual hold, apply filters, and step dependencies are enforced before execution.
- [ ] No actionable route fails closed.
- [ ] Timeout outcomes never count toward promotion.
- [ ] Diagnostics explain pending, completed, failed, cancelled, blocked, skipped, and promoted
  states.

### Current open items

- Confirm the exact Home Assistant actionable notification payload shape for supported notify
  providers before AH2 implementation.
- Decide whether restart-safe persisted runtime requests are still out of scope after the first AH
  implementation is validated in production.

---

## Phase AN — Notification Admin UI & Execution Policy Profiles

**Status:** `DONE`
**Depends on:** AH
**Spec source:** `docs/specs/core/notification_admin_ui_spec.md`

### Goal

Replace raw object/JSON editing for notification routing with a guided admin UI, and add reusable
execution policy profiles that reactions can reference by stable id.

The implementation must keep notification routing domain-generic. Runtime confirmation, promotion
reviews, and future reaction families must all consume the same notification recipients, recipient
groups, service capabilities, and execution policy profile model.

### Scope Guardrails

- Do not add domain-specific notification configuration for lighting, camera privacy, security, or
  any other single reaction family.
- Keep inline `execution_policy` valid for compatibility.
- Prefer `execution_policy_ref` for newly edited reactions so group membership and profile changes
  affect future executions without rewriting every reaction.
- Invalid `execution_policy_ref` must fail closed and surface a configuration error. It must not
  silently fall back to `auto_apply`.
- `recipient_id`, `group_id`, and `profile_id` are immutable in the first implementation.
- Recipient labels are derived from `people_named.display_name` when available; otherwise the
  immutable id is shown. Do not introduce a separate recipient display-name field.
- `supports_actions` defaults to false and must be explicitly persisted before a service can receive
  actionable runtime confirmation notifications.

### Development Plan

1. **AN1 — Execution policy profile model and resolver** — `DONE`
   - Add canonical support for `reactions.execution_policy_profiles`. `DONE`
   - Add pure resolution logic for: `DONE`
     - valid `execution_policy_ref`
     - `execution_policy_ref` plus `execution_policy_override`
     - legacy inline `execution_policy`
     - no policy, which keeps current `auto_apply` behavior
   - Implement override merge semantics: `DONE`
     - objects merge recursively
     - scalars replace
     - lists replace
     - null/empty values cannot delete required fields unless that field explicitly supports
       clearing
   - Add fail-closed unresolved-reference handling. `DONE`
   - Tests:
     - [x] resolver unit tests for profile-only, profile-plus-override, inline-only, default
       `auto_apply`, unresolved reference, list replacement, scalar replacement, nested object merge,
       and invalid override attempts.
   - Verification:
     - `.venv/bin/python -m pytest tests/test_runtime_confirmation.py -q` — 18 passed.
     - `.venv/bin/ruff check custom_components/heima/runtime/runtime_confirmation.py tests/test_runtime_confirmation.py`
       — passed.

2. **AN2 — Runtime integration and diagnostics** — `DONE`
   - Route runtime confirmation and promotion logic through the resolved effective execution policy.
     `DONE`
   - Preserve current inline-policy behavior. `DONE`
   - Extend diagnostics to expose: `DONE`
     - policy source: `inline`, `profile`, `profile_with_override`, or `default_auto_apply`
     - referenced profile id
     - unresolved reference errors
     - effective mode
     - effective confirmation targets and timeout behavior
     - effective promotion review targets and thresholds
   - Tests:
     - [x] engine/runtime tests proving profile-backed `ask_residents` creates requests
     - [x] profile-backed `auto_apply` applies immediately through resolved policy defaults
     - [x] invalid profile reference fails closed
     - [x] inline legacy reactions still work
     - [x] overrides affect only the edited fields
     - [x] diagnostics report the effective policy source correctly.
     - [x] promotion eligibility and admin promotion decisions honor profile-backed policies.
   - Verification:
     - `.venv/bin/python -m pytest tests/test_runtime_confirmation.py tests/test_reaction_framework.py tests/test_runtime_confirmation_promotion_stats.py -q`
       — 53 passed.
     - `.venv/bin/ruff check custom_components/heima/runtime/runtime_confirmation.py custom_components/heima/runtime/engine.py custom_components/heima/coordinator.py tests/test_runtime_confirmation.py tests/test_reaction_framework.py tests/test_runtime_confirmation_promotion_stats.py`
       — passed.

3. **AN3 — Recipient editor UI** — `DONE`
   - Add guided options-flow screens for notification recipients. `DONE`
   - Support creating and deleting recipients. `DONE`
   - Block deletion while a recipient is referenced by a group, route target, or execution policy.
     `DONE`
   - Show labels from `people_named.display_name` when available. `DONE`
   - Tests:
     - [x] create recipient
     - [x] delete unreferenced recipient
     - [x] block referenced recipient deletion
     - [x] derived label display
     - [x] config validation rejects malformed recipient ids.
   - Verification:
     - `.venv/bin/python -m pytest tests/test_options_flow_e2e.py -q -k "notification_recipient or notifications_step"`
       — 9 passed, 170 deselected.
     - `.venv/bin/ruff check custom_components/heima/config_flow/__init__.py custom_components/heima/config_flow/_steps_notifications.py tests/test_options_flow_e2e.py`
       — passed.
     - `.venv/bin/python -m json.tool custom_components/heima/translations/en.json` — passed.

4. **AN4 — Recipient group editor UI** — `DONE`
   - Add guided options-flow screens for recipient groups. `DONE`
   - Support group membership editing through existing recipients. `DONE`
   - Block deletion while a group is referenced by default routing or execution policy profiles.
     `DONE`
   - Tests:
     - [x] create group
     - [x] edit group members
     - [x] block unknown members
     - [x] block referenced group deletion
     - [x] persist stable group ids without rename side effects.
   - Verification:
     - `.venv/bin/python -m pytest tests/test_options_flow_e2e.py -q -k "notification_recipient or notification_group or notifications_step"`
       — 15 passed, 170 deselected.
     - `.venv/bin/ruff check custom_components/heima/config_flow/__init__.py custom_components/heima/config_flow/_steps_notifications.py tests/test_options_flow_e2e.py`
       — passed.
     - `.venv/bin/python -m json.tool custom_components/heima/translations/en.json` — passed.

5. **AN5 — Default routing and service capability editor** — `DONE`
   - Add guided screens for default `notifications.route_targets`. `DONE`
   - Add guided screens for `notification_service_capabilities`. `DONE`
   - Require explicit `supports_actions: true` before a notify service can receive actionable
     requests. `DONE`
   - Tests:
     - [x] configure default route targets
     - [x] configure action-capable services
     - [x] non-actionable services are excluded from runtime confirmation routes
     - [x] informational notifications can still use non-actionable services when appropriate.
   - Verification:
     - `.venv/bin/python -m pytest tests/test_options_flow_e2e.py -q -k "notification_recipient or notification_group or notification_routes or notification_service or notifications_step"`
       — 21 passed, 170 deselected.
     - `.venv/bin/ruff check custom_components/heima/config_flow/__init__.py custom_components/heima/config_flow/_steps_notifications.py tests/test_options_flow_e2e.py`
       — passed.
     - `.venv/bin/python -m json.tool custom_components/heima/translations/en.json` — passed.

6. **AN6 — Execution policy profile UI** — `DONE`
   - Add guided screens for creating and editing reusable execution policy profiles. `DONE`
   - Support at least: `DONE`
     - `auto_apply`
     - `ask_residents`
     - confirmation target groups
     - timeout minutes
     - timeout behavior
     - promotion review target groups
     - promotion thresholds and reminder interval
   - Block deletion while a profile is referenced by any configured reaction. `DONE`
   - Tests:
     - [x] create `ask_residents` profile
     - [x] edit timeout and routing fields
     - [x] create `auto_apply` profile
     - [x] block invalid target groups
     - [x] block referenced profile deletion
     - [x] persist only canonical profile data, not UI-only derived labels.
   - Verification:
     - `.venv/bin/python -m pytest tests/test_options_flow_e2e.py -q -k "execution_policy_profile or notification_recipient or notification_group or notification_routes or notification_service"`
       — 25 passed, 172 deselected.
     - `.venv/bin/ruff check custom_components/heima/config_flow/__init__.py custom_components/heima/config_flow/_steps_notifications.py tests/test_options_flow_e2e.py`
       — passed.
     - `.venv/bin/python -m json.tool custom_components/heima/translations/en.json` — passed.

7. **AN7 — Reaction editing integration** — `DONE`
   - Update supported reaction editor surfaces to prefer `execution_policy_ref`. `DONE`
   - Keep inline `execution_policy` rendering/editing available for legacy data. `DONE`
   - Add focused override editing for allowed per-reaction deviations, such as timeout minutes or
     target groups. `DONE`
   - Surface unresolved references as blocking validation errors before saving. `DONE`
   - Tests:
     - [x] select profile for a reaction
     - [x] save reaction with profile reference
     - [x] save reaction with profile reference plus override
     - [x] load legacy inline reaction without data loss
     - [x] reject unresolved profile reference.
   - Verification:
     - `.venv/bin/python -m pytest tests/test_options_flow_e2e.py -q -k "execution_policy_profile or context_conditioned_runtime_policy or saves_execution_policy_profile"`
       — 9 passed, 190 deselected.
     - `.venv/bin/ruff check custom_components/heima/config_flow/_reaction_forms.py custom_components/heima/config_flow/_steps_reaction_editing.py custom_components/heima/config_flow/_steps_notifications.py tests/test_options_flow_e2e.py`
       — passed.
     - `.venv/bin/python -m json.tool custom_components/heima/translations/en.json` — passed.

8. **AN8 — Live and end-to-end coverage** — `DONE`
   - Add live coverage for profile-backed runtime confirmation using the first supported descriptor.
     `DONE`
   - Add live coverage proving group membership changes affect future notifications without editing
     the reaction. `DONE` at routing-unit level via `tests/test_notifications.py`, where actionable
     notification delivery expands `recipient_groups` at send time and filters by
     `supports_actions`.
   - Add live coverage for invalid profile reference fail-closed behavior. `DONE`
   - Add live coverage proving inline legacy execution policies still work. `DONE` via
     `078_runtime_confirmation_promotion_revert_live.py`.
   - Tests:
     - [x] new live script for profile-backed `ask_residents`
     - [x] new live script or diagnostic assertion for effective-policy diagnostics
     - [x] invalid profile references fail closed and are exposed in effective-policy diagnostics.
     - [x] `check_all_live.sh --tier diagnostic` includes live profile-backed coverage.
   - Verification:
     - `source scripts/.env && ./scripts/check_all_live.sh --tier diagnostic --skip 030,031,062,063,064,065,070,071,072,074,075,076,077,078`
       — passed, running `079_runtime_confirmation_profile_policy_live.py`.

9. **AN9 — Documentation and migration notes** — `DONE`
   - Update admin guide with guided UI workflow. `DONE`
   - Document immutable ids and manual migration steps for id changes: `DONE`
     - create the new recipient/group/profile
     - update references
     - verify diagnostics
     - delete the old unreferenced id
   - Document compatibility rules for inline execution policies. `DONE`
   - Document fail-closed unresolved-reference behavior. `DONE`
   - Tests:
     - `git diff --check`
     - schema/config examples covered by existing parser tests where applicable.

### Acceptance Criteria

- [x] Admins can configure recipients, groups, default route targets, service capabilities, and
  execution policy profiles without editing raw JSON/YAML objects directly.
- [x] Reactions can reference an execution policy profile by stable id.
- [x] Profile changes affect future reaction executions without rewriting every referencing
  reaction.
- [x] Inline `execution_policy` remains supported for existing reactions.
- [x] Invalid profile references fail closed and are visible in diagnostics/config validation.
- [x] Actionable runtime notifications are sent only through services with persisted
  `supports_actions: true`.
- [x] Recipient/group/profile ids are immutable in the first implementation, with documented manual
  migration steps.
- [x] Tests cover the resolver, options-flow UI, runtime integration, diagnostics, and live
  profile-backed runtime confirmation.

### Current open items

- Final focused review/CI before merge.

---

## Updating this document

After completing each phase:

1. Update the phase row in the [Phase overview](#phase-overview) table: `NOT STARTED` → `IN PROGRESS` → `DONE`.
2. Update [Current State](#current-state): set `Last completed phase`, `Active phase`, `Next action`.
3. Add any new open blockers or decisions to [Current State](#current-state).
4. Commit this file together with the phase code.

Do not rewrite completed phase sections — they are the historical record.
If a spec change causes a phase to be revised, note it in the relevant phase section under a `**Spec revision note:**` heading and update the spec file.
