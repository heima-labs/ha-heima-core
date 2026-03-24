# Heima — SPEC v1
## Intelligent Home Engine for Home Assistant (Custom Integration)

**Status:** Foundational product guide for v1.x
**Last Verified Against Code:** 2026-03-11

---

## Role of this document

This document is the foundational product-level guide for Heima v1.x.

It exists to define:
- what Heima is
- what kind of product it is trying to be
- which architectural and product principles are non-negotiable
- which domains belong to the v1 product perimeter

It is intentionally broader and more stable than the narrower subsystem specs.

## Normative precedence

This document is normative for product intent and product boundaries.

More specific operational behavior is defined in narrower specs such as:
- `core/options_flow_spec.md`
- `core/reactive_behavior_spec.md`
- `core/events_and_notifications_spec.md`
- `learning/learning_system_spec.md`

Interpretation rule:
- if a narrow subsystem spec and this document differ in implementation detail, the narrower spec
  governs that subsystem behavior
- if a narrow spec or implementation diverges from the product intent defined here, that divergence
  must be resolved explicitly as a product/design decision

## Non-goals

This document does not try to:
- describe every runtime detail of the current implementation
- replace subsystem contracts maintained in narrower specs
- serve as a changelog of v1.x implementation progress

## 0. Purpose and Principles

**Heima** is a product-grade intelligent home engine distributed as a **Home Assistant custom integration**.
Home Assistant provides the UI, state machine, storage, and device services; Heima provides a **policy-driven control plane**.

### Core intent: invisible intelligence

Heima's goal is not to build a configurable automation platform — Home Assistant already does that.
Heima's goal is to make the home **truly smart**: invisible to those who live in it, yet functional and aware.

This means:
- **The home should feel like it already knows what to do.** Inhabitants should never have to think "I need to set a scene" or "I should turn something on". Things should happen at the right moment, in the right context, without interaction.
- **Minimal configuration should produce already useful behavior.** The engine reasons from context (presence, time, house state, habits) rather than executing explicit rules. A new installation should work reasonably well with little setup.
- **The system adapts to context, not the other way around.** House state, occupancy, time of day, and presence patterns are inputs to a reasoning layer — not triggers to a script.
- **Overrides exist but are exceptions, not the normal flow.** Manual holds and intent overrides are escape hatches for edge cases, not the primary interaction model.
- **Invisibility is the success metric.** If inhabitants do not notice the system, it is working correctly. If they have to fight it or configure it constantly, it is not.

Heima is a **context interpretation layer**: it transforms raw signals (sensors, people, time) into coherent intents, and applies those intents safely and transparently. It is not a scripting platform and not a rules engine.

### Non‑negotiable principles
1. Heima **creates and owns all canonical entities** (100%).
2. Configuration is done via **Config Entry + Options Flow** (upgrade‑friendly).
3. Policies operate **only on canonical entities**, never directly on raw devices.
4. **Intent‑driven architecture**: policies produce intents; a single orchestrator applies them safely.
5. **Portability**: different houses and sensors — same engine via bindings.

---

## 1. Supported Domains (v1)

Core:
- people
- occupancy
- house_state

Policies:
- lighting
- heating
- security (read‑only)
- notification

---

## 2. Canonical Entity Contract (Created by Heima)

### 2.1 People — Named Persons

For each configured person `<p>` (slug):

- `binary_sensor.heima_person_<p>_home`
- `sensor.heima_person_<p>_confidence` (0–100)
- `sensor.heima_person_<p>_source` (e.g., `ha_person`, `quorum`, `manual`)
- `select.heima_person_<p>_override` (`auto | force_home | force_away`) (optional v1)

Aggregates:
- `binary_sensor.heima_anyone_home`
- `sensor.heima_people_count`
- `sensor.heima_people_home_list` (comma-separated slugs)

### 2.2 People — Unnamed / Anonymous Presence

Heima supports **unnamed (anonymous) presence** for cases such as:
- guests not represented as named persons,
- privacy‑preserving setups,
- generic “someone is home” signals.

Canonical entities:
- `binary_sensor.heima_anonymous_presence`
- `sensor.heima_anonymous_presence_confidence`
- `sensor.heima_anonymous_presence_source`

Aggregation rules:
- `heima_anyone_home = OR(named_people_home, anonymous_presence)`
- `heima_people_count` includes anonymous presence as **+N** (configurable `anonymous_count_weight`, default `1`).

---

## 3. Occupancy Model (Per Room / Zone)

For each room `<r>`:
- `binary_sensor.heima_occupancy_<r>` (stabilized)
- `sensor.heima_occupancy_<r>_source`
- `sensor.heima_occupancy_<r>_last_change` (optional)

For each zone `<z>`:
- `binary_sensor.heima_occ_zone_<z>`

Occupancy is **local presence** and is distinct from people presence.

### 3.1 Room Semantics (v1.x clarification)
A room is a **valid actuation unit** even when it has no occupancy sensors.

Each room may operate in one of two occupancy modes:
- `derived` (default): occupancy is computed from `sources` + `logic`
- `none`: no local occupancy sensing for that room

