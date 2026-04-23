# Context-Conditioned Lighting Learning Spec

## Status

Implemented on `main`.

## Problem

Heima already records strong contextual signals through:

- `rooms[*].learning_sources`
- `learning.context_signal_entities`

These signals are meant to be a shared substrate for learning, not a domain-specific shortcut.

Today this substrate is underused for learned lighting proposals:

- `LightingPatternAnalyzer` mainly learns `lighting_scene_schedule`
- composite room-lighting learning uses hardcoded room signals such as `room_lux`
- strong context signals like projector / TV / console state are recorded, but they do not
  materially shape the learned lighting proposal family

This creates a product mismatch:

- users expect Heima to learn “when this context is active, use this lighting scene”
- the current system mostly learns “at this weekday/time, replay this lighting scene”

That is the wrong abstraction for many real homes.

## Goal

Allow learned lighting proposals to depend on **abstract context conditions** derived from strong
context signals, without introducing domain-specific families such as `media_*`.

The key design rule is:

- context is an orthogonal explanatory dimension
- not a new proposal family axis per device category

## Non-goals

- no dedicated `projector_lighting_assist` or `tv_lighting_assist` family
- no raw per-integration logic in analyzers
- no requirement to expose low-level context entity internals in end-user labels
- no attempt to solve arbitrary multi-condition causal inference in v1

## Core model

### Context conditions

A learned lighting proposal may carry an optional bounded list of abstract context conditions:

```yaml
context_conditions:
  - signal_name: projector_context
    state_in: ["active"]
```

Minimal v1 shape:

- `signal_name: str`
- `state_in: list[str]`

Normative constraints:

- `signal_name` MUST refer to a canonicalized context signal, not a raw HA entity label
- `state_in` MUST be bounded, explicit, and finite
- empty `context_conditions` means the proposal is not context-scoped

### Canonical signal abstraction

The abstraction layer MUST remain:

- generic
- bounded
- reusable across lighting and future families

Examples of acceptable canonical signal names:

- `projector_context`
- `media_context`
- `desk_mode`
- `tv_context`

Examples of canonicalized states:

- `active`
- `inactive`
- `idle`
- `background`

The product contract is intentionally abstract:

- analyzers reason about canonical signal names and bounded states
- mapping from HA entities to those canonical names belongs to the normalization / context layer

## Product semantics

### What Heima should learn

Heima should be able to distinguish between:

- a fixed scheduled scene
- a room-darkness assist
- a context-conditioned scene

Example:

- every evening the user turns on a projector
- then turns on two lights and turns off the rest

The preferred learned meaning is:

- “when projector context is active in this room, apply this lighting scene”

Not:

- “every weekday around 21:00, replay this scene”

unless the evidence is better explained by time than by context.

### Preference order for learned lighting explanations

For ordinary room lighting, Heima SHOULD prefer explanations in this order:

1. room-aware contextual reaction
2. room-darkness reaction
3. pure scheduled replay

This is a product preference, not a hard guarantee.

The analyzer may still emit `lighting_scene_schedule` when:

- the pattern is genuinely schedule-owned
- occupancy / darkness evidence is weak
- context-signal separation is weak

## V1 scope

V1 should stay deliberately bounded.

### In scope

- context-conditioned learned lighting proposals
- abstract `context_conditions` contract
- analyzer logic that can prefer a context-conditioned explanation over pure schedule replay
- review UX that explains the context scope clearly
- lifecycle identity that treats context scope as part of the logical proposal identity

### Out of scope

- arbitrary boolean expressions over many context signals
- generic multi-family context-conditioned learning across every reaction family
- user-authored editing of `context_conditions` in options flow
- improvement proposal automation from `lighting_scene_schedule` to context-conditioned lighting
  in the first slice

## Proposal family direction

This RFC does **not** require a new media-specific family.

It does require a learned lighting family that can express context-scoped scenes.

Two acceptable implementation directions:

1. introduce a generic learned family such as `contextual_lighting_scene`
2. extend an existing richer room-lighting family to accept `context_conditions`

Product preference:

- prefer a generic context-capable lighting family
- avoid naming or scoping the family around media/projector specifically

