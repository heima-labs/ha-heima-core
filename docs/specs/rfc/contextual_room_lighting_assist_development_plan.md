# Contextual Room Lighting Assist Development Plan

## Goal

Implement `room_contextual_lighting_assist` in small, verifiable slices.

The first implementation should:

- keep `room_darkness_lighting_assist` unchanged
- introduce the new reaction type with deterministic runtime behavior
- expose a guided JSON config flow in V1
- ship enough diagnostics to debug rule/profile resolution without guesswork

## Phase 1: Contract And Registry

### Scope

- add canonical reaction type:
  - `room_contextual_lighting_assist`
- register descriptor/builder
- define and validate minimum persisted contract

### Deliverables

- registry entry
- builder stub
- config validation helper

### Tests

- rebuild rejects malformed config
- registry exposes the new reaction type

## Phase 2: Pure Resolver

### Scope

Implement pure helpers for:

- `occupancy_reason`
- time window matching
- midnight-crossing windows
- ordered rule selection
- `default_profile` fallback

### Deliverables

- side-effect-free resolver module

### Tests

- `house_state_in` matching
- `occupancy_reason_in` matching
- same-day time windows
- midnight-crossing time windows
- first-match-wins behavior
- default fallback

## Phase 3: Runtime Reaction

### Scope

Implement `RoomContextualLightingAssistReaction` with:

- primary bucket trigger
- room occupancy requirement
- rule/profile resolution
- `needs_apply`
- cooldown
- `last_applied_profile`

### Deliverables

- new reaction class
- builder implementation

### Tests

- fires when room is occupied and primary bucket matches
- does not fire when no rule matches and no default exists
- re-applies when selected profile changes
- does not re-apply when profile is unchanged and all lights already satisfy the profile
- resets `last_applied_profile` when room becomes unoccupied
- suppresses while cooldown is active even on profile switch

## Phase 4: Diagnostics

### Scope

Expose required contextual diagnostics:

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
- `fire_count`
- `suppressed_count`
- `last_fired_iso`

### Deliverables

- runtime diagnostics payload
- diagnostics normalization/update if needed

### Tests

- diagnostics include required fields
- diagnostics correctly report selected rule/profile

## Phase 5: Guided JSON Config Flow V1

### Scope

Implement a V1 flow with:

1. room selection
2. target lights selection
3. preset/template selection
4. generated JSON textarea
5. preview summary

### Deliverables

- new admin-authored flow step(s)
- preset generator
- strict JSON validator

### Tests

- successful creation from preset
- editable JSON persists correctly
- invalid JSON returns form errors
- unknown profile names in rules are rejected
- malformed time windows are rejected

## Phase 6: Presentation And Labels

### Scope

Improve human-facing summaries for:

- configured reactions list
- review summary
- diagnostics summaries

### Deliverables

- readable label generator
- compact summary renderer for profiles/rules

### Tests

- label is stable and readable
- summary references selected profiles/rules correctly

## Phase 7: Live Test Lab Support

### Scope

Add a lab-safe end-to-end path for the new reaction.

### Deliverables

- at least one live template using `all_day_adaptive`
- live script to create and verify contextual lighting in studio

### Tests

- live/manual verification path documented
- test lab entities support the required light payload semantics

## Phase 8: Optional Conversion Flow

### Scope

Do not implement this in the first slice unless earlier phases are stable.

Later, add:

- explicit conversion from `room_darkness_lighting_assist`
- one-profile + default-rule bootstrap

### Tests

- conversion preserves lights and primary bucket trigger
- conversion is opt-in only

## Recommended Implementation Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7
8. Phase 8

## Risk Notes

### Occupancy Age

Use effective room occupancy age, not candidate age.

Otherwise the resolver will oscillate near occupancy dwell boundaries.

### Cooldown Versus Profile Switch

This is intentionally strict.

If the profile changes during cooldown, diagnostics must explain that the
reaction was suppressed despite a different selected profile.

### JSON Flow

V1 should be strict, not permissive.

If the flow accepts invalid JSON and “tries to fix it later”, debugging will get
worse immediately.

## V1 Exit Criteria

V1 is complete when:

1. a studio contextual reaction can switch profile by time window
2. it can switch profile by `house_state=working`
3. diagnostics show the selected profile and rule
4. the guided JSON flow can create one valid reaction from preset
5. existing darkness assist behavior remains unchanged
