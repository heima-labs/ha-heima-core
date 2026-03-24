# House State Domain Spec

**Status:** Target vNext for v1.x evolution  
**Implementation status:** Not yet implemented as specified here  
**Last reviewed:** 2026-03-24

---

## 1. Purpose

`house_state` is Heima's canonical interpretation of the current global home context.

It must:
- remain simple and explainable to the user
- stay stable under noisy or short-lived signals
- support explicit overrides and explicit modes
- infer meaningful states from behaviorally relevant evidence, not only from direct helper booleans

This spec defines the **target model** for `house_state` evolution beyond the current
direct-signal v1 implementation.

---

## 2. Canonical Outputs

Canonical entities remain:
- `sensor.heima_house_state`
- `sensor.heima_house_state_reason`

Allowed values remain:
- `vacation`
- `away`
- `sleeping`
- `guest`
- `working`
- `relax`
- `home`

No new canonical top-level house-state values are introduced by this spec.

---

## 3. Resolution Model

House-state resolution is split into two layers:

1. **Hard state layer**
- explicit override
- explicit vacation / guest
- presence-derived away

2. **Home substate layer**
- resolves only when someone is home and no harder state is active
- chooses among:
  - `sleeping`
  - `relax`
  - `working`
  - `home`

The home substate layer is **candidate-based** and **hysteresis-driven**.

This replaces the current direct mapping:
- `sleep_window -> sleeping`
- `relax_mode -> relax`
- `work_window -> working`

with:
- candidate inference
- enter/exit thresholds
- state persistence across cycles

---

## 4. Resolution Priority

Final effective resolution order:

1. `manual_override`
2. `vacation`
3. `guest`
4. `away`
5. `sleeping`
6. `relax`
7. `working`
8. `home`

Interpretation:
- `vacation`, `guest`, and `away` are hard states
- `sleeping`, `relax`, `working`, and `home` belong to the home substate machine

---

## 5. Inputs

### 5.1 Hard inputs

- `anyone_home`
- `vacation_mode`
- `guest_mode`
- runtime-only `house_state_override`

### 5.2 Candidate inputs

Candidate inference may use:

- `sleep_window`
- `relax_mode`
- `work_window`
- calendar result (`vacation`, `office`, `wfh`)
- `media_active`
- optional workday evidence
- optional charging evidence
- current effective `house_state`
- previous-cycle canonical state and timestamps

### 5.3 Current configurable bindings

Existing bindings remain valid:
- `vacation_mode_entity`
- `guest_mode_entity`
- `sleep_window_entity`
- `relax_mode_entity`
- `work_window_entity`

### 5.4 New planned bindings

This spec introduces the following planned additions:

- `media_active_entities`
  - one or more entities that indicate active media usage
  - normalized as a boolean set
- `workday_entity`
  - optional explicit workday indicator when calendar is not sufficient
- `sleep_requires_media_off`
  - bool, default `true`
- `sleep_charging_min_count`
  - optional integer corroboration threshold

These bindings are additive. Existing configurations must remain backward compatible.

---

## 6. Candidate Definitions

### 6.1 `sleep_candidate`

Target meaning:
- "the house plausibly entered a sleeping phase"

Default built-in rule:
- `anyone_home == on`
- `sleep_window == on`
- if `sleep_requires_media_off == true`, `media_active == off`
- if `sleep_charging_min_count` is configured, charging-home count must be `>= threshold`

Default interpretation:
- `sleep_charging_min_count = None`
- charging evidence is optional corroboration, not a mandatory requirement unless explicitly configured

### 6.2 `wake_candidate`

Target meaning:
- "the house plausibly left the sleeping phase"

Default built-in rule:
- `sleep_window == off`
  OR
- `media_active == on`

### 6.3 `work_candidate`

Target meaning:
- "the house is plausibly in a working-from-home phase"

Default built-in rule:
- `anyone_home == on`
- `work_window == on`
- effective workday evidence is positive
- no harder home substate is active

Effective workday evidence is resolved as:

1. if calendar says `office` today -> `false`
2. else if calendar says `wfh` today -> `true`
3. else if `workday_entity` is configured -> normalized boolean value
4. else -> `true`

This preserves usefulness even without explicit workday configuration.

### 6.4 `relax_candidate`

Target meaning:
- "the house is plausibly in a relax / media phase"

Default built-in rule:
- `anyone_home == on`
- `sleeping` is not effective
- one of:
  - `relax_mode == on`
  - `media_active == on`

`relax_mode` is considered stronger evidence than passive media activity.
Explicit `relax_mode` may activate `relax` immediately, while passive media-based relax
must satisfy the configured enter timer.

---

## 7. Hysteresis and Timers

The home substate layer uses explicit enter/exit thresholds.

Default timers:
- `sleep_enter_min = 10`
- `sleep_exit_min = 2`
- `work_enter_min = 5`
- `relax_enter_min = 2`
- `relax_exit_min = 10`

