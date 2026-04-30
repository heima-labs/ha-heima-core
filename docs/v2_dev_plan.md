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
| 9 | All persistent stores use HA `Store`. Keys: `heima_snapshots`, `heima_inference_approvals`. |
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
| D | InferenceEngine v2 (base) | `NOT STARTED` | A |
| E | OutcomeTracker + Feedback Loop | `NOT STARTED` | D |
| F | House State Learning | `NOT STARTED` | D, E |
| G | ActivityDomain | `NOT STARTED` | A, D |
| H | Activity Inference and Learning | `NOT STARTED` | D, F, G |
| I | Event-Driven Trigger | `NOT STARTED` | G |

---

## Current State

**Last completed phase:** Phase C — IInvariantCheck.
**Active phase:** None. Next phase must be agreed before implementation.
**Branch:** `feat/v2` — created from `main`.
**Next action:**

Review Phase C results and agree the next slice before implementation.

### Current Working Notes

- Current slice: Phase C — complete.
- Status: invariant contracts, built-in checks, debounce state machine, and pre-Apply engine
  wiring are implemented.
- Files read:
  - `custom_components/heima/runtime/engine.py`
  - `custom_components/heima/coordinator.py`
  - `custom_components/heima/runtime/domains/lighting.py`
  - `custom_components/heima/runtime/domains/heating.py`
  - `custom_components/heima/runtime/domains/security.py`
  - `custom_components/heima/runtime/contracts.py`
  - `custom_components/heima/runtime/snapshot.py`
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
- Next concrete step: agree the next phase/slice before writing more runtime code.
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
| `runtime/inference/approval_store.py` | `ApprovalStore` (stub for Phase F) | §10.9 |
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

- [ ] `SnapshotStore` persists to HA Store key `heima_snapshots`
- [ ] `_record_snapshot_if_changed()` only writes on state change (deduplication)
- [ ] `WeekdayStateModule` and `HeatingPreferenceModule` return typed signals
- [ ] `ILearningModule.infer()` completes in < 1ms (verified via test timing)
- [ ] All 660 tests pass

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

### Acceptance criteria

- [ ] Positive outcome (entity state matches expected within timeout) → recorded
- [ ] Negative outcome (timeout, no match) → degradation proposal emitted
- [ ] `check_pending()` is synchronous and completes in O(pending count)
- [ ] Tests: positive outcome, negative outcome, timeout policy
- [ ] All 660 tests pass

---

## Phase F — House State Learning

**Spec section:** §13 (House State Learning), §10.9
**Goal:** `HouseStateInferenceModule`, user-approval gate.
**Depends on:** Phases D and E complete.

### New files to create

| File | What to implement | Spec ref |
|---|---|---|
| `runtime/inference/modules/house_state_inference.py` | `HouseStateInferenceModule` | §13, §10.6 |

### Files to modify

| File | Change |
|---|---|
| `runtime/inference/approval_store.py` | Full implementation (was stub in Phase D) | §10.9 |
| `runtime/domains/house_state.py` | Consume `HouseStateSignal`; approval gate | §10.9 |
| `config_flow/` | `house_state_learned_context` proposal type review screen |

### Acceptance criteria

- [ ] `HouseStateInferenceModule` emits `HouseStateSignal` only for approved patterns
- [ ] `ApprovalStore` persists to HA Store key `heima_inference_approvals`
- [ ] Unapproved signals are ignored by `HouseStateDomain`
- [ ] User approval/rejection survives HA restart
- [ ] All 660 tests pass

---

## Phase G — ActivityDomain

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
| `config_flow/` | Add `activity_bindings` section (maps detector names to HA entity IDs) | §7.3 |

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

- [ ] All 5 hysteresis transitions tested
- [ ] `ActivityResult.active` contains only phase=ACTIVE detectors
- [ ] `ActivityResult.candidates` contains only phase=CANDIDATE detectors
- [ ] `CanonicalState` keys written correctly each cycle
- [ ] `InferenceContext.previous_activity_names` reads from CanonicalState (one-cycle lag)
- [ ] `HouseSnapshot.detected_activities` populated
- [ ] All 660 existing tests pass; new tests ≥ 20

---

## Phase H — Activity Inference and Learning

**Spec section:** §7.7 (ActivityProposal), §10.5 (ActivityInferenceModule)
**Goal:** composite activity discovery; `ActivityAnalyzer`; user-approved `ActivitySignal`.
**Depends on:** Phases D, F, and G complete.

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

### Acceptance criteria

- [ ] `ActivityAnalyzer` does not emit `ActivityProposal` with < 10 co-occurrences or < 3 distinct days
- [ ] `ActivityInferenceModule.infer()` returns `[]` until at least one `ActivityProposal` approved
- [ ] Approved composite activity appears in `ActivityResult.active` when signal fired
- [ ] Approval survives HA restart (via `ApprovalStore`)
- [ ] All 660 tests pass; new tests ≥ 15

---

## Phase I — Event-Driven Trigger

**Spec section:** §11 (Event-Driven Trigger)
**Goal:** HA `state_changed`-driven evaluation, per-class debounce, 300s periodic fallback.
**Depends on:** Phase G (power threshold binding config).

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

## Updating this document

After completing each phase:

1. Update the phase row in the [Phase overview](#phase-overview) table: `NOT STARTED` → `IN PROGRESS` → `DONE`.
2. Update [Current State](#current-state): set `Last completed phase`, `Active phase`, `Next action`.
3. Add any new open blockers or decisions to [Current State](#current-state).
4. Commit this file together with the phase code.

Do not rewrite completed phase sections — they are the historical record.
If a spec change causes a phase to be revised, note it in the relevant phase section under a `**Spec revision note:**` heading and update the spec file.
