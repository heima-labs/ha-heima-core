# Heima Configuration Reference

This document explains, step by step, what each Options Flow section configures, what each field means, when it is required, and what values are expected.

The flow order is:

1. `General`
2. `People` (named people)
3. `Anonymous Presence`
4. `Rooms`
5. `Lighting Rooms`
6. `Lighting Zones`
7. `Heating`
8. `Heating Override Branches`
9. `Security`
10. `Notifications`

---

## 1. General

Purpose:
- global engine behavior
- localization
- house-state side-signal bindings

Fields:

### `engine_enabled`
- Type: boolean
- Default: `true`
- Meaning: globally enables or disables the Heima runtime engine.
- When `false`: Heima still exists, but policy/apply logic is disabled.

### `timezone`
- Type: string
- Required: yes
- Meaning: timezone used by Heima for time-based logic.
- Must be a valid Home Assistant timezone string.

### `language`
- Type: string
- Required: yes
- Meaning: preferred language for Heima text/runtime-facing labels.

### `lighting_apply_mode`
- Type: choice
- Allowed values:
  - `scene`
  - `delegate`
- Meaning:
  - `scene`: Heima applies `scene.turn_on`
  - `delegate`: Heima computes lighting state but does not directly apply scenes

Guide:
- for practical guidance on when to prefer `scene.*` vs `script.*`, see
  [`docs/guides/scene_and_script_usage.md`](guides/scene_and_script_usage.md)

### `vacation_mode_entity`
- Type: entity selector (`input_boolean`, `binary_sensor`, `sensor`)
- Optional
- Meaning: source entity that indicates vacation mode for house-state resolution.

### `guest_mode_entity`
- Type: entity selector (`input_boolean`, `binary_sensor`, `sensor`)
- Optional
- Meaning: source entity that indicates guest mode.

### `sleep_window_entity`
- Type: entity selector (`input_boolean`, `binary_sensor`, `sensor`)
- Optional
- Meaning: source entity that indicates the house is in a sleeping window.

### `relax_mode_entity`
- Type: entity selector (`input_boolean`, `binary_sensor`, `sensor`)
- Optional
- Meaning: source entity that indicates relax mode.

### `work_window_entity`
- Type: entity selector (`input_boolean`, `binary_sensor`, `sensor`)
- Optional
- Meaning: source entity that indicates work mode.

Important:
- all house-state signals are now configurable
- if a binding is omitted, that signal is treated as `off`

Target evolution:
- these bindings remain valid, but future `house_state` resolution will treat them as
  candidate inputs rather than direct one-to-one final states
- planned additive bindings:
  - `media_active_entities`
  - `workday_entity`
  - house-state enter/exit timer settings
- see [house_state_spec.md](./docs/specs/domains/house_state_spec.md)
  for the target model

---

## 2. People (Named People)

Purpose:
- configure known people who contribute to:
  - `heima_anyone_home`
  - `people_count`
  - `people_home_list`
  - `house_state`

This section is menu-based:
- add
- edit
- remove
- save/continue

Fields for each person:

### `slug`
- Type: slug string
- Required: yes
- Must be unique
- Must not start with `heima_`
- Used to create canonical entity ids such as:
  - `binary_sensor.heima_person_<slug>_home`

### `display_name`
- Type: string
- Optional
- Human-readable label.

### `presence_method`
- Type: choice
- Allowed values:
  - `ha_person`
  - `quorum`
  - `manual`

Meaning:
- `ha_person`: use a `person.*` entity
- `quorum`: use multiple source entities and a strategy
- `manual`: user-controlled only

### `person_entity`
- Type: entity selector (`person`)
- Required only when `presence_method = ha_person`
- Meaning: the Home Assistant `person.*` entity to bind.

### `sources`
- Type: multi-entity selector (`binary_sensor`, `sensor`, `device_tracker`)
- Required when:
  - `presence_method = quorum`
- Ignored for:
  - `ha_person`
  - `manual`

### `group_strategy`
- Type: choice
- Allowed values:
  - `quorum`
  - `weighted_quorum`
- Used only with:
  - `presence_method = quorum`

### `required`
- Type: positive integer
- Required when:
  - `group_strategy = quorum`
- Meaning: minimum number of active sources required to consider the person home.

### `weight_threshold`
- Type: float
- Required in practice when:
  - `group_strategy = weighted_quorum`
- Meaning: minimum weighted sum required to mark the person as home.

### `source_weights`
- Type: multiline text
- Used only when:
  - `group_strategy = weighted_quorum`
- Format:
  - one line per source
  - `entity_id=weight`
- Example:
```text
binary_sensor.motion_studio=0.4
sensor.mmwave_studio=0.8
```

### `arrive_hold_s`
- Type: positive integer
- Default: `10`
- Meaning: debounce/hold before confirming arrival.

