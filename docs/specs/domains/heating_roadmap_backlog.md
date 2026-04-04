# Heima — Heating Roadmap

**Status:** Draft roadmap — not yet approved for implementation
**Last Updated:** 2026-04-04

## Purpose

Describe a complete staged roadmap for Heating, from the current bounded runtime
to a much more complete domain.

This document is intentionally a roadmap, not the canonical runtime contract.
The current source of truth for implemented behavior remains:

- [heating_spec.md](/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/docs/specs/domains/heating_spec.md)
- [house_state_spec.md](/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/docs/specs/domains/house_state_spec.md)
- [calendar_domain_spec.md](/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/docs/specs/domains/calendar_domain_spec.md)

---

## 1. Current Starting Point

Today, Heating already has a real bounded runtime:

- canonical `house_state` input
- fixed built-in branch tree
- `delegate_to_scheduler` and `set_temperature`
- `fixed_target` and `vacation_curve`
- manual override guard
- small-delta and rate-limit guards
- diagnostics and runtime events

The context contract is already intentionally narrow:

- Heating reads canonical `house_state`
- calendar semantics reach Heating indirectly through `HouseStateDomain`
- branch-local helper bindings are still acceptable for:
  - outdoor temperature
  - vacation timing

This bounded base is the correct starting point for the roadmap.

---

## 2. End-State Vision

The eventual Heating domain should become a strong orchestration domain able to:

- reason over home context credibly
- coordinate multiple bounded heating strategies
- explain why a target or delegation choice was made
- support learned/admin-authored behavior where useful
- handle richer device topologies
- remain diagnosable and operationally manageable

The final target is **not** “maximum cleverness”.
The final target is:

- strong context usage
- bounded automation authority
- explainability
- safe actuation
- composable evolution

---

## 3. Roadmap Structure

The roadmap is split into four maturity levels:

1. **Stage A: Bounded Domain-Strong Heating**
2. **Stage B: Expanded Single-Zone Heating**
3. **Stage C: Structured Multi-Zone / Device Coordination**
4. **Stage D: Definitive Heating Domain**

Each stage is intentionally smaller than the final vision.

---

## 4. Stage A — Bounded Domain-Strong Heating

This is the recommended next stream if Heating is started soon.

### Scope

Primary focus:

- `vacation`
- `away`

Possible extension at the end of the stage:

- `sleeping`

Explicitly deferred:

- `working`
- `relax`
- direct `wfh` / `office` branching in `HeatingDomain`
- multi-zone behavior

### A1. Runtime Semantics

Goal:
- make the existing Heating runtime product-strong and operationally clear

Tasks:
1. clarify runtime semantics for `away` vs `vacation`
2. verify branch-selection behavior against actual `house_state` values
3. improve heating diagnostics wording and operational summary
4. review branch handoff between:
- active override branch
- scheduler delegation
5. harden branch trace and apply trace where needed

Exit criteria:
- `away` and `vacation` are clearly distinct in runtime behavior
- diagnostics explain selected branch, phase and reason without ambiguity

### A2. UX Operativa

Goal:
- make Heating understandable through bounded existing product surfaces

Tasks:
1. add heating-specific diagnostics summary
2. improve overview wording in options/diagnostics
3. make provenance clear between:
- runtime branch behavior
- last applied target
- manual override blocking

Exit criteria:
- an admin can understand Heating state quickly without inspecting raw payloads

### A3. Heating Learning Review

Goal:
- assess current Heating learning before expanding it

Scope:

- `heating_preference`
- `heating_eco`

Tasks:
1. review proposal identity and summary stability
2. improve explainability of current learned proposals
3. decide whether bounded tuning is worth adding now or deferring

Exit criteria:
- Heating learning is either:
  - explicitly improved and bounded
  - or explicitly deferred with a reason

### A4. Validation & Closeout

Goal:
- close the stage with explicit validation

Tasks:
1. final spec alignment
2. local sweep on runtime, diagnostics and any touched learning paths
3. targeted live validation for:
- `vacation_curve`
- `away`
- manual override guard
- summary/diagnostics surfaces
4. full live suite if shared runtime behavior was touched

Exit criteria:
- Heating is domain-strong in a bounded single-device / single-zone sense

---

## 5. Stage B — Expanded Single-Zone Heating

This stage assumes Stage A is already stable.

### Scope

Expand Heating context and product behavior without yet introducing true multi-zone control.

