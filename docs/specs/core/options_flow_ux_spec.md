# Heima — Options Flow UX SPEC

**Status:** Active v1.x UX and persistence contract
**Created:** 2026-03-17
**Last Verified Against Code:** 2026-04-03

> Naming note:
> this document describes the current bounded Options Flow UX used on `main`.
> It is not a separate product-generation `v2` flow.

---

## Motivation

The v1 config flow had three main problems:

1. **No visibility of the current configuration** in the menus: the user didn't know what was configured without entering every sub-step.
2. **Confusing UX for the heating vacation curve**: branch type selector and parameters in the same form — changing the type required an intermediate submit to update the visible fields.
3. **Reactions menu silently empty**: after accepting a proposal in the config flow but before saving, the Reactions menu came out empty because `_get_registered_reaction_ids` only read the post-save engine, not the current session.

## Contract of this spec

This spec describes the user behavior and the persistence contract of the Options Flow.
It doesn't require reading the code to understand:
- which steps exist
- which data the user can configure
- when a change must be saved
- which runtime objects must be configurable or reconstructible after saving

Normative rule:
- the Options Flow is the source of truth for the user-configured profile
- the runtime must be able to fully reconstruct itself from the persisted payload produced by
  this flow

---

## Goals and non-goals

Goals:
- make the configured state visible without entering every sub-step
- allow incremental saves without losing profile consistency
- ensure accepted proposals produce reconstructible runtime configuration

Non-goals:
- describing internal interface rendering details beyond what's needed for the
  UX contract
- imposing a specific file or mixin organization for the flow

---

## Product decisions and contract

### D0 — Scheduled routine is bounded admin-authored intent

The options flow exposes one bounded admin-authored time-based routine template:

- `scheduled_routine.basic`

Normative UX rules:
- it represents explicit admin intent, not learned behavior
- create/edit MUST share the same schema and normalization core
- the visible fixed guardrails are only:
  - `house_state_in`
  - `skip_if_anyone_home`
- the flow MUST NOT expose:
  - arbitrary boolean conditions
  - arbitrary service payload builders
  - chained delayed steps

Wizard shape:
1. choose weekday
2. choose time
3. choose routine kind
4. choose bounded targets
5. optionally constrain:
   - allowed house states
   - skip if anyone home

Allowed `routine_kind` values in v1:
- `scene`
- `script`
- `entity_action`

Allowed target domains in v1:
- `scene`
- `script`
- `light`
- `switch`
- `input_boolean`

### D1 — Status block in the main menu (init)

The `init` menu shows a status block in the `description`, with one line per configurable section. Each line shows the section name and its current status.

**Format (a single `status_block` placeholder, multi-line text separated by `\n`):**
```
Motore: attivo
Persone (3): Stefano, Elena, Marco
Stanze (4): Soggiorno, Cucina, Studio, Camera
Illuminazione: 3/4 stanze
Riscaldamento: climate.termostato | 2 branch
Sicurezza: disabilitata
```