### `leave_hold_s`
- Type: positive integer
- Default: `120`
- Meaning: debounce/hold before confirming departure.

### `enable_override`
- Type: boolean
- Default: `false`
- Meaning: enables the per-person canonical override entity:
  - `select.heima_person_<slug>_override`

---

## 3. Anonymous Presence

Purpose:
- model “someone is home, but not necessarily a known named person”

Fields:

### `enabled`
- Type: boolean
- Default: `false`

### `sources`
- Type: multi-entity selector (`binary_sensor`, `sensor`, `device_tracker`)
- Required when `enabled = true`

### `group_strategy`
- Type: choice
- Allowed values:
  - `quorum`
  - `weighted_quorum`

### `required`
- Type: positive integer
- Used for `quorum`

### `weight_threshold`
- Type: float
- Used for `weighted_quorum`

### `source_weights`
- Type: multiline text
- Used for `weighted_quorum`
- Same format as named people:
  - `entity_id=weight`

### `anonymous_count_weight`
- Type: positive integer
- Default: `1`
- Meaning: how much anonymous presence contributes to people-count style aggregates.

### `arrive_hold_s`
- Type: positive integer
- Default: `10`

### `leave_hold_s`
- Type: positive integer
- Default: `120`

---

## 4. Rooms

Purpose:
- define canonical rooms
- define occupancy detection for rooms
- provide the base input for occupancy, lighting, and other domains
- provide the primary room-scoped source set for the learning system

This section is menu-based:
- add
- edit
- remove
- import areas
- save/continue

Fields for each room:

### `room_id`
- Type: slug string
- Required: yes
- Must be unique
- Must not start with `heima_`

### `display_name`
- Type: string
- Optional

### `area_id`
- Type: Home Assistant area selector
- Optional
- Recommended
- Used especially for:
  - `light.turn_off(area_id)` fallback when no `scene_off` exists

### `occupancy_mode`
- Type: choice
- Allowed values:
  - `derived`
  - `none`

Meaning:
- `derived`: room occupancy is computed from sources
- `none`: room exists for actuation/grouping only, but has no local occupancy sensing

### `occupancy_sources`
- Type: multi-entity selector (`binary_sensor`, `sensor`)
- Required when:
  - `occupancy_mode = derived`
- Not required when:
  - `occupancy_mode = none`

Meaning:
- room-local source entities used for occupancy resolution

Important:
- these sources define room occupancy semantics only
- they are distinct from room-scoped learning signals

### `learning_sources`
- Type: multi-entity selector (`binary_sensor`, `sensor`)
- Required when:
  - never

Meaning:
- room-local entities that should be available as room-scoped inputs for learning plugins
- these signals explain **when** a behavior tends to happen, not necessarily whether the room is occupied

Important:
- the learning system should not force the user to duplicate room-scoped learning semantics in a
  global-only section
- `rooms[*].learning_sources` are the primary room-scoped learning inputs
- `learning.context_signal_entities` is an additive global override set for non-room-specific extras

Practical guidance:
- put stable, normalized room signals here when they describe the room meaningfully:
  - `sensor.room_lux`
  - `sensor.room_co2`
  - `sensor.room_temperature`
  - `switch.room_fan`
- keep noisy occupancy pulses in `occupancy_sources` when they are useful to know if the room is
  occupied, but not as learning inputs unless they are semantically meaningful for a plugin

Important distinction:
- room entities are not all used in the same role by learning
- some entities are useful as trigger/context signals:
  - `sensor.room_lux`
  - `sensor.room_co2`
  - `sensor.room_temperature`
- other entities are more naturally observed as user responses:
  - `light.room_main`
  - `light.room_spot`

Example:
- for darkness-driven lighting learning, the lux sensor explains **when** the user reacts
- the lighting events explain **what** the user did
- this means lights do not need to be treated as generic trigger signals in order for Heima to
  learn lighting behavior correctly

### `logic`
- Type: choice
- Allowed values:
  - `any_of`
  - `all_of`
  - `weighted_quorum`
- Used when:
  - `occupancy_mode = derived`

### `weight_threshold`
- Type: float
- Used when:
  - `logic = weighted_quorum`

### `source_weights`
- Type: multiline text
- Used when:
  - `logic = weighted_quorum`
- Format:
  - `entity_id=weight`

### `on_dwell_s`
- Type: positive integer
- Default: `5`
- Meaning: room must remain in an `on` candidate state this long before becoming occupied.

### `off_dwell_s`
- Type: positive integer
- Default: `120`
- Meaning: room must remain in an `off` candidate state this long before becoming unoccupied.

### `max_on_s`
- Type: positive integer or empty
- Optional
- Meaning: maximum allowed continuous occupied state before forcing the room back to `off`.

