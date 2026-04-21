# Improvement Proposals Development Plan

## Goal

Implement improvement proposals in bounded slices, starting with:

- `room_darkness_lighting_assist` -> `room_contextual_lighting_assist`

and ending with a generalized system that can support similar upgrade paths across
other learned/admin-authored reaction families.

## Scope

In scope:

- proposal contract additions for improvement semantics
- first end-to-end improvement flow for darkness -> contextual
- review wording and acceptance behavior for conversion proposals
- lifecycle identity for improvement proposals
- reusable infrastructure so future families do not need a bespoke one-off path

Out of scope for the first complete slice:

- direct learned discovery of `room_contextual_lighting_assist`
- automatic acceptance or silent replacement of active reactions
- generic N-to-N upgrade graph across every reaction family
- ML-based policy inference for contextual contracts

## Product framing

Heima should treat proposal intent as one of:

- `discovery`
- `refinement`
- `improvement`

The first implementation should not try to build a fully generic policy engine first.

Instead:

1. implement one real improvement family well
2. extract the stable abstractions from that work
3. only then generalize proposal lifecycle and conversion hooks

## Phase 0 — Preconditions and invariants

Before implementation, keep these invariants explicit:

- improvement proposals are still normal `ReactionProposal` objects
- accepted improvements rebuild into plain reaction configs, not a second runtime layer
- v1 default is conversion semantics:
  - create/update target reaction
  - remove or replace source reaction
- the source reaction remains review-visible until acceptance

Required source/target fields for v1:

- `proposal_kind = "improvement"`
- `target_reaction_id`
- `target_reaction_type`
- `improves_reaction_type`
- `improvement_reason`

## Phase 1 — Proposal contract and engine plumbing

### Goal

Teach the shared proposal model and `ProposalEngine` to represent improvement proposals
without adding a new persisted status machine.

### Work

1. extend `ReactionProposal` serialization/deserialization with optional improvement metadata
2. keep backward compatibility for existing stored proposals
3. add proposal-kind-aware diagnostics summaries:
   - discovery count
   - refinement count
   - improvement count
4. ensure proposal sensor/diagnostics stay compact

### Acceptance

- old proposals still load
- new improvement metadata persists cleanly
- diagnostics distinguish improvement proposals from discovery/refinement

## Phase 2 — Lifecycle identity for improvement proposals

### Goal

Make improvement proposals deduplicate and refresh correctly.

### Work

1. extend plugin lifecycle hooks or helper factories with an improvement identity convention
2. define identity for the first family:
   - `improvement|room=<room_id>|from=room_darkness_lighting_assist|to=room_contextual_lighting_assist`
3. ensure pending improvement proposals refresh in place
4. ensure accepted improvement proposals do not reopen as pending

### Acceptance

- rerunning the analyzer refreshes the same pending improvement proposal
- no duplicate improvement proposals appear for the same source slot

## Phase 3 — First concrete analyzer: darkness -> contextual candidate

### Goal

Emit a real improvement proposal when a darkness reaction exists but observed behavior suggests
contextual variants are warranted.

### First bounded heuristic

Do not attempt deep inference initially.

Use explicit, debuggable evidence only:

- an accepted or admin-authored `room_darkness_lighting_assist` already exists
- observed user-driven lighting follow-ups in that room show materially different scene choices
  across:
  - distinct time windows
  - distinct `house_state`
  - or both
- simple brightness/kelvin tuning is no longer enough to explain the variation

### Work

1. add a bounded analyzer or analyzer extension inside the composite/lighting learning family
2. read accepted/configured darkness reactions as eligible sources
3. produce an improvement proposal targeting `room_contextual_lighting_assist`
4. generate a safe seed contract:
   - carried-over trigger fields
   - carried-over target lights
   - preset-backed or one-profile baseline contextual contract
5. emit diagnostics:
   - source reaction id
   - evidence dimensions (`time_window_variation`, `house_state_variation`)
   - chosen preset/seed strategy

### Acceptance

- with sufficient evidence, one improvement proposal is emitted
- without sufficient evidence, none is emitted
- the learned darkness proposal path remains unchanged

## Phase 4 — Review wording and UX

### Goal

Make improvement proposals legible and distinguishable in review.

### Work

1. add proposal review wording for:
   - source reaction family
   - target reaction family
   - improvement reason
2. show clear conversion intent:
   - “upgrade this reaction”
   - not “new automation”
3. show enough contract detail for the target contextual policy:
   - preset or profile summary
   - target lights
   - trigger bucket

### Acceptance

- options flow review clearly distinguishes improvement from discovery/refinement
- admins can understand what will be replaced and with what

## Phase 5 — Acceptance semantics: conversion

### Goal

Make accepting the first improvement proposal perform a deterministic conversion.

### Work

