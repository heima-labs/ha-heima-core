# Reaction Identity Spec
## `reaction_type` as canonical reaction key

**Status**: Active v1.x reaction identity contract
**Last Verified Against Code**: 2026-04-18

---

## Problem

Today every entry in `options.reactions.configured` carries two identity fields:

| Field | Example | Layer |
|---|---|---|
| `reaction_type` | `"room_darkness_lighting_assist"` | Proposal / learning |
| `reaction_class` | `"RoomLightingAssistReaction"` | Plugin registry / runtime |

This produces:
- Dual-path checks everywhere (`reaction_type == "X" or reaction_class == "Y"`)
- Ambiguity over which field to use in new code paths
- `reaction_class` exposed in diagnostics/UI as if it were a public contract
- Local debug tooling that has to guess which of the two fields is actually populated
- Higher risk of mismatch between:
  - config flow
  - runtime rebuild
  - diagnostics
  - debug scripts

---

## Solution

`reaction_type` becomes the **sole persisted identifier** in options.
`reaction_class` becomes an internal registry detail, not saved in `configured`.

### Post-reform invariants

1. `options.reactions.configured[id]["reaction_type"]` is always present and non-empty.
2. `reaction_class` never appears in `configured` for new entries.
3. The registry maps `reaction_type → builder` (not `reaction_class → builder`).
4. All dispatch (engine, config_flow, diagnostics) uses `reaction_type`.
5. Admin-authored and learned reactions share the same persisted format in `configured`.
6. `reaction_class` may still exist in memory in the registry or in Python code, but it is no
   longer a persistence contract field.

---

## N:1 case — multiple types, same implementation

Three `reaction_type` values currently share the same Python class:

| `reaction_type` | `reaction_class` (internal) |
|---|---|
| `room_signal_assist` | `RoomSignalAssistReaction` |
| `room_cooling_assist` | `RoomSignalAssistReaction` |
| `room_air_quality_assist` | `RoomSignalAssistReaction` |

## Active lighting reaction types (Phase AB)

| `reaction_type` | `reaction_class` (internal) | Note |
|---|---|---|
| `room_smart_lighting_assist` | `RoomSmartLightingAssistReaction` | Active — see `core/smart_lighting_assist_spec.md` |
| ~~`room_darkness_lighting_assist`~~ | ~~`RoomLightingAssistReaction`~~ | Removed Phase AB |
| ~~`room_contextual_lighting_assist`~~ | ~~`ContextualLightingAssistReaction`~~ | Removed Phase AB |

Post-reform, the registry has explicit entries for all three types, each with its own builder.
Builders can share the same Python implementation, but lookup happens by `reaction_type`.

---

## Changes per layer

### 1. `runtime/reactions/__init__.py` — ReactionPluginRegistry

**Before**: keyed by `reaction_class`
**After**: keyed by `reaction_type`

```python
# Plugin descriptor
@dataclass
class ReactionPluginDescriptor:
    reaction_type: str        # canonical key (e.g. "room_signal_assist")
    reaction_class: str       # internal Python name, used only for log/debug
    ...

# Registry lookup
def builder_for(self, reaction_type: str) -> ReactionPluginBuilder | None: ...
def presenter_for(self, reaction_type: str) -> ReactionPresenterHooks | None: ...
```

Explicit entries for the three N:1 types:
```python
RegisteredReactionPlugin(descriptor=ReactionPluginDescriptor(
    reaction_type="room_signal_assist",
    reaction_class="RoomSignalAssistReaction",
    ...
), builder=_build_room_signal_assist)

RegisteredReactionPlugin(descriptor=ReactionPluginDescriptor(
    reaction_type="room_cooling_assist",
    reaction_class="RoomSignalAssistReaction",  # same builder
    ...
), builder=_build_room_signal_assist)

RegisteredReactionPlugin(descriptor=ReactionPluginDescriptor(
    reaction_type="room_air_quality_assist",
    reaction_class="RoomSignalAssistReaction",  # same builder
    ...
), builder=_build_room_signal_assist)
```

### 2. `runtime/engine.py`

- `_rebuild_configured_reactions`: lookup via `cfg["reaction_type"]` instead of `cfg["reaction_class"]`
- `_configured_reaction_ids_by_type`: already uses `reaction_type`, no change
- `mute/unmute_reactions_by_type`: no change
- `heima_reactions_active` and runtime diagnostics expose `reaction_type` as the primary semantic key

### 3. `config_flow/_steps_reactions.py`

- Edit-form dispatch: from `reaction_class` to `reaction_type`
- `_configured_reaction_from_proposal`: removes `reaction_class` from the saved dict
- All dual-path checks eliminated: `reaction_type` only
- Direct admin-authored paths into `options.reactions.configured` always write `reaction_type`
- Presenter labels and UI groups use `reaction_type` as the canonical discriminant

### 4. `runtime/proposal_engine.py`

- Already uses `reaction_type` as the primary field. Remove `reaction_class` from the serialized
  proposal dict.

### 5. `diagnostics.py`

- All dual-path checks → `reaction_type` only
- Display and grouping already work on `reaction_type`

### 6. Local `debug/` scripts

- All local filters on reaction family use `reaction_type`
- If the live payload is legacy, scripts may apply a temporary `reaction_class -> reaction_type`
  fallback
- The fallback stays confined to the compat layer and is removed after the repo-wide migration

---

