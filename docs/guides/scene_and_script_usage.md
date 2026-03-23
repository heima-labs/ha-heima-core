# Heima Guide: Using `scene.turn_on` and `script.turn_on`

This guide explains how `scene.*` and `script.*` actions behave in Heima today, when to use each
one, and what the learning/runtime can trace reliably.

This is an operational guide, not a normative spec.

For the normative contracts, see:
- [`docs/specs/core/options_flow_ux_v2_spec.md`](../specs/core/options_flow_ux_v2_spec.md)
- [`docs/specs/learning/learning_system_spec.md`](../specs/learning/learning_system_spec.md)

## 1. The short version

Use `scene.*` when:
- you want to apply a lighting scene
- the behavior is mostly about lights in one room/area
- you want the strongest provenance and learning friendliness currently available

Use `script.*` when:
- you need a more advanced sequence
- the action touches multiple domains or non-light entities
- a scene is too limited for the behavior you want

If both would work, prefer `scene.*`.

## 2. What Heima does with them

When a proposal is accepted or a reaction is configured with action entities:
- `scene.*` is normalized to a runtime step using `scene.turn_on`
- `script.*` is normalized to a runtime step using `script.turn_on`

At runtime, Heima also tracks short-lived provenance batches so recorder behaviors do not learn
from Heima-caused follow-up changes as if they were user actions.

## 3. Why `scene.*` is preferred when possible

`scene.turn_on` has better provenance today.

Current behavior:
- it still executes through the lighting runtime path
- Heima creates an explicit short-lived scene batch
- if Home Assistant exposes scene member entities via the scene state, Heima uses those concrete
  light entities as expected subjects
- otherwise Heima falls back to the room-scoped light entities for that room/area

Practical effect:
- lighting follow-up state changes caused by the scene are less likely to be relearned as user
  behavior
- multi-light routines are better supported

## 4. What `script.*` is good for

`script.turn_on` is the flexible option.

Use it when:
- you need to touch fan, switch, cover, climate, script chains, or mixed domain actions
- you need conditional logic inside Home Assistant
- you need a sequence that is not well expressed as a pure scene

Current provenance behavior:
- Heima creates a short-lived `ScriptApplyBatch`
- the batch may include:
  - `room_id`
  - `expected_domains`
  - `expected_subject_ids`
  - `origin_reaction_id`
  - `origin_reaction_class`
- recorder behaviors use that batch to avoid misclassifying immediate follow-up changes as
  `source="user"`

Practical limitation:
- script provenance is still best-effort
- Heima does not fully introspect arbitrary Home Assistant scripts into a perfect concrete action
  graph

## 5. Decision rule

Use this rule:

1. If the behavior is a room-scoped lighting scene, use `scene.*`.
2. If the behavior needs multi-domain logic or procedural logic, use `script.*`.
3. If a script only wraps a simple room lighting scene, consider replacing it with `scene.*`.

## 6. Good patterns

Good `scene.*` examples:
- living room evening scene
- studio focus scene
- bedroom night scene

Good `script.*` examples:
- bathroom assist: fan + delay + follow-up actions
- cooling assist: fan + cover + optional climate step
- mixed-domain room recovery or shutdown sequence

## 7. Anti-patterns

Avoid these when possible:
- using `script.*` for a pure room lighting scene that could be a `scene.*`
- very large scripts touching many unrelated rooms when you expect precise learning provenance
- hidden side effects inside scripts that make it hard to reason about expected affected entities

## 8. Learning implications

Heima tries to learn from user behavior, not from its own outputs.

Today:
- `scene.*` is the strongest option for lighting-related learning compatibility
- `script.*` is useful and supported, but still less precise than `scene.*`
- heating uses a separate domain-specific attribution rule based on observed thermostat state, even
  though it now exposes compatible provenance metadata in diagnostics

## 9. Troubleshooting

If a behavior is being relearned incorrectly:
- check whether a `script.*` can be replaced with `scene.*`
- inspect diagnostics for recent apply provenance
- verify the room mapping is correct
- verify the entities touched by the action belong to the expected room or domain scope

Useful diagnostics:
- `scripts/diagnostics.py --section engine`
- `scripts/diagnostics.py --section plugins`
- `scripts/diagnostics.py --section event_store`

## 10. Current boundary

Heima supports:
- executable `scene.turn_on`
- executable `script.turn_on`
- short-lived provenance for both
- explicit scene batches for lighting
- explicit script batches with room/domain/subject scope

Heima does not yet guarantee:
- perfect introspection of arbitrary Home Assistant scripts
- perfect entity expansion for every scene/script path
- a general batch lifecycle engine beyond the current short-lived provenance window
