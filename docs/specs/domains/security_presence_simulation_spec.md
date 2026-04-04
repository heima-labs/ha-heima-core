# Heima — Security Presence Simulation Spec

**Status:** Draft backlog — not implemented
**Last Updated:** 2026-04-04

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

### 4.3 Output Shape

The learned output should not be a literal history replay.
It should instead derive a bounded simulation profile:

- typical darkness-relative or seasonally plausible activation periods
- candidate rooms / entities
- event count budget
- plausible duration/jitter bounds

The output should be rich enough that the runtime can operate even when the
admin provides little or no detailed timing configuration.

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

---

## 10. Recommendation

Recommended approach:

- **semantic placement:** `security`
- **technical packaging:** new plugin family
- **first implementation style:** runtime-first MVP with admin-authored policy and learned execution source

This avoids two common mistakes:

1. modeling it as just another lighting routine
2. treating omitted configuration as a reason to fall back to static schedule defaults
