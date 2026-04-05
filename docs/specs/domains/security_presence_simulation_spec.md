# Heima — Security Presence Simulation Spec

**Status:** MVP implemented / maturation backlog open
**Last Updated:** 2026-04-05

## Purpose

Define a future Heima capability that simulates home occupancy during `vacation`
by replaying, in a bounded and security-oriented way, historically learned
lighting behavior associated with real occupancy.

This capability belongs semantically to the `security` domain even if its first
actuation surface is primarily lighting.

The intent is:

- deterrence
- occupancy simulation
- vacation-specific presence mimicry

The intent is **not**:

- comfort lighting
- room assist
- routine replay for convenience
- user-authored schedules with fixed clock times

---

## 1. Product Placement

Recommended placement:

- **new plugin family**
  - `security_presence_simulation`

Product/domain placement:

- `security`

Primary actuation surface:

- lighting

Possible later actuation surfaces:

- shutters / covers
- lightweight media cues

The capability should not be modeled as a plain lighting routine because:

- the goal is security-oriented
- the active condition is contextual (`vacation`, no real occupancy)
- the runtime semantics and guardrails are different from normal lighting automations

It should also not be modeled as a user-authored clock schedule because:

- Heima already learns when and how lights are used
- the point of the feature is to reuse that learned behavior
- static times would be less plausible across seasons and daylight conditions

---

## 2. Proposed Family Shape

The family should eventually own:

- analyzer / learning logic
- proposal type
- lifecycle hooks
- reaction implementation
- presenter hooks
- diagnostics summary

Recommended identifiers:

- plugin family: `security_presence_simulation`
- proposal type: `vacation_presence_simulation`
- reaction type / class:
  - `vacation_presence_simulation`
  - `VacationPresenceSimulationReaction`

Later admin-authored template possibility:

- `security.vacation_presence_simulation.basic`

---

## 3. Core Runtime Semantics

### 3.1 Activation

The simulation should only be eligible when:

- canonical `house_state = vacation`

Recommended additional guards:

- no one is currently home
- no recent manual occupancy evidence
- security policy does not explicitly disable simulation

### 3.2 Runtime Goal

The runtime should produce a plausible occupancy impression rather than replaying
an exact historical schedule.

Required properties:

- learned timing baseline
- bounded number of activations
- bounded room/entity set
- bounded randomness
- easy manual disable

The primary source of timing, room choice and activation density should be
learned historical behavior, not fixed configured hours.

### 3.3 Behavioral Style

The simulation should be:

- plausible
- variable
- sparse enough to avoid looking scripted
- deterministic enough to be explainable

The runtime should avoid:

- strict fixed daily schedules
- overly random chaotic switching
- exact copies of past evenings
- daytime actions without explicit justification

### 3.4 Authored Policy, Learned Execution

The recommended model for this family is:

- **admin-authored policy**
- **learned execution source**

Meaning:

- the admin enables and constrains the capability
- Heima decides concrete timing and actuation using learned occupancy-like lighting patterns

This family should therefore not be treated as a classic authored schedule.

---

## 4. Learning Model

### 4.1 Data Source

The family should learn primarily from:

- non-vacation periods
- periods with real occupancy
- historically plausible evening lighting behavior

Normative rule:

- the source profile for this family MUST NOT be built primarily from `vacation` behavior
- `vacation` periods are considered execution-time context for the simulation, not the normal
  baseline from which to infer credible occupancy behavior

Priority sources:

- first evening light-on events
- room transitions across the evening
- final light-off behavior
- room-level occupancy-like sequences

### 4.2 Exclusions

The analyzer should exclude or down-rank:

- rare one-off events
- maintenance/cleaning anomalies
- late-night outliers
- events during already-automated special modes
- events that occurred while `house_state = vacation`

### 4.2.1 Learning During Vacation

Heima should **not** suspend the global learning system only because `vacation` is active.

However, for this specific family:

- `vacation` behavior SHOULD be excluded from the occupancy-simulation source profile
- the active simulation itself MUST NOT become the primary evidence used to refresh its own learned
  baseline

