# Heima — HA-Backed Room Inventory SPEC
## Synced Room Inventory And Suggested Bindings

**Status:** Draft target for next implementation slice  
**Last Updated:** 2026-04-08

This document defines the target contract for a Home-Assistant-backed room inventory in Heima.

The goal is to let Heima:
- stay aligned with Home Assistant `area` / device / entity placement
- expose a reliable per-room inventory for review and debugging
- suggest useful bindings for occupancy, learning, and lighting

The goal is explicitly **not** to fully auto-configure room behavior.

---

## Scope

In scope:
- synced room inventory derived from HA area/device/entity registries
- per-room inventory shape
- suggested binding model
- `Rooms` flow UX direction
- diagnostics expectations

Out of scope:
- fully automatic occupancy binding
- fully automatic learning-source binding
- automatic activation of suggestions without review
- generic inventory sync for people or other object families

---

## Product Principle

Home Assistant is the source of truth for:
- room existence via `area`
- entity placement via `entity_registry.area_id`
- device placement via `device_registry.area_id`

Heima should derive a **room inventory** from those sources and keep it synchronized.

Heima should then let the admin:
- inspect what HA says belongs to the room
- choose which signals matter for Heima
- accept or refine suggested bindings

Normative direction:
- HA provides structure
- Heima provides interpretation and review

---

## Inventory Model

For each Heima room linked to an HA area, Heima SHOULD be able to derive:
- `area_id`
- `room_id`
- `display_name`
- `entity_ids_in_area`
- `device_ids_in_area`
- `entities_by_domain`

Recommended grouped view:
- `lights`
- `binary_sensors`
- `sensors`
- `climates`
- `covers`
- `media_players`
- `switches`
- `misc`

Entities MAY belong to the room either because:
- the entity itself has `area_id`
- or its linked device has `area_id`

If both are present, direct entity placement SHOULD win over device-derived placement for display
purposes, but both remain acceptable evidence that the entity belongs to the room.

---

## Suggested Bindings

The inventory SHOULD be used to compute **suggested bindings**, not committed bindings.

Suggested binding families:
- `suggested_occupancy_sources`
- `suggested_learning_sources`
- `suggested_lighting_entities`

Examples:
- motion / mmwave binary sensors in the room → suggested occupancy sources
- lux / humidity / co2 / temperature sensors in the room → suggested learning sources
- light entities in the room → suggested lighting entities

Normative rule:
- suggestions MUST NOT be treated as active Heima config until the admin confirms or edits them
- `suggested_lighting_entities` are inventory context first; they do not by themselves configure room
  lighting behavior

---

## Heuristics

Heuristics SHOULD be conservative.

Good candidates:
- occupancy:
  - `binary_sensor.*motion*`
  - `binary_sensor.*presence*`
  - mmwave/presence radar sensors
- learning:
  - lux / illuminance sensors
  - humidity sensors
  - co2 sensors
  - temperature sensors
  - selected switches that are meaningful behavioral signals
- lighting:
  - `light.*` in area

Bad candidates by default:
- noisy availability sensors
- battery sensors
- diagnostics-only entities
- generic helper entities not tied to room behavior

Heuristics SHOULD be explainable in diagnostics.

---

## Flow UX Direction

`Rooms` should remain edit-first.

Recommended edit view additions:
- linked HA area
- inventory summary:
  - entity count
  - device count
  - domain breakdown
- suggested bindings section:
  - suggested occupancy sources
  - suggested learning sources
  - suggested lights
- explicit lighting handoff:
  - the `Rooms` flow SHOULD make it clear that suggested lights belong to room inventory context
  - the admin SHOULD be able to jump from the selected room into the corresponding
    `Lighting Rooms` configuration for that same room

Recommended workflow:
1. Heima shows synced HA inventory
2. Heima shows suggestions derived from that inventory
3. Admin confirms, edits, or ignores suggestions
4. Only confirmed choices become active room config

Normative rule:
- the flow MUST clearly distinguish:
  - current configured bindings
  - suggested bindings

Those are different states.

Normative clarification for lights:
- `occupancy_sources` and `learning_sources` are configured directly in `Rooms`
- suggested lights shown in `Rooms` are not a third room-binding field
- room lighting scenes and manual-hold behavior remain configured under `Lighting Rooms`
- therefore the `Rooms` UX SHOULD expose suggested lights as:
  - room inventory context
  - and a navigation bridge to `Lighting Rooms`

---

## Diagnostics

Diagnostics SHOULD expose enough detail to debug room sync and suggestion quality.

Recommended diagnostics per room:
- linked area id
- inventory entity count
- inventory device count
- domain breakdown
- suggested occupancy sources
- suggested learning sources
- suggested lighting entities
- configured occupancy sources
- configured learning sources
- mismatch indicators:
  - configured source no longer in area
  - area empty
  - linked area missing

---

## Reconciliation Behavior

Room inventory SHOULD be refreshed when:
- Heima starts
- the HA area/device/entity registries materially change
- the admin explicitly triggers a rescan from the `Rooms` menu

If inventory changes:
- diagnostics SHOULD update
- suggested bindings SHOULD update
- configured bindings MUST remain unchanged until the admin reviews them

This preserves safety while keeping the sync current.

---

## Non-Goal

This feature is **not** intended to automatically “configure the room correctly”.

Specifically, this slice does not aim to:
- automatically set occupancy sources
- automatically set learning sources
- automatically accept suggested lights
- rewrite room behavior without admin review

Heima should help the admin make the right decision, not silently make every decision.

---

## Recommended First Slice

First implementation slice:
- derive per-room inventory from HA area/device/entity registry
- expose inventory summary in diagnostics
- expose suggested occupancy / learning / lighting bindings in diagnostics
- show suggestions in `Rooms` edit flow
- keep active config separate and explicit

Next UX slice:
- remove any ambiguity that suggested lights are directly editable inside `Rooms`
- add a room-scoped handoff from `Rooms` to `Lighting Rooms`
- keep the same room selected across that handoff so the admin can immediately configure
  scene/manual-hold behavior for the room whose inventory they were reviewing

That slice already improves:
- transparency
- discoverability
- debugging
- room onboarding UX

without crossing into unsafe auto-configuration.