Main additions:

- richer branch coverage
- more deliberate learning/admin-authored surfaces
- stronger calendar/house-state-informed behavior

### B1. Additional States

Candidate additions:

- `sleeping`
- `working`
- `guest`

Possible later addition:

- bounded `relax`

Tasks:
1. decide which states deserve Heating behavior at all
2. define state-by-state branch semantics
3. avoid adding branches that are hard to explain operationally

Exit criteria:
- every supported state has a clear product reason and a bounded heating behavior

### B2. Heating Learning Bounded Expansion

Goal:
- make Heating learning genuinely useful

Tasks:
1. improve proposal quality for:
- `heating_preference`
- `heating_eco`
2. add bounded follow-up / tuning where credible
3. make review diffs understandable
4. suppress noisy or low-value suggestions

Exit criteria:
- Heating learning feels trustworthy rather than experimental

### B3. Admin-Authored Heating Surface

Goal:
- decide whether Heating needs admin-authored bounded templates

Possible early templates:

- `heating.fixed_target.by_house_state`
- `heating.vacation_curve.basic`

Tasks:
1. decide if admin-authored heating belongs in this stage
2. if yes, keep it tightly bounded to already-supported runtime semantics

Exit criteria:
- any admin-authored heating surface stays aligned with runtime reality

### B4. Validation

Tasks:
1. local sweep on runtime + learning + options flow
2. targeted live validation on newly supported states
3. regression checks on `house_state` and manual override behavior

Exit criteria:
- expanded single-zone Heating remains explainable and safe

---

## 6. Stage C — Structured Multi-Zone / Device Coordination

This stage should only start if Stage B is already operationally solid.

### Scope

Move from single bound climate control to structured coordination across a more complex heating topology.

Possible topology elements:

- central thermostat
- room TRVs
- smart radiator valves
- mixed delegation / direct actuation

### C1. Device Topology Model

Goal:
- represent bounded heating topology explicitly

Tasks:
1. define supported topology classes
2. define authority boundaries between:
- central thermostat
- room devices
- scheduler ownership
3. define safe fallback modes

Exit criteria:
- Heating knows what it is allowed to control and what it must only observe

### C2. Multi-Zone Coordination Rules

Goal:
- introduce coordination without turning Heating into an opaque optimizer

Tasks:
1. define per-zone vs global intent
2. define conflict handling
3. define rate-limiting and anti-thrashing rules across devices
4. keep diagnostics readable

Exit criteria:
- multi-zone coordination is bounded, deterministic and explainable

### C3. Operability

Tasks:
1. stronger diagnostics for per-zone behavior
2. better lifecycle and provenance surfaces
3. possibly stronger UI needs than config flow alone

Exit criteria:
- device coordination is operationally manageable

---

## 7. Stage D — Definitive Heating Domain

This is the long-term target, not the next implementation step.

### Characteristics

The definitive Heating domain would likely include:

- richer context-aware policy composition
- clearer separation between:
  - context
  - constraints
  - policy
  - actuation
- credible multi-zone support
- bounded learning and tuning
- possibly a more specialized management surface than the current config flow

### Candidate Features

Potential future capabilities:

- bounded policy plugin framework
- richer weather/context policy inputs
- topology-aware coordination
- stronger lifecycle management
- possible direct relation with future constraints framework

### Guardrail

The definitive domain should still avoid:

- opaque optimization
- poorly explainable temperature changes
- uncontrolled authority creep over the house

The goal is not “fully autonomous HVAC AI”.
The goal is a robust and inspectable Heating domain.

---

## 8. Recommended Order

Preferred order:

1. Stage A
2. Stage B
3. Stage C
4. Stage D

Practical reading:

- first prove a bounded strong domain
- then expand useful single-zone behavior
- only then take on topology complexity
- keep the definitive domain as a convergence target, not a premature implementation plan

---

## 9. Recommended First Slice If Work Starts Soon

If Heating is started in the near term, the recommended first slice is:

- Stage A
- runtime-first
- focused on:
  - `vacation`
  - `away`

Concrete first slice:

1. audit current `away` behavior vs intended product semantics
2. improve diagnostics and summary surfaces around:
- selected branch
- reason
- phase
- scheduler delegation vs active override
3. validate live against:
- vacation branch
- manual override guard
- away-state runtime behavior

This is the smallest slice that meaningfully improves Heating without overcommitting to a large cross-domain program.
