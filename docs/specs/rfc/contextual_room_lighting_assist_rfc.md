# Contextual Room Lighting Assist RFC

## Status

Draft

## Problem

`room_darkness_lighting_assist` today is too static:

- trigger: room becomes occupied while room lux is in a dark-enough bucket
- effect: apply one fixed set of `entity_steps`

This is good for a basic room-light-on behavior, but it is not good enough for rooms whose lighting should vary by context.

Example: `studio`

- during daytime while `house_state=working`, the room should prefer brighter and cooler light
- during daytime while not working, the room should prefer a softer and more neutral scene
- in the evening, the room should prefer warmer light
- late at night, the room should prefer low-intensity warm navigation light

The current model cannot express this cleanly without duplicating multiple reactions or encoding brittle logic outside the reaction.

## Goal

Introduce a new reaction family that:

- keeps the same primary trigger semantics as `room_darkness_lighting_assist`
- resolves the final `entity_steps` from contextual policy rules
- chooses different light profiles depending on time and occupancy context

This reaction should be explicit, deterministic, and easy to debug.

## Non-goals

This RFC does not try to:

- infer deep semantic human intent from ambiguous signals
- replace all existing lighting reactions immediately
- build a probabilistic or ML-based scene selector

The first version should stay rule-based.

## New Reaction Type

Introduce a new canonical reaction type:

- `room_contextual_lighting_assist`

This reaction is room-scoped and bucket-triggered, like darkness assist, but its apply
payload is selected from a list of profiles and rules instead of one fixed `entity_steps` block.

## Core Model

### Trigger Layer

The trigger layer remains simple:

- room is occupied
- primary signal is `room_lux`
- current bucket matches a configured darkness condition

Suggested canonical fields:

- `reaction_type = "room_contextual_lighting_assist"`
- `room_id`
- `primary_signal_name = "room_lux"`
- `primary_bucket`
- `primary_bucket_match_mode`
- `followup_window_s`

Optional corroboration stays allowed but is not the focus of this RFC.

### Ambient Modulation Layer

Some rooms should not only choose a different profile by context, but also adjust
the final light intensity according to outside brightness.

Example:

- the selected profile remains `workday_focus`
- color temperature stays aligned with the selected profile
- final brightness is reduced when outdoor light is strong
- final brightness is increased slightly when outdoor light is very low

This must be modeled as an optional **modulation layer inside the same reaction**,
not as a second independent reaction targeting the same lights.

Reason:

- two separate reactions writing to the same lights would create ordering conflicts
- debugging would become opaque
- cooldown interactions would become harder to reason about

So the correct evaluation order is:

1. primary trigger matches
2. contextual rule selects a profile
3. optional ambient modulation adjusts the selected profile `entity_steps`
4. final `needs_apply` / cooldown / fire logic runs on the adjusted result

The modulation layer is optional.

### Policy Layer

The final light behavior is chosen from profiles.

Each reaction contains:

- `profiles`
- `rules`
- `default_profile`
- optional `ambient_modulation`

#### Profiles

A profile is a named set of `entity_steps`.

Example:

```yaml
profiles:
  workday_focus:
    entity_steps:
      - entity_id: light.studio_desk
        action: on
        brightness: 180
        color_temp_kelvin: 4300
      - entity_id: light.studio_main
        action: on
        brightness: 140
        color_temp_kelvin: 4000

  day_generic:
    entity_steps:
      - entity_id: light.studio_desk
        action: on
        brightness: 140
        color_temp_kelvin: 3600

  evening_relax:
    entity_steps:
      - entity_id: light.studio_desk
        action: on
        brightness: 100
        color_temp_kelvin: 2700

  night_navigation:
    entity_steps:
      - entity_id: light.studio_desk
        action: on
        brightness: 25
        color_temp_kelvin: 2200
```

#### Rules

Rules select one profile.

Rules are evaluated in order, first match wins.

Suggested fields:

- `profile`
- `house_state_in`
- `time_window`
- `occupancy_reason_in`
- `min_presence_age_s`
- `max_presence_age_s`

Example:

```yaml
rules:
  - profile: workday_focus
    house_state_in: [working]
    time_window:
      start: "08:00"
      end: "18:30"

  - profile: day_generic
    house_state_in: [home, relax]
    time_window:
      start: "08:00"
      end: "18:30"

  - profile: evening_relax
    time_window:
      start: "18:30"
      end: "23:30"

  - profile: night_navigation
    time_window:
      start: "23:30"
      end: "06:30"

default_profile: day_generic
```

#### Ambient Modulation

Version 2 of this RFC should support optional brightness modulation driven by an
external signal such as `outdoor_lux`.

The first supported mode should be:

- `brightness_multiplier`

Suggested shape:

