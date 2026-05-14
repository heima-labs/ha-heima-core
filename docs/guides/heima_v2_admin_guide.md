# Heima v2 Admin Guide

This guide explains how an administrator should configure and operate Heima v2 through the Home Assistant config flow and options flow.

It covers:
- what to do on first install
- what to do on later runs
- every options-flow section
- how to review proposals and admin-authored automations
- what to monitor after configuration

Related guides:
- [Operations Guide](heima_operations_guide.md)
- [House State Behavior Guide](house_state_behavior_guide.md)
- [Scene and Script Usage](scene_and_script_usage.md)
- [Plugin Authoring](plugin_authoring.md)

## Admin Access

Only Home Assistant administrators can open the Heima config flow and options flow.

If a non-admin user opens the flow, Heima aborts with `admin_required`. This is intentional: the flow can change runtime behavior, persistence, reaction execution, notification routing, and security-related configuration.

## Mental Model

Heima v2 is configured in layers:

1. Global runtime settings and house-state signals.
2. People and room model.
3. Domain mappings such as lighting, calendar, heating, security, notifications, and external context.
4. Learning configuration.
5. Reactions, proposals, and admin-authored automations.
6. Validation and operational review.

Do not start by accepting proposals or creating many reactions. A proposal is only as good as the underlying people, room, signal, and domain configuration.

## First Install

The initial config flow is intentionally small.

When you add the integration:

1. Open `Settings` -> `Devices & services` -> `Add integration`.
2. Select `Heima`.
3. Set `engine_enabled`.
4. Create the entry.

The first entry stores only the minimum startup options:

- `engine_enabled`
- `timezone`
- `language`
- `lighting_apply_mode`

The timezone and language are taken from Home Assistant defaults. After the entry is created, immediately open the options flow to complete the real setup.

Recommended first-run posture:

- Keep `engine_enabled = true` if you are ready to observe runtime behavior.
- Set `engine_enabled = false` if you want to configure everything before Heima acts.
- Do not configure reactions until people, rooms, and relevant domain mappings are stable.

## First Options-Flow Run

After creating the entry, open `Configure`.

Recommended order for the first complete setup:

1. `General`
2. `Discovery`
3. `People`
4. `Rooms`
5. `Lighting Rooms`
6. `Calendar`
7. `External Context`
8. `Learning`
9. `Heating`
10. `Security`
11. `Notifications`
12. `Validation`
13. `Save`

You can skip sections that do not apply to the house. For example, skip `Heating` if you do not want Heima to reason about climate control, and skip `Security` if there is no stable alarm/security state.

## Later Options-Flow Runs

Use later runs for narrow changes:

- Add or review a new Home Assistant person.
- Add a room or resync HA areas.
- Tune dwell timers after observing room occupancy.
- Add a calendar or adjust keywords.
- Enable one learning family after the base model is stable.
- Review proposals.
- Edit, mute, or delete configured reactions.
- Create one bounded admin-authored automation.
- Run `Validation` after structural changes.

Do not use later runs to change many independent axes at once. If behavior changes afterward, it becomes hard to know which change caused it.

## Save Behavior

Most options-flow sections update the entry options immediately when the step succeeds. Menu `Save` closes the flow with the finalized option snapshot.

Practical rule:

- Use section-specific `Save` or top-level `Save` when you are done.
- If a section returns to the main menu, its accepted changes have already been written into the flow's options snapshot.
- Run `Validation` before final save after a large setup pass.

## Top-Level Menu

The options flow exposes these top-level entries:

- `General`
- `Discovery`
- `Validation`
- `People`
- `Rooms`
- `Lighting Rooms`
- `Heating`
- `Security`
- `Notifications`
- `Calendar`
- `Learning`
- `External Context`
- `Reactions`
- `Edit Reactions`
- `Create Automation`
- `Proposals`
- `Save`

The menu summaries are operational hints. Treat them as quick status, not as a full diagnostic report.

## General