## Analyzer behavior

### Candidate generation

When repeated lighting sequences are observed, the analyzer SHOULD evaluate whether the sequence is:

- primarily time-owned
- primarily darkness/occupancy-owned
- or better explained by one or more context conditions

### Minimum useful v1 heuristic

The first implementation does not need full causal inference.

A sufficient heuristic is:

1. detect a stable lighting scene candidate
2. inspect the bounded context signals observed around those episodes
3. identify context signals whose active state is strongly concentrated in the positive episodes
4. if that context signal materially improves separation from nearby non-matching episodes,
   prefer a context-conditioned proposal

### Negative evidence requirement

To avoid noise, context-conditioned proposals MUST express contrast between episodes where the
context signal was active versus inactive.

Two quantities are required:

**Concentration** — fraction of scene episodes where the context signal was active:

```
concentration(signal, scene) = |episodes(scene ∧ context_active)| / |episodes(scene)|
```

Normative default: `min_concentration = 0.65` (configurable).

**Lift** — how much more likely the scene is when context is active than when inactive:

```
lift(signal, scene) = P(scene | context_active) / P(scene | context_inactive)
```

Normative default: `min_lift = 2.0` (configurable).

Both thresholds MUST be exceeded for the proposal to be emitted as context-conditioned.

#### Contrast availability

Lift requires observations in the context-inactive window. These may not exist when the context
signal is highly correlated with the user's routine (e.g. projector is always on in the evening).

The analyzer MUST count `negative_episode_count`: episodes within the plausible time window where
the context signal was inactive, regardless of whether the scene occurred.

Normative default: `min_negative_episodes = 3` (configurable).

If `negative_episode_count < min_negative_episodes`, lift is uncomputable. In this case:

- the analyzer MAY still emit a context-conditioned proposal if `concentration ≥ min_concentration`
- the proposal MUST carry `contrast_status: unverified`
- `contrast_status: unverified` MUST be exposed in diagnostics and review UX

If `negative_episode_count ≥ min_negative_episodes` and both thresholds are met:

- the proposal carries `contrast_status: verified`

If `negative_episode_count ≥ min_negative_episodes` and lift is below threshold:

- the context signal does not provide sufficient separation
- the analyzer SHOULD prefer a scheduled or darkness explanation instead

## Identity and lifecycle

For context-conditioned learned lighting, lifecycle identity SHOULD include context scope.

Illustrative identity shape:

```text
contextual_lighting_scene|room=<room_id>|context=<normalized_context_signature>|scene=<scene_signature>
```

Where `normalized_context_signature` is a stable encoding of:

- `signal_name`
- normalized allowed states

Rationale:

- unlike composite `house_state`, context scope here is not just a tuning dimension by default
- removing it from identity would collapse materially different learned meanings

## Review UX

Proposal review MUST make the context scope explicit.

Minimum useful detail lines:

- room
- context condition(s)
- affected lights
- on/off composition
- observed time pattern, when relevant

Example wording:

- `Context: projector_context in [active]`
- `Scene: 2 lights on, 4 lights off`

## Diagnostics

Learned context-conditioned proposals SHOULD expose:

- context signals considered
- selected context conditions
- `concentration` score
- `lift` score (or `null` if uncomputable)
- `negative_episode_count`
- `contrast_status`: `verified` | `unverified`
- competing explanation type:
  - `schedule`
  - `darkness`
  - `context`

## Migration / coexistence

Initial rollout MAY coexist with:

- `lighting_scene_schedule`
- `room_darkness_lighting_assist`

but analyzer policy SHOULD avoid emitting a weaker scheduled proposal when a stronger
context-conditioned explanation exists for the same evidence window.

## Acceptance criteria

The first production slice is acceptable when:

1. a repeated projector-like context pattern can produce a learned lighting proposal without any
   media-specific family name
2. the proposal contract uses abstract `context_conditions`
3. review UX shows the context scope clearly
4. scheduled replay is suppressed when the same evidence is better explained by the context signal
5. the implementation remains generic enough to reuse the same context substrate for future
   non-media context signals
