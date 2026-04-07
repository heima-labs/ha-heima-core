# Heima — Options Flow Configuration Guide

Practical guidance for configuring Heima through the Options Flow.

This is not the schema spec. Its goal is to explain:
- what each section is for
- what is usually worth configuring
- what is better left alone until later

Canonical references:
- [options_flow_spec.md](/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/docs/specs/core/options_flow_spec.md)
- [options_flow_ux_spec.md](/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/docs/specs/core/options_flow_ux_spec.md)

## Recommended order

For a normal installation, this is the best order:

1. `General`
2. `People`
3. `Rooms`
4. `Lighting`
5. `Calendar`
6. `Heating`
7. `Security`
8. `Learning`
9. `Notifications`
10. `Reactions`

Practical rule:
- configure the canonical context first
- then the physical house model
- then the domains that act on it
- only after that, tune learning and add admin-authored automations

## 1. General

This section defines the base runtime behavior of the integration.

### `engine_enabled`
Recommended:
- keep it `true` most of the time
- set it to `false` only for debugging or controlled maintenance

Effect:
- Heima still computes context and canonical state
- but it stops applying actions

### `timezone`
Recommended:
- always use the real house timezone
- do not leave an almost-correct timezone in place

This affects:
- calendar interpretation
- weekday/time learning
- runtime scheduling
- time-based domain behavior

### `language`
Recommended:
- pick the language you want for review, summaries, and options flow surfaces

This is mostly an admin readability choice, not a runtime logic choice.

### `lighting_apply_mode`
Recommended:
- keep the default unless you are actively testing a specific lighting apply path

### House signal bindings

Fields:
- `vacation_mode_entity`
- `guest_mode_entity`
- `sleep_window_entity`
- `relax_mode_entity`
- `work_window_entity`

Configure these only if you already have a meaningful upstream signal.

Good use cases:
- an `input_boolean` explicitly set by the user
- a well-defined external automation
- a signal with a clear semantic meaning

Bad use cases:
- vague helper entities
- weak proxies that are only sometimes correlated with the intended state

Practical advice:
- a small number of strong house-level signals is much better than many weak ones

### House-state tuning

Main fields:
- `media_active_entities`
- `sleep_charging_entities`
- `workday_entity`
- `sleep_enter_min`
- `sleep_exit_min`
- `work_enter_min`
- `relax_enter_min`
- `relax_exit_min`
- `sleep_requires_media_off`
- `sleep_charging_min_count`

How to think about them:
- `media_active_entities`
  - use only entities that really indicate active media consumption
- `sleep_charging_entities`
  - useful only if charging is a strong sleep signal in your home
- `workday_entity`
  - useful if you want a stable workday hint outside of calendar-only logic
- enter/exit timers
  - increase them if the system is too noisy
  - reduce them only if you need faster state changes and the inputs are clean

Recommended approach:
- start with defaults
- change one axis at a time
- use diagnostics before changing multiple timers together

## 2. People

This section models:
- named people
- anonymous presence

### Named people

Each person can use:
- `ha_person`
- `quorum`

#### `ha_person`
Use this when:
- you already have a reliable HA `person.*` entity
- HA is already doing a good job at identity-level presence

This is the simplest and usually the best option.

#### `quorum`
Use this when:
- one source is not enough
- you want to combine BLE, Wi-Fi, trackers, sensors, and similar signals

Main fields:
- `sources`
- `group_strategy`
- `required`
- `weight_threshold`
- `source_weights`
- `arrive_hold_s`
- `leave_hold_s`
- `enable_override`

Recommended strategy choice:
- `quorum`
  - when sources have similar quality
- `weighted_quorum`
  - when some sources are clearly stronger than others

Practical advice:
- if you already have a reliable `person.*`, do not over-engineer this
- if you need multiple sources, `weighted_quorum` is often the better long-term model

`arrive_hold_s` / `leave_hold_s`:
- increase `leave_hold_s` if people drop out too easily
- keep `arrive_hold_s` low if you want fast re-entry detection

`enable_override`:
- useful for testing and manual control
- not required for normal day-to-day use

### Anonymous presence

Anonymous presence means:
- someone is home
- but Heima does not know who

Main fields:
- `enabled`
- `sources`
- `group_strategy`
- `required`
- `weight_threshold`
- `source_weights`
- `anonymous_count_weight`
- `arrive_hold_s`
- `leave_hold_s`

Use it when:
- guests are common
- your setup has meaningful house-level presence signals without named identity
- you want a privacy-preserving “someone is home” layer

Do not use it as a substitute for well-configured named people.

Good sources:
- strong house-level occupancy signals
- signals that really mean “someone is home”

Bad sources:
- generic motion signals spread across the house
- weak event spikes that do not indicate presence continuity

`anonymous_count_weight`:
- keep it at `1` in most homes
- raise it only if you intentionally want anonymous presence to contribute more to `people_count`

