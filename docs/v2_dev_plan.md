# Heima v2.1 — Development Plan

**Spec:** `docs/specs/heima_v2_spec.md` (v2.1.0-draft)
**Branch:** `feat/semantic-policy-advisor`
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
| T | Learning Signal Analyzers | `NOT STARTED` | P, S |
| U | Physical Light State Awareness | `NOT STARTED` | A, Q |
| V | Signal Discovery Pipeline | `IN PROGRESS` | N, L |

---

## Current State

**Last completed phases:** Phase E — OutcomeTracker + Feedback Loop; Phase F — ActivityDomain; Phase G — Role model + product constraints; Phase H — House State Learning; Phase I — Activity Inference and Learning; Phase J — Event-Driven Trigger; Phase K — Installer alert channel + health entity; Phase L — Auto-discovery config flow; Phase M — Installation validation; Phase N — Semantic Policy Suggestions; Phase O — HouseSnapshot Alignment + Proposal Revocation; Phase P — Learning Modules D2; Phase Q — AnomalyAnalyzer Statistical Detection Rules; Phase R — OutcomeTracker Positive Feedback + WeekdayStateModule Consolidation; Phase S — Learning Module Threshold Configurability.
**Active phase:** Phase V — Signal Discovery Pipeline (`IN PROGRESS`).
**Branch:** `feat/semantic-policy-advisor`.
**Next action:**

Continue Phase V — Signal Discovery Pipeline with V5 triggering and final coverage.

### Current Working Notes

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
- Current slice: Phase Q complete for current v2 scope.
  - Implemented operational rules: 15/17.
  - Deferred rules: `lights_on_unattended`, `lighting_scene_drift`.
  - Deferred reason: they require physical light state awareness; current
    `HouseSnapshot.lighting_scenes` records Heima scene decisions, not reliable physical light
    state.
  - Live coverage: diagnostic tier includes `062_anomaly_rules_live.py`, validating
    `heima.configure_anomaly_rule`, implemented rule IDs, threshold persistence, validation
    errors, and the next `learning_run` path.
- Phase Q / Q4 complete.
  - Q4 scope: `stove_on_unattended`, `oven_on_unattended`, `appliance_unusual_hour` (3 rules only).
  - `lights_on_unattended` and `lighting_scene_drift` deferred to Phase U (Physical Light State
    Awareness): `HouseSnapshot.lighting_scenes` records Heima's own scene decisions, not physical
    light states. Phase U / physical light state awareness implements both rules.
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
**Goal:** allineare HouseSnapshot con i dati necessari alle fasi successive; aggiungere revoca proposal.
**Depends on:** Phase N.

### Working slices

1. O1 — HouseSnapshot `security_state`:
   - Sostituire `security_armed: bool` con `security_state: str` in `HouseSnapshot`.
   - Aggiungere migrazione backward-compatible in `from_dict()`: se `security_state` assente, deriva da `security_armed` (True → `"armed_away"`, False → `"disarmed"`).
   - Aggiornare `HeatingDomain` e qualsiasi altro riferimento a `security_armed`.
   - Tests: deserializzazione legacy, round-trip nuovo formato.
2. O2 — HouseSnapshot `heating_current_temperature`:
   - Aggiungere campo `heating_current_temperature: float | None` a `HouseSnapshot`.
   - `HeatingDomain` legge `climate.ATTR_CURRENT_TEMPERATURE` e lo passa allo snapshot.
   - Tests: campo popolato quando disponibile, None quando assente.
3. O3 — `ProposalEngine.async_withdraw`:
   - Aggiungere `async_withdraw(identity_key) -> bool` a `ProposalEngine`.
   - Rimuove solo proposal in stato `pending`; no-op su approved/rejected.
   - Aggiornare `_async_evaluate_semantic_policies()` in coordinator per chiamare `async_withdraw()` sulle regole non più applicabili.
   - Tests: withdraw pending → True, withdraw approved → False, withdraw assente → False.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `tests/test_snapshot_migration_o.py` | Migrazione legacy format, nuovi campi | Phase O |