## Migration — existing data

Entries in `configured` already present in a live installation have `reaction_class` but may be
missing `reaction_type` (or have both).

**Strategy**: one-shot migration on first load post-deploy.

Backward-compat mapper (internal, used only during migration):

```python
_CLASS_TO_TYPE: dict[str, str] = {
    "LightingScheduleReaction": "lighting_scene_schedule",
    "ContextConditionedLightingReaction": "context_conditioned_lighting_scene",
    "RoomSignalAssistReaction": "room_signal_assist",   # default for the three N:1 types
    "RoomLightingAssistReaction": "room_darkness_lighting_assist",  # removed in Phase AB
    "RoomLightingVacancyOffReaction": "room_vacancy_lighting_off",
    "VacationPresenceSimulationReaction": "vacation_presence_simulation",
    "HeatingPreferenceReaction": "heating_preference",
    "HeatingEcoReaction": "heating_eco",
    "PresencePatternReaction": "presence_preheat",
}
```

**Phase AB note:** `room_darkness_lighting_assist` and `room_contextual_lighting_assist` are
removed in Phase AB (hard cut). They no longer appear in the active registry. If encountered
in persisted options the engine raises a config error. The mapper above retains the legacy
entry only to document what the class was mapped to; the builder is removed.

**Note**:
- for `RoomSignalAssistReaction` the mapper produces `room_signal_assist` by default —
  `room_cooling_assist` and `room_air_quality_assist` are only produced by new entries created
  post-reform. Migrated entries work correctly because `room_signal_assist` is the generic type.
- `LightingScheduleReaction -> lighting_scene_schedule` remains a legacy migration mapping only; the schedule-owned learned lighting family is no longer part of the active product model.

The migration runs in `async_reload_options` (or a helper called from there) and rewrites
`options` when it finds an entry with `reaction_class` but no `reaction_type`.

### Migration rules

1. If `reaction_type` is present and non-empty:
   - it remains the source of truth
   - legacy `reaction_class` is removed from the persisted payload
2. If `reaction_type` is missing but `reaction_class` is known:
   - it is populated via the mapper
   - then `reaction_class` is removed
3. If both are missing:
   - the reaction is left intact
   - a warning is emitted
   - the runtime rebuild ignores it
4. If both fields exist but are inconsistent:
   - `reaction_type` wins
   - `reaction_class` is discarded

---

## What disappears

| Element | Post-reform state |
|---|---|
| `configured[id]["reaction_class"]` | Removed from new entries; migration removes it from old ones |
| `ReactionPluginRegistry.builder_for(reaction_class)` | Signature changes to `builder_for(reaction_type)` |
| Dual-path `or` check | Eliminated |
| `reaction_class` in diagnostics output | Removed or moved to a debug-only section |

---

## What stays unchanged

- `reaction_type` in `ReactionProposal` (already correct)
- `mute_reaction_type` / `unmute_reaction_type` service (already use `reaction_type`)
- Lifecycle hooks keyed by `reaction_type` in `LearningPluginRegistry`
- Identity key / deduplication logic (already uses `reaction_type`)

## Scheduled Routine Clarification

`scheduled_routine` is a canonical `reaction_type`, but it is not part of the learned proposal
lifecycle.

Normative distinction:
- configured `scheduled_routine` reactions are persisted as normal configured reactions keyed by
  `reaction_id`
- the admin-authored template layer currently uses this proposal identity string:

```text
scheduled_routine|weekday={weekday}|scheduled_min={scheduled_min}|kind={routine_kind}|targets={sorted(target_entities)}
```

This identity is:
- a template/proposal materialization key
- not a learned analyzer identity
- not a separate runtime reaction identity beyond the configured `reaction_id`

The normalized runtime contract for `scheduled_routine` is defined in:
- `core/scheduled_routine_spec.md`

---

## Risks

| Risk | Mitigation |
|---|---|
| Migration fails on malformed entries (neither `reaction_type` nor `reaction_class`) | Entry skipped with a warning log; reaction inactive but options not corrupted |
| N:1 mapping produces the wrong type for migrated entries | Acceptable: `room_signal_assist` covers the general case; the `cooling`/`air_quality` variants are only generated by new proposals |
| Tests looking for `reaction_class` in `configured` | To be updated in the same PR |

---

## PR Scope

1. `runtime/reactions/__init__.py` — registry keyed by `reaction_type`, explicit N:1 entries
2. `runtime/engine.py` — lookup on `reaction_type`
3. `config_flow/_steps_reactions.py` — dispatch and storage
4. `runtime/proposal_engine.py` — remove `reaction_class` from the serialized payload
5. `diagnostics.py` — eliminate dual-path checks
6. Migration helper in `async_reload_options`
7. Local `debug/` tooling — filters and presenters aligned to `reaction_type`
8. Tests: update all checks on `reaction_class` in `configured`

---

## Acceptance Criteria

- A new reaction saved in `options.reactions.configured` contains `reaction_type` but not `reaction_class`
- `_rebuild_configured_reactions()` can rebuild all supported reactions using only `reaction_type`
- The `Edit reaction` config flow dispatches correctly without reading `reaction_class`
- `diagnostics --section reactions` does not depend on `reaction_class`
- Room/reaction debug scripts show the correct reactions even after `reaction_class` removal
- The migration correctly converts the most common legacy entries without corrupting options

No changes to public APIs (services, HA events).
