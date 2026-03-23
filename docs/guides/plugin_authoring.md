# Heima Guide: Authoring Learning and Reaction Plugins

This guide explains how to add new behavior to Heima using the current plugin-oriented model.

This is a practical guide, not a normative spec.

For the normative contracts, see:
- [`docs/specs/learning/learning_system_spec.md`](../specs/learning/learning_system_spec.md)
- [`docs/specs/core/reactive_behavior_spec.md`](../specs/core/reactive_behavior_spec.md)
- [`docs/LEARNING_PLUGIN_STATUS.md`](../LEARNING_PLUGIN_STATUS.md)

## 1. The model

Heima has:
- one shared learning system
- one shared reaction system
- built-in registries for:
  - `Learning Pattern Plugins`
  - `Reaction Plugins`

A new behavior should normally be added as:
1. a new `Learning Pattern Plugin`
2. optionally targeting an existing `Reaction Plugin`
3. only if needed, a new `Reaction Plugin`

## 2. Decision rule before you write code

Ask these questions in order:

1. Is this just a new learnable pattern family on the existing event substrate?
- if yes, add a new `Learning Pattern Plugin`

2. Can the accepted behavior be executed by an existing reaction family?
- if yes, reuse an existing `Reaction Plugin`

3. Does it require a richer runtime contract than existing reactions support?
- only then add a new `Reaction Plugin`

4. Does it need a completely separate subsystem?
- only in exceptional cases

## 3. When to add only a Learning Pattern Plugin

Do this when:
- the runtime execution model already exists
- only the learned pattern is new
- an existing reaction can execute the accepted result

Examples:
- `room_air_quality_assist` reuses `RoomSignalAssistReaction`
- a new composite room-scoped assist should usually reuse the same reaction plugin first

## 4. When to add a new Reaction Plugin

Do this when:
- the accepted config contract is materially different
- the evaluate semantics are different
- the reaction needs different step-generation logic
- reusing an existing reaction would create awkward config shims or unclear behavior

Examples:
- `LightingScheduleReaction`
- `PresencePatternReaction`
- `RoomSignalAssistReaction`

## 5. Learning Pattern Plugin checklist

### 5.1 Implement the analyzer

Usually this means:
- add or extend an analyzer under
  [`custom_components/heima/runtime/analyzers/`](../../custom_components/heima/runtime/analyzers)
- implement the `IPatternAnalyzer` contract
- return `list[ReactionProposal]`

Good rules:
- keep `analyze()` read-only with respect to `EventStore`
- prefer deterministic logic
- keep proposal count small and explainable

### 5.2 Register the plugin

Update the built-in registry in:
- [`custom_components/heima/runtime/analyzers/__init__.py`](../../custom_components/heima/runtime/analyzers/__init__.py)

You usually need:
- a concrete analyzer in `builtin_learning_pattern_plugins()`
- a metadata entry in `builtin_learning_pattern_plugin_descriptors()`

Minimum metadata:
- `plugin_id`
- `analyzer_id`
- `plugin_family`
- `proposal_types`
- `reaction_targets`

### 5.3 If proposals must be reviewable, make the config explicit

A good proposal should make it clear:
- what pattern was learned
- what room/entities/signals were involved
- which reaction target it expects after acceptance

For composite plugins, keep diagnostics in `suggested_reaction_config["learning_diagnostics"]`.

### 5.4 Tests you should add

At minimum:
- analyzer unit tests
- proposal shape tests
- registry metadata tests if plugin descriptors change

Often also:
- rebuild/options path tests
- live lab tests if the behavior is important enough

## 6. Reaction Plugin checklist

### 6.1 Implement the reaction class

Usually under:
- [`custom_components/heima/runtime/reactions/`](../../custom_components/heima/runtime/reactions)

Your reaction should define:
- accepted config contract
- `evaluate(history)`
- step generation
- diagnostics

Rules:
- `evaluate()` should stay side-effect free
- generated steps must be executable by the shared runtime
- keep diagnostics meaningful

### 6.2 Register the builder

Update:
- [`custom_components/heima/runtime/reactions/__init__.py`](../../custom_components/heima/runtime/reactions/__init__.py)

You usually need:
- a builder in `builtin_reaction_plugin_builders()`
- a metadata entry in `builtin_reaction_plugin_descriptors()`

Minimum metadata:
- `reaction_class`
- `reaction_id_strategy`
- `supported_config_contracts`
- `supports_normalizer`

### 6.3 Rebuild path

A reaction plugin is not complete unless persisted config can rebuild it.

Today the builder registry is the main integration point.  
The engine still owns some concrete build logic, but the registry is the source of truth for what
reaction classes are supported.

### 6.4 Tests you should add

At minimum:
- direct reaction tests
- rebuild tests
- diagnostics tests if the reaction exposes new runtime state

## 7. How to choose between extending and creating

Prefer extending existing plugin families when:
- the semantics are clearly the same family
- the config contract remains understandable
- diagnostics stay easy to read

Create a new plugin when:
- matching semantics are materially different
- accepted config shape becomes unclear if merged
- reuse would hide important conceptual differences

## 8. Current built-in examples

Useful examples to copy from:

Learning plugins:
- [`PresencePatternAnalyzer`](../../custom_components/heima/runtime/analyzers/presence.py)
- [`LightingPatternAnalyzer`](../../custom_components/heima/runtime/analyzers/lighting.py)
- [`HeatingPatternAnalyzer`](../../custom_components/heima/runtime/analyzers/heating.py)
- [`CompositePatternCatalogAnalyzer`](../../custom_components/heima/runtime/analyzers/cross_domain.py)

Reaction plugins:
- [`PresencePatternReaction`](../../custom_components/heima/runtime/reactions/presence.py)
- [`LightingScheduleReaction`](../../custom_components/heima/runtime/reactions/lighting_schedule.py)
- [`RoomSignalAssistReaction`](../../custom_components/heima/runtime/reactions/signal_assist.py)
- [`HeatingPreferenceReaction`](../../custom_components/heima/runtime/reactions/heating.py)

## 9. Recommended workflow

Use this order:

1. Write or update the spec first.
2. Decide whether this is:
   - a new learning plugin
   - a new reaction plugin
   - or both
3. Implement the smallest useful behavior.
4. Register the plugin metadata.
5. Add focused unit tests.
6. Add live coverage only when the behavior matters enough to justify fixture complexity.
7. Update docs/checkpoint documents if the architecture meaningfully changed.

## 10. Anti-patterns

Avoid:
- adding a new subsystem when a plugin would do
- adding a new reaction class when an existing one already fits
- hiding important behavior differences behind generic names
- mixing guide text into the specs instead of linking the specs
- creating plugin metadata that is richer than what the runtime actually uses today

## 11. Current boundary

The current plugin model is intentionally simple:
- registries are built-in
- plugin metadata are minimal
- dynamic third-party loading is not part of the current runtime model

That is intentional. Prefer small, explicit extensions over building a general plugin platform too
early.