```yaml
ambient_modulation:
  source_signal_name: outdoor_lux
  mode: brightness_multiplier
  buckets:
    bright: 0.70
    normal: 1.00
    dark: 1.15
  clamp_min: 20
  clamp_max: 255
```

Semantics:

- modulation does **not** change the selected profile
- modulation does **not** change `color_temp_kelvin`
- modulation adjusts only `brightness`
- modulation applies after profile selection and before `needs_apply`
- if a selected `entity_step` has no brightness field, it is left unchanged

This keeps the policy model simple:

- profile = intent
- ambient modulation = contextual refinement of brightness

Future extensions may add more advanced modes such as profile overrides by
outdoor bucket, but the initial design should stay brightness-only.

## Occupancy Reason

The user requirement includes:

- different light depending on why a person occupies a room

Heima does not currently know a true semantic reason such as:

- working
- studying
- relaxing
- passing through

So this RFC introduces a constrained proxy model instead of pretending to know more than the system actually knows.

### Allowed Context Inputs

Version 1 should support only explicit or strongly justified proxies:

- `house_state`
- time window
- presence age in room
- optional room-local mode signal later

### Proposed `occupancy_reason`

Version 1 should compute a derived reason with a conservative resolver:

- `focus`
  - when `house_state=working`
- `settled`
  - when room has been occupied for at least `min_presence_age_s`
- `transient`
  - when room has just become occupied and presence age is below a threshold
- `generic`
  - fallback

This is intentionally limited.

The system should not emit more refined meanings unless a dedicated explicit signal exists.

### Version 1 Threshold for `settled`

In v1, the threshold used to classify `settled` is a fixed internal constant of **600 seconds**.

`settled` is emitted when the room has been continuously occupied for at least 600s.

The ability to configure this threshold per-reaction (`min_presence_age_s` as a rule field)
is deferred to phase 2.

## Resolver Semantics

The reaction evaluation flow becomes:

1. verify primary trigger condition
2. verify room occupancy
3. compute current contextual facts:
   - `house_state`
   - local time
   - room occupancy age
   - derived `occupancy_reason`
4. select the first matching rule
5. load the target profile
6. optionally apply `ambient_modulation`
7. compute `needs_apply`
8. fire `entity_steps` from that profile if cooldown allows it

### needs_apply Definition

`needs_apply` is true when either:

- at least one entity in the selected profile's `entity_steps` is currently off, OR
- the selected profile differs from `last_applied_profile`

The second condition enables re-evaluation on context change: if the room is occupied
and the lights are on but the context has changed (new `house_state`, new time window,
new `occupancy_reason`), the reaction will re-apply the newly selected profile.

`last_applied_profile` is stored per reaction instance and updated each time the
reaction fires. It is reset to `None` when the room becomes unoccupied.

### Cooldown on Profile Switch

The cooldown (`followup_window_s`) is **not reset** when the selected profile changes.

Cooldown tracks time since last fire regardless of which profile was applied.
If the cooldown has not elapsed, the reaction is suppressed even if the profile
would change. This avoids rapid re-firing when context oscillates near a boundary
(e.g. `house_state` toggling between `working` and `home`).

### Time Window Midnight Crossing

A time window where `end < start` (in HH:MM comparison) crosses midnight.

Example: `start: "23:30"`, `end: "06:30"` matches from 23:30 to 06:30 the next day.

The resolver must handle this explicitly:

- if `start <= end`: window is active when `start <= current_time < end`
- if `start > end`: window is active when `current_time >= start` OR `current_time < end`

## Diagnostics

Diagnostics must explain not only whether the reaction fired, but why a profile was chosen.

Required diagnostics:

- `current_primary_bucket`
- `primary_bucket_match_mode`
- `current_house_state`
- `occupancy_age_s`
- `occupancy_reason`
- `selected_profile`
- `last_applied_profile`
- `selected_rule_index`
- `selected_rule_summary`
- `available_profiles`
- `ambient_source_bucket`
- `ambient_brightness_scale`
- `fire_count`
- `suppressed_count`
- `last_fired_iso`

This is required to avoid repeating the same class of opaque runtime debugging we have already seen with current darkness assist.

## Config Contract

Suggested persisted shape:

