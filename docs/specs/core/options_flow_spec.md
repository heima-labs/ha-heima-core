# Heima — Options Flow SPEC v1
## Configuration & UX Schema (Product-Grade)

**Status:** Active v1 options contract
**Last Verified Against Code:** 2026-03-30

This document defines the **Options Flow schema** for the Heima integration.
It specifies UI steps, fields, validation rules, defaults, and runtime effects.

---

## Normative precedence

This document defines the normative v1 options schema and configuration contract.

Interpretation rule:
- if implementation and spec diverge, the divergence must be resolved explicitly
- code is a reference implementation, not the source of truth

## Relationship to UX v2 spec

This document defines the stable configuration schema and runtime effects.

The companion document `core/options_flow_ux_v2_spec.md` refines UX behavior, session flow, and
proposal-configuration interactions without replacing the schema contract defined here.

## Scope and non-goals

In scope:
- option names and field meanings
- validation rules
- runtime effects of persisted configuration

Not a goal of this document:
- prescribing one exact UI rendering strategy for every step
- documenting every internal helper or migration detail
- replacing narrower specs for reactions, notifications, or scheduler semantics

## Design Principles

- Incremental configuration (minimal viable setup first)
- Strong validation (no free-text entity_id)
- Deterministic effects (no hidden side effects)
- Restart-safe and non-destructive
- Backward compatible with config entry migrations
- Administrative safety for high-impact decisions

## Access Control

Heima configuration is **admin-only**.

Normative rules:
- the initial config flow MUST only be executable by a Home Assistant administrator
- the options flow MUST only be executable by a Home Assistant administrator
- non-admin household users MUST NOT be allowed to create, edit, accept, reject, or save Heima configuration
- this restriction applies to all high-impact configuration surfaces, including proposal review and reaction editing

Rationale:
- Heima configuration can change home behavior, automation policy, notifications, and reaction execution
- proposal acceptance can materialize new configured reactions with real runtime effects
- these decisions are part of system administration, not day-to-day household interaction

---

## Options Flow Overview

```
Heima Options
 ├─ General
 ├─ Learning
 ├─ People
 │   ├─ Named persons
 │   └─ Anonymous presence
 ├─ Rooms (Occupancy)
 ├─ Lighting
 │   ├─ Rooms → Scenes
 │   └─ Zones
 ├─ Heating
 ├─ Security
 ├─ Notifications
 ├─ Reactions
 ├─ Reactions Edit
 ├─ Create Automation
 ├─ Proposals
 └─ Save
```

Each step is independently editable after initial setup.

---

## 1. General

### Fields
- `engine_enabled` (bool, default: true)
- `timezone` (string, default: HA timezone)
- `language` (string, default: HA language)
- `lighting_apply_mode` (enum: `scene`, `delegate`)

Optional house-signal bindings:
- `vacation_mode_entity` (entity picker: `input_boolean|binary_sensor|sensor`)
- `guest_mode_entity` (entity picker: `input_boolean|binary_sensor|sensor`)
- `sleep_window_entity` (entity picker: `input_boolean|binary_sensor|sensor`)
- `relax_mode_entity` (entity picker: `input_boolean|binary_sensor|sensor`)
- `work_window_entity` (entity picker: `input_boolean|binary_sensor|sensor`)

Optional house-state tuning/config:
- `media_active_entities` (entity picker: `media_player|binary_sensor|sensor`, multiple)
- `sleep_charging_entities` (entity picker: `input_boolean|binary_sensor|sensor`, multiple)
- `workday_entity` (entity picker: `input_boolean|binary_sensor|sensor`)
- `sleep_enter_min` (int, min `0`)
- `sleep_exit_min` (int, min `0`)
- `work_enter_min` (int, min `0`)
- `relax_enter_min` (int, min `0`)
- `relax_exit_min` (int, min `0`)
- `sleep_requires_media_off` (bool)
- `sleep_charging_min_count` (int or null, min `0`)

### Validation
- timezone must be valid IANA TZ
- language must be supported by HA

### Runtime Effect
- disabling engine blocks all apply phases but keeps canonical state updates
- stores the configurable house-signal bindings used by canonical house-state resolution

---

## Learning

### Fields
- `enabled_plugin_families` (multi-select of learning plugin families, default: all enabled)