---

## 5. Lighting Rooms

Purpose:
- map each room to its lighting scenes

This section edits only rooms that already exist in `Rooms`.

Fields:

### `room_id`
- Type: existing room selector
- Required
- Must reference a room defined in `Rooms`

### `scene_evening`
- Type: `scene.*` entity selector
- Optional

### `scene_relax`
- Type: `scene.*` entity selector
- Optional

### `scene_night`
- Type: `scene.*` entity selector
- Optional

### `scene_off`
- Type: `scene.*` entity selector
- Optional

Important:
- all scene mappings are optional
- if `scene_off` is omitted and the room has an `area_id`, Heima can fall back to:
  - `light.turn_off(area_id=...)`

### `enable_manual_hold`
- Type: boolean
- Default: `true`
- Meaning: enables the canonical per-room lighting hold guard.

---

## 6. Lighting Zones

Purpose:
- group rooms into zones for lighting policy and zone-level intent

Fields:

### `zone_id`
- Type: slug string
- Required
- Must be unique
- Must not start with `heima_`

### `display_name`
- Type: string
- Optional

### `rooms`
- Type: multi-select from existing room ids
- Required
- Must contain only rooms defined in `Rooms`

Important:
- a room may exist in multiple zones, but this can create zone conflicts
- current runtime policy is:
  - `first_wins`

---

## 7. Heating

Purpose:
- configure the thermostat binding
- configure the Heating domain baseline
- configure branch-local inputs used by timed branches

Fields:

### `climate_entity`
- Type: `climate.*` entity selector
- Required
- Main thermostat entity controlled by Heima.

### `apply_mode`
- Type: choice
- Allowed values:
  - `delegate_to_scheduler`
  - `set_temperature`

Meaning:
- `delegate_to_scheduler`: Heima yields control to the external scheduler
- `set_temperature`: Heima may call `climate.set_temperature` when a branch wants an active target

### `temperature_step`
- Type: positive float
- Required
- Meaning: target quantization step and minimum meaningful delta for thermostat writes.

### `manual_override_guard`
- Type: boolean
- Default: `true`
- Meaning: enables Heating apply blocking when:
  - `heima_heating_manual_hold` is active
  - or a thermostat-native manual/hold preset is detected

### `outdoor_temperature_entity`
- Type: `sensor.*` entity selector
- Optional
- Required in practice for:
  - `vacation_curve`

### `vacation_hours_from_start_entity`
- Type: `sensor.*` entity selector
- Optional
- Required in practice for:
  - `vacation_curve`

### `vacation_hours_to_end_entity`
- Type: `sensor.*` entity selector
- Optional
- Required in practice for:
  - `vacation_curve`

### `vacation_total_hours_entity`
- Type: `sensor.*` entity selector
- Optional
- Required in practice for:
  - `vacation_curve`

### `vacation_is_long_entity`
- Type: `binary_sensor.*` entity selector
- Optional
- Used by:
  - `vacation_curve`
- If missing, Heima can infer “long vacation” from total hours and branch config.

---

## 8. Heating Override Branches

Purpose:
- define, per canonical `house_state`, which Heating branch should run

All canonical states are available:
- `away`
- `home`
- `guest`
- `vacation`
- `sleeping`
- `relax`
- `working`

Default branch for every state:
- `disabled`

This section is menu-based:
- select a house state
- edit its branch
- save/continue

### Common field: `branch`
- Type: choice
- Allowed values:
  - `disabled`
  - `scheduler_delegate`
  - `fixed_target`
  - `vacation_curve`

Meaning:
- `disabled`: no override branch for that state
- `scheduler_delegate`: explicitly yield to external scheduler in that state
- `fixed_target`: set a fixed thermostat target in that state
- `vacation_curve`: use the vacation temperature curve in that state

### `fixed_target` branch fields

#### `target_temperature`
- Type: positive float
- Required when:
  - `branch = fixed_target`

### `vacation_curve` branch fields

#### `vacation_ramp_down_h`
- Type: float >= 0
- Required
- Meaning: hours spent ramping from the captured start temperature down toward the vacation minimum.

#### `vacation_ramp_up_h`
- Type: float >= 0
- Required
- Meaning: hours spent ramping up from the vacation minimum toward the return preheat target.

#### `vacation_min_temp`
- Type: positive float
- Required
- Meaning: energy-saving / preservation floor during the vacation.

#### `vacation_comfort_temp`
- Type: positive float
- Required
- Meaning: **return preheat target** before the branch hands control back to the external scheduler.
- Important:
  - this is **not** guaranteed to match the scheduler’s real post-vacation target

#### `vacation_min_total_hours_for_ramp`
- Type: float >= 0
- Required
- Meaning: minimum total vacation duration needed before ramp behavior is considered “long” enough to use the full curve.

