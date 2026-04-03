# House State Domain Spec

**Status:** Active v1.x house-state contract with remaining refinement targets  
**Implementation status:** Largely implemented on `main`; remaining items are incremental refinements  
**Last reviewed:** 2026-04-03

---

## 1. Purpose

`house_state` is Heima's canonical interpretation of the current global home context.

It must:
- remain simple and explainable to the user
- stay stable under noisy or short-lived signals
- support explicit overrides and explicit modes
- infer meaningful states from behaviorally relevant evidence, not only from direct helper booleans

This spec defines the current candidate/hysteresis-driven `house_state` model on `main`,
plus the remaining refinement targets that may still land in later v1.x work.

---

## 2. Canonical Outputs

Canonical entities remain:
- `sensor.heima_house_state`
- `sensor.heima_house_state_reason`

Additional diagnostic entities currently implemented:
- `sensor.heima_house_state_path`
- `sensor.heima_house_state_active_candidates`
- `sensor.heima_house_state_pending_candidate`
- `sensor.heima_house_state_pending_remaining_s`

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

This replaces the earlier direct mapping:
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

### 5.4 Additional configurable bindings

The following bindings are part of the current v1.x contract:

- `media_active_entities`
  - one or more entities that indicate active media usage
  - normalized as a boolean set
- `sleep_charging_entities`
  - zero or more boolean-like entities that indicate "device charging" evidence
  - counted as corroboration inputs for `sleep_candidate`
- `workday_entity`
  - optional explicit workday indicator when calendar is not sufficient
- `sleep_requires_media_off`
  - bool, default `true`
- `sleep_charging_min_count`
  - optional integer corroboration threshold

These bindings are additive. Existing configurations remain backward compatible.

---

## 6. Candidate Definitions

### 6.1 `sleep_candidate`

Target meaning:
- "the house plausibly entered a sleeping phase"

Default built-in rule:
- `anyone_home == on`
- `sleep_window == on`
- if `sleep_requires_media_off == true`, `media_active == off`
- if `sleep_charging_min_count` is configured, active count over `sleep_charging_entities` must be `>= threshold`

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

The home substate layer uses explicit enter/exit thresholds. This behavior is already implemented
on `main`.

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

Current v1.x implementation already exposes most of this contract through two surfaces:

1. diagnostics payload
- `house_signals_trace`
- `candidate_trace`
- `candidate_summary`
- `timers`
- `resolution_trace`
- `override`

2. canonical sensor attributes and helper sensors
- `sensor.heima_house_state.attributes["resolution_trace"]`
- `sensor.heima_house_state.attributes["candidate_summary"]`
- `sensor.heima_house_state_reason.attributes["resolution_trace"]`
- `sensor.heima_house_state_reason.attributes["candidate_summary"]`
- `sensor.heima_house_state_path`
- `sensor.heima_house_state_active_candidates`
- `sensor.heima_house_state_pending_candidate`
- `sensor.heima_house_state_pending_remaining_s`

Interpretation rule:
- the helper sensors are an operability surface for dashboards and quick inspection
- the diagnostics payload remains the deeper source of truth for candidate and signal traces

For bounded operability surfaces in v1.x, the system SHOULD also expose a compact summary that
helps an admin answer quickly:
- what state is currently active
- why it is active
- whether the result is pending, retained, or calendar-influenced

That compact summary may include fields equivalent to:
- `state`
- `reason`
- `resolution_path`
- `active_candidates`
- `pending_candidate`
- `pending_remaining_s`
- `calendar_context`

The compact summary is intended for diagnostics CLI, dashboards, and options-flow overviews.
It does not replace the deeper `resolution_trace` / `candidate_trace` payload.

---

## 12. Backward Compatibility

The canonical entities remain unchanged:
- `sensor.heima_house_state`
- `sensor.heima_house_state_reason`

Existing options must continue to work:
- if only legacy direct bindings are configured, the candidate engine still derives usable states
- if candidate-support bindings are absent, defaults apply and the system remains functional

This means:
- old installations keep working
- new installations can progressively adopt richer house-state inference

---

## 13. Remaining Refinement Targets

Most of the base model described above is already implemented on `main`.

The remaining useful refinement targets are:

### R1
- continue refining candidate heuristics without changing the canonical top-level state set

### R2
- improve operability wording and diagnostics where helpful

### R3
- keep strengthening the calendar-aware context that future heating logic will consume

---

## 14. Non-goals

This spec does not:
- introduce probabilistic house-state inference
- make `house_state` directly learned from user behavior
- remove explicit overrides
- depend on current-cycle outputs of other domains

Those remain future directions outside the current v1.x contract.
