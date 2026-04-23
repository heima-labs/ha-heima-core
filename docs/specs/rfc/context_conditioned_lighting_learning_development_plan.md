# Context-Conditioned Lighting Learning Development Plan

## Goal

Teach Heima to learn lighting behavior conditioned by abstract context signals, using:

- canonical context signals
- abstract `context_conditions`
- explicit negative-evidence scoring

without introducing media-specific reaction families.

This plan assumes the RFC direction in:

- [../learning/context_conditioned_lighting_learning_spec.md](../learning/context_conditioned_lighting_learning_spec.md)

## Product target

Heima should be able to learn:

- “when this abstract context is active, apply this lighting scene”

instead of falling back to:

- “at this time, replay this scene”

when the evidence is better explained by context.

## Non-goals

- no raw device-specific projector / TV family
- no full generic context-conditioned learning across all reaction families in v1
- no free-form boolean expression editor for context rules
- no migration of every historical lighting proposal family in the first slice

## Phase 1 — Contract and scoring substrate

### Scope

Introduce the data contracts and the scoring helper layer without yet changing the default analyzer
output.

### Deliverables

1. Context condition contract

Suggested v1 shape:

```yaml
context_conditions:
  - signal_name: projector_context
    state_in: ["active"]
```

2. Scoring result contract

Suggested v1 shape:

```yaml
context_signal_score:
  signal_name: projector_context
  state_in: ["active"]
  concentration: 0.78
  lift: 2.4
  negative_episode_count: 6
  contrast_status: verified
```

3. Configurable thresholds

Introduce defaults in code and diagnostics:

- `context_condition_min_concentration = 0.65`
- `context_condition_min_lift = 2.0`
- `context_condition_min_negative_episodes = 3`

### Rules

- a context-conditioned candidate is considered contrast-verified only if:
  - `concentration >= min_concentration`
  - `lift >= min_lift`
  - `negative_episode_count >= min_negative_episodes`
- if `negative_episode_count < min_negative_episodes`, the proposal may still be emitted with:
  - `contrast_status = "unverified"`
  - `lift = null`

### Tests

- pure unit tests for:
  - concentration calculation
  - lift calculation
  - insufficient negatives
  - ordering/tie handling

## Phase 2 — Context extraction for lighting candidates

### Scope

Given a learned lighting scene candidate, extract the bounded context evidence around its positive
episodes and comparable negative episodes.

### Deliverables

1. Positive episode context extraction

For each scene candidate episode:

- read canonical context signal states from the event context
- build a bounded frequency table by `signal_name -> state`

2. Negative episode selection

Pick comparable negative episodes from the same room/time neighborhood where:

- the learned lighting scene is absent or materially different
- the time window is close enough to remain comparable

This phase does not need perfect causal inference.
It does need bounded, reproducible sampling.

### Tests

- unit tests for negative-episode selection
- tests proving that unrelated room/time episodes are excluded

## Phase 3 — Context scoring and candidate promotion

### Scope

Add scoring logic that can decide whether a lighting scene should become context-conditioned.

### Deliverables

1. Candidate scoring helper

Input:

- positive episodes
- negative episodes
- context signal observations

Output:

- best context condition candidate(s)
- concentration
- lift or `null`
- negative count
- `contrast_status`

2. Promotion rule

If context evidence is strong enough:

- emit a context-conditioned learned lighting proposal

If not:

- keep existing learned lighting behavior

### Tests

- strong positive separation -> emits context-conditioned candidate
- insufficient negatives -> emits candidate with `contrast_status = unverified`
- weak concentration or weak lift -> does not promote

## Phase 4 — Proposal family integration

### Scope

Choose and wire the learned reaction family that will carry `context_conditions`.

### Preferred direction

Use a generic context-capable lighting family rather than a media-specific one.

This may be:

1. a new generic lighting family
2. or an extension of an existing richer lighting family

This decision should be made explicitly before implementation.

### Deliverables

1. lifecycle identity contract including context signature
2. proposal config shape including:
   - `context_conditions`
   - diagnostics block
3. review label/detail presenters

### Tests

- identity separates materially different context scopes
- identical context scopes refresh the same proposal

## Phase 5 — Analyzer integration and suppression rules

### Scope

Integrate the context scoring into learned lighting analysis and suppress weaker schedule proposals
when the context explanation is better.

### Deliverables

1. Analyzer integration

Likely integration point:

- `LightingPatternAnalyzer`

Optional secondary integration point later:

- richer room-lighting/composite path

2. Suppression policy

If a scene candidate has a stronger context-conditioned explanation:

- suppress weaker `lighting_scene_schedule` output for the same evidence window

### Tests

- schedule-only pattern -> still emits `lighting_scene_schedule`
- context-dominant pattern -> emits context-conditioned proposal
- context-dominant pattern -> suppresses weaker schedule replay

## Phase 6 — Review UX and diagnostics

### Scope

Make the proposal legible and debuggable.

### Deliverables

Review details must show:

- context condition
- concentration
- lift or `n/a`
- negative episode count
- contrast status
- scene summary

Diagnostics must expose:

- `context_conditions`
- `concentration`
- `lift`
- `negative_episode_count`
- `contrast_status`
- competing explanation type

### Tests

- diagnostics presence tests
- review placeholder/detail tests

## Phase 7 — Live E2E validation

### Scope

Verify the full path on HA-test with a real abstract context signal.

### Live test target

Simulate a room scenario like:

- context signal active
- learned lighting scene with mixed `on` and `off`
- repeated enough to generate a proposal

The live test should verify:

1. proposal appears
2. proposal is context-conditioned
3. diagnostics show:
   - `concentration`
   - `lift` or `null`
   - `negative_episode_count`
   - `contrast_status`
4. weaker `lighting_scene_schedule` is absent when context explanation is preferred

### Deliverables

- one dedicated live script
- optionally one fixture-seeded path if thresholds need historical evidence

## Phase 8 — Hardening and generalization

### Scope

After one real lighting case works, decide what should become reusable substrate for other families.

### Likely reusable pieces

- context scoring helper
- contrast diagnostics contract
- context identity signature builder
- negative-episode sampling helper

### Do not generalize yet

- family-specific proposal builders
- family-specific review copy
- family-specific suppression policy

Only extract what survives one real slice cleanly.

## Recommended implementation order

1. Phase 1 — contract and scoring substrate
2. Phase 2 — positive/negative context extraction
3. Phase 3 — promotion logic
4. Phase 4 — choose and wire target family
5. Phase 5 — analyzer integration + schedule suppression
6. Phase 6 — review UX + diagnostics
7. Phase 7 — live E2E
8. Phase 8 — reusable abstractions

## Risks

1. Too many noisy context proposals

Mitigation:

- bounded canonical states
- negative evidence requirement
- verified vs unverified contrast status

2. Incorrect negative episode sampling

Mitigation:

- narrow time/room comparison windows
- explicit unit tests

3. Over-suppressing valid scheduled lighting

Mitigation:

- suppression only when context explanation is materially stronger
- keep schedule path as fallback

4. Leaking raw entity-specific semantics into learned contracts

Mitigation:

- require canonical `signal_name`
- forbid raw HA entity ids in `context_conditions`

## Merge criteria for first production slice

The slice is merge-ready when:

1. one real context-conditioned lighting case works end-to-end
2. diagnostics expose the negative-evidence fields
3. `contrast_status = unverified` works correctly when negatives are insufficient
4. the learned contract stays abstract and not media-specific
5. schedule replay is not emitted when a clearly stronger context-conditioned explanation exists