Purpose:

- Enable or disable the runtime engine.
- Set timezone and language.
- Choose lighting apply mode.
- Bind house-state signals.
- Tune house-state timing.

Fields:

- `engine_enabled`: global runtime toggle.
- `timezone`: Home Assistant timezone string used for time-based logic.
- `language`: language used for admin-facing flow text and summaries.
- `lighting_apply_mode`: lighting execution mode.
- `vacation_mode_entity`
- `guest_mode_entity`
- `sleep_window_entity`
- `relax_mode_entity`
- `work_window_entity`
- `media_active_entities`
- `sleep_charging_entities`
- `work_activity_entities`
- `workday_entity`
- `sleep_enter_min`
- `sleep_exit_min`
- `work_enter_min`
- `work_activity_required`
- `work_activity_grace_min`
- `relax_enter_min`
- `relax_exit_min`
- `sleep_requires_media_off`
- `sleep_charging_min_count`

Recommended first-run settings:

- Confirm `timezone`.
- Confirm `language`.
- Keep `lighting_apply_mode = scene` unless you intentionally want delegated behavior.
- Bind only house-state entities with clear semantics.
- Leave timing defaults unless you already know your home needs slower or faster state transitions.

`lighting_apply_mode`:

- `scene`: Heima can apply scene/script-backed lighting reactions.
- `delegate`: Heima computes and stores configuration but does not execute configured reactions.

If `delegate` is active while reactions exist, the General step shows a warning. This is expected.

House-state signal guidance:

- Use explicit helpers or stable sensors.
- Avoid weak proxies.
- A few strong signals are better than many noisy signals.

Timing guidance:

- Increase enter timers if state changes are too eager.
- Increase exit timers if states drop too quickly.
- Change one timing value at a time.

Work activity guidance:

- Use `work_activity_entities` for recent human work activity, not raw computer power.
- Set `work_activity_required = true` only when a missing activity signal should prevent `working`.
- Use `work_activity_grace_min` to keep `working` stable during short breaks.
- Do not add work computers to `media_active_entities` just to detect work; that can interfere with sleep.

For expected state transitions and examples, see [House State Behavior Guide](house_state_behavior_guide.md).

## Discovery

Purpose:

- Scan HA registries and states for candidate bindings.
- Apply suggested bindings to rooms or activity-related options.

Actions:

- `accept_all`
- `accept_non_ambiguous`
- `accept_selected`
- `reject_all`

First-run guidance:

- Start with `accept_non_ambiguous`.
- Review ambiguous candidates manually.
- Use `accept_selected` when you understand exactly what each candidate does.
- Use `reject_all` if discovery suggestions do not match your naming or area model.

Discovery is a helper, not a source of truth. After applying candidates, review `Rooms` and `Validation`.

## Validation

Purpose:

- Show installation/configuration issues.
- Let the admin save or go back.

Actions:

- `back`
- `save`

Use `Validation`:

- after first setup
- after adding people
- after changing rooms
- after changing lighting mappings
- after adding reactions or learning families
- before considering the setup ready

Do not ignore validation warnings. They usually indicate missing entities, inconsistent room mappings, or options that will produce poor runtime behavior.

## People

Purpose:

- Configure named people.
- Configure anonymous presence.
- Configure debug aliases for test setups.

The People menu contains:

- `people_edit`
- `people_anonymous`
- `people_debug_aliases`
- `people_save`
- `people_next`

Heima also bootstraps HA-backed people from the Home Assistant `person.*` inventory. Entries may show sync status such as `[new]`, `[configured]`, or `[orphaned]`.

### Named People

Fields:

- `slug`
- `display_name`
- `presence_method`
- `presence_rule`
- `person_entity`
- `sources`
- `group_strategy`
- `required`
- `weight_threshold`
- `source_weights`
- `arrive_hold_s`
- `leave_hold_s`
- `enable_override`

`slug`:

- Must be stable.
- Must be unique.
- Must not start with `heima_`.
- Do not rename casually because canonical entity IDs depend on it.

`presence_method`:

- `ha_person`: use a Home Assistant `person.*` entity.
- `quorum`: combine multiple sensors or trackers.
- `manual`: keep the person controlled manually.

First-run recommendation:

- Use `ha_person` for every reliable Home Assistant person.
- Use `quorum` only when a single `person.*` entity is not reliable enough.
- Avoid `manual` except for deliberate testing or special cases.

`presence_rule`:

- `resident`: normal resident.
- `observer`: tracked for context but should be treated more cautiously.
- `recurrent`: recurring person or frequent visitor-like identity.

Quorum guidance:

- `group_strategy = quorum`: require a count of active sources.
- `group_strategy = weighted_quorum`: assign weights when sources have different quality.
- `required` must be realistic for the number of sources.
- `weight_threshold` should reflect the weight total needed to trust presence.
- `source_weights` is a mapping such as:

```text
binary_sensor.phone_ble_stefano=0.8
device_tracker.phone_stefano=1.0
sensor.router_stefano=0.5
```

Hold timers:

- Increase `leave_hold_s` if people drop to away too easily.
- Keep `arrive_hold_s` short when fast arrival is important and sources are clean.

`enable_override`:

- Creates/uses a per-person override control.
- Useful for testing and recovery.
- Not required for normal households.

### Anonymous Presence

Purpose:

- Represent "someone is home" without identifying a named person.

Fields:

- `enabled`
- `sources`
- `group_strategy`
- `required`
- `weight_threshold`
- `source_weights`
- `anonymous_count_weight`
- `arrive_hold_s`
- `leave_hold_s`

Use anonymous presence when:

- guests are common
- house-level presence is meaningful
- privacy-preserving occupancy matters

Avoid anonymous presence when:

- it is only compensating for broken named people setup
- sources are broad motion spikes
- signals do not indicate continuous presence

Keep `anonymous_count_weight = 1` unless there is a specific reason to count anonymous presence more strongly.

### Debug Aliases

Purpose:

- Test/demo identity behavior without changing real HA people.

Fields:

- `enabled`
- `aliases`

Expected alias shape:

```json
{
  "demo_alex": {
    "mode": "alias_person",
    "person_entity": "person.alex",
    "display_name": "Demo Alex"
  },
  "guest_test": {
    "mode": "synthetic",
    "display_name": "Guest Test",
    "synthetic_state": "home"
  }
}
```

Use this only for testing. Do not rely on debug aliases as the normal production identity model.

## Rooms

Purpose:

- Define the room model.
- Bind rooms to HA areas.
- Configure room occupancy and learning sources.
- Configure canonical room signals.

The Rooms menu contains:

- `rooms_add`
- `rooms_edit`
- `rooms_remove`
- `rooms_import_areas`
- `rooms_save`
- `rooms_next`

Room fields:

- `room_id`
- `display_name`
- `area_id`
- `learning_sources`
- `signals`
- `occupancy_mode`
- `occupancy_sources`
- `logic`
- `weight_threshold`
- `source_weights`
- `on_dwell_s`
- `off_dwell_s`
- `max_on_s`

`room_id`:

- Must be stable.
- Must be unique.
- Must not start with `heima_`.
- Use clean slugs such as `studio`, `living_room`, `bedroom`.

`area_id`:

- Bind to the matching Home Assistant area.
- If omitted while adding/editing, Heima attempts to create or reuse a matching HA area.
- Removing a room can also remove the associated HA area managed through the flow.

`occupancy_mode`:

- `derived`: room occupancy is computed from sources.
- `none`: room exists but has no derived occupancy.

Use `derived` only when there are credible room-level signals. Use `none` for rooms that are useful for lighting or organization but do not have meaningful occupancy sensing.

`occupancy_sources`:

- Use sensors local to the room.
- Good: PIR, mmWave, door/contact relevant to that room, strong room-specific binary sensors.
- Bad: whole-home presence, hallway sensors used for multiple rooms, weak generic proxies.