### Validation
- every selected family MUST exist in the built-in learning registry
- empty selection is allowed only if the implementation interprets it as "all enabled"

### Runtime Effect
- filters the built-in learning registry to the configured families
- disabled families MUST not emit proposals in that runtime session
- proposal diagnostics MUST reflect which families were enabled and which were not

---

## 2. People — Named Persons

### Add / Edit Person

Fields:
- `slug` (string, required, immutable)
- `display_name` (string)
- `presence_method` (enum: `ha_person`, `quorum`, `manual`)

If `ha_person`:
- `person_entity` (entity picker: domain `person`)

If `quorum`:
- `sources` (multi-entity picker)
- `required` (int, 1..N)

Tuning (all methods):
- `arrive_hold_s` (int, default 10)
- `leave_hold_s` (int, default 120)

Optional:
- `enable_override` (bool)

### Validation
- slug unique
- entity exists and domain matches
- quorum.required <= len(sources)

### Runtime Effect
- updates PeopleAdapter
- recompute canonical person state

---

## 3. People — Anonymous Presence

Fields:
- `enabled` (bool)
- `sources` (multi-entity picker)
- `required` (int, default 1)
- `anonymous_count_weight` (int, default 1)
- `arrive_hold_s` (int, default 10)
- `leave_hold_s` (int, default 120)

Validation:
- required <= len(sources)

Runtime Effect:
- updates anonymous presence adapter
- affects `anyone_home`, `people_count`, `house_state`

---

## 4. Rooms (Occupancy)

### Add / Edit Room

Fields:
- `room_id` (slug, immutable)
- `display_name`
- `area_id` (HA area picker, optional but recommended for actuation fallback)
- `occupancy_mode` (enum: `derived`, `none`; default `derived`)
- `sources` (multi-entity picker, conditional)
- `logic` (enum: `any_of`, `all_of`, conditional)
- `on_dwell_s` (int, default 5)
- `off_dwell_s` (int, default 120)
- `max_on_s` (int, optional)

Validation:
- if `occupancy_mode = derived`: at least one source and `logic` required
- if `occupancy_mode = none`: `sources` may be empty and `logic` is ignored
- dwell values >= 0

Runtime Effect:
- updates room actuation + occupancy metadata
- recompute room occupancy only for `occupancy_mode = derived`

---

## 5. Lighting — Rooms → Scenes

### Per Room Mapping

Fields:
- `room_id` (from Rooms)
- `scene_evening` (scene picker or empty)
- `scene_relax` (scene picker or empty)
- `scene_night` (scene picker or empty)
- `scene_off` (scene picker or empty)

Optional:
- `enable_manual_hold` (bool, default true)

Validation:
- scenes must exist
- all scenes optional (room may rely on partial mapping or runtime fallback)

Runtime Effect:
- used by orchestrator for per-room apply
- creates `binary_sensor.heima_lighting_hold_<room>`
- when intent is `off` and `scene_off` is empty, runtime may fallback to `light.turn_off` using the room `area_id`

---

## 6. Lighting — Zones

### Add / Edit Zone

Fields:
- `zone_id` (slug)
- `display_name`
- `rooms` (multi-select from rooms)
- `intent_entity` (auto-created select)

Validation:
- at least one room

Runtime Effect:
- lighting policy runs per-zone
- apply decomposed per-room
- zone occupancy ignores rooms with `occupancy_mode = none`
- zone with only `occupancy_mode = none` rooms resolves `zone_occupied = false` in `auto`

---

## 7. Heating

Fields:
### 7.1 Heating — General

Fields:
- `climate_entity` (entity picker: domain `climate`, required)
- `apply_mode` (enum: `delegate_to_scheduler`, `set_temperature`; default `delegate_to_scheduler`)
- `temperature_step` (float, required, > 0)
- `manual_override_guard` (bool, default `true`)

Optional external bindings:
- `outdoor_temperature_entity` (entity picker: domain `sensor`)
- `vacation_hours_from_start_entity` (entity picker: domain `sensor`)
- `vacation_hours_to_end_entity` (entity picker: domain `sensor`)
- `vacation_total_hours_entity` (entity picker: domain `sensor`)
- `vacation_is_long_entity` (entity picker: domain `binary_sensor`)

Validation:
- climate entity must exist and be `climate.*`
- `temperature_step > 0`
- helper bindings must match allowed domains