Rules:
- Rooms with `occupancy_mode = none` are still valid for lighting/heating mappings.
- `binary_sensor.heima_occupancy_<r>` remains created and is reported as `off` for `occupancy_mode = none`.
- `sensor.heima_occupancy_<r>_source` should indicate `none` (or equivalent diagnostic marker).
- Rooms with `occupancy_mode = none` do **not** contribute to `occupied_rooms`.

### 3.2 Zone Occupancy Computation (v1.x clarification)
Lighting zone occupancy is computed from member rooms that have `occupancy_mode = derived`.

Implications:
- Rooms with `occupancy_mode = none` are ignored for zone occupancy calculation.
- A zone containing only non-sensorized rooms resolves `zone_occupied = false`.
- Therefore, in `auto`, a zone with only non-sensorized rooms resolves to lighting intent `off` unless an explicit/manual intent is set.

---

## 4. House State Model

Canonical entities:
- `sensor.heima_house_state`
- `sensor.heima_house_state_reason`

Allowed values:
`away | home | sleeping | working | relax | guest | vacation`

### Priority order (v1)
1. vacation
2. guest
3. away
4. sleeping
5. relax
6. working
7. home

### Determination rules (v1)
1. configured `vacation_mode` house signal = `on` → `vacation`
2. configured `guest_mode` house signal = `on` → `guest`
3. `anyone_home == off` → `away`
4. configured `sleep_window` house signal = `on` → `sleeping`
5. configured `relax_mode` house signal = `on` → `relax`
6. configured `work_window` house signal = `on` → `working`
7. default → `home`

Unnamed presence counts as `anyone_home = on`.

### House signal bindings (v1)
The mode/window signals used by house-state resolution are not hardcoded helper entity ids.
They must be explicitly configured in the Options Flow `General` step under:

- `vacation_mode_entity`
- `guest_mode_entity`
- `sleep_window_entity`
- `relax_mode_entity`
- `work_window_entity`

If a binding is omitted, that signal is treated as inactive (`off`).

---

## 5. Lighting Domain

Entities:
- `select.heima_lighting_intent_<zone>`
- `binary_sensor.heima_lighting_hold_<room>` (per room)

Intents:
`auto | off | scene_evening | scene_relax | scene_night`

Rules (v1):
- `away/vacation` → `off`
- `sleeping` → `scene_night` when occupied (else `off`)
- `relax` → `scene_relax` when occupied (else `off` or configurable)
- `home/working/guest` → `scene_evening` when occupied (else `off` with idle delay)

Manual hold is **per room** and blocks apply (not intent computation).

Apply mechanisms:
- Preferred: `scene.turn_on`
- Advanced: `script.turn_on` (optional)

Room-scene mappings are optional per intent. For `off`, if no room `scene_off` is defined and the room has `area_id`, Heima may fallback to `light.turn_off` on the room area.

---

## 6. Heating Domain

Entities:
- `sensor.heima_heating_state`
- `sensor.heima_heating_reason`
- `sensor.heima_heating_phase`
- `sensor.heima_heating_branch`
- `sensor.heima_heating_target_temp`
- `sensor.heima_heating_current_setpoint`
- `sensor.heima_heating_last_applied_target`
- `binary_sensor.heima_heating_manual_hold`
- `binary_sensor.heima_heating_applying_guard`

Safe apply features (v1):
- rate limiting
- idempotent apply (reconciliation)
- manual override detection

Apply modes:
- `delegate_to_scheduler` (no temperature writes)
- `set_temperature`
- `hvac_off`

---

## 7. Security Domain (Read‑Only)

Entities:
- `select.heima_security_intent`
- `sensor.heima_security_state`
- `sensor.heima_security_reason`

Purpose:
- consistency checks
- policy constraints
- notification triggers

---

## 8. Notification Domain

Entities:
- `sensor.heima_last_event`
- `sensor.heima_event_stats`

Features:
- event catalog
- deduplication window
- rate limiting per event key
- routing via `notify.*` services
- recipient aliases / recipient groups above raw `notify.*` services

---

## 9. Input Binding (Configurable per House)

### 9.1 People presence methods (per named person)
- `ha_person` (bind to `person.*`)
- `quorum` (multiple sources, threshold-based)
- `manual` (override)

All methods normalize to:
`binary_sensor.heima_person_<p>_home`

### 9.2 Anonymous presence binding
- can bind to occupancy aggregates, mmWave, door sensors, or any generic presence signal
- contributes to `anyone_home` and `house_state`

---

## 10. Safety & Orchestration

- single apply orchestrator
- idempotent reconciliation
- anti‑loop guards
- debounce and dwell times
- restart‑safe behavior

---

## 11. Configuration UX (Options Flow)

1. General
2. People (named + anonymous)
3. Rooms (occupancy)
4. Lighting zones (zone mapping + per-room holds)
5. Heating
6. Security
7. Notifications

---

## 12. Roadmap / Milestones

### Milestone 0 — Spec & Scaffolding
- integration skeleton
- entity contract
- config entry versioning & migrations

### Milestone 1 — Portable MVP
- people (named + anonymous)
- occupancy
- lighting with per-room override
- notifications (basic)

### Milestone 2 — Heating Safe Engine
- rate-limit, guard, verify, retry
- manual override detection
- scheduler delegation

### Milestone 3 — Security & Relax Refinement
- relax as first-class state
- security consistency events

### Milestone 4 — Product Hardening
- migrations
- diagnostics
- tests
- documentation & profiles

---
