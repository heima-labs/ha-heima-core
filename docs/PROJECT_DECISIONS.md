# Project Decisions

This file records temporary or transitional product/architecture decisions that are intentional today and expected to be revisited later.

## 2026-03-09 — Reactive Behavior Engine replaces apply_filter use case in behaviors

Decision:
- Split the behavior concept into two orthogonal abstractions:
  - `HeimaBehavior` (SPEC v1.1): passive observer, `on_snapshot` only. Use for diagnostics and
    snapshot history logging. `apply_filter` remains an extension point but is not used for
    concrete built-in behaviors.
  - `HeimaReaction` (Reactive SPEC v1): active contributor, `evaluate(history) -> list[ApplyStep]`.
    Use for temporal pattern detection and pre-conditioning.

Reason:
- `apply_filter` on `HeimaBehavior` is fundamentally unsafe without a `tags` field on `ApplyStep`:
  a behavior cannot distinguish auto-generated steps from user-intent steps (fake presence,
  vacation curve) without this context.
- `HeimaReaction` solves a different problem: it adds steps based on temporal patterns rather
  than blocking existing ones.
- The constraint layer handles blocking correctly and does not need behavior delegation.

Current rule:
- `HeimaBehavior.apply_filter` is an advanced extension point; not used in built-in code.
- All step blocking goes through `_apply_filter` (engine) + `_compute_active_constraints`.
- All new temporal/adaptive logic uses `HeimaReaction`.

Future follow-up:
- If `apply_filter` behaviors become necessary, add `tags: frozenset[str]` to `ApplyStep` first.

## 2026-03-09 — HeimaReaction is level-triggered and passes through the constraint layer

Decision:
- `HeimaReaction.evaluate()` is level-triggered: fires on every evaluation cycle where the
  pattern is active.
- Reaction steps are merged into the apply plan before `_apply_filter`, subject to the same
  security constraints as domain steps.

Reason:
- Level-triggered matches "ensure this state is maintained" use cases (eco heating while away).
  Domain rate-limiting prevents spam.
- Treating reaction steps equally with domain steps preserves the constraint layer invariant.

Current rule:
- No reaction can bypass `security.armed_away` or any future constraint.
- Reaction steps are tagged `source="reaction:{id}"` for traceability.

## 2026-03-09 — ILearningBackend uses explicit override signaling

Decision:
- `NaiveLearningBackend.record_override(reaction_id)` must be called explicitly by the caller.
  The backend does not read HA state to detect overrides automatically.

Reason:
- Automatic detection would couple the backend to the runtime, making it hard to test.
- Explicit signaling keeps the backend a pure data structure.

Current rule:
- `record_override()` is the only override signal path.
- Automatic engine-side override detection is deferred to a future step.

Future follow-up:
- Engine compares last reaction steps with next-cycle HA state and calls `record_override`
  automatically for heating and lighting domains.

---

## 2026-03-09 — Domain dependencies use a DAG model via CanonicalState inter-cycle memory

Decision:
- domain handlers may read other domains' outputs via `CanonicalState` (previous evaluation cycle)
- domain handlers must NOT read current-cycle outputs of other domain handlers
- this forms a DAG per cycle: no circular dependencies, but real cross-domain reasoning is permitted

Reason:
- `house_state` in particular needs to be a convergent inference layer: the richer the observations
  it can read, the more the system can infer without requiring explicit user configuration
- blocking all cross-domain dependencies would prevent the system from ever being truly adaptive
- using previous-cycle `CanonicalState` as the inter-cycle bridge eliminates circularity while
  still allowing holistic reasoning

Current rule:
- `CanonicalState` is both entity storage and shared inter-cycle memory
- `house_state` reads from normalized observations + CanonicalState (past), never from current-cycle intents
- all domain handlers follow the same rule
- engine orchestrates evaluation as a DAG: observations → house_state → domain intents → apply → CanonicalState

Future follow-up:
- as `house_state` inference matures, document explicitly which CanonicalState keys it reads
- behavioral signals (lighting duration, occupancy stability, heating phase) are the next natural inputs
  to `house_state` inference, enabling detection of e.g. sleeping state without explicit configuration

## 2026-03-04 — Notification routes are retained as legacy fallback

Decision:
- keep `notifications.routes` in v1
- do **not** deprecate it yet

Reason:
- the new notification recipient alias/group model is being introduced incrementally
- existing installations already use flat `notify.*` routes
- immediate deprecation would add migration friction for little short-term value

Current rule:
- `routes` remains supported as a legacy fallback transport list
- recipient aliases/groups are the preferred direction for new configuration

Future follow-up:
- deprecate `routes` after:
  - recipient aliases/groups are stable in real use
  - migration semantics are defined
  - UI/runtime coverage for logical routing is complete

## 2026-03-04 — Heating v1 does not implement retry/verify loops

Decision:
- keep Heating apply in v1 limited to guarded `climate.set_temperature` requests
- do **not** implement thermostat verify/retry logic inside Heima for now