Runtime Effect:
- defines the Heating domain device binding
- defines shared apply-guard parameters
- provides external timing/weather inputs for built-in override branches

### 7.2 Heating — Override Branches

Heating v1 exposes a fixed mapping:

- `house_state -> built-in branch config`

All canonical `house_state` values are configurable:
- `away`
- `home`
- `guest`
- `vacation`
- `sleeping`
- `relax`
- `working`

Default for every state:
- `branch = disabled`

### 7.3 Heating — Branch Editor Flow

Recommended UI shape:

1. `Heating General`
2. `Heating Override Branches Menu`
3. select one `house_state`
4. edit its branch config
5. save and return to the branch menu

This mirrors the existing Heima edit-menu pattern and avoids one oversized form.

### 7.4 Heating — Per-State Branch Form

Common fields:
- `house_state` (selected from canonical values, immutable in edit)
- `branch` (enum: `disabled`, `scheduler_delegate`, `fixed_target`, `vacation_curve`)

#### If `branch = disabled`
- no additional fields

#### If `branch = scheduler_delegate`
- no additional fields

#### If `branch = fixed_target`
- `target_temperature` (float, required, > 0)

#### If `branch = vacation_curve`
- `vacation_ramp_down_h` (float, required, >= 0)
- `vacation_ramp_up_h` (float, required, >= 0)
- `vacation_min_temp` (float, required, > 0)
- `vacation_comfort_temp` (float, required, > 0)
  - semantic meaning: return preheat target before control is handed back to the external scheduler
- `vacation_min_total_hours_for_ramp` (float, required, >= 0)

### 7.5 Heating — Validation Rules

General:
- exactly one branch config per canonical `house_state`
- if a state has no stored config, effective branch = `disabled`

Branch-specific:
- `disabled` / `scheduler_delegate`:
  - no extra branch fields allowed
- `fixed_target`:
  - `target_temperature` required and > 0
- `vacation_curve`:
  - all vacation fields required
  - all temperatures > 0
  - hour-based values >= 0
  - no user-configured start temperature field:
    - branch start temperature is captured at runtime from the thermostat when the branch activates

Cross-checks:
- if any branch uses `vacation_curve`, the relevant timing bindings should be present in `Heating General`
  - `vacation_hours_from_start_entity`
  - `vacation_hours_to_end_entity`
  - `vacation_total_hours_entity`
  - `vacation_is_long_entity`
- if any branch uses `vacation_curve`, `outdoor_temperature_entity` is strongly recommended and may be required by the implementation

### 7.6 Heating — Persistence Shape

Conceptual stored shape:

```yaml
heating:
  climate_entity: climate.termostato
  apply_mode: delegate_to_scheduler
  temperature_step: 0.5
  manual_override_guard: true
  outdoor_temperature_entity: sensor.outdoor_temp
  vacation_hours_from_start_entity: sensor.heating_vacation_hours_from_start
  vacation_hours_to_end_entity: sensor.heating_vacation_hours_to_end
  vacation_total_hours_entity: sensor.heating_vacation_total_hours
  vacation_is_long_entity: binary_sensor.heating_vacation_is_long
  override_branches:
    vacation:
      branch: vacation_curve
      vacation_ramp_down_h: 8
      vacation_ramp_up_h: 10
      vacation_min_temp: 16.5
      vacation_comfort_temp: 19.5
      vacation_min_total_hours_for_ramp: 24
    sleeping:
      branch: fixed_target
      target_temperature: 17.5
    guest:
      branch: scheduler_delegate
```

### 7.7 Heating — Runtime Effect

- `Heating General` config binds the device and common external inputs
- `override_branches` drives the built-in fixed policy tree:
  - if current `house_state` matches a configured built-in branch, that branch is used
  - otherwise Heating falls back to the normal scheduler-following branch
- no policy plugins are involved in v1

---

## 8. Security (Read-Only)

Fields:
- `enabled` (bool)
- `security_state_entity` (entity picker)
- `armed_away_value` (string)
- `armed_home_value` (string)

Runtime Effect:
- consistency checks
- emits notification events only

---

## 9. Notifications

