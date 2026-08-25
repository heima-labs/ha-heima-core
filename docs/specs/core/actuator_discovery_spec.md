# Actuator Discovery Spec

**Status:** Draft — under review, open questions pending resolution before phasing.
**Date:** 2026-08-25
**Scope:** Extends Phase L's rule-based discovery to also suggest `Actuator` candidates
(`core/actuator_registry_spec.md`), and exposes the same candidate data to the AU4 admin-panel
Actuator editor as a prioritized entity picker. Adds no new persisted schema — only new ways to
*populate* the existing `Actuator` schema faster.
**Related specs:** `core/actuator_registry_spec.md` (the registry this populates; depends on),
`heima_v2_spec.md` §Phase L (the discovery mechanism this extends), `core/room_topology_spec.md`
(Room this resolves candidates against), `core/ha_backed_room_inventory_spec.md` (the existing
Area→Room reconciliation this reuses, not duplicates).

## Purpose

Two related gaps, both raised during AU4 retrospective discussion:

1. Phase L's rule-based discovery (options flow) never proposes `Actuator` candidates — every
   `Actuator` must be added manually today, even for entities whose HA Area already unambiguously
   maps to a Heima Room.
2. The AU4 admin-panel Actuator editor's Entity ID field is free text, with no visibility into
   which HA entities are already known to belong to a room.

Both share the same missing primitive: a way to enumerate HA entities that look like actuators,
together with the Room they already belong to (via existing Area membership). This spec adds that
primitive once, in one place, and wires it into both surfaces.

## Product Principle

Rule-based only — the same discipline Phase L already established for every other discovery
candidate: no ML, no entity-name heuristics, no confidence scoring beyond domain/device_class/Area
signal. Nothing here changes that discipline; it extends the same rule table.

## Non-Goals

- **Opening-level inference.** Discovery only ever proposes `room_id`; `opening_id` is always left
  `null` for the admin to link manually afterward via the existing AU4 editor. Nothing in this
  codebase can infer "this cover corresponds to that window," and building that heuristic is
  explicitly out of scope here — see Open Questions for why it isn't even attempted narrowly.
- **Broad domain coverage.** v1 proposes restricting candidate domains to `cover`, `fan`, `climate`,
  `humidifier` — see Open Questions #1 for the `switch` boundary case and why it's excluded by
  default.
- **Auto-applying candidates without explicit review.** Matches every existing Phase L candidate
  type: discovery only ever suggests; acceptance is always an explicit installer/admin action.
- **Any change to `Actuator`'s persisted schema** (`actuator_id`, `entity_id`, `room_id`,
  `opening_id`, `display_name` — unchanged). This spec only adds faster ways to populate that
  schema, not new fields on it.
- **Any change to `actuators.py`'s "no `homeassistant` import" rule.** All registry-touching logic
  introduced by this spec lives in `discovery.py`/`websocket_api.py`; `actuators.py` itself gains
  zero new code.

## Overlap With Existing Constructs

Mandatory check before introducing anything new:

- **`DiscoveredBindingCandidate`/`DiscoveryReport`** (`discovery.py`, Phase L) — reused as-is, no
  new dataclass. This spec adds one new `category` value (`"actuator"`) and one new
  `suggested_binding` value (`"actuator_candidate"`), following the exact shape every existing
  candidate type already follows (`candidate_id`, `entity_id`, `domain`, `device_class`, `reason`,
  `confidence`, `area_id`/`area_name`, `ambiguous`).
- **`_apply_discovery_candidates()`** (`config_flow_steps/_steps_discovery_validation.py`, Phase L)
  — gains one new branch (`actuator_candidate` → `actuators.apply_actuator_upsert`), following the
  same pattern already used for `room_occupancy_source`/`activity_shower_humidity`. Found during
  this review: most other candidate types (`presence_source`, `security_contact`,
  `activity_power_candidate`, `activity_media_candidate`) are **not** actually wired into this
  function today — accepting them in the review UI records the decision (`OPT_DISCOVERY`) but does
  not mutate config. Out of scope to fix here; noted so the new branch isn't mistaken for closing
  that pre-existing gap.