`learning_sources`:

- Evidence sources used for learning.
- Usually align with occupancy sources.
- Add extra learning sources only when they materially improve room-specific evidence.

`signals`:

- Advanced JSON room-signal configuration.
- Used by signal-based assists, bucket thresholds, and burst detection.
- Each item can include `entity_id`, `signal_name`, `device_class`, `buckets`, and optional burst fields.

Example:

```json
[
  {
    "entity_id": "sensor.studio_temperature",
    "signal_name": "room_temperature",
    "device_class": "temperature",
    "buckets": [
      {"label": "cool", "upper_bound": 20},
      {"label": "ok", "upper_bound": 24},
      {"label": "warm", "upper_bound": 27},
      {"label": "hot", "upper_bound": null}
    ],
    "burst_threshold": 1.5,
    "burst_window_s": 600,
    "burst_direction": "up"
  }
]
```

Occupancy logic:

- `any_of`: pragmatic default.
- `all_of`: strict; use only when all sources must be active.
- `weighted_quorum`: best when sources have different trust levels.

Dwell and timeout:

- `on_dwell_s`: delay before confirming occupied.
- `off_dwell_s`: delay before confirming vacant.
- `max_on_s`: cap for sticky occupancy.

First-run recommendation:

- Import or review HA areas.
- Add only real rooms.
- Start with `any_of`.
- Keep `off_dwell_s` conservative.
- Do not force every room to have occupancy.

## Lighting Rooms

Purpose:

- Map room-level scenes.
- Enable or disable manual hold behavior per room.

The Lighting Rooms menu contains:

- `lighting_rooms_edit`
- `lighting_rooms_save`
- `lighting_rooms_next`

Fields:

- `room_id`
- `scene_evening`
- `scene_relax`
- `scene_night`
- `scene_off`
- `enable_manual_hold`

First-run recommendation:

- Configure `scene_evening` and `scene_off` first.
- Add `scene_relax` and `scene_night` only where the distinction is meaningful.
- Keep `enable_manual_hold = true`.

Manual hold prevents Heima from immediately fighting manual user changes.

For action selection guidance, see [Scene and Script Usage](scene_and_script_usage.md).

## Lighting Zones

Purpose:

- Group rooms into shared lighting zones.

The Lighting Zones menu appears after Lighting Rooms and contains:

- `lighting_zones_add`
- `lighting_zones_edit`
- `lighting_zones_remove`
- `lighting_zones_save`
- `lighting_zones_next`

Fields:

- `zone_id`
- `display_name`
- `rooms`

Use zones for real shared spaces:

- open-plan living room and kitchen
- room plus adjacent transition area
- multiple rooms that should be coordinated

Avoid zones that merely duplicate the room model.

## Calendar

Purpose:

- Give Heima vacation, office, WFH, and visitor context from calendars.

Fields:

- `calendar_entities`
- `lookahead_days`
- `cache_ttl_hours`
- `calendar_keywords`
- `priority_text`

`calendar_entities`:

- Add only calendars that matter for home behavior.
- Avoid noisy personal calendars unless keywords are precise.

`lookahead_days`:

- Range: 1 to 30.
- Keep short unless planning farther ahead is useful.

`cache_ttl_hours`:

- Range: 1 to 24.
- Use shorter TTLs if calendar changes frequently.

`calendar_keywords`:

- Object mapping category to keywords.
- Typical categories: `vacation`, `wfh`, `office`, `visitor`.

Example:

```json
{
  "vacation": ["vacation", "holiday", "trip"],
  "wfh": ["wfh", "work from home"],
  "office": ["office"],
  "visitor": ["guest", "visitors"]
}
```

`priority_text`:

- Comma-separated category priority.
- Example: `vacation, office, wfh, visitor`.

First-run recommendation:

- Configure one or two high-value calendars.
- Keep keywords strict.
- Put `vacation` first if vacation behavior matters.

