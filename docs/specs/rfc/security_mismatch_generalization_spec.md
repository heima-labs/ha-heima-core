# Heima — Security Mismatch Generalization Spec (v1.1)

**Status:** Implemented on `main`  
**Scope:** Event taxonomy and migration only (no behavior-policy changes)

## 1. Goal

Generalize security inconsistency events under one canonical event type:

- `security.mismatch`

while still covering the already implemented case:

- `security.armed_away_but_home`

without breaking existing automations.

Current runtime status:
- canonical `security.mismatch` is emitted on `main`
- compatibility modes `explicit_only | generic_only | dual_emit` are implemented
- default remains `explicit_only`

## 2. Event Model

### 2.1 Canonical Event

- `type`: `security.mismatch`
- `key`: `security.mismatch.<subtype>`
- `severity`: `warn`

Required context fields:

- `subtype` (string, stable id)
- `policy` (`off|smart|strict`)
- `persist_s` (int)
- `evidence` (object, normalized)
- `details` (object, subtype-specific payload)

### 2.2 v1.1 Subtypes

Initial subtype set:

- `armed_away_but_home`

Mapping of current runtime event:

- `security.armed_away_but_home` -> `security.mismatch` with `subtype=armed_away_but_home`

## 3. Compatibility and Migration

To avoid breaking existing automations, v1.1 introduces an emission mode:

- `security_mismatch_event_mode`
  - `explicit_only` (default in v1.1 and current `main`)
  - `generic_only`
  - `dual_emit`

Semantics:

- `explicit_only`: emit current specific event(s) only.
- `generic_only`: emit only `security.mismatch`.
- `dual_emit`: emit both generic and specific events in the same evaluation cycle.

Notes:

- `dual_emit` can produce duplicate notifications if routes target both forms.
- Default remains `explicit_only` until a major-version switch.

## 4. Taxonomy Rules

- New security mismatch scenarios MUST be introduced as:
  - `security.mismatch` + new `subtype`
- Specific legacy events are allowed only for backward compatibility.
- Event category remains `security`.

## 5. Payload Standardization

For `subtype=armed_away_but_home`, canonical payload mapping:

- `evidence.has_room_evidence`
- `evidence.has_anonymous_evidence`
- `evidence.occupied_rooms`
- `details.security_state`
- `details.security_observation_reason`
- `details.people_home_list`

This keeps a stable top-level schema while preserving current diagnostics.

## 6. Deprecation Plan

Phase A (v1.1):

- Add mode switch. Implemented on `main`.
- Keep default `explicit_only`. Implemented on `main`.
- Document generic event and subtype mapping. Implemented on `main`.

Phase B (v1.x later):

- Encourage `generic_only` for new installs.
- Mark specific security mismatch events as legacy.

Phase C (v2):

- Default to `generic_only`.
- Remove legacy specific mismatch events after one full compatibility cycle.

## 7. Out of Scope

- No change to mismatch detection policy (`smart|strict|off`) logic.
- No change to corroboration logic or persistence timers.
- No change to notification routing internals besides event type consumption.

## 8. Verification Notes

Current runtime behavior is covered by:
- unit coverage in `tests/test_security_mismatch_policy.py`
- live validation in `scripts/live_tests/040_security_mismatch_runtime.py`

The live test asserts:
- `explicit_only` emits only the specific event
- `generic_only` emits only `security.mismatch`
- `dual_emit` emits both forms on the HA event bus