- **Area→Room resolution** — reuses the existing `room["area_id"]` field and `_entry_area_id()`
  (`discovery.py`), the same mapping `reconcile_ha_backed_options` (`reconciliation.py`) already
  establishes when Rooms are created from HA Areas. No new mapping construct.
- **`heima/actuators/snapshot`** (AU4, `core/actuator_registry_spec.md`) — extended with one new,
  additive, optional field (`entity_candidates`); existing fields (`rooms`, `openings`, `actuators`,
  `issues`) unchanged. No new websocket command type.

## Two Surfaces, One Shared Primitive

### New shared primitive: `discover_actuator_candidates()`

New function in `discovery.py` — not a new module. Same registry-touching, no-`hass`-object,
dict/list-of-entries input shape as `discover_binding_candidates` (same testability reason: pure
function over plain data, `hass` registries adapted at the call site).

| HA domain | Heima suggestion |
|---|---|
| `cover` | `actuator_candidate` |
| `fan` | `actuator_candidate` |
| `climate` | `actuator_candidate` |
| `humidifier` | `actuator_candidate` |

For each matching entity: resolve `area_id` (existing `_entry_area_id()` helper, reused), then
resolve `room_id` by matching `area_id` against `options[OPT_ROOMS]` — a new step; none of Phase
L's existing candidate types resolve past `area_id`/`area_name`, since none of them populate an
`Actuator`-shaped record. Skip any entity whose `entity_id` already appears in
`options[OPT_ROOM_ACTUATORS]` — an already-registered actuator isn't a "candidate" anymore.

Returns a `DiscoveryReport`, `category="actuator"`. Confidence `0.8` — between
`room_occupancy_source`'s `0.85` and `activity_media_candidate`'s `0.55`: Area-based room placement
over a small, high-precision domain set, but never fully certain the physically-primary room
matches the HA Area (a ducted `climate` unit, or a `cover` mounted between two Areas, can still be
wrong).

### Surface 1 — Options Flow discovery step (Phase L)

`async_step_discovery` (`_steps_discovery_validation.py`) already runs `discover_binding_candidates`;
extended to also run `discover_actuator_candidates` and merge results into the same
`DiscoveryReport`/review form — same accept-all / accept-non-ambiguous / accept-selected /
reject-all UX, no new step, no new screen.

`_apply_discovery_candidates` gains one new branch:

```
actuator_candidate → actuators.apply_actuator_upsert(
    options, actuator_id=None, entity_id=candidate.entity_id,
    room_id=<resolved room_id>, opening_id=None,
)
```

A candidate whose `area_id` no longer matches any Room by the time it's accepted (e.g. the Room was
deleted between discovery and review) is silently skipped — not applied — matching
`room_occupancy_source`'s existing non-mutating-when-unresolvable behavior.

### Surface 2 — AU4 admin-panel Actuator editor (prioritized entity picker)

`websocket_actuators_snapshot` (`websocket_api.py`) additionally calls
`discover_actuator_candidates()` against the live entity/device/area registries (`hass`, already in
scope there) and includes the result as a new, additive `entity_candidates` field:
`[{entity_id, domain, device_class, room_id, area_name}]` — already excluding entities already
registered as Actuators, same as Surface 1.