Reason:
- Home Assistant and the thermostat integration remain the right place for transport/device retry behavior at this stage
- adding a retry layer now would increase complexity and blur responsibility boundaries

Current rule:
- Heating uses:
  - small-delta skip
  - rate limit
  - idempotence
  - startup/service-race tolerance
- but no post-apply verification or retry loop

Future follow-up:
- revisit only as an optional enhancement if real-world device behavior proves it necessary

## 2026-03-04 — `scheduler_delegate` means Heima yields to the external scheduler

Decision:
- treat `scheduler_delegate` as a passive handoff mode

Reason:
- Heima does not yet integrate with external scheduler internals or future setpoints
- the clean v1 behavior is to stop writing thermostat targets and let the external scheduler own control

Current rule:
- when Heating selects `scheduler_delegate`, Heima:
  - reports delegated state
  - does not push thermostat setpoints

Future follow-up:
- explicit scheduler integration can be added later if a real contract is defined

## 2026-03-04 — Heating remains fixed-policy in v1 (not policy-pluggable yet)

Decision:
- keep Heating on a fixed built-in policy tree in v1
- do **not** implement policy plugins in runtime yet

Reason:
- Heating needed a stable MVP first
- introducing pluggable domain policies now would add more abstraction before the base domain proves itself in real use

Current rule:
- built-in branch catalog:
  - `disabled`
  - `scheduler_delegate`
  - `fixed_target`
  - `vacation_curve`

Future follow-up:
- first planned adopter of the future Policy Plugin Framework is Heating, starting with `vacation_curve`

## 2026-03-04 — House-state signals are configurable, not hardcoded helpers

Decision:
- remove hardcoded helper assumptions for house-state side signals

Reason:
- hardcoded entities like `binary_sensor.work_window` were not guaranteed to exist
- this made `house_state` behavior fragile and environment-dependent

Current rule:
- `vacation_mode`
- `guest_mode`
- `sleep_window`
- `relax_mode`
- `work_window`
are read only from configured `house_signals` bindings
- missing bindings are treated as `off`

Future follow-up:
- none required for the model itself; only UX refinements if needed

## 2026-03-04 — `heima.set_mode` is a final runtime-only house-state override

Decision:
- define `heima.set_mode` as a final `house_state` override, not a boolean mode-signal setter

Reason:
- the service name implies “set the house mode/state”, not “toggle one input signal”
- using it for signal toggles would make the API misleading

Current rule:
- `state=true`:
  - set the singular runtime override to the requested canonical state
- `state=false`:
  - clear it only if the current override matches that same state
- the override is runtime-only and cleared on reload/restart

Future follow-up:
- persistent overrides are possible later, but not part of v1

## 2026-03-04 — `vacation_curve` captures start temperature at activation

Decision:
- remove configured `vacation_start_temp`
- capture the curve start temperature from the thermostat when the branch becomes active

Reason:
- a fixed configured start value can drift from the real thermostat state
- the correct ramp-down origin is the actual active setpoint when vacation control starts

Current rule:
- `vacation_curve` stores the start temperature at branch activation
- it reuses that captured value until the branch exits

Future follow-up:
- optional fallback behavior can be added only if a thermostat current setpoint is unavailable

## 2026-03-04 — `vacation_comfort_temp` is a return preheat target, not the post-vacation truth

Decision:
- keep `vacation_comfort_temp`, but treat it as a preheat target before scheduler handoff

Reason:
- the external scheduler may want a different target at the exact end of vacation
- Heima does not yet know the scheduler’s future setpoint

Current rule:
- ramp-up aims toward a return preheat target
- at vacation end, control returns to `scheduler_delegate`
- the external scheduler may immediately apply a different target

Future follow-up:
- if Heima later knows the scheduler return target, `vacation_curve` can ramp toward that instead

## 2026-03-04 — Runtime timing is centralized in the shared scheduler

Decision:
- use the shared Runtime Scheduler as the single timing substrate for internal delayed/deadline-based behavior

Reason:
- ad hoc timers across domains would fragment timing logic and make cleanup/diagnostics harder

Current rule:
- occupancy dwell and max-on
- occupancy mismatch persistence
- security mismatch persistence
- Heating `vacation_curve` timed rechecks
all schedule through the shared runtime scheduler

Future follow-up:
- future timed domains/features (e.g. Watering, policy plugins) must reuse this scheduler instead of introducing custom timer paths

## 2026-03-04 — Normalization plugins and policy plugins remain distinct layers

Decision:
- keep the normalization plugin framework separate from the future policy plugin framework

Reason:
- normalization plugins combine and normalize signals
- policy plugins change domain decisions
- mixing the two would make the architecture ambiguous

Current rule:
- normalization plugins are active and used in runtime
- policy plugins are specified only, not implemented yet

Future follow-up:
- implement the policy plugin framework as a distinct runtime subsystem, with Heating as the first planned real adopter