## 3. Rooms

This is one of the most important sections. Rooms are a core product-level unit.

Main fields:
- `room_id`
- `display_name`
- `area_id`
- `occupancy_mode`
- `occupancy_sources`
- `learning_sources`
- `logic`
- `weight_threshold`
- `source_weights`
- `on_dwell_s`
- `off_dwell_s`
- `max_on_s`

### `room_id`
Recommended:
- use stable, clean slugs
- do not rename room IDs casually

### `area_id`
Use it when:
- the room matches a real HA area

That usually improves clarity and integration consistency.

### `occupancy_mode`
Values:
- `derived`
- `none`

Use `derived` when:
- you have real signals for room occupancy

Use `none` when:
- the room still matters for actuation or grouping
- but you do not have credible room-level occupancy sensing

This is a valid and useful setup. Not every room needs occupancy.

### `occupancy_sources`
Only include sources that really describe that room.

Good examples:
- PIR in the room
- mmWave in the room
- tightly local sensors

Bad examples:
- hallway sensors used as proxies for multiple rooms
- whole-home signals

### `learning_sources`
These define the room-scoped evidence Heima can learn from.

Recommended:
- if you do not need special separation, keep them aligned with `occupancy_sources`
- add extra learning sources only if they improve room-level learning materially

### `logic`
Useful values:
- `any_of`
- `all_of`
- `weighted_quorum`

Recommended:
- `any_of` is the pragmatic default
- `all_of` is often too strict
- `weighted_quorum` is best when your sources differ significantly in quality

### Dwell and timeout tuning

Fields:
- `on_dwell_s`
- `off_dwell_s`
- `max_on_s`

Recommended use:
- increase `off_dwell_s` if occupancy falls off too quickly
- increase `on_dwell_s` if false positives are common
- use `max_on_s` only to guard against genuinely sticky room-on conditions

## 4. Lighting

This section has two parts:
- room-level lighting mapping
- lighting zones

### Lighting Rooms

Fields:
- `room_id`
- `scene_evening`
- `scene_relax`
- `scene_night`
- `scene_off`
- `enable_manual_hold`

Recommended approach:
- start with `scene_evening` and `scene_off`
- add `scene_relax` and `scene_night` only where they really matter

Do not try to fill every scene slot in every room just for completeness.

`enable_manual_hold`:
- keep it `true` in most installations
- it prevents Heima from fighting the user after manual lighting changes

### Lighting Zones

Fields:
- `zone_id`
- `display_name`
- `rooms`

Use zones when:
- the physical space is really shared
- the behavior should be coordinated across multiple rooms

Examples:
- open-plan living + kitchen
- office + corridor transition

Avoid zones when:
- they just duplicate the room structure with no real operational benefit

Recommended:
- keep zones few and meaningful

## 5. Calendar

Fields:
- `calendar_entities`
- `lookahead_days`
- `cache_ttl_hours`
- `calendar_keywords`
- `priority_text`

### `calendar_entities`
Only configure calendars that really matter for:
- vacation
- office
- WFH
- visitors

Avoid noisy or irrelevant calendars.

### `lookahead_days`
Recommended:
- keep it short unless you have a strong reason to plan further ahead

### `cache_ttl_hours`
Recommended:
- do not make it too long
- if calendar changes often, prefer a shorter cache

### `calendar_keywords`
This is one of the most important calendar fields.

Configure strong keywords for:
- `vacation`
- `wfh`
- `office`
- `visitor`

Recommended:
- a small number of robust keywords beats a long list of weak variants

### `priority_text`
Use this to define category conflict order.

Recommended order in most homes:
1. `vacation`
2. `office` / `wfh`
3. `visitor`

## 6. Heating

Only configure this once your climate model is already clear.

General fields:
- `climate_entity`
- `apply_mode`
- `temperature_step`
- `manual_override_guard`
- `outdoor_temperature_entity`
- `vacation_hours_from_start_entity`
- `vacation_hours_to_end_entity`
- `vacation_total_hours_entity`
- `vacation_is_long_entity`
- `context_entities`

### `climate_entity`
Required if you want to use the heating domain at all.

Recommended:
- one stable, authoritative climate entity
- avoid wrappers unless you are sure they expose the right semantics

### `temperature_step`
Set it to the actual granularity supported by the device.

Do not use a finer step than the climate entity can realistically apply.

### `manual_override_guard`
Recommended:
- keep it `true` almost always

This avoids fighting user-driven climate changes.

### Vacation bindings

These matter mostly for `vacation_curve`.

If you do not have reliable upstream entities for:
- hours since vacation start
- hours to vacation end
- total vacation duration
- long-vacation boolean

then do not rush into `vacation_curve`.

### Override branches

Each `house_state` can be assigned a branch such as:
- `disabled`
- `fixed_target`
- `vacation_curve`