This distinction is important:

- the house may continue learning other things during `vacation`
- but presence-simulation source material must remain grounded in normal occupied behavior

### 4.2.2 Rolling Source Profile

The execution source for this family should be treated as a rolling profile, not as a frozen model.

Recommended properties:

- prefer recent evidence over old evidence
- adapt gradually as real household behavior changes
- avoid immediate instability from a few recent outliers

The preferred interpretation is:

- the reaction policy is persistent
- the nightly execution profile is dynamic and continually refreshed from suitable recent evidence

For the current MVP bootstrap:

- the source profile is derived from accepted `lighting_scene_schedule` reactions
- the nightly plan is anchored relative to `sun.sun`
- stale lighting reactions MUST be excluded from the usable nightly source set
- source suitability SHOULD weight:
  - recentness
  - weekday compatibility
  - plausible evening density
  - late-night penalties for weak outliers
- for rooms selected into the nightly plan, the runtime SHOULD prefer preserving observed `on/off`
  closure patterns instead of emitting only isolated `on` activations
- when multiple suitable rooms exist, the nightly plan SHOULD prefer room diversity before selecting
  multiple closely related events from the same room
- when multiple suitable source reactions exist, the nightly plan SHOULD prefer a temporally spread subset
  over tightly clustered near-duplicates
- if the usable nightly source set is too small or too weak after these suitability checks, the runtime
  SHOULD skip the simulation rather than inventing a low-credibility evening
- the nightly plan SHOULD apply bounded deterministic jitter rather than pure random runtime drift
- the nightly plan MUST enforce a minimum gap between consecutive simulated events
- diagnostics SHOULD expose which source reactions are considered recent enough for tonight

### 4.3 Output Shape

The learned output should not be a literal history replay.
It should instead derive a bounded simulation profile:

- typical darkness-relative or seasonally plausible activation periods
- candidate rooms / entities
- event count budget
- plausible duration/jitter bounds

The output should be rich enough that the runtime can operate even when the
admin provides little or no detailed timing configuration.

### 4.4 Minimum Evidence Requirement

This family is only valid when the learned source profile is strong enough to
produce a credible simulation.

Normative rule:

- if suitable learned evidence is too weak, the capability MUST NOT be offered
  as a normally available automation choice
- the system SHOULD surface an explicit reason instead of silently degrading to
  a poor static schedule

Examples of insufficient evidence:

- no accepted recent lighting reactions in suitable rooms
- accepted lighting reactions exist, but are too old
- accepted lighting reactions exist, but do not yield credible darkness-relative timing
- the usable room/entity set is too small to produce plausible occupancy simulation

---

## 5. Proposal Model

### 5.1 Proposal Type

Recommended proposal type:

- `vacation_presence_simulation`

### 5.2 Proposal Summary

Proposal wording should make the intent explicit, for example:

- `Simulazione presenza in vacation`
- `Vacation presence simulation for evening lighting`

The summary should expose at least:

- learned activity profile
- rooms involved
- variability/jitter policy
- event budget or density

### 5.3 Identity and Lifecycle

The lifecycle should not reuse normal lighting-scene identity.

The logical slot should instead be security-oriented, roughly by:

- simulation family
- home scope
- possibly learned simulation profile class

Small changes in:

- jitter
- room subset size
- event budget
- learned activation distribution

should normally be treated as bounded tuning, not as completely new identity.

---

## 6. Reaction Model

The reaction should encapsulate:

- activation guards
- nightly simulation plan generation
- bounded actuation execution
- diagnostics and stop reasons

Recommended configuration surface:

- `enabled`
- `allowed_rooms`
- `allowed_entities`
- `requires_dark_outside`
- `simulation_aggressiveness`
- `min_jitter_override_min`
- `max_jitter_override_min`
- `max_events_per_evening_override`
- `latest_end_time_override`
- `skip_if_presence_detected`

Optional later additions:

- room weighting
- weekday/weekend distinctions
- cover/media participation

### 6.1 Configuration Precedence