```yaml
reaction_type: room_contextual_lighting_assist
room_id: studio
primary_signal_name: room_lux
primary_bucket: ok
primary_bucket_match_mode: lte
followup_window_s: 900
profiles:
  workday_focus:
    entity_steps: [...]
  day_generic:
    entity_steps: [...]
  evening_relax:
    entity_steps: [...]
  night_navigation:
    entity_steps: [...]
rules:
  - profile: workday_focus
    house_state_in: [working]
    time_window: {start: "08:00", end: "18:30"}
  - profile: day_generic
    house_state_in: [home, relax]
    time_window: {start: "08:00", end: "18:30"}
  - profile: evening_relax
    time_window: {start: "18:30", end: "23:30"}
  - profile: night_navigation
    time_window: {start: "23:30", end: "06:30"}
default_profile: day_generic
ambient_modulation:
  source_signal_name: outdoor_lux
  mode: brightness_multiplier
  buckets:
    bright: 0.70
    normal: 1.00
    dark: 1.15
  clamp_min: 20
  clamp_max: 255
```

## Config Flow

Version 1 should use a guided JSON approach, not a fully structured editor.

The reason is pragmatic:

- the runtime contract in this RFC is already expressive and stable enough
- a structured editor would take longer to implement and validate correctly
- advanced users may want direct control over profiles and rules immediately

So V1 should:

1. collect the minimum guided inputs:
   - room
   - target lights
   - preset/template choice
2. generate a valid JSON payload from that input
3. show the generated JSON in an editable textarea
4. validate it strictly before saving
5. render a readable preview summary before final confirmation

This is not meant to be the final UX.

Version 2 can replace or augment this with a structured editor once the contract
has stabilized in production.

### V1 UX Shape

Version 1 UX should provide:

1. room selection
2. target lights selection
3. a small set of built-in profile templates
4. generated JSON contract, editable by the user
5. preview summary

Suggested built-in templates:

- `daytime_focus`
- `evening_warmth`
- `night_navigation`
- `all_day_adaptive`

### V1 Validation Requirements

The JSON editor must reject:

- unknown profile references in rules
- missing `default_profile`
- malformed `time_window`
- invalid `house_state_in`
- empty `entity_steps`
- invalid or missing `primary_bucket`

Errors must be attached to the form and not crash the flow.

Version 1 may omit `ambient_modulation` from the guided UI even if the contract
already reserves the field.

When the JSON editor exposes it, validation must reject:

- unknown outdoor buckets
- non-numeric multipliers
- invalid clamp bounds

## Migration Strategy

Do not mutate existing `room_darkness_lighting_assist` reactions automatically.

Migration should be opt-in:

1. existing darkness assist keeps working unchanged
2. admin can convert one darkness assist into contextual lighting assist
3. conversion tool creates:
   - one profile from current `entity_steps`
   - one default rule
   - same primary bucket trigger

This avoids risky silent behavior changes.

## Why A New Reaction Type

Do not overload `room_darkness_lighting_assist` with profile logic.

Reasons:

- clearer contract
- simpler diagnostics
- easier migration
- avoids breaking current stable behavior

`room_darkness_lighting_assist` remains the simple deterministic version.

`room_contextual_lighting_assist` becomes the richer policy-driven version.

### Implementation: shared base class

The two reaction classes share a non-trivial amount of logic:

- trigger check (room occupancy + lux bucket match)
- cooldown enforcement
- `entity_steps` application
- base diagnostics counters (fire_count, suppressed_count, last_fired_iso)

This shared logic must live in a common base class, not be duplicated.

`RoomLightingAssistReaction` and `RoomContextualLightingAssistReaction` both extend
`_BaseRoomLightingAssist`, which provides the shared primitives.

Each subclass implements only its own `evaluate()` path. There are no `if reaction_type`
or `if policy_mode` branches in the base class or in either subclass.

This keeps `room_darkness_lighting_assist` untouched and fully stable, while the
contextual path is developed as greenfield code with independent test coverage.

## Acceptance Criteria

This RFC is complete when:

1. a configured `room_contextual_lighting_assist` can choose different profiles by time window
2. it can choose a different profile when `house_state=working`
3. diagnostics show the selected profile and rule
4. config flow can create at least one built-in template for `room_contextual_lighting_assist`
5. an optional outdoor-light brightness modulation can be expressed without
   introducing a second competing reaction
6. existing `room_darkness_lighting_assist` reactions remain unchanged

## Recommended First Implementation Scope

To keep the first slice small:

1. support rule conditions:
   - `house_state_in`
   - `time_window` (including midnight-crossing)
   - `occupancy_reason_in`
   - `default_profile`
2. compute `occupancy_reason` as defined: `focus` / `settled` / `transient` / `generic`
3. implement `needs_apply` with profile-change re-evaluation and `last_applied_profile` tracking
4. ship one built-in template (`all_day_adaptive`)
5. expose a generated-and-editable JSON payload in the flow
6. defer `min_presence_age_s` / `max_presence_age_s` as raw rule fields to phase 2
   (they are superseded by `occupancy_reason` in most practical cases)
7. defer `ambient_modulation` guided UI to phase 2, but keep the contract ready
   for JSON-level support

This is enough to solve the concrete user problem without overdesign.