### Files to modify

| File | Change |
|---|---|
| `runtime/inference/snapshot_store.py` | `security_state`, `heating_current_temperature`, `from_dict()` migration |
| `runtime/domains/heating.py` | Legge `current_temperature` attr, passa a snapshot |
| `runtime/proposal_engine.py` | `async_withdraw(identity_key)` |
| `coordinator.py` | `_async_evaluate_semantic_policies()`: chiama `async_withdraw()` |
| `tests/test_proposal_engine.py` | Extend: test `async_withdraw` |

### Acceptance criteria

- [x] `HouseSnapshot.security_state` è `str` e non `bool`
- [x] Snapshot serializzati con `security_armed: bool` vengono deserializzati correttamente
- [x] `HouseSnapshot.heating_current_temperature` è popolato quando climate entity disponibile
- [x] `ProposalEngine.async_withdraw()` rimuove solo proposal pending, no-op sulle altre
- [x] `_async_evaluate_semantic_policies()` chiama `async_withdraw()` per regole non applicabili
- [x] Full regression tests pass

---

## Phase P — Learning Modules D2: Lighting, Room Correlation, Occupancy

**Spec section:** Phase P
**Goal:** completare Phase D2; aggiungere OccupancyInferenceModule.
**Depends on:** Phase D (ILearningModule, SnapshotStore), Phase F (room_occupancy in HouseSnapshot).

### Working slices

1. P1 — `LightingPatternModule`:
   - Implementare `ILearningModule` che apprende `P(scene | room_id, house_state, hour_bucket)`.
   - Min support 8 snapshot/slot. Emette `LightingSignal(importance=SUGGEST, confidence ≥ 0.65)`.
   - Tests: model building da sequenza snapshot, signal emission, min support respected.
2. P2 — `RoomStateCorrelationModule`:
   - Implementare `ILearningModule` che apprende `P(house_state | frozenset(occupied_rooms))`.
   - Min support 15 snapshot/pattern. Emette `HouseStateSignal`.
   - Tests: pattern con support < 15 ignorati, signal con confidence corretta.
3. P3 — `OccupancyInferenceModule` + `OccupancyDomain` consumption:
   - Implementare `ILearningModule` che apprende `P(room_occupied | room_id, weekday, hour_bucket, anyone_home)`.
   - Min support 10 snapshot/slot. Emette `OccupancySignal` solo per stanze senza sensore.
   - `OccupancyDomain.compute()`: per stanze senza sensore, applica `OccupancySignal` se confidence ≥ 0.70.
   - Tests: stanze con sensore ignorano il segnale, stanze senza sensore lo applicano.