For this family, configuration fields should behave as **overrides**, not as the
primary source of behavior.

Required precedence:

1. explicit admin-configured override
2. learned value
3. minimal static safety fallback, only if learned evidence is insufficient

Normative rule:

- omitted configuration fields MUST resolve to learned values when available
- static defaults MUST NOT be the normal source of behavior for omitted fields

Examples:

- if `allowed_rooms` is omitted:
  - use learned credible rooms
- if `max_events_per_evening_override` is omitted:
  - derive event density from learned behavior
- if `latest_end_time_override` is omitted:
  - derive a learned plausible end boundary

This rule is central to the product semantics of the family.

### 6.2 Nightly Plan Generation Contract

The nightly plan generation algorithm MUST be explicit and stable enough that:

- runtime behavior is explainable
- diagnostics can describe why a plan exists or does not exist
- future tuning work refines the same model instead of replacing it ad hoc

The nightly plan is a **bounded replay of observed occupied-evening behavior**.

It is not:

- a fixed authored schedule
- a random evening generator
- an exact historical copy of one past night

The current family contract SHOULD therefore treat nightly-plan generation as
the following ordered pipeline.

#### 6.2.1 Inputs

The planner consumes:

- persisted policy configuration
- learned source profiles or accepted lighting reactions
- current `house_state`
- current occupancy state
- current `sun.sun` context
- current local date / weekday

The planner MUST prefer learned source profiles when they are present.
Accepted lighting reactions are the fallback bootstrap source only when learned
source profiles are absent.

#### 6.2.2 Guard Phase

Before building a plan, the runtime MUST verify:

1. reaction is enabled
2. a source profile is present
3. snapshot history exists
4. `house_state = vacation`
5. no occupancy guard blocks execution
6. darkness requirement is satisfied if configured

If any of these fail, the reaction MUST expose a clear blocked reason rather
than synthesizing a degraded plan.

#### 6.2.3 Darkness Anchor Resolution

The planner MUST anchor the evening relative to the current darkness context,
not to fixed clock times.

Preferred sources:

- `sun.sun.last_setting`
- `sun.sun.next_setting`
- `sun.sun.next_dusk`

Normative rule:

- after sunset, if Home Assistant only exposes the next setting/dusk for the
  following day, the planner SHOULD derive tonight's darkness anchor from that
  next event rather than treating darkness context as unavailable

If no credible darkness anchor can be resolved, the planner MUST fail with an
explicit reason such as `sun_unavailable`.

#### 6.2.4 Candidate Source Selection

From the source profile, the planner builds a candidate set for tonight.

The candidate set SHOULD:

- exclude stale sources
- exclude weak or low-credibility sources
- exclude sources outside allowed room/entity scope
- prefer recent evidence
- prefer same-weekday evidence when available
- penalize late-night outliers

If the remaining candidate set is too weak, the planner MUST not produce a
nightly plan.

#### 6.2.5 Budget and Subset Selection

The planner then chooses a bounded subset for tonight.

The subset selection SHOULD optimize for:

- strong source suitability
- room diversity when plausible
- temporal spread across the evening
- credible room closeout behavior (`on -> off`)

The planner MUST NOT simply take the first `N` candidates sorted by time.

It SHOULD instead select a subset that remains faithful to the observed
evening shape while respecting:

- event budget
- minimum gap constraints
- room/entity scope constraints
- optional latest-end overrides

#### 6.2.6 Time Projection

For each selected source item, the planner projects a runtime due time for the
current evening.

The projection model is:

1. choose an evening darkness anchor for tonight
2. preserve relative ordering between selected source items
3. preserve approximate inter-event spacing where possible
4. apply bounded deterministic jitter
5. enforce minimum gap between consecutive events
6. discard items that violate end-of-evening guardrails

This projection MUST remain:

- darkness-relative
- deterministic enough to be explainable
- variable enough not to look scripted

#### 6.2.7 Empty-Plan Semantics

A reaction may be valid and source-ready while the nightly plan is still empty.

Examples:

- waiting for darkness
- waiting for the first planned activation
- no valid events survive current-night guardrails