1. extend proposal acceptance handling for `proposal_kind = improvement`
2. first family semantics:
   - create configured `room_contextual_lighting_assist`
   - remove the source `room_darkness_lighting_assist`
3. preserve provenance:
   - source proposal / source reaction linkage
4. ensure atomicity:
   - no “accepted but source still active and target half-persisted” state

### Acceptance

- accepting the proposal results in one active contextual reaction
- the old darkness reaction is removed from `configured`
- runtime rebuild succeeds after reload

## Phase 6 — Runtime rebuild, diagnostics, and edit surfaces

### Goal

Make the converted target reaction behave like any other first-class configured reaction.

### Work

1. ensure rebuild from persisted improvement-produced config is identical to normal contextual config
2. diagnostics should keep visible:
   - origin = learned/improvement
   - source reaction linkage where useful
3. edit flow should operate on the resulting contextual reaction normally

### Acceptance

- converted contextual reactions are indistinguishable from other configured contextual reactions at runtime
- provenance remains visible where it helps review/debug

## Phase 7 — Tests for the first family

### Required test layers

1. unit tests
   - proposal identity
   - seed contract generation
   - conversion acceptance logic
2. proposal engine tests
   - refresh, dedup, no reopening
3. options flow tests
   - review wording
   - accept conversion path
4. rebuild/runtime tests
   - converted contextual reaction rebuilds and executes

### Stretch tests

- live lab flow for a handcrafted darkness -> contextual upgrade

## Phase 7b — Live end-to-end verification

### Goal

Verify the first improvement family against the HA test lab, not only via unit and options-flow tests.

### Required live checks

1. seed state
   - an accepted/configured `room_darkness_lighting_assist` exists in the target room
   - no contextual reaction exists yet for the same room slot
2. learned evidence
   - inject or replay sufficient evidence so the improvement proposal becomes pending
3. review path
   - verify the options flow surfaces the proposal as an upgrade/conversion, not a new discovery
4. acceptance path
   - accept the proposal
   - verify:
     - contextual reaction appears in `configured`
     - source darkness reaction is removed/replaced
5. runtime path
   - trigger the room under darkness conditions
   - verify the contextual reaction actually fires and applies a profile

### Deliverables

- one or more live scripts under `scripts/live_tests/`
- recovery/setup support in the test lab if needed
- documentation of the expected diagnostics checkpoints

## Phase 8 — Generalization pass

### Goal

Extract the reusable framework from the first family without prematurely over-designing it.

### Work

1. introduce a plugin-owned improvement descriptor or helper contract
   - source family
   - target family
   - identity helper
   - seed builder
   - acceptance strategy
2. keep lifecycle ownership plugin-local, not in `ProposalEngine` hardcoded branches
3. make presenter hooks capable of rendering improvement reviews generically
4. define a small acceptance-strategy interface:
   - `convert_replace`
   - future room for `convert_disable_old`
   - future room for `coexist`

### Acceptance

- a second future improvement family can plug in without copying the darkness/contextual path
- `ProposalEngine` stays generic

## Phase 9 — Candidate next families

These should come only after the framework is extracted:

- `room_signal_assist` -> richer contextual/compound variant, if such a family becomes real
- simple learned lighting schedule -> darkness/context-aware room lighting assist, where product policy supports that
- future admin-authored templates whose active reactions routinely attract structural follow-ups rather than mere tuning

## Risks

### 1. Over-detecting upgrades

Risk:
- Heima proposes contextual upgrades too eagerly

Mitigation:
- start with conservative evidence thresholds
- require an existing active darkness reaction
- require variation across more than one contextual dimension

### 2. Confusing review semantics

Risk:
- admins mistake improvement proposals for new independent automations

Mitigation:
- explicit “upgrade / replace” wording
- show source reaction id and family

### 3. Acceptance race / partial state

Risk:
- target reaction is created but source remains active or vice versa

Mitigation:
- keep acceptance atomic in one config mutation path
- test failure cases explicitly

### 4. Premature abstraction

Risk:
- building a generic improvement framework before the first family proves the right shape

Mitigation:
- phases 1-7 stay concrete and family-specific
- generalization only in phase 8

## Recommended implementation order

1. Phase 1 — contract + engine plumbing
2. Phase 2 — lifecycle identity
3. Phase 3 — darkness -> contextual analyzer
4. Phase 4 — review wording
5. Phase 5 — acceptance conversion
6. Phase 6 — rebuild/diagnostics/edit polish
7. Phase 7 — full tests
8. Phase 7b — live end-to-end verification
9. Phase 8 — generalized improvement framework

## Exit criteria

This plan is complete when:

1. Heima can emit a real improvement proposal converting darkness to contextual
2. the proposal is reviewable and clearly marked as an upgrade
3. accepting it converts the active reaction deterministically
4. the infrastructure is then extracted so future improvement families can reuse the same mechanism