4. P4 — Coordinator wiring:
   - Registrare i tre nuovi moduli nel coordinator.
   - P4a: i moduli girano nel ciclo reale e sono osservabili in diagnostics; solo
     `OccupancySignal` influenza runtime. `LightingSignal` e `RoomStateCorrelationModule`
     restano signal-only.
   - P4b: formalizzare il consumo proposal-gated. `LightingSignal` e il segnale di correlazione
     stanza/stato casa non entrano nei domini; futuri analyzer producono proposte reviewabili.
   - Tests: verifica che i moduli vengano chiamati nel ciclo di inference, che la sync delle
     stanze sensorless avvenga su startup/options reload, e che segnali senza consumer non
     causino errori.
   - Verification: `context_conditioned_lighting_scene` esiste come reaction type per future
     proposte lighting. Per house-state correlation il percorso resta il meccanismo
     approval/candidate dedicato, non un reaction plugin runtime diretto.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/inference/modules/lighting_pattern.py` | `LightingPatternModule` | Phase P, §10.6 |
| `runtime/inference/modules/occupancy_inference.py` | `OccupancyInferenceModule` | Phase P |
| `tests/test_learning_modules_p.py` | Tests P1–P4 | Phase P |

### Files to modify

| File | Change |
|---|---|
| `runtime/inference/modules/room_state.py` | Implementare `RoomStateCorrelationModule` (file esiste come stub) |
| `runtime/domains/occupancy.py` | Consumare `OccupancySignal` per stanze senza sensore |
| `coordinator.py` | Registrare tre nuovi moduli |

### Acceptance criteria

- [x] `LightingPatternModule` non emette segnali con support < 8 snapshot/slot
- [x] `RoomStateCorrelationModule` non emette segnali per pattern con support < 15
- [x] `OccupancyInferenceModule` emette `OccupancySignal` solo per stanze senza sensore
- [x] `OccupancyDomain` applica `OccupancySignal` con confidence ≥ 0.70 per stanze non sensorizzate
- [x] `OccupancyDomain` ignora `OccupancySignal` per stanze con almeno un sensore
- [x] P4a registra i moduli P1-P3 nel coordinator lifecycle
- [x] `sync_sensorless_rooms()` è chiamato su startup/options reload, non nel loop di analyze
- [x] `LightingSignal` senza consumer operativo è routed/observable e non causa errori
- [x] `RoomStateCorrelationModule` resta observable ma non altera `HouseStateDomain`
- [x] P4b policy: segnali statistici operativi solo via ProposalEngine + review admin
- [x] Verificato target lighting: `context_conditioned_lighting_scene` esiste
- [x] Tutti i test esistenti verdi; nuovi test ≥ 20

---

## Phase Q — AnomalyAnalyzer: Statistical Detection Rules

**Spec section:** Phase Q
**Goal:** implementare `AnomalyAnalyzer` con 15 regole operative configurabili nel current v2 scope; mantenere nel catalogo le 2 regole lighting pianificate ma rinviarle a Phase U / physical light state awareness; servizio `heima.configure_anomaly_rule`.
**Depends on:** Phase O (security_state, heating_current_temperature), Phase P (snapshot data quality).

### Working slices

1. Q1 — `AnomalyRule` + catalogo + infrastruttura: `DONE`
   - Definire `AnomalyRule` dataclass con `rule_id`, `enabled`, `severity`, `thresholds`.
   - Definire catalogo con default thresholds per tutte le 17 regole pianificate.
   - Implementare caricamento soglie dalle options a ogni `analyze()`.
   - Implementare almeno una regola reale end-to-end per validare il percorso
     `AnomalyAnalyzer -> FindingRouter -> installer alert`.
   - Il servizio `heima.configure_anomaly_rule` è fuori da Q1; resta in Q6.
2. Q2 — Regole presenza (4): `DONE`
   - `arrival_time_outlier`, `departure_time_outlier`, `extended_absence`, `presence_pattern_drift`.
   - `arrival_time_outlier` e `departure_time_outlier` usano transizioni consecutive
     `anyone_home=False -> True` e `anyone_home=True -> False`; la transizione più recente
     viene confrontata con la mediana storica delle transizioni precedenti.
   - `extended_absence` usa il run corrente di `anyone_home=False` e lo confronta con il
     percentile 90 dei run storici di assenza.
   - `presence_pattern_drift` confronta il rapporto `anyone_home=True` recente con il baseline
     dello stesso `(weekday, hour_bucket)`.
   - Tests: ogni regola copre trigger, supporto insufficiente, condizione normale, override soglia,
     e regola disabilitata.
3. Q3 — Regole riscaldamento (3): `DONE`
   - `heating_setpoint_outlier`, `heating_unresponsive`, `heating_vacation_mismatch`.
   - Tests: `heating_unresponsive` usa `heating_current_temperature` da Phase O.
4. Q4 — Regole attività (3): `DONE`
   - `stove_on_unattended`, `oven_on_unattended`, `appliance_unusual_hour`.
   - `lights_on_unattended` e `lighting_scene_drift` rimandate a Phase U / physical light state awareness:
     `HouseSnapshot.lighting_scenes` registra le scene di Heima, non lo stato fisico.
   - `appliance_unusual_hour` triggera solo se l'attività è attiva nell'ultimo snapshot (option A).
5. Q5 — Regole security + sensor + cross-domain (5): `DONE`
   - `alarm_disarm_unusual_hour`, `alarm_expected_not_armed`, `sensor_activity_drop`, `ghost_activity`, `unusual_stillness`.
   - Security subset `DONE`: `alarm_disarm_unusual_hour`, `alarm_expected_not_armed`.
   - Residual subset `DONE`: `sensor_activity_drop`, `ghost_activity`, `unusual_stillness`.
6. Q6 — Servizio `heima.configure_anomaly_rule`: `DONE`
   - Handler nel coordinator: aggiorna options, prende effetto al prossimo `analyze()`.
   - Tests: override soglia applicato, regola disabilitata non triggera.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `tests/test_anomaly_analyzer_q.py` | Tests Q1–Q6 | Phase Q |

### Files to modify

| File | Change |
|---|---|
| `runtime/analyzers/anomaly.py` | Implementazione completa (sostituisce placeholder) |
| `services.yaml` | `heima.configure_anomaly_rule` |
| `coordinator.py` | Handler servizio, passa options aggiornate ad AnomalyAnalyzer |

### Acceptance criteria

- [x] Ogni regola in scope Q triggera su sequenza snapshot costruita ad hoc nel test
- [x] Regola disabilitata non produce findings
- [x] Override soglia via `heima.configure_anomaly_rule` applicato al prossimo `analyze()` pass
- [x] Q1 valida almeno una regola reale end-to-end fino all'installer alert
- [x] `heating_unresponsive` usa `heating_current_temperature` (Phase O prerequisito verificato)
- [x] `heating_setpoint_outlier` usa `heating_setpoint` e finestra snapshot-count
- [x] `heating_vacation_mismatch` usa `security_state`, `heating_setpoint`, e soglia stretta `>`
- [x] Q2 presence rules usano solo `HouseSnapshot.anyone_home`, slot temporali, e transizioni
      consecutive
- [x] `alarm_disarm_unusual_hour` usa `security_state` e transizioni consecutive `armed_* -> disarmed`
- [x] `alarm_expected_not_armed` usa solo pattern statistici da `security_state` nello stesso slot
- [x] `sensor_activity_drop` non si sovrappone a `SensorStuck` (snapshot/hour frequency vs timeout assoluto)
- [x] `ghost_activity` usa `room_occupancy` + `anyone_home` da `HouseSnapshot`
- [x] `unusual_stillness` usa run di `room_occupancy` invariata con `anyone_home == True`
- [x] Q4 activity rules usano `HouseSnapshot.detected_activities`; le 2 lighting rules sono
      deferred a Phase U / physical light state awareness
- [x] `heima.configure_anomaly_rule` mergea `entry.options["anomaly"]["rules"][rule_id]` senza reload
- [x] Tutti i test esistenti verdi; i test Q coprono ogni regola operativa, override soglie,
      regola disabilitata, e percorso end-to-end verso installer alert

---

## Phase R — OutcomeTracker Feedback Positivo + Consolidamento WeekdayStateModule

**Spec section:** Phase R
**Goal:** feedback loop bidirezionale; downgrade WeekdayStateModule a OBSERVE.
**Depends on:** Phase E (OutcomeTracker base), Phase P (HouseStateInferenceModule + room correlation wired).

### Working slices

1. R1 — OutcomeTracker `positive_streak` + boost:
   - Status: `DONE`.
   - Aggiungere `positive_streak: int` per reaction al fianco del `negative_streak` esistente.
   - Dopo K=10 consecutivi positivi, chiamare `ProposalEngine.async_boost_confidence(reaction_id, delta=0.05)`.
   - Azzerare `positive_streak` dopo il boost (non dopo il prossimo negativo).
   - `positive_streak` si azzera a ogni esito negativo.
   - Tests: accumulo streak, boost a K=10, reset, no double-boost per stesso cycle.
2. R2 — `ProposalEngine.async_boost_confidence`:
   - Status: `DONE`.
   - Aggiungere `async_boost_confidence(reaction_id, delta) -> None`.
   - Incrementa la confidence del record proposal approvato per `reaction_id`, cappata a 1.0.
   - No-op se reaction_id non trovato o proposal non approvata.
   - Tests: boost applicato, cap a 1.0, no-op su unknown reaction.
3. R3 — WeekdayStateModule downgrade:
   - Status: `DONE`.
   - Modificare `WeekdayStateModule.infer()`: tutti i segnali emessi con `importance=Importance.OBSERVE`.
   - Verificare che `HouseStateDomain` ignori segnali OBSERVE (già definito in §10.3/§10.8).
   - Tests: WeekdayStateModule emette OBSERVE; HouseStateDomain non li consuma.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `tests/test_outcome_tracker_r.py` | Tests R1–R2 | Phase R |
| `tests/test_weekday_consolidation_r.py` | Tests R3 | Phase R |

### Files to modify

| File | Change |
|---|---|
| `runtime/outcome_tracker.py` | `positive_streak`, boost trigger a K=10 |
| `runtime/proposal_engine.py` | `async_boost_confidence(reaction_id, delta)` |
| `runtime/inference/modules/weekday_state.py` | `importance=Importance.OBSERVE` |
| `scripts/live_tests/066_positive_outcome_boost_live.py` | Live E2E for accepted proposal confidence boost |

### Acceptance criteria

- [x] `OutcomeTracker` accumula `positive_streak` separato da `negative_streak`
- [x] Boost inviato a `ProposalEngine` dopo esattamente K=10 positivi consecutivi
- [x] `positive_streak` azzerato dopo il boost, non dopo il prossimo negativo
- [x] Nessun double-boost per lo stesso positive streak cycle
- [x] `async_boost_confidence` cappato a 1.0
- [x] `WeekdayStateModule` emette `Importance.OBSERVE` (non `SUGGEST`)
- [x] `HouseStateDomain` non consuma segnali OBSERVE (test di regressione)
- [x] Live E2E: proposal accettata con `target_reaction_id`, 10 outcome positivi, boost confidence e reset streak
- [x] Tutti i test esistenti verdi; nuovi test ≥ 12

---

## Phase S — Learning Module Threshold Configurability

**Spec section:** §10.6 (nota "Threshold configurability")
**Goal:** rendere `min_support` e `confidence_threshold` di ogni modulo parametri del costruttore, passati da `entry.options["learning"]`. Nessun cambiamento ai valori di default. Nessuna UI admin per i threshold.
**Depends on:** Phase R (feedback loop operativo — permette di osservare se i valori di default sono adeguati prima di rendere i threshold configurabili).

### Motivation

Famiglie con densità dati molto diversa (es. smart working vs. viaggi frequenti) possono avere slot con supporto insufficiente anche dopo mesi di utilizzo. I threshold configurabili permettono di abbassare `min_support` per ambienti con pochi dati senza cambiare il codice. La policy di auto-tuning (OutcomeTracker-driven) resta fuori scope.

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

1. S1 — Refactor costruttori:
   - `WeekdayStateModule(min_support=10, confidence_threshold=0.40)`
   - `HeatingPreferenceModule(min_support=10, confidence_threshold=0.40)`
   - Keep existing constructor contracts for:
     - `HouseStateInferenceModule(min_support=3, confidence_threshold=0.60)`
     - `LightingPatternModule(min_support=8, confidence_threshold=0.65)`
     - `RoomStateCorrelationModule(min_support=15, confidence_threshold=0.60)`
     - `OccupancyInferenceModule(min_support=10, confidence_threshold=0.70)`
   - Tutti i valori di default invariati rispetto ai valori hardcoded attuali.
2. S2 — Lettura da `learning_config` nel coordinator:
   - Leggere `entry.options.get("learning", {})` e passare i valori ai costruttori.
   - Chiavi di options: `{module_id}_min_support`, `{module_id}_confidence_threshold`.
   - Se la chiave non esiste in options, usare il default del costruttore.
   - Parsing conservativo: valori mancanti, non numerici, `None`, o fuori range vengono ignorati
     e lasciano attivo il default del modulo. Nessuna validazione UI in Phase S.
3. S3 — `diagnostics()` espone i valori effettivi:
   - Ogni modulo aggiunge `min_support` e `confidence_threshold` al proprio `diagnostics()`.
   - Permette di verificare i valori attivi senza accedere alle options.
   - I moduli che già espongono questi valori restano invariati salvo eventuale test di regressione.

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

- [x] Tutti i moduli accettano `min_support` e `confidence_threshold` come parametri costruttore con default invariati
- [x] Il coordinator legge da `entry.options["learning"]` e passa i valori ai costruttori
- [x] `diagnostics()` di ogni modulo espone i valori effettivi di `min_support` e `confidence_threshold`
- [x] Nessun cambio di comportamento osservabile con options di default
- [x] Tutti i test esistenti verdi (nessun test deve cambiare i valori di default) — 1362 passed

---

## Phase T — Learning Signal Analyzers

**Spec section:** §10 (inference engine — proposal-gated signal consumption)
**Goal:** trasformare i segnali statistici maturi (`LightingSignal`, `HouseStateSignal`) in `ReactionProposal` tramite ProposalEngine + review admin. Nessun segnale acquisisce autorità operativa diretta sui domini.
**Depends on:** Phase P (learning modules attivi e osservabili), Phase S (threshold configurabili — i segnali devono essere misurabili prima di promuoverli a proposal).

### Motivation

`LightingPatternModule` e `RoomStateCorrelationModule` producono segnali osservabili da P4a. Prima di dare loro potere runtime, i segnali passano dal gate umano: l'analyzer emette una `ReactionProposal`, l'admin approva o rifiuta, solo allora diventa regola operativa.

### Working slices

1. T1 — LightingPatternAnalyzer:
   - Nuovo `IBehaviorAnalyzer` in `runtime/analyzers/`.
   - Per ogni `LightingSignal` con confidence stabile, verifica se esiste già una regola configurata per quella stanza + contesto (`house_state`, `hour_bucket`).
   - Se non esiste, emette `ReactionProposal` con `reaction_type = "context_conditioned_lighting_scene"`.
   - `origin = "learning_derived"`. Nessun effetto runtime finché non approvata.

2. T2 — HouseStateCorrelationAnalyzer:
   - Nuovo `IBehaviorAnalyzer` in `runtime/analyzers/`.
   - Il segnale da `RoomStateCorrelationModule` compete con calendar, work window, manual override: il proposal va emesso solo quando nessuna sorgente a priorità superiore è attiva al momento dell'osservazione.
   - **Prerequisito bloccante:** non esiste un `reaction_type` per "house state rule". T2 richiede o un nuovo tipo o una soluzione alternativa — da decidere prima dell'implementazione.
   - `origin = "learning_derived"`.

### Acceptance criteria

- [ ] `LightingPatternAnalyzer` emette `ReactionProposal` per pattern lighting stabili non già coperti da config admin
- [ ] `HouseStateCorrelationAnalyzer` emette `ReactionProposal` solo in assenza di sorgenti prioritarie attive
- [ ] Nessun segnale statistico influenza domini direttamente — tutto passa da ProposalEngine
- [ ] Tutti i test esistenti verdi

---

## Phase U — Physical Light State Awareness

**Goal:** dare a Heima contezza runtime e storica delle light entity fisicamente accese in HA, indipendentemente dalle scene gestite da Heima. Sblocca la resident card (stato luci live) e le regole anomalia lighting deferred dalla Phase Q.
**Depends on:** Phase A (plugin framework), Phase Q (catalogo anomaly già definito).

### Motivation

`HouseSnapshot.lighting_scenes` registra le decisioni di Heima (scene applicate), non lo stato fisico delle luci. Se un residente accende una luce manualmente e poi esce, Heima non ne ha traccia. Questa fase aggiunge un layer di osservazione "fisica" per tutte le light entity configurate, senza richiedere il meccanismo generale `monitored_entities` (deferred al Plugin API v3+).

### Working slices

1. U1 — `LightingResult.lights_on`:
   - Aggiungere `lights_on: dict[str, bool]` (entity_id → is_on) a `LightingResult`.
   - `LightingDomain.compute()` legge `hass.states.get(entity_id).state == "on"` per tutte
     le light entity configurate (rooms + lighting_rooms). Entity assente in hass.states → False.
   - Solo light entity con domain `light.*` (coerente con `_unique_entities` in semantic_policies).

2. U2 — `CanonicalState` e `InferenceContext`:
   - L'engine scrive `lighting.lights_on` (dict serializzato) in `CanonicalState` dopo la
     valutazione del LightingDomain.
   - `InferenceContext` espone `lights_on: dict[str, bool]` per i learning module.

3. U3 — `HouseSnapshot.lights_physically_on`:
   - Aggiungere `lights_physically_on: dict[str, bool]` a `HouseSnapshot`.
   - `_record_snapshot_if_changed()` popola il campo da `LightingResult.lights_on`.
   - Serializzazione/deserializzazione coerente con gli altri campi dict del snapshot.

4. U4 — Lighting anomaly rules:
   - Implementare `lights_on_unattended` e `lighting_scene_drift` in `AnomalyAnalyzer`,
     ora che `HouseSnapshot.lights_physically_on` e `lighting_scenes` sono disponibili insieme.
   - `lights_on_unattended`: trigger se negli ultimi `window` snapshot, almeno una entry in
     `lights_physically_on` è True AND `anyone_home == False` per `min_observations` snapshot.
     Defaults: window=6, min_observations=3. Severity: warning.
   - `lighting_scene_drift`: confronta la scena recente per `(room_id, house_state, hour_bucket)`
     con la baseline storica da `lighting_scenes`. Diagnostica pura, nessun proposal.
     Defaults: history_window=1000, min_observations=10, recent_observations=3, baseline_ratio=0.65.
   - Rimuovere le note "deferred" da Phase Q e dal dev plan.

### Files to modify

| File | Change |
|---|---|
| `runtime/plugin_contracts.py` o `runtime/domains/lighting.py` | Aggiungere `lights_on` a `LightingResult` |
| `runtime/domains/lighting.py` | Leggere stati fisici in `compute()` |
| `runtime/engine.py` | Scrivere `lighting.lights_on` in `CanonicalState`; popolare `InferenceContext` |
| `runtime/inference/snapshot_store.py` | Aggiungere `lights_physically_on` a `HouseSnapshot` |
| `runtime/analyzers/anomaly.py` | Implementare `lights_on_unattended` e `lighting_scene_drift` |
| `tests/test_anomaly_analyzer_q.py` | Test U4 lighting rules |

### Acceptance criteria

- [ ] `LightingResult.lights_on` riflette stato fisico HA, non le scene Heima
- [ ] `CanonicalState["lighting.lights_on"]` disponibile dopo ogni ciclo di valutazione
- [ ] `HouseSnapshot.lights_physically_on` persistito e leggibile dall'anomaly analyzer
- [ ] `lights_on_unattended` triggera quando almeno una light entity configurata è fisicamente
      accesa mentre `anyone_home == False`
- [ ] `lighting_scene_drift` confronta scene recenti vs baseline storica per slot `(room_id, house_state, hour_bucket)`
- [ ] Tutti i test esistenti verdi; nuovi test ≥ 2 (una per regola lighting)

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

## Updating this document

After completing each phase:

1. Update the phase row in the [Phase overview](#phase-overview) table: `NOT STARTED` → `IN PROGRESS` → `DONE`.
2. Update [Current State](#current-state): set `Last completed phase`, `Active phase`, `Next action`.
3. Add any new open blockers or decisions to [Current State](#current-state).
4. Commit this file together with the phase code.

Do not rewrite completed phase sections — they are the historical record.
If a spec change causes a phase to be revised, note it in the relevant phase section under a `**Spec revision note:**` heading and update the spec file.