Normative rule:

- diagnostics MUST distinguish:
  - missing source profile
  - blocked context
  - source-ready but empty plan
  - plan derived and waiting for next activation

#### 6.2.8 Diagnostics Requirements

The runtime diagnostics for this family SHOULD expose at least:

- source profile kind
- source profile readiness
- selected source trace
- excluded source trace
- tonight-plan count
- tonight-plan preview
- next planned activation
- blocked reason

This is required because the nightly plan is derived dynamically and cannot be
understood from persisted config alone.

---

## 7. Guardrails

These are mandatory for the family.

### 7.1 Occupancy Guard

Do not run if:

- anyone is home
- recent occupancy evidence suggests the house is not actually empty

### 7.2 Vacation Guard

Do not run unless:

- `house_state = vacation`

### 7.3 Daylight Guard

Prefer not to run unless:

- it is dark enough

Daytime behavior should be explicitly disabled by default.

### 7.4 Manual Override Guard

Allow explicit disable/hold semantics so the family can be turned off without
reconfiguring the full proposal/reaction.

### 7.5 Rate Guard

Avoid excessive toggling:

- bounded number of events per evening
- bounded minimum gap between activations

---

## 8. UX and Diagnostics

### 8.1 Review UX

The review should clearly state:

- this is a security-oriented simulation
- not a comfort lighting automation

It should show:

- learned activity profile
- entities/rooms used
- variability policy
- why the system considers the pattern plausible

It should avoid presenting the feature as a manually scheduled clock-based automation
unless explicit overrides were actually configured.

### 8.2 Runtime Diagnostics

Suggested diagnostics:

- simulation active tonight: `true|false`
- current block reason
- next planned activation
- last executed simulated activation
- source reactions considered usable tonight
- derived tonight-plan preview
- selected source trace with suitability score and selection reason
- excluded source trace with exclusion reason
- reasons for skipping:
  - daylight
  - occupancy detected
  - not in vacation
  - manual hold

### 8.3 Operational Summary

If this family is implemented, it should have a dedicated summary similar to:

- configured total
- pending total
- active tonight
- blocked tonight

---

## 9. Suggested Roadmap

### SPS-1 Family Definition

Goal:
- define the family shape, proposal type and reaction contract

### SPS-2 Runtime-First MVP

Goal:
- implement a bounded security-owned reaction that simulates evening occupancy in `vacation`

This MVP may start with:

- admin-authored policy first
- no learned proposal yet

The expected MVP shape is:

- policy authored by admin
- execution driven by already learned lighting behavior

This keeps the first slice smaller while preserving the correct family boundary.

### SPS-3 Learned Proposal

Goal:
- add analyzer/proposal generation from historical evening occupancy patterns

The first learned slice should stay bounded:

- emit at most one home-scoped proposal
- derive an initial `learned_source_profiles` payload directly from historical
  user lighting events
- exclude `vacation` periods from the learned baseline
- only emit when the learned material is strong enough to run credibly without
  degrading to a static fallback

The learned proposal should therefore carry:

- `reaction_class = VacationPresenceSimulationReaction`
- `dynamic_policy = true`
- `learned_source_profiles`
- learned `allowed_rooms`
- learned `allowed_entities`
- conservative default guards (`requires_dark_outside`, `skip_if_presence_detected`)

### SPS-4 Tuning and UX

Goal:
- add bounded tuning/follow-up and operational summaries

### SPS-5 Validation

Goal:
- local + live verification of guards, actuation bounds and diagnostics

---

## 9.1 First MVP Backlog

This is the recommended concrete backlog for the first implementation slice.

The MVP should be:

- admin-authored at the policy layer
- learned-driven at the execution layer
- runtime-first
- vacation-only

### SPS-A1 Family and Runtime Skeleton

Goal:
- introduce the family with the minimum runtime ownership needed to make it a real security capability

Tasks:
1. add plugin family wiring:
- `security_presence_simulation`
2. add reaction type / class:
- `vacation_presence_simulation`
- `VacationPresenceSimulationReaction`
3. add presenter hooks:
- reaction label
- review details
- diagnostics label
4. add runtime diagnostics surface stub for the family

