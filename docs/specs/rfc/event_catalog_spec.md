# Heima — Event Catalog SPEC v1
## Notification Domain: Standard Events, Keys, Severity, Payloads

**Status:** Active v1 catalog (runtime-aligned); deferred items explicitly listed in section 5
**Last Verified Against Code:** 2026-03-11

This document defines the **standard event catalog** emitted by Heima.
Events are consumed by the Notification domain to route messages via `notify.*`
with **deduplication** and **rate limiting**.

---

## 0. Event Model

### 0.1 Event Envelope (Canonical)
All events conform to this envelope:

- `event_id` (string, uuid-like)
- `ts` (ISO8601)
- `key` (string) — used for dedup/rate-limit
- `type` (string) — stable event type identifier
- `severity` (enum: `info | warn | crit`)
- `title` (string)
- `message` (string)
- `context` (object/dict) — redacted, safe to share in diagnostics

### 0.2 Dedup & Rate Limit Controls
Configured in Options Flow:
- `dedup_window_s` (default 60)
- `rate_limit_per_key_s` (default 300)

Rules:
- Events with same `key` within `dedup_window_s` are dropped
- Events with same `key` within `rate_limit_per_key_s` are suppressed (counted)

---

## 1. Naming Conventions

### 1.1 `type`
Use dot-separated stable identifiers:
- `people.*`
- `occupancy.*`
- `house_state.*`
- `lighting.*`
- `heating.*`
- `security.*`
- `system.*`
- `reaction.*`

### 1.2 `key`
`key` must be stable and suitable for throttling.
Recommended patterns:
- `people.arrive.<person_slug>`
- `people.leave.<person_slug>`
- `security.armed_away_but_home`
- `heating.manual_override_blocked`
- `lighting.hold.<room_id>`

---

## 2. Standard Events (v1)

### 2.1 People

#### E001 — Named Person Arrived
- `type`: `people.arrive`
- `key`: `people.arrive.<person_slug>`
- `severity`: `info`
- `context`:
  - `person`: `<person_slug>`
  - `source`: `ha_person|quorum|manual`
  - `confidence`: int 0..100

#### E002 — Named Person Left
- `type`: `people.leave`
- `key`: `people.leave.<person_slug>`
- `severity`: `info`
- `context`:
  - `person`
  - `source`
  - `confidence`

#### E003 — Anonymous Presence Detected
- `type`: `people.anonymous_on`
- `key`: `people.anonymous`
- `severity`: `info`
- `context`:
  - `source`
  - `confidence`
  - `weight`: anonymous_count_weight

#### E004 — Anonymous Presence Cleared
- `type`: `people.anonymous_off`
- `key`: `people.anonymous`
- `severity`: `info`
- `context`:
  - `source`
  - `confidence`

---

### 2.2 House State

#### E010 — House State Changed
- `type`: `house_state.changed`
- `key`: `house_state.changed`
- `severity`: `info`
- `context`:
  - `from`
  - `to`
  - `reason`

Notes:
- Optional (can be disabled to avoid noise)

---

### 2.3 Occupancy

#### E020 — Room Occupancy Max-ON Timeout (Failsafe)
- `type`: `occupancy.max_on_timeout`
- `key`: `occupancy.max_on_timeout.<room_id>`
- `severity`: `info`
- `context`:
  - `room`
  - `max_on_s`

#### E021 — Occupancy / People Inconsistency (Someone Home, No Room Occupancy)
- `type`: `occupancy.inconsistency_home_no_room`
- `key`: `occupancy.inconsistency_home_no_room`
- `severity`: `info`
- `context`:
  - `anyone_home`
  - `occupied_rooms` (list)
  - `policy` (`smart|strict`)
  - `derived_room_count` (int)
  - `persist_s` (int)

Emission policy (v1.x):
- `smart` (default): emit only if occupancy sensor coverage is sufficient and mismatch persists
- `strict`: emit immediately when condition is true
- `off`: disabled

#### E022 — Occupancy / People Inconsistency (Room Occupied, No One Home)
- `type`: `occupancy.inconsistency_room_no_home`
- `key`: `occupancy.inconsistency_room_no_home.<room_id>`
- `severity`: `info`
- `context`:
  - `room`
  - `anyone_home`
  - `source_entities`
  - `policy` (`smart|strict`)
  - `persist_s` (int)

Emission policy (v1.x):
- `smart` (default): emit only if mismatch persists and room is occupancy-capable (`occupancy_mode = derived`)
- `strict`: emit immediately when condition is true
- `off`: disabled

---

### 2.4 Lighting

#### E030 — Lighting Manual Hold Enabled
- `type`: `lighting.hold_on`
- `key`: `lighting.hold.<room_id>`
- `severity`: `info`
- `context`:
  - `room`

#### E031 — Lighting Manual Hold Disabled
- `type`: `lighting.hold_off`
- `key`: `lighting.hold.<room_id>`
- `severity`: `info`
- `context`:
  - `room`

#### E032 — Lighting Scene Missing (Misconfiguration)
- `type`: `lighting.scene_missing`
- `key`: `lighting.scene_missing.<room_id>.<intent>`
- `severity`: `warn`
- `context`:
  - `room`
  - `intent`
  - `expected_scene`

---

### 2.5 Heating

#### E040 — Heating Manual Override Blocked
- `type`: `heating.manual_override_blocked`
- `key`: `heating.manual_override_blocked`
- `severity`: `info`
- `context`:
  - `branch`
  - `source`