Recommended:
- start with very few overrides
- do not define branches for every state just because the menu allows it

`fixed_target`:
- good for simple, explicit states

`vacation_curve`:
- only worth using if the vacation helper entities are solid

## 7. Security

Fields:
- `enabled`
- `security_state_entity`
- `armed_away_value`
- `armed_home_value`

Recommended:
- enable this only if you have a reliable upstream security state

`security_state_entity`:
- ideally an `alarm_control_panel`
- a sensor or binary sensor is acceptable only if it is semantically stable

`armed_away_value` / `armed_home_value`:
- always verify the real state strings exposed by your entity
- do not assume HA-standard wording unless you have checked it

## 8. Learning

Fields:
- `outdoor_lux_entity`
- `outdoor_temp_entity`
- `weather_entity`
- `context_signal_entities`
- `enabled_plugin_families`

### Context entities

Recommended:
- configure only a small number of global context signals that are genuinely useful

Good examples:
- outdoor lux
- outdoor temperature
- weather
- a small number of semantically strong helper signals

Avoid:
- large bags of noisy entities
- context signals that are only weakly correlated with behavior

### `enabled_plugin_families`
Use this to control which learning families are active.

Very useful for:
- phased rollout
- debugging
- reducing noise in an early installation

Recommended:
- enable only the families you are actually ready to use
- if one family is not mature or too noisy for your house, disable it here

## 9. Notifications

Main fields:
- `recipients`
- `recipient_groups`
- `route_targets`
- `enabled_event_categories`
- `dedup_window_s`
- `rate_limit_per_key_s`
- occupancy mismatch policy fields
- security mismatch policy fields

### Recipients, groups, and routes

Only configure these if you already know how notifications should be routed.

Recommended:
- a small set of clear recipients
- groups only where they add real value
- route targets kept minimal

### Event categories

Do not enable everything by default.

Recommended:
- keep only the categories you actively want to observe
- start narrow and expand later

### Dedup and rate limiting

If notifications are noisy:
- increase `dedup_window_s`
- increase `rate_limit_per_key_s`

If notifications feel too delayed:
- reduce them carefully

### Occupancy and security mismatch settings

These are more advanced operational controls.

Use them when:
- you are actively validating occupancy consistency
- you want explicit security mismatch reporting

If not, keep the defaults.

## 10. Reactions

This section is for:
- inspecting configured reactions
- muting or unmuting them
- editing or deleting them
- creating admin-authored automations

Recommended:
- do not start your setup journey here
- use it after the base context and domain configuration are already stable

## 11. Create Automation / Admin-Authored Templates

Important current templates:
- `lighting.scene_schedule.basic`
- `room.signal_assist.basic`
- `room.darkness_lighting_assist.basic`
- `security.vacation_presence_simulation.basic`

### `lighting.scene_schedule.basic`
Use it when:
- you want a simple, explicit recurring lighting routine

Do not use it:
- before the room model is already stable

### `room.signal_assist.basic`
Use it when:
- you have a very clear primary signal
- and a bounded, obvious actuation

Good example:
- bathroom humidity -> ventilation

### `room.darkness_lighting_assist.basic`
Use it when:
- you have a reliable room light sensor
- and you want a clear darkness-driven lighting assist

### `security.vacation_presence_simulation.basic`
Use it when:
- you already have accepted or credible lighting routines
- and the flow marks it as available

Important:
- this template is intentionally unavailable if the lighting evidence is too weak
- that is the correct behavior, not a missing feature

## 12. Proposals

Do not accept proposals in bulk.

Recommended:
- accept only proposals you understand clearly
- if a proposal is directionally right but still noisy, improve the underlying context first
- use review and diagnostics as validation tools, not as a rubber stamp

## Recommended setup profiles

### Simple home
- `General`
- `People` with `ha_person`
- a small, clean `Rooms` model
- basic `Lighting Rooms`
- a narrow `Learning` setup

Avoid early:
- weighted quorum everywhere
- complex zones
- advanced heating
- rich notification routing

### Complex presence home
- named people with `weighted_quorum`
- anonymous presence only if the house-level signals are truly credible
- more conservative room dwell timers

### Security / vacation-focused home
- well-configured calendar
- reliable security state entity
- mature lighting routines
- then `security_presence_simulation`

## Common mistakes

- binding too many weak house-level signals
- using anonymous presence as a replacement for proper named people setup
- creating `derived` rooms without meaningful sources
- filling lighting or heating mappings just for completeness
- enabling all learning families too early
- accepting proposals without understanding their identity and semantics

## Recommended rollout strategy

1. make `People` solid
2. stabilize `Rooms`
3. add `Lighting`
4. add `Calendar`
5. only then move to `Heating`, `Security`, `Reactions`, and `Notifications`

This is the most robust and least noisy path.
