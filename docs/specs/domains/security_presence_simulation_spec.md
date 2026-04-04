# Heima — Security Presence Simulation Spec

**Status:** Draft backlog — not implemented
**Last Updated:** 2026-04-04

## Purpose

Define a future Heima capability that simulates home occupancy during `vacation`
by driving selected lights in a plausible, bounded way.

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

- bounded time windows
- bounded number of activations
- bounded room/entity set
- bounded randomness
- easy manual disable

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

---

## 4. Learning Model

### 4.1 Data Source

The family should learn primarily from:

- non-vacation periods
- periods with real occupancy
- historically plausible evening lighting behavior

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

### 4.3 Output Shape

The learned output should not be a literal history replay.
It should instead derive a bounded simulation profile:

- typical time window
- candidate rooms / entities
- event count budget
- plausible duration/jitter bounds

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

- active window
- rooms involved
- variability/jitter policy
- event budget or density

### 5.3 Identity and Lifecycle

The lifecycle should not reuse normal lighting-scene identity.

The logical slot should instead be security-oriented, roughly by:

- simulation family
- home scope
- possibly evening window class

Small changes in:

- jitter
- room subset size
- event budget

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
- `active_window_start`
- `active_window_end`
- `rooms`
- `entities`
- `requires_dark_outside`
- `min_jitter_min`
- `max_jitter_min`
- `max_events_per_evening`
- `skip_if_presence_detected`

Optional later additions:

- room weighting
- weekday/weekend distinctions
- cover/media participation

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

- active window
- entities/rooms used
- variability policy
- why the system considers the pattern plausible

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

- admin-authored/manual configuration first
- no learned proposal yet

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

## 10. Recommendation

Recommended approach:

- **semantic placement:** `security`
- **technical packaging:** new plugin family
- **first implementation style:** runtime-first MVP, possibly admin-authored first

This avoids two common mistakes:

1. modeling it as just another lighting routine
2. waiting for a fully learned/advanced version before creating the right domain boundary
