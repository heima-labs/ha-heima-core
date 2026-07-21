# Runtime State Flow Audit - 2026-07-21

Scope: runtime state that is derived from events or in-memory transitions and can become stale if
the corresponding clear/reconcile path is missing.

## Summary

| Area | Owner | Source of truth | Clear/reconcile path | Current risk | Coverage |
| --- | --- | --- | --- | --- | --- |
| Health invariant alert | `HeimaCoordinator` + `HeimaEngine` | Engine invariant loop unresolved state | Coordinator reconciles stored alert against `unresolved_invariant_check_ids()` before publishing health | Low after fix | `tests/test_health_k.py`, `tests/test_invariant_checks.py` |
| Last anomaly | `HeimaCoordinator` | Last emitted anomaly event | Invariant anomalies clear with invariant reconciliation; non-invariant critical anomalies have no generic resolution model | Medium, explicit by design gap | `tests/test_health_k.py` |
| Event sensor | `EventsDomain` | Last successfully emitted event | No clear; it is an event log pointer, not current state | Low if callers do not treat it as state | `tests/test_event_category_gating.py`, `tests/test_services_notify_event.py` |
| Manual hold | `ManualHoldManager` | Explicit helper state, external state changes, pending apply provenance | Expiry, helper-off sync, service clear, camera disarmed-to-armed reset | Low | `tests/test_manual_hold_manager.py`, `tests/test_engine_lighting_runtime.py` |
| Runtime confirmations | `RuntimeConfirmationController` | In-memory pending request registry | First-writer-wins claim, timeout, dismiss/approve, shutdown cancellation | Low for runtime; restart-safe persistence is intentionally out of scope | `tests/test_runtime_confirmation_controller.py`, `tests/test_runtime_confirmation.py` |
| Outcome tracking | `OutcomeTracker` | Pending reaction verification records | Positive event match or timeout; reset API | Medium: repeated firing replaces pending verification for same reaction | `tests/test_outcome_tracker_e3.py`, `tests/test_outcome_tracker_e4.py` |
| House state sensor | `HouseStateDomain` + engine snapshot | Current evaluation snapshot | Recomputed on each evaluation and state-change fallback | Low | Existing inference/runtime tests |
| Reaction diagnostics | `HeimaEngine` | Reaction objects and configured metadata | Rebuilt on options reload and synced after mute/apply | Low | `tests/test_observability.py`, reaction tests |

## Fix Verified In This Audit

The previous stale-health bug happened because health depended on a stored
`_last_invariant_violation` and only cleared when `anomaly.resolved` was observed through
`heima_last_event`. That event can be missed, suppressed, or not reconstructed after a restart.

The corrected flow is:

1. The engine exposes `active_invariant_check_ids()` for checks that emitted after debounce.
2. The engine exposes `unresolved_invariant_check_ids()` for checks whose current condition has not
   cleared yet, including checks still inside their debounce window.
3. The coordinator reconciles `_last_invariant_violation` against unresolved checks before
   publishing `sensor.heima_health`.
4. If the stored invariant `check_id` is no longer unresolved, both `_last_invariant_violation` and
   matching `_last_anomaly` are cleared.

This makes health depend on the current invariant state, not only on a resolution event.

## Remaining Risks

### Non-invariant critical anomaly lifetime

Critical anomalies that do not carry a `context.check_id` still degrade health and currently do not
have a generic resolution policy. This is different from invariant violations: invariants can be
re-evaluated directly against current runtime state.

Recommendation: define per-anomaly resolution semantics before adding more critical non-invariant
anomaly types. Options are explicit resolved events, TTL-based expiry, or analyzer-owned current
state reconciliation.

### Outcome tracker replacement semantics

`OutcomeTracker` keeps one pending verification per `reaction_id`. A new fire for the same reaction
replaces the previous pending verification. This avoids unbounded growth, but it can hide repeated
failures for fast recurring reactions.

Recommendation: keep current behavior unless a reaction family can fire faster than its outcome
window. If that happens, use occurrence-scoped pending keys.

### Runtime confirmations after restart

Pending runtime confirmations are intentionally in-memory. A restart cancels the local registry and
timeout handles, while already delivered mobile notifications can still be tapped later. The
controller handles those responses as stale/no-op.

Recommendation: keep this behavior for the current MVP. Persisting executable runtime requests
would require a stronger restart-safe execution contract.

## Regression Commands

```bash
.venv/bin/python -m pytest tests/test_health_k.py tests/test_invariant_checks.py tests/test_manual_hold_manager.py tests/test_runtime_confirmation_controller.py tests/test_outcome_tracker_e3.py tests/test_outcome_tracker_e4.py -q
.venv/bin/python -m pytest tests/test_engine_lighting_runtime.py tests/test_reaction_framework.py tests/test_camera_privacy_policy_materializer.py tests/test_runtime_confirmation.py tests/test_runtime_confirmation_promotion_stats.py tests/test_observability.py tests/test_event_category_gating.py -q
.venv/bin/ruff check custom_components/heima/coordinator.py custom_components/heima/runtime/engine.py tests/test_health_k.py tests/test_invariant_checks.py
```

## Verification Infrastructure

Added after the audit:

- `tests/test_runtime_state_transitions.py` covers explicit transition sequences for health
  reconciliation, manual hold ownership/release, and runtime confirmation first-writer-wins.
- `scripts/runtime_state_replay.py` replays exported diagnostics or observability JSON files and
  flags stale runtime state. It accepts direct files, directories, and glob patterns for batch
  replay.
- `tests/test_runtime_state_replay.py` covers replay rules with minimized fixtures.
- `scripts/live_tests/082_runtime_state_replay_live.py` runs the same replay checks against live HA
  diagnostics, `sensor.heima_health`, and a combined health+runtime payload.
- `scripts/live_tests/083_health_invariant_clear_active_live.py` actively forces
  `security_presence_mismatch`, waits for health to become `degraded`, clears the condition, and
  verifies health returns to `ok`.

Additional commands:

```bash
.venv/bin/python -m pytest tests/test_runtime_state_replay.py tests/test_runtime_state_transitions.py -q
scripts/runtime_state_replay.py --summary 'heima-observability*.json'
./scripts/check_all_live.sh --tier diagnostic
```

The active live test requires HA to have loaded the current Python modules. Updating files on a
mounted volume is not enough for code changes in already imported modules; restart HA before using
`083_health_invariant_clear_active_live.py` to validate a new runtime fix.