Exit criteria:
- the family exists as a first-class security capability in the plugin/runtime layer

### SPS-A2 Admin-Authored Policy Template

Goal:
- allow an admin to enable the capability without authoring timings manually

Template:

- `security.vacation_presence_simulation.basic`

Recommended config surface:

- `enabled`
- `allowed_rooms`
- `allowed_entities`
- `requires_dark_outside`
- `simulation_aggressiveness`
- `min_jitter_override_min`
- `max_jitter_override_min`
- `max_events_per_evening_override`
- `latest_end_time_override`
- `skip_if_presence_detected`

Important rule:

- all fields above are optional overrides except `enabled`
- omitted fields should resolve to learned values when available

Availability rule:

- this template SHOULD be hidden, disabled, or marked unavailable when the
  learned source profile does not meet the minimum evidence requirement
- the admin-facing surface MUST provide a reason such as:
  - insufficient recent learned lighting routines
  - no suitable rooms/entities
  - learned profile not credible enough for vacation simulation

Exit criteria:
- the admin can enable the policy from the config flow without specifying clock schedules

### SPS-A3 Learned Execution Source

Goal:
- derive nightly simulation behavior from already stabilized lighting behavior

Tasks:
1. bootstrap the execution source from **accepted recent lighting reactions** rather than from:
- raw generic event history
- pending proposals
- non-accepted lighting candidates
2. define the learned input contract the runtime will consume:
- credible rooms
- credible entities
- plausible darkness-relative activation distribution
- plausible event density
- plausible end boundary
3. define how the runtime resolves each field:
- config override if present
- learned value if available
- conservative fallback if learning is insufficient
4. apply suitability gates:
- recency
- stability
- darkness-relative plausibility
5. explicitly exclude `vacation` periods and simulation-generated activity from the source-profile
   refresh path
6. reject activation if learned evidence is too weak and no safe fallback exists

Exit criteria:
- the MVP is not schedule-authored; it is truly learned-driven

### SPS-A4 Guarded Vacation Runtime

Goal:
- execute the simulation safely and plausibly

Tasks:
1. only activate when:
- `house_state = vacation`
2. block when:
- anyone is home
- recent occupancy evidence exists
- dark requirement is not satisfied
- manual disable/hold is active
3. generate a bounded nightly plan:
- project candidate activations relative to current darkness context
- choose room/entity subset
- apply bounded jitter
- enforce event count cap
- enforce end boundary
4. stop or suppress activity immediately when occupancy reappears
5. if the usable learned profile falls below the minimum evidence threshold:
- do not derive a nightly plan
- expose a block/unavailable reason explicitly

Exit criteria:
- the simulation can run for a vacation evening without looking purely static or unsafe

### SPS-A5 Diagnostics and UX

Goal:
- make the feature legible as a security capability

Tasks:
1. review wording:
- explain this is presence simulation, not comfort automation
2. diagnostics:
- active tonight
- blocked reason
- unavailable reason
- next planned activation
- last simulated activation
- events executed tonight
- learned profile summary
3. operational summary:
- configured
- active
- blocked
- pending, if future learned proposals are later added

Exit criteria:
- an admin can understand what the simulation will do and why it may not run

### SPS-A6 Validation

Goal:
- close the MVP with explicit verification

Tasks:
1. unit tests for:
- field resolution precedence
- guard behavior
- nightly-plan bounds
2. options flow tests for the admin-authored template
3. live tests for:
- active in vacation
- blocked if presence appears
- blocked if dark requirement fails
- unavailable when learned evidence is insufficient
- diagnostics visibility

Exit criteria:
- MVP is verifiably safe, bounded and learned-driven

### Suggested Order

1. `SPS-A1`
2. `SPS-A2`
3. `SPS-A3`
4. `SPS-A4`
5. `SPS-A5`
6. `SPS-A6`

### Recommended First Coding Slice

If implementation starts, the recommended first slice is:

