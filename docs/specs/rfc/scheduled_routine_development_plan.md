# Scheduled Routine Development Plan

**Status:** Historical / deprecated  
**Superseded by:** `docs/specs/core/scheduled_routine_spec.md`

## Goal

Implement a bounded **admin-authored only** family for pure time-based routines:

- `scheduled_routine`

This family exists to represent explicit admin intent such as:

- run a scene every weekday at a given time
- turn on/off one or more actuators at a given time
- call a script at a given time

It is explicitly **not**:

- a learned family
- a lighting-only family
- a target for tuning/improvement proposals
- a valid source for `vacation_presence_simulation`

## Product constraints

Normative constraints carried into implementation:

1. `scheduled_routine` is **admin-authored only**
2. no analyzer may emit `scheduled_routine`
3. no improvement proposal may target or originate from `scheduled_routine`
4. `vacation_presence_simulation` must ignore `scheduled_routine`
5. the actuation model must be generic across actuator domains
6. the config flow must stay bounded, not become a universal automation builder
7. bounded product guardrails are allowed only when they remain first-class fixed fields, not
   arbitrary boolean logic

## Scope of v1

### In scope

- weekday + time trigger
- bounded runtime guardrails:
  - `house_state_in`
  - `skip_if_anyone_home`
- bounded actuation targets:
  - `scene.*`
  - `script.*`
  - `light.*`
  - `switch.*`
  - `input_boolean.*`
- direct admin create/edit/delete
- runtime execution through the existing reaction engine
- diagnostics and labels

### Out of scope

- learned discovery
- tuning/improvement proposals
- arbitrary service payload authoring
- arbitrary conditions/boolean logic beyond the fixed guardrails above
- per-step delays/chains
- climate/cover/media_player support in the first slice if they make the form too broad

## Proposed config contract

Target persisted reaction contract:

```yaml
reaction_type: scheduled_routine
enabled: true
weekday: 0
scheduled_min: 1200
window_half_min: 0
house_state_in:
  - vacation
skip_if_anyone_home: true
routine_kind: scene | script | entity_action
target_entities:
  - scene.evening_relax
entity_action: turn_on | turn_off
entity_domains:
  - light
  - switch
steps:
  - entity_id: light.living_main
    action: turn_on
```

Notes:

- `window_half_min` may remain `0` in v1 unless jitter support proves necessary
- `routine_kind` keeps the flow bounded and readable
- `steps` remains the generic runtime actuation payload
- for scene/script routines, the persisted payload may still normalize into `steps`
- `house_state_in` and `skip_if_anyone_home` are the only v1 guardrails; they are product-level
  fields, not a generic condition builder

## UX direction

The admin flow should offer one bounded template:

- `scheduled_routine.basic`

Wizard shape:

1. choose trigger:
   - weekday
   - time
2. choose guardrails:
   - allowed house states
   - skip if anyone home
3. choose routine kind:
   - scene
   - script
   - entity actions
4. choose targets
5. review summary

Edit flow should reuse the same schema/normalization core.

## Implementation phases

### Phase 1 — Contract and reaction registration

Implement:

- new `reaction_type = scheduled_routine`
- compat mapping and registry registration
- builder + presenter hooks
- persisted config normalizer
- persisted support for:
  - `house_state_in`
  - `skip_if_anyone_home`

Acceptance:

- runtime can rebuild one persisted `scheduled_routine`
- labels and diagnostics work

### Phase 2 — Runtime reaction

Implement:

- runtime reaction with weekday + time execution
- generic `steps`-based apply
- idempotent per-day firing semantics
- scheduler integration
- guardrail enforcement:
  - skip when current house state not in `house_state_in`
  - skip when `skip_if_anyone_home=true` and `anyone_home=true`

Acceptance:

- the routine fires once in the intended window
- no learning-specific metadata is required at runtime

### Phase 3 — Admin-authored options flow

Implement:

- template descriptor:
  - `scheduled_routine.basic`
- bounded create flow
- dedicated edit flow
- shared create/edit form logic

Acceptance:

- admin can create, edit, disable, delete the routine
- no generic unrelated fields leak into the editor
- the only conditions visible are the bounded guardrails above

### Phase 4 — Exclusion from learning lifecycle

Implement:

- no analyzer emits `scheduled_routine`
- proposal lifecycle / review flow does not treat it as learned
- no tuning/improvement follow-up path for this family

Acceptance:

- `ProposalEngine` never surfaces `scheduled_routine` from batch learning
- review surfaces keep it clearly admin-authored

### Phase 5 — Exclusion from vacation presence simulation

Implement:

- hard exclusion in source selection for `vacation_presence_simulation`
- diagnostics note if only `scheduled_routine` sources exist

Acceptance:

- presence simulation never uses scheduled routines as source material

### Phase 6 — Tests

Required tests:

- unit:
  - reaction execution timing
  - rebuild from persisted config
  - labels/diagnostics
- options flow:
  - create
  - edit
  - delete
  - invalid schema paths
- lifecycle:
  - no tuning/improvement path
  - no learning proposal path
- domain:
  - `vacation_presence_simulation` ignores scheduled routines

### Phase 7 — Live E2E

Live tests should cover:

1. create `scheduled_routine.basic`
2. verify the configured reaction exists
3. trigger execution in the lab
4. verify target entities/services fired
5. verify presence simulation diagnostics do not include it as a source

## Risks

1. The flow can drift toward a universal automation builder.
- Mitigation:
  - keep `routine_kind` bounded
  - keep target domains bounded
  - normalize to one simple `steps` model

2. The runtime scheduler semantics can duplicate existing lighting-schedule behavior in a confusing way.
- Mitigation:
  - keep `scheduled_routine` clearly admin-authored and generic
  - do not reintroduce learned schedule semantics

3. Users may expect improvement/tuning on these routines.
- Mitigation:
  - make the docs and review wording explicit:
    - explicit admin intent
    - no automatic learning follow-up

- 4. Guardrails can silently grow into ad hoc condition logic.
- Mitigation:
  - keep only:
    - `house_state_in`
    - `skip_if_anyone_home`
  - reject additional free-form condition requests in the first slice

## Deliverable definition

This effort is done when:

1. `scheduled_routine` exists as an admin-authored-only family
2. it supports bounded generic actuator routines
3. it is absent from learned proposal emission
4. it is absent from improvement/tuning automation
5. it is absent from `vacation_presence_simulation` source selection
6. it supports only bounded guardrails:
   - `house_state_in`
   - `skip_if_anyone_home`
7. unit/options/live tests are green