## External Context

Purpose:

- Bind canonical external-context slots to Home Assistant sensors.

Fields:

- `outdoor_temp`
- `outdoor_humidity`
- `outdoor_lux`
- `wind_speed`
- `rain_last_1h`
- `rain_forecast_next_6h`
- `weather_condition`
- `weather_alert_level`
- `weather_alert_phenomena`

Use this when:

- you have stable weather/environment sensors
- you want domain logic and learning to use canonical external signals

Do not bind weak or inconsistent sensors. Leave slots empty until a reliable source exists.

## Learning

Purpose:

- Configure global learning context.
- Choose active learning plugin families.

Fields:

- `outdoor_lux_entity`
- `outdoor_temp_entity`
- `weather_entity`
- `context_signal_entities`
- `enabled_plugin_families`

Plugin families:

- `presence`
- `heating`
- `lighting`
- `composite_room_assist`
- `security_presence_simulation`

First-run recommendation:

- Configure outdoor lux and outdoor temperature if available.
- Keep `context_signal_entities` small and meaningful.
- Do not enable a family unless the relevant base configuration is ready.

Phased rollout:

1. Start with `presence` and `lighting` only if people/rooms/lighting are stable.
2. Add `composite_room_assist` after room signals are configured.
3. Add `heating` after the heating model is configured.
4. Add `security_presence_simulation` after lighting routines and security state are reliable.

## Heating

Purpose:

- Configure the climate entity and heating policy context.
- Define optional override branches per house state.

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

`climate_entity`:

- Required to use heating.
- Should be the authoritative Home Assistant `climate.*` entity.

`apply_mode`:

- Controls how Heima delegates or applies heating behavior.
- Keep the default unless you are validating a specific heating runtime path.

`temperature_step`:

- Match the device capability.
- Do not configure a finer step than the climate entity can apply.

`manual_override_guard`:

- Keep enabled in most homes.
- It prevents Heima from fighting manual climate changes.

Vacation bindings:

- Required for `vacation_curve` branches.
- Leave `vacation_curve` unused unless these sensors are reliable.

Override branches:

1. Select a house state.
2. Select a branch type.
3. Fill branch parameters if needed.

Branch types:

- `disabled`: no override.
- `fixed_target`: set a fixed target temperature.
- `vacation_curve`: use vacation ramp-down/ramp-up parameters.

First-run recommendation:

- Configure only the general heating section.
- Add one `fixed_target` branch only if there is an obvious need.
- Postpone `vacation_curve` until vacation helper sensors are proven.

## Security

Purpose:

- Bind a security state entity.
- Configure armed-state values.
- Configure camera evidence sources for security mismatch and return-home evidence.

Fields:

- `enabled`
- `security_state_entity`
- `armed_away_value`
- `armed_home_value`
- `camera_evidence_sources`

`security_state_entity`:

- Prefer `alarm_control_panel`.
- Use `sensor` or `binary_sensor` only when the state vocabulary is stable.

`armed_away_value` and `armed_home_value`:

- Must match the actual state strings from Home Assistant.
- Check Developer Tools before configuring.

`camera_evidence_sources`:

- Object keyed by camera/source ID.
- Each item supports:
  - `id`
  - `display_name`
  - `enabled`
  - `role`
  - `motion_entity`
  - `person_entity`
  - `vehicle_entity`
  - `contact_entity`
  - `return_home_contributor`
  - `security_priority`

Example:

```json
{
  "entry_cam": {
    "display_name": "Front Door Camera",
    "enabled": true,
    "role": "entry",
    "person_entity": "binary_sensor.front_cam_person",
    "contact_entity": "binary_sensor.front_door_contact",
    "return_home_contributor": true,
    "security_priority": "high"
  }
}
```

First-run recommendation:

- Enable security only after confirming the upstream alarm/security entity.
- Add camera evidence sources later, one by one.

## Notifications

Purpose:

- Configure notification recipients, groups, routing, event categories, deduplication, and mismatch reporting.

Fields:

- `recipients`
- `recipient_groups`
- `route_targets`
- `enabled_event_categories`
- `dedup_window_s`
- `rate_limit_per_key_s`
- `occupancy_mismatch_policy`
- `occupancy_mismatch_min_derived_rooms`
- `occupancy_mismatch_persist_s`
- `security_mismatch_policy`
- `security_mismatch_event_mode`
- `security_mismatch_persist_s`

`recipients`:

- Mapping of recipient ID to service/target configuration.

`recipient_groups`:

- Mapping of group ID to recipient IDs.
- Every group member must exist in `recipients`.

`route_targets`:

- List of recipient IDs or group IDs.
- Every route target must exist.

Recommended first-run settings:

- Keep routing minimal.
- Enable only event categories that someone will act on.
- Keep default dedup and rate limits until there is real noise to tune.

Mismatch policies:

- Use occupancy mismatch settings when validating room/home occupancy consistency.
- Use security mismatch settings when armed-state behavior and presence behavior must be compared.

## Reactions

Purpose:

- Manage configured reactions.
- Mute or unmute reactions.
- Edit reaction settings.
- Delete reactions.

Top-level entries:

- `Reactions`: mute/unmute configured reactions.
- `Edit Reactions`: choose a configured reaction and edit or delete it.

Reaction editing supports specialized forms for:

- room signal assist
- room cooling assist
- room air quality assist
- room darkness lighting assist
- room contextual lighting assist
- room vacancy lights off
- scheduled routine
- vacation presence simulation
- generic action-based reactions

Common edit fields:

- `enabled`
- action entities or light entities
- trigger signal names and buckets
- contextual lighting policy JSON
- scheduled time and weekday
- delete confirmation

Operational guidance:

- Prefer muting when you want a temporary pause.
- Prefer disabling when the reaction should remain configured but inactive.
- Delete only when the reaction is no longer meaningful.
- Edit one reaction at a time and observe behavior afterward.

## Create Automation

Purpose:

- Create bounded admin-authored reactions without waiting for learning proposals.

The flow starts with `admin_authored_create`, where available templates are listed. Some templates can be unavailable if prerequisites are missing.

Implemented templates:

- `room.signal_assist.basic`
- `room.darkness_lighting_assist.basic`
- `room.contextual_lighting_assist.basic`
- `room.vacancy_lighting_off.basic`
- `scheduled_routine.basic`
- `security.vacation_presence_simulation.basic`

### Room Signal Assist

Use when a primary room signal should trigger a scene or script.

Typical examples:

- humidity high -> bathroom fan script
- temperature burst -> cooling script
- air quality bucket -> ventilation scene/script

Important fields:

- room
- primary signal name
- trigger mode: bucket or burst
- primary bucket and match mode
- optional corroboration signal and bucket
- action entities

Use a corroboration signal only when it materially reduces false positives.

### Darkness Lighting Assist

Use when darkness in a room should apply one or more light actions.

Important fields:

- room
- primary light signal, usually `room_lux`
- bucket and match mode
- light entities
- action
- brightness
- color temperature

Use only with reliable lux or darkness signals.

### Contextual Room Lighting

Use when room lighting should vary by time or context.

Important fields:

- room
- primary light signal
- bucket and match mode
- preset
- light entities
- generated policy JSON

Built-in presets:

- `daytime_focus`
- `evening_warmth`
- `night_navigation`
- `all_day_adaptive`

The policy editor stores a JSON contract with profiles, rules, default profile, ambient modulation, and follow-up window.

Use custom JSON only when you understand the contract. Built-in presets are safer for normal administration.

### Vacancy Lights Off

Use when lights should turn off after a room remains vacant.

Important fields:

- room
- light entities
- vacancy delay in minutes

Keep delay conservative in rooms where people may sit still.

### Scheduled Routine

Use for explicit weekday/time routines.