Fields:
- `routes` (list of notify services)
- `recipients` (object mapping, `recipient_id -> list[notify.*]`)
- `recipient_groups` (object mapping, `group_id -> list[recipient_id]`)
- `route_targets` (list/object of logical notification targets: recipient ids or group ids)
- `enabled_event_categories` (multi-select: `people`, `occupancy`, `house_state`, `lighting`, `heating`, `security`; `system` always enabled)
- `dedup_window_s` (int, default 60)
- `rate_limit_per_key_s` (int, default 300)
- `occupancy_mismatch_policy` (`off|smart|strict`, default `smart`)
- `occupancy_mismatch_min_derived_rooms` (int, default `2`)
- `occupancy_mismatch_persist_s` (int, default `600`)
- `security_mismatch_policy` (`off|smart|strict`, default `smart`)
- `security_mismatch_persist_s` (int, default `300`)

Runtime Effect:
- affects notification policy and orchestrator
- route delivery resolves legacy `routes` plus logical `route_targets` through configured recipients/groups
- category toggles gate event emission before routing/dedup pipeline
- occupancy mismatch policy reduces false positives in partial-room-sensing homes
- security mismatch policy delays/suppresses `armed_away_but_home` false positives caused by stale trackers

---

## 10. Reactions and Proposal Review

### Reactions

The `reactions` step manages currently configured reactions and persisted mute state.

Runtime effect:
- reads configured reactions from `options["reactions"]["configured"]`
- lets the admin mute or unmute known reaction ids
- does not create new reactions by itself

### Reactions Edit

The `reactions_edit` surface edits existing configured reaction payloads.

Normative rules:
- it remains admin-only
- it operates on already configured reactions
- it MUST NOT bypass the shared reaction persistence model

### Create Automation

The `admin_authored_create` step is the bounded admin-authored entry point.

Normative rules:
- it MUST be admin-only
- it MUST only expose plugin-declared templates
- it MUST NOT act as a universal free-form automation builder
- the resulting artifact MUST be created as a normal `ReactionProposal` with
  `origin = "admin_authored"`
- the proposal MUST then flow through the same shared review and rebuild pipeline as learned proposals
- template availability and implementability MUST be sourced from plugin/template
  descriptors rather than a flow-local hardcoded allowlist
- the flow SHOULD progressively delegate template-specific authoring schema and
  submit handling to plugin-owned hooks instead of expanding central
  `template_id` branching

Current v1 implementation:
- the bounded template flow is implemented for `lighting.scene_schedule.basic`
- plugin families may declare more admin-authored templates than the current flow exposes
- only templates explicitly implemented in the options flow are user-selectable

### Proposals

The `proposals` step is the shared review surface for both:
- learned proposals
- admin-authored proposals

Normative rules:
- review is one proposal at a time
- `accept`, `reject`, and `skip` semantics are shared
- admin-authored proposals MUST preserve visible provenance in review wording
- accepted proposals persist into `options["reactions"]["configured"]`
- the flow SHOULD progressively obtain compact labels, review titles, and review
  details from plugin-owned presenter hooks rather than central
  `reaction_type`/`reaction_class` branching
- tuning follow-ups SHOULD be renderable through the same presenter layer so the
  central flow does not grow ad hoc per-type review logic

Current v1 implementation:
- if no pending proposals exist, entering `proposals` returns immediately to `init`
- proposals that require extra user completion may continue into `proposal_configure_action`

---

## 11. Apply & Reload Semantics

- Option changes trigger re-evaluation
- No immediate mass-apply unless intent changes
- Safety rules always enforced

---

## 12. Migration Rules

- New fields get defaults
- Removed fields are ignored but preserved
- Major changes require migration step

---

## 13. Current Implementation Notes

- `proposals` step is implemented:
  - reads pending proposals from `ProposalEngine`
  - reviews them one at a time
  - accepts/rejects/skips them
  - persists accepted items in `options["reactions"]["configured"]`
- `learning.enabled_plugin_families` is implemented and filters the built-in learning registry at runtime
- `admin_authored_create` is implemented as a bounded template-driven authoring path
- current bridge target:
  - plugin/template descriptors should become the source of truth for authoring
    availability and flow delegation
  - proposal/reaction presentation should progressively move behind plugin-owned
    presenter hooks
- the current admin-authored template implemented end-to-end in the options flow is:
  - `lighting.scene_schedule.basic`
- REST-driven options-flow tests may intentionally return HTTP 400 for invalid schema values; this is expected validation behavior.