Important:
- `vacation_start_temp` is **not configured**
- Heima captures the start temperature from the thermostat when the `vacation_curve` branch becomes active

---

## 9. Security

Purpose:
- bind a read-only security state source
- enable consistency checks and security-related events

Fields:

### `enabled`
- Type: boolean
- Default: `false`

### `security_state_entity`
- Type: entity selector (`alarm_control_panel`, `sensor`, `binary_sensor`)
- Required when:
  - `enabled = true`

### `armed_away_value`
- Type: string
- Default: `armed_away`
- Meaning: raw state value mapped to canonical `armed_away`.

### `armed_home_value`
- Type: string
- Default: `armed_home`
- Meaning: raw state value mapped to canonical `armed_home`.

---

## 10. Notifications

Purpose:
- define event routing
- configure event suppression policies
- define logical notification recipients

Fields:

### `routes` (legacy)
- Type: list of `notify.*` services in old persisted options only
- Editable in UI: no (removed from Notifications Options Flow)
- Meaning: migration-only legacy transport routes
- Current status:
  - no longer used directly by runtime delivery
  - removed from normalized options payload when saved
  - runtime emits `system.notifications_routes_deprecated` when legacy routes are still present
  - routes-only legacy profiles are auto-bridged to:
    - recipient alias `legacy_routes`
    - route target `legacy_routes`

### `recipients`
- Type: object editor (JSON-like mapping)
- Optional
- Meaning: logical recipient aliases mapped to one or more `notify.*` services
Example:
```json
{
  "stefano": ["mobile_app_phone_stefano", "mobile_app_mac_stefano"],
  "laura": ["mobile_app_laura"]
}
```

You can also map aliases to Home Assistant native grouped notify services.
Example:
```json
{
  "stefano": ["mobile_app_phone_stefano", "mobile_app_mac_stefano"],
  "family_transport": ["family_notifications"]
}
```
Where `family_notifications` is an existing `notify.*` service in HA.

### `recipient_groups`
- Type: object editor (JSON-like mapping)
- Optional
- Meaning: logical groups mapped to recipient aliases
- Example:
```json
{
  "family": ["stefano", "laura"],
  "admins": ["stefano"]
}
```

Note:
- groups contain recipient aliases, not raw `notify.*` services.
- if you want to use a HA-native notify group, map it in `recipients` first and then reference that alias in `recipient_groups` and/or `route_targets`.

### `route_targets`
- Type: object editor (array or map-like)
- Optional
- Meaning: default logical notification targets used by the event pipeline
- Values may be:
  - recipient aliases
  - group ids
- Example:
```json
["family", "admins"]
```

### `enabled_event_categories`
- Type: multi-select
- Allowed values:
  - `people`
  - `occupancy`
  - `house_state`
  - `lighting`
  - `heating`
  - `security`
- Note:
  - `system` is always enabled and is not user-toggleable

### `dedup_window_s`
- Type: non-negative integer
- Default: `60`
- Meaning: same-key events inside this window are dropped as duplicates.

### `rate_limit_per_key_s`
- Type: non-negative integer
- Default: `300`
- Meaning: same-key events cannot be emitted again before this window expires.

### `occupancy_mismatch_policy`
- Type: choice
- Allowed values:
  - `off`
  - `smart`
  - `strict`
- Default: `smart`

### `occupancy_mismatch_min_derived_rooms`
- Type: non-negative integer
- Default: `2`
- Meaning: minimum number of `derived` rooms required before smart occupancy mismatch becomes meaningful.

### `occupancy_mismatch_persist_s`
- Type: non-negative integer
- Default: `600`
- Meaning: persistence required before occupancy mismatch events are emitted.

### `security_mismatch_policy`
- Type: choice
- Allowed values:
  - `off`
  - `smart`
  - `strict`
- Default: `smart`

### `security_mismatch_event_mode`
- Type: choice
- Allowed values:
  - `explicit_only`
  - `generic_only`
  - `dual_emit`
- Default: `explicit_only`
- Meaning: controls emission style for security mismatch events.
  - `explicit_only`: emit only specific events (for example `security.armed_away_but_home`)
  - `generic_only`: emit only canonical `security.mismatch` with `subtype`
  - `dual_emit`: emit both specific and generic events (useful during migration)

### `security_mismatch_persist_s`
- Type: non-negative integer
- Default: `300`
- Meaning: persistence required before security mismatch events are emitted.

---

## Where temporary decisions are tracked

Temporary or transitional product/architecture decisions are now recorded in:

- `docs/PROJECT_DECISIONS.md`

This is the correct place to document choices such as:
- keeping legacy compatibility for now
- intentional deferrals
- architectural constraints we plan to revisit later