#### E041 — Heating Apply Rate-Limited
- `type`: `heating.apply_rate_limited`
- `key`: `heating.apply_rate_limited`
- `severity`: `info`
- `context`:
  - `branch`
  - `target_temperature`

#### E042 — Heating Target Changed
- `type`: `heating.target_changed`
- `key`: `heating.target_changed`
- `severity`: `info`
- `context`:
  - `branch`
  - `target_temperature`
  - `phase`

#### E043 — Heating Branch Changed
- `type`: `heating.branch_changed`
- `key`: `heating.branch_changed`
- `severity`: `info`
- `context`:
  - `previous`
  - `current`

#### E044 — Heating Vacation Phase Changed
- `type`: `heating.vacation_phase_changed`
- `key`: `heating.vacation_phase_changed`
- `severity`: `info`
- `context`:
  - `phase`

#### E045 — Heating Apply Skipped (Small Delta)
- `type`: `heating.apply_skipped_small_delta`
- `key`: `heating.apply_skipped_small_delta`
- `severity`: `info`
- `context`:
  - `branch`
  - `target_temperature`

#### E046 — Heating Vacation Bindings Unavailable
- `type`: `heating.vacation_bindings_unavailable`
- `key`: `heating.vacation_bindings_unavailable`
- `severity`: `warn`
- `context`:
  - `branch`

---

### 2.6 Security (Read-Only)

#### E051 — Armed Away While Someone Home (Inconsistency)
- `type`: `security.armed_away_but_home`
- `key`: `security.armed_away_but_home`
- `severity`: `warn`
- `context`:
  - `security_state`
  - `security_observation_reason`
  - `people_home_list`
  - `policy`
  - `persist_s`
  - `occupied_rooms`
  - `has_room_evidence`
  - `has_anonymous_evidence`

---

### 2.7 System / Health

#### E900 — Engine Disabled
- `type`: `system.engine_disabled`
- `key`: `system.engine_disabled`
- `severity`: `info`
- `context`:
  - `reason`

#### E901 — Invalid Configuration (Hard Fail)
- `type`: `system.config_invalid`
- `key`: `system.config_invalid`
- `severity`: `warn`
- `context`:
  - `issues`

#### E902 — Behavior Error (Recovered)
- `type`: `system.behavior_error`
- `key`: `system.behavior_error.<component>.<id>.<hook>`
- `severity`: `warn`
- `context`:
  - `component`
  - `behavior`
  - `hook`
  - `error`

#### E903 — House-State Override Changed
- `type`: `system.house_state_override_changed`
- `key`: `system.house_state_override_changed:<from>-><to>:<action>`
- `severity`: `info`
- `context`:
  - `previous`
  - `current`
  - `action`
  - `source`

#### E904 — Legacy Notification Routes Deprecated
- `type`: `system.notifications_routes_deprecated`
- `key`: `system.notifications_routes_deprecated`
- `severity`: `warn`
- `context`:
  - `routes_count`
  - `has_recipients`
  - `has_recipient_groups`
  - `has_route_targets`

### 2.8 Reactions

#### E950 — Reaction Fired
- `type`: `reaction.fired`
- `key`: `reaction.fired.<reaction_id>`
- `severity`: `info`
- `context`:
  - `reaction_id`
  - `step_count`

---

## 3. Event Enablement (v1)

Events can be toggled by category:
- `people`
- `occupancy`
- `house_state`
- `lighting`
- `heating`
- `security`
- `system` (always enabled)

Defaults:
- system: enabled
- heating/security: enabled
- people/occupancy: enabled
- house_state: disabled (noise-prone)

### 3.1 Occupancy Mismatch Policy (v1.x)
To avoid false positives in homes with partial or sparse room sensing coverage, occupancy mismatch events use a dedicated policy:

- `occupancy_mismatch_policy`: `off | smart | strict` (default: `smart`)
- `occupancy_mismatch_min_derived_rooms` (default: `2`)
- `occupancy_mismatch_persist_s` (default: `600`)

`smart` policy semantics:
- `home_no_room` (`E021`) is emitted only if:
  - derived room coverage is at least `occupancy_mismatch_min_derived_rooms`
  - the mismatch persists for at least `occupancy_mismatch_persist_s`
- `room_no_home` (`E022`) is emitted only if:
  - the room is occupancy-capable (`occupancy_mode = derived`)
  - the mismatch persists for at least `occupancy_mismatch_persist_s`

### 3.2 Security Mismatch Policy (v1.x)
To avoid false positives when person trackers lag after arming away, security mismatch events use a dedicated policy:

- `security_mismatch_policy`: `off | smart | strict` (default: `smart`)
- `security_mismatch_persist_s` (default: `300`)

`smart` policy semantics for `security.armed_away_but_home`:
- requires mismatch persistence for at least `security_mismatch_persist_s`
- requires corroborating local evidence of presence:
  - at least one occupied room with `occupancy_mode = derived`, or
  - anonymous presence is active

`strict` policy semantics:
- emits immediately when security is `armed_away` and `anyone_home = true`

---

## 4. Diagnostics & Privacy

- Context must avoid personally sensitive details beyond configured person slugs
- No raw GPS coordinates or device IDs
- Use redaction for entity_id lists if configured

---

## 5. Deferred in v1

The following event types are intentionally not implemented in the current v1 runtime:
- `heating.verify_failed`
- `heating.apply_failed`

Note:
- a generic umbrella `security.mismatch` event is intentionally not part of v1 taxonomy.
- v1 standardizes on explicit event types only (for example `security.armed_away_but_home`).

---