Important fields:

- weekday
- scheduled time
- routine kind
- target entities
- entity action
- house states
- skip if anyone home

Routine kinds:

- `scene`
- `script`
- `entity_action`

Use `scene` when possible. Use `script` for procedural or multi-domain logic. Use `entity_action` for simple `turn_on` / `turn_off` entity behavior.

### Vacation Presence Simulation

Use when Heima should simulate presence during vacation using accepted lighting behavior.

Important fields:

- enabled
- allowed rooms
- allowed entities
- requires dark outside
- simulation aggressiveness
- jitter overrides
- max events per evening
- latest end time
- skip if presence detected

Availability:

- This template is intentionally unavailable until accepted lighting routines exist.
- If it is unavailable, build or accept credible lighting routines first.

Security guidance:

- Keep `skip_if_presence_detected = true`.
- Keep `requires_dark_outside = true` unless there is a clear reason.
- Start with `medium` aggressiveness.

## Proposals

Purpose:

- Review learning-generated proposals.
- Accept, skip, ignore, or configure proposed actions.
- Convert some improvement proposals into better reaction types.

Do not bulk-accept proposals.

Review checklist:

- Does the proposal match a real behavior?
- Is the room correct?
- Are the target entities correct?
- Is the trigger understandable?
- Is the confidence meaningful?
- Is the proposal a duplicate of an existing configured reaction?
- Would accepting it make Heima act in a way a user expects?

Common actions:

- accept a clear proposal
- configure action entities before accepting
- skip when more evidence is needed
- ignore when the proposal is wrong

For action entities:

- Prefer `scene.*` for room-scoped lighting.
- Use `script.*` for procedural or multi-domain behavior.

## Recommended Rollout Plans

### Minimal Home

1. General
2. People with `ha_person`
3. Rooms with simple occupancy
4. Lighting Rooms with evening/off scenes
5. Learning with only relevant families
6. Validation
7. Observe before adding reactions

### Presence-Heavy Home

1. Configure named people carefully.
2. Use `weighted_quorum` only where needed.
3. Add anonymous presence only after named people are stable.
4. Keep room dwell timers conservative.
5. Validate before enabling proposal-driven automation.

### Lighting-First Home

1. Rooms and HA areas.
2. Lighting Rooms.
3. Outdoor lux in Learning or External Context.
4. Accept only clear lighting proposals.
5. Add contextual lighting after basic lighting behavior is stable.

### Security/Vacation Home

1. Calendar with strict vacation keywords.
2. Security state entity.
3. Lighting routines.
4. Security presence simulation learning family.
5. Vacation presence simulation template.
6. Operations review after the first vacation window.

## After First Run

Use this operational sequence:

1. Run `Validation`.
2. Let the system observe normal behavior.
3. Review `Proposals` periodically.
4. Accept only clear proposals.
5. Use `Reactions` to mute/edit/delete configured behavior.
6. Use diagnostics when something is confusing.

Useful commands:

```bash
source scripts/.env
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
python3 scripts/learning_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section engine
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section learning
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section reactions
```

## Common Mistakes

- Accepting proposals before rooms are stable.
- Binding too many weak house-state signals.
- Using anonymous presence to mask broken named people setup.
- Creating derived rooms without room-local signals.
- Filling every scene slot just because it exists.
- Enabling every learning family at once.
- Using `script.*` for simple lighting scenes that could be `scene.*`.
- Configuring vacation simulation before lighting routines exist.
- Changing people, rooms, learning families, and reactions in the same run.
- Ignoring validation warnings.

## Admin Rules Of Thumb

- Configure structure before behavior.
- Prefer stable HA entities over clever proxies.
- Prefer fewer, stronger signals.
- Prefer `scene.*` for lighting and `script.*` for procedural behavior.
- Prefer muting before deleting if you are not sure.
- Tune one thing at a time.
- Run validation after structural changes.
- Review diagnostics before assuming learning is wrong.
