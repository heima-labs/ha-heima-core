# Learning Plugin Status

## Purpose

This document is the current-state reference for the plugin-oriented learning and reaction model.

It answers four questions:
- what the target architecture is
- what is already implemented
- what is still intentionally incomplete
- what the next recommended development steps are

This document is intentionally shorter and more operational than the full specifications.

## Target Architecture

Heima has:
- one shared `Learning System`
- one shared `Reaction System`
- one shared event substrate
- one shared proposal/acceptance pipeline

Extensibility is expressed through two built-in plugin concepts:

1. `Learning Pattern Plugin`
- learns one family of recurring behavior from the shared event substrate
- emits one or more reviewable proposal types
- targets one or more reaction targets

2. `Reaction Plugin`
- rebuilds an accepted proposal/config into executable runtime behavior
- evaluates history at runtime
- contributes steps to the shared apply plan

The current model is **built-in registry only**.
It is intentionally not a dynamic third-party plugin system.

## Current State

### Implemented

Shared learning/runtime substrate:
- generic persisted learning-event envelope
- source attribution and correlation support
- proposal persistence and dedup
- proposal acceptance -> configured reaction rebuild path
- runtime constraint-layer execution shared by domain steps and reaction steps

Built-in Learning Pattern Plugins:
- `builtin.presence_preheat`
- `builtin.heating_preferences`
- `builtin.lighting_routines`
- `builtin.composite_room_assist`

Built-in Reaction Plugins:
- `PresencePatternReaction`
- `LightingScheduleReaction`
- `HeatingPreferenceReaction`
- `HeatingEcoReaction`
- `RoomSignalAssistReaction`

Composite Pattern Engine v1.1:
- S1: declarative composite pattern catalog
- S2: catalog-driven composite analyzer path
- S3: normalized runtime/rebuild contract for `RoomSignalAssistReaction`
- S4: stable `learning_diagnostics` in proposal payloads
- current built-in composite plugins:
  - `room_signal_assist`
  - `room_cooling_assist`
  - `room_air_quality_assist`

Plugin-oriented wiring:
- coordinator uses a built-in learning plugin registry
- engine rebuild uses a built-in reaction plugin builder registry
- minimal plugin metadata exists for both learning and reaction registries

Diagnostics / dev tooling:
- config-entry diagnostics expose `runtime.plugins`
- `scripts/diagnostics.py --section plugins` prints built-in plugin metadata

Verification:
- unit suite green
- live lab `--tier all` green at the time this document was updated

## What Is Still Incomplete

These items are still open by design:

1. Stronger scene/script provenance
- scene/script effects are improved, including room-scoped script attribution when a reaction source exposes
  room diagnostics, but not yet expanded into perfectly reliable concrete entity batches in all cases
- the runtime now has a minimal `ScriptApplyBatch` contract for short-lived script provenance,
  but it is still intentionally lightweight and in-memory only
- current batch metadata are now reaction-aware and usable by both lighting and generic signal recorders,
  with room scope, expected domains, and expected subjects

2. Composite grouping beyond current heuristics
- composite matching still relies on room scope, windows, event context, and correlation metadata
- there is no richer episode/grouping engine yet

3. Plugin metadata are minimal
- enough for diagnostics and architecture clarity
- not yet a full manifest or capability system

4. Reaction builders still live in the engine
- the reaction registry exists
- but builder implementations are still methods on `HeimaEngine`

5. Learning plugin descriptors are not yet used for runtime feature toggles or selective enable/disable

## Current Boundary

The system is considered complete enough for the current milestone if:
- new learnable behaviors can be reasoned about as `Learning Pattern Plugins`
- accepted behaviors can be reasoned about as `Reaction Plugins`
- the registries and diagnostics make those concepts visible
- no additional framework complexity is introduced unless it unlocks a clear product capability

The system is **not** trying to support yet:
- dynamic external plugin loading
- arbitrary unsupervised discovery
- a universal grouping engine
- a full metadata-driven runtime container

## Recommended Next Steps

Priority order:

1. Decide whether to stop here on plugin infrastructure
- this is already a coherent minimal architecture

2. If continuing infrastructure work, move only one reaction builder out of the engine first
- preferred candidate: `RoomSignalAssistReaction`
- use it as a validation step before moving other builders

3. If returning to feature work, prefer one of:
- stronger scene/script provenance
- next behavior implemented as a new Learning Pattern Plugin
- refinement of plugin diagnostics and operator tooling

## Practical Rule Of Thumb

When adding a new behavior:

Ask first:
- is this just a new `Learning Pattern Plugin` on the existing substrate?
- can it target an existing `Reaction Plugin`?

If yes:
- extend the registries and reuse the framework

Only create a new subsystem if:
- the storage model,
- proposal model,
- or runtime execution model

would otherwise become materially more complex or misleading.