Notes:
- `sleeping` is conservative on entry and fast on exit
- `relax` is fast on entry and sticky on exit
- `working` requires persistence before activation

No separate `work_exit_min` is required in the initial version of this spec:
- if `work_candidate` drops and no stronger substate applies, state returns to `home`

This keeps the model close to the original house-state resolver while avoiding unnecessary complexity.

---

## 8. Home Substate Resolution

This logic applies only when:
- no manual override is active
- `vacation_mode == off`
- `guest_mode == off`
- `anyone_home == on`

Let `current` be the current effective house state.

### 8.1 Sleeping

Rules:
- if `current == sleeping` and `wake_candidate` has not persisted for `sleep_exit_min`, remain `sleeping`
- else if `sleep_candidate` has persisted for `sleep_enter_min`, become `sleeping`

### 8.2 Relax

Rules:
- if `sleeping` is active, `relax` is suppressed
- if `current == relax`:
  - remain `relax` while `relax_candidate == on`
  - remain `relax` while `relax_candidate == off` but the off duration is less than `relax_exit_min`
- else if:
  - explicit `relax_mode == on`, `relax` activates immediately
  - passive `media_active`-based relax requires `relax_enter_min`

### 8.3 Working

Rules:
- if neither `sleeping` nor `relax` is active
- and `work_candidate` has persisted for `work_enter_min`
- then effective state becomes `working`

### 8.4 Home fallback

If none of the above substates applies:
- effective home substate is `home`

---

## 9. Final Resolution Algorithm

Normative algorithm:

1. if `house_state_override` is active:
   - use override
   - reason = `manual_override:<state>`
2. else if `vacation_mode == on`:
   - `vacation`
   - reason = `vacation_mode`
3. else if `guest_mode == on`:
   - `guest`
   - reason = `guest_mode`
4. else if `anyone_home == off`:
   - `away`
   - reason = `no_presence`
5. else:
   - resolve home substate machine
   - reason reflects winning candidate / persistence / fallback

---

## 10. Reason Semantics

`heima_house_state_reason` must remain explicit and user-comprehensible.

Allowed reason families:
- `manual_override:<state>`
- `vacation_mode`
- `guest_mode`
- `no_presence`
- `sleep_candidate_confirmed`
- `sleep_sticky_until_wake`
- `wake_candidate_confirmed`
- `relax_explicit_signal`
- `relax_candidate_confirmed`
- `relax_sticky_exit_guard`
- `work_candidate_confirmed`
- `default`

The exact string set may evolve, but reasons must distinguish:
- hard override
- candidate confirmation
- sticky retention
- plain fallback

---

## 11. Diagnostics Contract

`engine.house_state` diagnostics must be extended to expose:

- hard signals trace
- candidate evaluations
- candidate durations
- active thresholds
- current substate machine branch
- whether state was retained due to hysteresis
- whether calendar overrode workday/vacation evidence

Suggested shape:

```json
{
  "house_signals_trace": {...},
  "candidate_trace": {
    "sleep_candidate": {...},
    "wake_candidate": {...},
    "work_candidate": {...},
    "relax_candidate": {...}
  },
  "timers": {
    "sleep_enter_min": 10,
    "sleep_exit_min": 2,
    "work_enter_min": 5,
    "relax_enter_min": 2,
    "relax_exit_min": 10
  },
  "resolution_trace": {
    "current_state_before": "home",
    "resolved_state_after": "relax",
    "winning_reason": "relax_candidate_confirmed",
    "sticky_retention": false
  },
  "override": {...}
}
```

---

## 12. Backward Compatibility

The canonical entities remain unchanged:
- `sensor.heima_house_state`
- `sensor.heima_house_state_reason`

Existing options must continue to work:
- if only legacy direct bindings are configured, the candidate engine must still derive usable states
- if new candidate-support bindings are absent, defaults apply and the system remains functional

This means:
- old installations keep working
- new installations can progressively adopt richer house-state inference

---

## 13. Implementation Phasing

This spec is intentionally broader than the first implementation slice.

Recommended implementation phases:

### Phase A
- keep existing hard states
- introduce candidate traces
- implement hysteresis only on top of existing `sleep_window`, `relax_mode`, `work_window`

### Phase B
- add `media_active_entities`
- derive `relax_candidate` from media activity
- derive `wake_candidate` from media activity

### Phase C
- add `workday_entity` + calendar-aware work candidate
- add optional sleep corroboration (`media_off`, charging threshold)

### Phase D
- refine reasons, diagnostics, and learning/event visibility

---

## 14. Non-goals

This spec does not:
- introduce probabilistic house-state inference
- make `house_state` directly learned from user behavior
- remove explicit overrides
- depend on current-cycle outputs of other domains

Those remain future directions outside this target vNext contract.
