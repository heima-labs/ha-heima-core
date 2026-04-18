# Improvement Proposals RFC

## Status

Draft

## Problem

Heima already distinguishes well between:

- a newly learned behavior that should surface as a new proposal
- an existing active reaction that should receive a tuning follow-up

What is still underspecified is a third category:

- a reaction that is fundamentally valid, but no longer the best abstraction for the observed
  behavior

Example:

- Heima learns a stable `room_darkness_lighting_assist` in `studio`
- later evidence shows that the room is used in clearly different contexts across time windows or
  house states
- the right next step is not "tune brightness by 10" and not "create a second darkness reaction"
- the right next step is: propose a richer reaction family such as
  `room_contextual_lighting_assist`

Without an explicit model for this, the system tends to oscillate between:

- duplicate discovery proposals
- overly narrow tuning proposals
- human-only manual upgrades that Heima could have suggested

## Goal

Define a bounded v1 concept of **improvement proposal**:

- derived from learned evidence
- attached to an existing accepted or authored reaction
- proposing a better reaction shape, not just parameter drift
- still flowing through the existing proposal/reaction review pipeline

## Non-goals

This RFC does not introduce:

- a new runtime execution layer
- free-form AI-generated automations
- autonomous replacement of accepted reactions without review
- a generic graph of reaction upgrades between every family

## Proposal Taxonomy

Heima v1 should treat proposal intent as one of:

- **discovery**
  - no active reaction owns the observed behavior slot
  - result: propose a new reaction
- **refinement**
  - an active reaction already owns the slot
  - result: propose a bounded tuning or follow-up
- **improvement**
  - an active reaction owns the slot and is still valid
  - but a different reaction family or richer contract would better express the learned behavior
  - result: propose a conversion or upgrade

This taxonomy is conceptual. It does not require a new persisted `status` enum.

## Core Model

An improvement proposal remains a normal `ReactionProposal`.

Required semantics:

- it MUST identify the current target reaction or reaction slot
- it MUST declare the target reaction family it proposes
- it MUST carry a complete executable suggested config for that target family
- it MUST preserve provenance showing that the proposal is an improvement over an existing reaction,
  not a fresh unrelated discovery

Recommended metadata:

- `proposal_kind = "improvement"`
- `target_reaction_id`
- `target_reaction_type`
- `improves_reaction_type`
- `improvement_reason`

These are proposal metadata and diagnostics concepts. They do not require a second runtime model.

## Review Semantics

Improvement proposals must review differently from discovery:

- discovery wording:
  - "new learned automation"
- refinement wording:
  - "suggested adjustment"
- improvement wording:
  - "suggested upgrade" or "suggested conversion"

The review must make explicit:

- what existing reaction is being improved
- what new reaction family is proposed
- whether the outcome is intended to replace or coexist with the current reaction

## Acceptance Semantics

Improvement proposals SHOULD default to **conversion semantics**, not coexistence semantics.

That means:

1. accepting the proposal creates or updates the target reaction config
2. the old reaction is disabled, removed, or explicitly marked superseded by the accepted upgrade

For v1, the simplest acceptable implementation is:

- create the target reaction
- remove the source reaction from `configured`

The operation must remain review-driven and deterministic.

## First Concrete Family

The first concrete improvement proposal should be:

- `room_darkness_lighting_assist` -> `room_contextual_lighting_assist`

When it should be considered:

- an accepted or authored darkness assist already exists
- repeated learned evidence shows materially different preferred scenes across:
  - time windows
  - house states
  - or both
- simple tuning is no longer enough to express the pattern

Suggested seed behavior:

- carry over:
  - `room_id`
  - `primary_signal_name`
  - `primary_bucket`
  - `primary_bucket_match_mode`
  - target lights from current `entity_steps`
- generate:
  - a bounded preset-backed contextual contract
  - or a one-profile baseline contextual contract if evidence is still weak

## Why This Is Better Than Direct Learned Contextual Discovery

Direct learned contextual discovery is attractive, but riskier:

- it requires stronger inference about policy shape
- it hides the upgrade path from the user
- it makes debugging harder because the system jumps directly to a richer family

Improvement proposals are safer because:

- the observed simple pattern is still learned first
- the richer proposal is attached to an already understandable base reaction
- the user can reason about the upgrade in concrete terms

## Lifecycle Guidance

Improvement proposals should reuse the normal lifecycle rules:

- deduplicate by identity
- refresh evidence in place while pending
- suppress near-duplicate follow-ups

But their identity should include:

- source slot
- source reaction family
- target reaction family

Example conceptual identity:

- `improvement|room=studio|from=room_darkness_lighting_assist|to=room_contextual_lighting_assist`

## Diagnostics Guidance

Diagnostics for an improvement proposal should show:

- source reaction id and type
- target reaction type
- improvement reason summary
- evidence dimensions that triggered the upgrade
  - e.g. `house_state_variation`, `time_window_variation`

## Acceptance Criteria

This RFC is complete when:

1. Heima can express a proposal as an improvement over an existing accepted reaction
2. review wording distinguishes discovery vs refinement vs improvement
3. accepting the first improvement family can convert a darkness assist into contextual lighting
4. no separate runtime execution engine is introduced

