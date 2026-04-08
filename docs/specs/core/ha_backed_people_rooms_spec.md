# Heima — HA-Backed People/Rooms Reconciliation SPEC
## Source-Of-Truth Alignment for `People` and `Rooms`

**Status:** Draft target for next implementation slice  
**Last Updated:** 2026-04-08

This document defines the target product and runtime contract for keeping Heima `People` and
`Rooms` aligned with Home Assistant objects.

Normative direction:
- Home Assistant is the source of truth for:
  - `person.*` entities
  - `area` registry entries
- Heima does not own these objects
- Heima materializes them into its own options model and enriches them with Heima-specific config

The goal is to eliminate drift between Home Assistant and Heima while preserving explicit Heima
configuration and safe admin review.

---

## Scope

In scope:
- reconciliation model for `People` and `Rooms`
- source-of-truth rules
- config-flow behavior
- notification behavior for newly discovered objects
- lifecycle states for imported objects

Out of scope:
- detailed runtime semantics for `people_debug_aliases`
- entity-registry migration details
- generic reconciliation for all future object types

---

## Product Principle

`People` and `Rooms` are **HA-backed objects**.

That means:
- a Heima room corresponds to a Home Assistant area
- a canonical Heima person corresponds to a Home Assistant `person.*`
- Heima may add enrichment fields and domain-specific tuning
- Heima must not silently diverge from the underlying Home Assistant object model

Implication:
- users should primarily **edit imported objects**
- they should not need to manually add canonical people or rooms in Heima in normal operation

---

## Canonical Sources

### People

Canonical source:
- Home Assistant `person.*`

Normative rules:
- a canonical Heima person MUST map to an existing Home Assistant `person.*`
- a canonical Heima person MUST NOT be created without a valid `person_entity`
- two canonical Heima people MUST NOT map to the same `person_entity`
- if the target `person.*` disappears, Heima MUST surface the condition as a configuration problem

### Rooms

Canonical source:
- Home Assistant Area Registry

Normative rules:
- a Heima room MUST map to an existing Home Assistant area
- if a Heima room is created from the flow, Heima MUST create or link the corresponding HA area
- if area synchronization fails, the room MUST NOT be created
- if a Heima room is deleted through the flow, the linked HA area MUST be removed as part of the
  same confirmed action

---

## Materialization Model

Heima SHOULD maintain a materialized copy of HA-backed people and rooms inside options.

This materialized copy exists so Heima can attach:
- occupancy config
- learning sources
- display labels
- per-person overrides
- domain-specific tuning

But the materialized copy is not authoritative about existence. HA remains authoritative.

---

## Reconciliation Lifecycle

Each imported object SHOULD conceptually have a reconciliation status.

Recommended statuses:
- `new`
  - discovered in HA
  - materialized in Heima
  - not yet reviewed/configured by the admin
- `configured`
  - imported and completed for Heima use
- `incomplete`
  - imported but missing Heima-specific fields required for full behavior
- `orphaned`
  - previously materialized in Heima but no longer present in HA

These statuses MAY be represented explicitly in options, diagnostics, or derived runtime summaries.
They do not need to be exposed as standalone entities in the first slice.

---

## Discovery And Reconciliation

### Initial bootstrap

On first entry to the options flow:
- Heima SHOULD import all Home Assistant `person.*` into `people_named` if empty
- Heima SHOULD import all Home Assistant areas into `rooms` if empty

This is a bootstrap behavior, not the final reconciliation model.

### Ongoing reconciliation target

Target direction:
- Heima SHOULD periodically or opportunistically reconcile HA-backed objects
- reconciliation SHOULD detect:
  - new HA people
  - new HA areas
  - renamed HA people/areas
  - removed HA people/areas

For newly discovered objects:
- Heima SHOULD materialize them automatically in its options model
- Heima SHOULD mark them as `new` or `incomplete`
- Heima SHOULD notify the admin that review is needed

For renamed objects:
- Heima SHOULD update the materialized display fields where safe
- Heima MUST preserve Heima-specific enrichment config

For removed objects:
- Heima SHOULD mark them `orphaned`
- Heima SHOULD raise a configuration issue
- Heima MUST NOT silently keep treating them as valid canonical bindings

---

## Notifications

When reconciliation discovers new HA-backed objects, Heima SHOULD emit administrative notifications.

Recommended event types:
- `system.new_person_discovered`
- `system.new_room_discovered`

Recommended notification semantics:
- one notification per reconciliation batch, not per object
- deduplicated when the object is already known and still awaiting review
- clearly phrased as “new object detected, review needed”

Example wording:
- `Heima discovered 1 new Home Assistant person: Alex`
- `Heima discovered 2 new Home Assistant rooms: Garage, Studio`

Recommended action guidance:
- “Open Heima options and review the imported object”

---

## Options Flow Target UX

### People

Target UX direction:
- imported people should already be present in Heima
- the main operation should be `edit`, not `add`

Recommended menu direction:
- `Edit people`
- `Anonymous presence`
- `Debug aliases`
- optional `Rescan HA people`

`Add person` SHOULD become a fallback/admin path, not the primary path.

### Rooms

Target UX direction:
- imported rooms should already be present in Heima
- the main operation should be `edit`, not `add`

Recommended menu direction:
- `Edit rooms`
- optional `Rescan HA areas`

`Import HA areas` SHOULD become either:
- automatic, or
- an explicit rescan/reconciliation action

---

## Delete Safety

Deleting a materialized object in Heima is high-impact.

Normative rules:
- any delete in the options flow MUST require explicit confirmation
- deleting a room MUST explain that the linked HA area will also be removed
- deleting a person from Heima MUST be clearly described as deleting the Heima binding, not
  deleting the HA `person.*`, unless future implementation explicitly introduces that capability

Recommended product distinction:
- remove Heima binding
- remove underlying HA object

These are different actions and SHOULD remain clearly separated.

---

## Debug Aliases

`people_debug_aliases` is intentionally separate from canonical people.

Normative rule:
- debug aliases MUST NOT weaken the canonical rule that `people_named` maps only to real HA
  `person.*` entities

Debug aliases MAY provide:
- aliasing to another HA `person.*`
- synthetic test identities

They are an additive test/debug layer, not part of canonical HA-backed reconciliation.

---

## Diagnostics Target

Future diagnostics SHOULD expose reconciliation state for people and rooms, including:
- imported total
- new/unconfigured total
- orphaned total
- last reconciliation time
- pending review object labels

This SHOULD feed:
- monitoring dashboards
- `ops_audit.py`
- admin notifications

---

## Implementation Staging

Recommended slices:

1. `PR-A1` bootstrap-first alignment
- auto-import people and rooms when empty
- strong validation for canonical bindings
- confirm on delete

2. `PR-A2` reconciliation inventory
- detect newly discovered HA people/rooms after initial setup
- materialize them into options
- expose diagnostics

3. `PR-A3` admin notifications
- emit deduplicated notifications/events for new people/rooms needing review

4. `PR-A4` UX refinement
- make `Edit` the primary path
- downgrade `Add` into fallback/admin-only path
- add explicit rescan action if still useful

---

## Acceptance Criteria

This direction is considered achieved when:
- a new HA person appears in Heima without manual add
- a new HA room appears in Heima without manual add
- both are clearly marked as needing review/configuration
- the admin receives a deduplicated notification about new imported objects
- canonical people cannot drift away from real HA `person.*`
- canonical rooms cannot drift away from real HA areas

