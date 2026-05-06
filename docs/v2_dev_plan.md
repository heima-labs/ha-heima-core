# Heima v2.1 — Development Plan

**Spec:** `docs/specs/heima_v2_spec.md` (v2.1.0-draft)
**Branch:** `feat/v2` (to be created from `main`)
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
| I | Activity Inference and Learning | `NOT STARTED` | D, H, F |
| J | Event-Driven Trigger | `NOT STARTED` | F |
| K | Installer alert channel + health entity | `NOT STARTED` | C |
| L | Auto-discovery config flow | `NOT STARTED` | — |
| M | Installation validation | `NOT STARTED` | L |

---

## Current State

**Last completed phases:** Phase E — OutcomeTracker + Feedback Loop; Phase F — ActivityDomain; Phase G — Role model + product constraints; Phase H — House State Learning.
**Active phase:** none.
**Branch:** `feat/v2` — created from `main`.
**Next action:**

Discuss and plan Phase I — Activity Inference and Learning.

### Current Working Notes

- Current slice: Phase H6 — complete.
- Status: `HouseStateSignal` is passed from the engine to `HouseStateDomain`; the domain consumes
  only approved `house_state_inference` signals with confidence >= 0.60, after manual override,
  vacation, and everyone-away hard-state guards. Phase H is complete.
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
- Next concrete step: discuss Phase I scope and slice plan before implementation.
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

- [ ] `ActivityAnalyzer` does not emit `ActivityProposal` with < 10 co-occurrences or < 3 distinct days
- [ ] `ActivityInferenceModule.infer()` returns `[]` until at least one `ActivityProposal` approved
- [ ] Approved composite activity appears in `ActivityResult.active` when signal fired
- [ ] Approval survives HA restart (via `ApprovalStore`) with `approved_by` populated
- [ ] All existing tests pass; new tests ≥ 15

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

- [ ] State change on a classified entity triggers evaluation within debounce window
- [ ] Re-entrant evaluation is skipped (guard active)
- [ ] Periodic 300s fallback fires even with no state changes
- [ ] Environmental sensors do not trigger evaluation
- [ ] All 660 tests pass; new tests cover debounce timing and re-entrancy guard

---

## Phase K — Installer alert channel + health entity

**Spec section:** TBD — add to `heima_v2_spec.md`
**Goal:** Route anomaly/invariant violation alerts to installer HA user; expose `sensor.heima_health` for remote monitoring.
**Depends on:** Phase C (IInvariantCheck).

### Files to modify

| File | Change |
|---|---|
| `coordinator.py` | Route `anomaly.*` events to installer notification channel (HA admin user) |
| `entities/` | Add `sensor.heima_health` with state (`ok` / `degraded` / `error`) and diagnostic attributes |
| `services.yaml` | Add `heima.run_diagnostics` service returning structured diagnostic payload |

### Acceptance criteria

- [ ] Anomaly/invariant violation events routed to installer channel, not resident channel
- [ ] `sensor.heima_health` exposed with overall state and `last_anomaly` attribute
- [ ] `heima.run_diagnostics` service call returns structured diagnostic payload
- [ ] All existing tests pass

---

## Phase L — Auto-discovery config flow

**Spec section:** TBD — add to `heima_v2_spec.md`
**Goal:** Scan HA entity registry using device classes to suggest bindings; installer confirms in options flow.
**Depends on:** —

### Discovery strategy

Uses HA device classes — no ML, no NLP:

| HA device class | Heima binding candidate |
|---|---|
| `motion` | motion sensor |
| `door`, `window` | door/window security sensor |
| `occupancy` | presence sensor |
| `humidity` | shower detector |
| `power` | activity detector (stove, oven, appliances) |
| `media_player` | tv/pc detector |

### Files to modify

| File | Change |
|---|---|
| `config_flow/` | Add auto-discovery step: scan entities, group by device class, present suggestions |
| `coordinator.py` | Add `async_discover_entities()` helper |

### Acceptance criteria

- [ ] Discovery step presented before manual binding in options flow
- [ ] Suggestions grouped by functional category (presence, security, activity detectors)
- [ ] Installer can accept all, reject all, or selectively confirm
- [ ] Discovery result feeds into existing binding normalization
- [ ] All existing tests pass

---

## Phase M — Installation validation

**Spec section:** TBD — add to `heima_v2_spec.md`
**Goal:** After config, report what Heima can and cannot do with the current binding set.
**Depends on:** Phase L.

### Validation report covers

- Activities detectable with current bindings vs. activities missing required sensors
- Invariant checks active vs. inactive (missing required entities)
- Learning modules with sufficient data vs. insufficient data

### Files to modify

| File | Change |
|---|---|
| `config_flow/` | Add validation summary step at end of options flow |
| `coordinator.py` | Add `async_validate_config() -> ValidationReport` |

### Acceptance criteria

- [ ] Validation report generated after config save
- [ ] Missing bindings listed with human-readable description of what is unavailable
- [ ] Report accessible via `sensor.heima_health` attributes and via `heima.run_diagnostics`
- [ ] All existing tests pass

---

## Updating this document

After completing each phase:

1. Update the phase row in the [Phase overview](#phase-overview) table: `NOT STARTED` → `IN PROGRESS` → `DONE`.
2. Update [Current State](#current-state): set `Last completed phase`, `Active phase`, `Next action`.
3. Add any new open blockers or decisions to [Current State](#current-state).
4. Commit this file together with the phase code.

Do not rewrite completed phase sections — they are the historical record.
If a spec change causes a phase to be revised, note it in the relevant phase section under a `**Spec revision note:**` heading and update the spec file.