*(This example shows the actual Italian-language status block a resident sees on an
Italian-configured HA instance — see the `is_it` runtime localization mechanism; it's not
translated here since it's real UI output, not spec prose.)*

**Technical note:** HA does not support `description_placeholders` on individual `menu_options` entries — the entry text is static. The status block therefore goes in the menu's `description` via a single `{status_block}` placeholder.

### D2 — Configuration summary in second-level menus

Every second-level menu shows a summary of the current configuration via `description_placeholders`.

| Menu | Placeholder | Example |
|------|-------------|---------|
| `people_menu` | `summary` | `Configurate: 3: Stefano, Elena, Marco` |
| `rooms_menu` | `summary` | `Configurate: 4: Soggiorno, Cucina, Studio, Camera` |
| `lighting_rooms_menu` | `summary` | `Scene configurate: 3/4 stanze` |
| `heating_branches_menu` | `summary` | `climate.termostato \| 2 branch` |

### D3 — Heating branch: two-step flow

The configuration flow for a heating branch override was split:

1. `heating_branch_select` — shows only the branch type selector (`vacation_curve`, `fixed_temp`, `disabled`)
2. `heating_branch_edit_form` — shows only the parameters specific to the selected type (no branch selector)

If the selected branch is `disabled`, the parameters form is skipped and the flow returns directly to the menu.

### D4 — Reactions: engine merge + current session

The Reactions menu must show both:
1. reactions already reconstructed by the runtime
2. reactions accepted in the current session but not yet definitively saved

The persisted payload must include a readable label for accepted reactions, so the UI
can show them without depending on the already-reconstructed runtime.

### D5 — Proposal action configuration

After the user accepts one or more proposals in the `proposals` step, the flow does not immediately return to `init` but opens a new `proposal_configure_action` step for each accepted proposal (one at a time).

**Step `proposal_configure_action`:**

| Field | Type | Notes |
|-------|------|-------|
| `action_entities` | entity selector (`scene`, `script`), **multiple**, optional | The HA entities to activate when the reaction fires |
| `pre_condition_min` | positive integer, default 20 | Lead time in minutes relative to the typical time |

The proposal's description is shown via `description_placeholders: {proposal_description}`.

**Behavior:**
- If `action_entities` is set, they are normalized into steps executable by the runtime:
  - `scene.*` → `{"domain": "lighting", "target": entity_id, "action": "scene.turn_on", "params": {"entity_id": entity_id}}`
  - `script.*` → `{"domain": "script", "target": entity_id, "action": "script.turn_on", "params": {"entity_id": entity_id}}`
- If empty: `steps = []` — the reaction is registered with no action (configurable later)
- `pre_condition_min` overrides the default in the reaction's config

**Normalization contract:**
- the saved step must represent a request executable by the runtime, not a raw UI choice
- the persisted shape must be sufficient to reconstruct the reaction without depending on
  temporary UI session state
- accepting a proposal must never produce an "accepted but not executable" state

**Updated runtime note:**
- `scene.turn_on` still goes through `LightingDomain`; the runtime also marks a best-effort batch of the room/area's expected lights to improve multi-entity provenance in learning.
- `script.turn_on` is executable as a real runtime step; subsequently observed effects are attributed with batch-level provenance in a short window, as a less precise fallback than the `scene` case.

### D5.1 Provenance and correlation in the UX context

The Options Flow does not directly record learning events, but must produce configurations that
don't break the learning runtime's contracts.

Configuration rule:
- the `Rooms` flow defines the primary semantics of room-scoped entities
- the `Learning` flow only adds extra global signals and environmental bindings (`outdoor_*`,
  `weather_entity`, `context_signal_entities`)
- the learning runtime SHOULD therefore treat `rooms[*].learning_sources` as the base room-scoped
  learning source set, with `learning.context_signal_entities` as additive extras
- `rooms[*].occupancy_sources` and `rooms[*].learning_sources` must remain distinct concepts:
  - the former are used to understand whether the room is occupied
  - the latter are used to explain when a behavior tends to happen
- this separation avoids forcing the user to duplicate the same room modeling in multiple
  places in the UI

Signal quality rule:
- the fact that an entity appears in `rooms[*].learning_sources` does not imply it must be
  learned blindly
- the learning runtime SHOULD prefer only stable, already semantically normalized signals
- very noisy or purely impulsive entities can remain useful for occupancy without automatically
  becoming good inputs for richer inference

UX semantics rule:
- the UI SHOULD make the difference understandable between:
  - entities used to understand **when** a behavior happens
  - entities observed to understand **what** the user did
- canonical example:
  - `sensor.studio_lux` can be a learning trigger signal
  - `light.studio_main` can be a response observed by the lighting learner

- **Provenance**: the runtime must be able to distinguish between user-generated effects and
  Heima-generated effects, to avoid learning from its own output.
- **Correlation**: the runtime must be able to link multiple entity changes that belong to the same
  logical action, for example a scene or script that touches multiple lights.

For this reason, normalizing `action_entities` cannot just save a symbolic UI reference: it must
produce an executable step that goes through the normal runtime paths, so that provenance and
`correlation_id` can be correctly applied when the effects are observed.

Session contract:
- if multiple proposals are accepted together, action configuration must happen one
  proposal at a time, in deterministic order
- the flow's session must be able to hold this intermediate state without requiring the runtime
  to already be reconstructed

Persistence contract:
- the final save must update `configured[proposal_id]["steps"]`
- the final save must update `configured[proposal_id]["pre_condition_min"]`
- these fields must be sufficient to reconstruct the reaction without re-reading the UI session

Future extension point:
- a proposal MAY in the future expose multiple `acceptance modes`
- each mode would represent a different supported way to make the same learned behavior concrete
- v1's UX must not assume this yet; today the flow handles only one effective acceptance path per
  proposal

### D5.2 — Proposal review details must expose concrete affected entities

The `proposals` step is an administrative decision surface, not a simple summary.

Normative rule:
- when the proposal or the tuning target involve `entity_steps`, the `proposal_details` body
  MUST make the concrete entities involved visible
- a simple count, e.g. `Luci proposte: 3`, is not sufficient as the sole decision detail

For discovery proposals with `entity_steps`, the review SHOULD show at least:
- proposed entities
- an optional count as a secondary summary

For tuning/follow-up proposals with `entity_steps`, the review MUST show at least:
- current entities
- proposed entities
- added entities, if any
- removed entities, if any

If the same entity is present in both the current and the proposed payload, and material step
fields change, the review SHOULD also show the per-entity delta of the relevant fields:
- `action`
- `brightness`
- `color_temp_kelvin`
- `rgb_color`

This rule applies at least to the lighting/composite families that use `entity_steps`, including:
- `context_conditioned_lighting_scene`
- `room_darkness_lighting_assist`
- `room_vacancy_lighting_off`

Interpretation rule:
- if a reaction-specific presenter produces a body that shows only cardinality and not entity
  identity or delta, the implementation should be considered incomplete relative to the v1.x UX
  review.

---

## Invariants

- the Options Flow's persisted payload is self-sufficient to reconstruct the runtime
- a UI choice must not be persisted in an ambiguous or non-executable form
- the UI can show unsaved session state, but must not confuse it with runtime state
- accepting a proposal and configuring it must be atomically traceable to a coherent
  persisted payload

---

## Implementation status

| # | Description | Status |
|---|-------------|-------|
| TODO-1 | Status block in `init` with per-section separate placeholders | ✓ done |
| TODO-2 | `_update_options(updates)` — immediate memory + disk update | ✓ done |
| TODO-3 | Selective reload in `_async_entry_updated` via `STRUCTURAL_OPTION_KEYS` | ✓ done |
| TODO-4 | Save-per-step for structural keys (people, rooms, lighting) | ✓ done |
| TODO-5 | Readable reaction label in the mute multi_select + saved to `labels` | ✓ done |
| TODO-6 | `proposal_configure_action` — action configuration for an accepted proposal | ✓ done |

---

## Out of scope

- Adding new steps or domains
- Backward compatibility with previous entry versions
- Turning `scheduled_routine` into a generic automation builder