- `SPS-A1` + `SPS-A2` + bootstrap `SPS-A3`

Reason:

- it establishes the family boundary and the admin-authored policy shape
- and it already proves the intended dynamic model
- without requiring the full future learned proposal pipeline

Concretely, the first coding slice should already include:

- accepted-lighting-reaction selection
- darkness-relative timing bootstrap
- minimal nightly derived plan generation

The second slice should then expand:

- `SPS-A4` + `SPS-A5`

so the capability becomes truly learned-driven rather than degenerating into a static schedule.

## 9.2 Maturation Backlog

This is the recommended follow-up backlog after the MVP is already working end-to-end.

The intent of this phase is not to add a different behavioral model.
The intent is to make the family:

- more faithful to the observed source behavior
- more legible operationally
- safer to run and easier to debug

### SPS-B1 Planner Fidelity

Goal:
- preserve the credibility of the observed household behavior more faithfully in the derived nightly plan

Tasks:
1. improve closeout fidelity:
- preserve plausible `on -> off` room sequences
- prefer plausible room dwell durations when multiple closeout candidates exist
- avoid plans that only accumulate unrelated `on` activations
2. improve duration realism:
- prefer observed room dwell patterns when enough evidence exists
- avoid overly compressed or stretched room occupancy windows
3. improve evening-shape fidelity:
- weight same-weekday and recent profiles more strongly when selecting the final subset
- keep temporal spread without erasing the shape of the observed evening
- prefer plausible same-weekday temporal companions over stronger but less coherent cross-day candidates
4. avoid low-credibility derivations:
- skip the nightly plan when the selected subset is too weak or too distorted after guards and caps

Exit criteria:
- the nightly plan looks like a bounded replay of real occupied evenings, not a generic plausible schedule

### SPS-B2 Operability and Debug Surface

Goal:
- make the family easy to inspect and operate without reading raw diagnostics payloads

Tasks:
1. add richer plan preview:
- selected source profiles
- excluded source profiles and reasons
- expected nightly timeline
- closeout rationale
2. add operational summaries:
- ready tonight
- blocked tonight
- insufficient evidence
- waiting for darkness
3. expose clearer admin-facing runtime state:
- which source profile kind is active
- why the plan is empty
- whether the current plan was derived from learned profiles or accepted lighting reactions
4. prepare a panel-friendly summary contract:
- compact status
- tonight plan preview
- source-profile quality indicators

Exit criteria:
- an admin can understand what Heima plans to do tonight and why, without reading raw engine internals

### SPS-B3 Guardrails and Runtime Control

Goal:
- harden the family as an operational security automation

Tasks:
1. add stronger blocked-state polish:
- product-facing blocked reasons
- clearer distinction between unavailable evidence, waiting state and active suppression
2. add family-specific runtime controls where appropriate:
- explicit mute/disable behavior
- clearer hold semantics
- predictable recovery after temporary blocks
3. tighten safety around presence return:
- verify immediate stop behavior
- verify no further queued activation survives a presence comeback
4. validate guard combinations:
- darkness present but evidence weak
- evidence strong but presence detected
- eligible source profile but temporary runtime hold

Exit criteria:
- the family behaves predictably under real-world guard and override conditions

### Suggested Order

1. `SPS-B1`
2. `SPS-B2`
3. `SPS-B3`

### Recommendation

The recommended next step after the current MVP is:

- `SPS-B1` first

Reason:

- planner fidelity improves the actual behavior the user will observe
- it keeps the family grounded in the observed source behavior
- it avoids opening more learned complexity before the runtime shape is fully credible

After `SPS-B1`, the next most valuable step is:

- `SPS-B2`

because this family benefits unusually strongly from a serious control/debug surface.

---

## 10. Recommendation

Recommended approach:

- **semantic placement:** `security`
- **technical packaging:** new plugin family
- **first implementation style:** runtime-first MVP with admin-authored policy and learned execution source

This avoids two common mistakes:

1. modeling it as just another lighting routine
2. treating omitted configuration as a reason to fall back to static schedule defaults