Frontend (`heima-admin-panel.js`): the Entity ID field in `_actuatorsAddForm` changes from a
free-text `<input>` to a `<select>` (matching the Room/Opening fields' existing pattern), populated
from `snapshot.entity_candidates`: candidates whose `room_id` matches the currently-selected Room
listed first, then the rest, grouped by Room. A manual-entry escape hatch (see Open Questions #3)
must remain — the admin must always be able to register any `entity_id`, not just picker-covered
ones, matching `core/actuator_registry_spec.md`'s "any HA-domain entity" contract; this spec must
not narrow that.

## Storage and Persistence

None. No new options key, no new persisted field. Discovery review state for accepted/rejected
actuator candidates is recorded the same way Phase L already records it for every other candidate
type (`options[OPT_DISCOVERY]`, via `_store_discovery_review`) — not a new structure.

## Admin Observability

No change beyond what `core/actuator_registry_spec.md` already specifies.

## Testing Requirements

Unit tests:

- `discover_actuator_candidates()` returns a candidate for each of the 4 allowlisted domains,
  resolves `area_id` → `room_id` correctly, skips entities already present in
  `options[OPT_ROOM_ACTUATORS]`, and returns nothing for domains outside the allowlist (e.g.
  `switch`, `light`).
- `_apply_discovery_candidates`'s new `actuator_candidate` branch calls `apply_actuator_upsert`
  with the resolved `room_id` and `opening_id=None`; a candidate whose `area_id` has no matching
  Room is silently skipped.

Integration tests:

- `heima/actuators/snapshot` includes `entity_candidates`, correctly excluding already-registered
  actuators.
- Real-websocket e2e: seeding a `cover.*` entity in a known Area, calling
  `heima/actuators/snapshot`, asserting it appears in `entity_candidates` with the resolved
  `room_id`.

## Open Questions

1. **Domain allowlist scope.** Proposed: `cover`, `fan`, `climate`, `humidifier` only. `switch` was
   considered and excluded from v1 — HA `switch` entities are too heterogeneous (irrigation valve,
   smart plug for a lamp, water heater relay, garage door opener) to auto-suggest as a "room comfort
   actuator" without a much higher false-positive rate than the other four. Confirm this is the
   right line, or whether `switch` should be included when `device_class` narrows it (e.g.
   `device_class: outlet` excluded, unclassified/other `switch` included)?
2. **`ambiguous` flag for `actuator_candidate`.** Proposed `ambiguous=False` (same tier as
   `room_occupancy_source`) since domain alone fully determines the record's shape — no capability
   choice to make, per `core/actuator_registry_spec.md`'s existing "no kind field" decision. That
   means `accept_non_ambiguous` would silently create real, persisted `Actuator` records the first
   time an installer runs discovery after upgrading, without reviewing each one individually. Is
   that acceptable, or should `actuator_candidate` be forced `ambiguous=True` purely to guarantee a
   human looks at each one before persistence — even though there's no genuine binding choice
   behind it?
3. **Manual-fallback UX in the entity picker.** Proposed a `<select>` plus a
   "Other (type entity_id)…" option that reveals a text input. Acceptable, or would you rather keep
   the field a plain text input with a separate `<datalist>`/suggestion list under it (less UI
   work, weaker "prioritization" framing than what you described)?
4. **Re-registering a *removed* Actuator.** If an admin deletes an Actuator, its `entity_id`
   becomes a "candidate" again on the next discovery run — nothing distinguishes "never registered"
   from "deliberately removed." Phase L already has this exact behavior for, e.g., a
   `room_occupancy_source` an installer explicitly unlinked. Is inheriting that acceptable, or does
   Actuator deletion need to suppress future re-suggestion (would require a new small persisted
   "declined" set — new state this spec doesn't currently introduce)?

## Acceptance Criteria

- `discover_actuator_candidates()` exists in `discovery.py`, rule-based only, covering
  `cover`/`fan`/`climate`/`humidifier`, resolving `room_id` via the existing Area→Room mapping, and
  excluding entities already registered as Actuators.
- The Options Flow discovery step surfaces actuator candidates using the existing review UX (no new
  step/screen); accepting one persists a real `Actuator` via `actuators.apply_actuator_upsert`.
- `heima/actuators/snapshot` includes `entity_candidates`, computed live, additive to the existing
  response shape.
- The Actuators admin-panel editor's Entity ID field prioritizes known-room entities while still
  allowing any arbitrary `entity_id` to be entered (parity with today's free-text field, not a
  narrowing).
- Zero changes to `actuators.py`'s persisted schema or its "no `homeassistant` import" rule.
- Covered by unit and integration tests per Testing Requirements.
