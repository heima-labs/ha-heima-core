# Actuator Discovery Spec

**Status:** Planned — approved after design discussion. Phased as `docs/v2_dev_plan.md` Phase AV
(AV1-3); not yet implemented.
**Date:** 2026-08-25
**Scope:** Extends Phase L's rule-based discovery to also suggest `Actuator` candidates
(`core/actuator_registry_spec.md`), and exposes the same candidate data to the AU4 admin-panel
Actuator editor as a prioritized entity picker. Adds no new persisted schema, no new dataclass, and
no new websocket command — only new ways to *populate* the existing `Actuator` schema faster.
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

Both share the same missing primitive: a way to recognize HA entities that look like actuators. This
spec adds that recognition once, as a straightforward extension of Phase L's existing rule table,
and wires it into both surfaces.

## Product Principle

Rule-based only — the same discipline Phase L already established for every other discovery
candidate: no ML, no entity-name heuristics, no confidence scoring beyond domain/device_class/Area
signal. This spec **literally extends Phase L's existing rule table** (`_candidate_from_entry()` in
`discovery.py`) — it does not introduce a parallel discovery mechanism. `discovery.py` remains
exactly as options-agnostic as it is today: it does not gain any awareness of Heima's own
`options` (rooms, actuators, or anything else). Every place this spec needs to reconcile a
candidate against Heima's own config (resolving `room_id`, checking for an already-registered
`Actuator`) happens in the two existing callers — `_steps_discovery_validation.py` and
`websocket_api.py` — which already hold that context, not inside `discovery.py` itself.

## Non-Goals

- **Opening-level inference.** Discovery only ever proposes `room_id`; `opening_id` is always left
  `null` for the admin to link manually afterward via the existing AU4 editor. Nothing in this
  codebase can infer "this cover corresponds to that window," and building that heuristic is
  explicitly out of scope here. Every Actuator this spec creates is, by construction, "position-
  unaware" in `core/actuator_registry_spec.md`'s own terminology.
- **`light`.** Owned by Lighting's existing scene/area-based domain and Reaction model — see
  `core/actuator_registry_spec.md` §Why This Doesn't Touch Lighting. Suggesting `light.*` entities
  as generic Actuators here would conflate two already-deliberately-separate systems. Domains
  beyond the allowlist below (e.g. `valve`) can be added later without a schema change, since
  `Actuator` has no per-domain "kind" field to extend.
- **Any new dataclass, report type, or discovery function.** See Architecture below — this spec
  adds rule-table entries and two small, caller-local reconciliation steps, nothing else.
- **Filtering candidates inside `discovery.py` against Heima's own config.** No existing Phase L
  candidate type does this — `discover_binding_candidates()` always re-lists every matching entity
  on every run, regardless of what's already configured (verified: `room_occupancy_source`'s own
  idempotency is enforced at *apply* time — `if candidate.entity_id not in sources` — not at
  discovery time). This spec follows that same precedent for candidate generation; see Surface 1/2
  for where the equivalent idempotency actually lives instead.
- **Auto-applying candidates without explicit review.** Matches every existing Phase L candidate
  type: discovery only ever suggests; acceptance is always an explicit installer/admin action —
  but see Resolved (below) on why `actuator_candidate` is non-`ambiguous`, meaning the bulk
  "accept non-ambiguous" action does apply it without a per-item review step.
- **Any change to `Actuator`'s persisted schema** (`actuator_id`, `entity_id`, `room_id`,
  `opening_id`, `display_name` — unchanged). This spec only adds faster ways to populate that
  schema, not new fields on it.
- **Any change to `actuators.py`'s "no `homeassistant` import" rule.** All registry-touching logic
  introduced by this spec lives in `discovery.py`/`websocket_api.py`; `actuators.py` itself gains
  zero new code.
- **Loosening `Actuator`'s existing allowance of a shared `entity_id` across multiple records**
  (`core/actuator_registry_spec.md`: unconditional `warning`, never blocking). The apply-time
  idempotency guard this spec adds (Surface 1) is a discovery-flow safeguard against accidentally
  re-creating a duplicate on every re-run — it does not touch, restrict, or contradict the base
  spec's deliberate choice to allow an admin to manually create two Actuators sharing an
  `entity_id`. That path is untouched.

## Overlap With Existing Constructs

Mandatory check before introducing anything new:

- **`DiscoveredBindingCandidate`/`DiscoveryReport`** (`discovery.py`, Phase L) — reused as-is, no
  new fields, no new dataclass. This spec adds one new `category` value (`"actuator"`) and one new
  `suggested_binding` value (`"actuator_candidate"`) to `_candidate_from_entry()`'s existing
  if/elif rule chain — the exact same place every other candidate type is already defined,
  producing the exact same shape (`candidate_id`, `entity_id`, `domain`, `device_class`, `reason`,
  `confidence`, `area_id`/`area_name`, `ambiguous`). Both `category` and `suggested_binding` are
  plain strings, not a closed enum anywhere in the code — adding new values requires no schema
  change and no update to any switch/match elsewhere (verified: grouping in `DiscoveryReport.as_dict()`
  is fully dynamic, keyed off whatever `category` values are actually present).
- **`_apply_discovery_candidates()`** (`config_flow_steps/_steps_discovery_validation.py`, Phase L)
  — gains one new branch (`actuator_candidate`), following the *shape* of the existing
  `room_occupancy_source` branch (resolve via `area_id` match against the current room list,
  idempotency guard, then mutate) but not its *mechanism* — see Surface 1 for the one real
  mechanical difference (`apply_actuator_upsert` returns a whole new `options` dict, unlike the
  in-place list/dict mutation the two existing branches use). Found during this review: most other
  candidate types (`presence_source`, `security_contact`, `activity_power_candidate`,
  `activity_media_candidate`) are **not** actually wired into this function today — accepting them
  in the review UI records the decision (`OPT_DISCOVERY`) but does not mutate config. Out of scope
  to fix here; noted so the new branch isn't mistaken for closing that pre-existing gap.
- **Area→Room resolution** — reuses the existing `room["area_id"]` field, the same mapping
  `reconcile_ha_backed_options` (`reconciliation.py`) already establishes when Rooms are created
  from HA Areas, and the same per-branch matching loop `room_occupancy_source`'s own
  `_apply_discovery_candidates` branch already performs. No new mapping construct, and — corrected
  from an earlier draft of this spec — this resolution is **not** performed inside `discovery.py`;
  it happens independently in each of the two callers below, exactly where `options[OPT_ROOMS]` is
  already in scope.
- **`heima/actuators/snapshot`** (AU4, `core/actuator_registry_spec.md`) — extended with one new,
  additive, optional field (`entity_candidates`); existing fields (`rooms`, `openings`, `actuators`,
  `issues`) unchanged. No new websocket command type.

## Architecture

### One rule-table extension, no new function

`discovery.py`'s `_candidate_from_entry()` — the single dispatcher `discover_binding_candidates()`
already uses for every existing candidate type — gains five new domain branches:

| HA domain | `suggested_binding` | `category` |
|---|---|---|
| `cover` | `actuator_candidate` | `actuator` |
| `fan` | `actuator_candidate` | `actuator` |
| `climate` | `actuator_candidate` | `actuator` |
| `humidifier` | `actuator_candidate` | `actuator` |
| `switch` | `actuator_candidate` | `actuator` |

`switch` is included deliberately, not by default caution: HA `switch` entities are heterogeneous
(irrigation valve, smart plug for a lamp, water heater relay, garage door opener), but an incorrect
`Actuator` suggestion is low-cost — it is never auto-actuated (no comfort Reaction consumes this
registry yet), and is one click to delete from the already-shipped AU4 editor. `light` remains
excluded (see Non-Goals).

Every branch sets `ambiguous=False` (domain alone fully determines an `Actuator`'s shape — no
capability choice for the installer to make, per `core/actuator_registry_spec.md`'s "no kind
field" decision) and `confidence=0.8` — between `room_occupancy_source`'s `0.85` and
`activity_media_candidate`'s `0.55`, informational only since acceptance is gated on `ambiguous`,
not on a confidence threshold (verified: nothing in `discovery.py` or
`_steps_discovery_validation.py` filters or sorts by `confidence`).

`discover_binding_candidates()`'s output, its resolution of `area_id` (`_entry_area_id()`), and its
`DiscoveryReport` shape are otherwise **completely unchanged** — no new function, no new dataclass
field, no `options` parameter added to anything in `discovery.py`.

### Surface 1 — Options Flow discovery step (Phase L)

Nothing new is needed to *show* actuator candidates: `async_step_discovery` already calls
`discover_binding_candidates()` and renders every candidate generically, grouped dynamically by
`category` — the five new rules above surface automatically in the existing review form (accept-all
/ accept-non-ambiguous / accept-selected / reject-all), no new step, no new screen.

`_apply_discovery_candidates()` gains one new branch, run once per accepted `actuator_candidate`:

1. Resolve `room_id`: scan the current room list for a room whose `area_id` matches the candidate's
   `area_id` (identical loop shape to the existing `room_occupancy_source` branch). No match →
   skip this candidate entirely, same "silently unresolvable" discipline that branch already has.
2. Idempotency guard: if any existing entry in `options[OPT_ROOM_ACTUATORS]` already has this
   `entity_id`, skip — this is the mechanism that actually prevents duplicate creation on repeated
   discovery runs (see Non-Goals for why this is a discovery-flow safeguard, not a general model
   constraint).
3. Otherwise call `actuators.apply_actuator_upsert(options, actuator_id=None, entity_id=candidate.entity_id, room_id=<resolved>, opening_id=None)`.

**Mechanical note, not present in the two existing branches:** `apply_actuator_upsert` returns a
whole new `options` dict (`(new_options, issues)`), unlike `room_occupancy_source`'s/
`activity_shower_humidity`'s in-place mutation of a local `room_updates`/`activity_bindings` copy
written once at the end. When multiple `actuator_candidate`s are accepted in the same batch, the
loop must thread the result forward (`options = new_options`) between iterations, or all but the
last accepted candidate in that batch will be silently dropped.

**Failure handling is not needed:** `apply_actuator_upsert` with `opening_id=None` can never return
a blocking (`error`-severity) issue — `dangling_room` is only a `warning`, and
`opening_room_mismatch` can only fire when `opening_id` is set, which it never is here (verified
against `validate_actuators()`'s rules in `core/actuator_registry_spec.md`). The new branch does
not need rejection-handling logic the other branches also don't have.

### Surface 2 — AU4 admin-panel Actuator editor (prioritized entity picker)

`websocket_actuators_snapshot` (`websocket_api.py`) additionally calls `discover_binding_candidates()`
against the live entity/device/area registries (`hass`, already in scope there — same registries
`_discovery_report()` already reads in the options flow) and filters the result to
`candidate.category == "actuator"`. For each remaining candidate it performs the *same* two
reconciliation steps as Surface 1 — resolve `room_id` via `area_id` against `options[OPT_ROOMS]`
(already in scope, since the snapshot already builds the `rooms` list from it), dropping candidates
with no match; skip any `entity_id` already present in `options[OPT_ROOM_ACTUATORS]` — and includes
what remains as a new, additive `entity_candidates` field:

```json
[{"entity_id": "...", "domain": "...", "device_class": "...", "room_id": "...", "area_name": "..."}]
```

This is a transformed, enriched shape built by `websocket_actuators_snapshot` itself — not
`DiscoveredBindingCandidate.as_dict()` verbatim (that dataclass never carries `room_id`, only
`area_id`/`area_name`, by design — see Architecture above).

Frontend (`heima-admin-panel.js`): the Entity ID field in `_actuatorsAddForm` changes from a
free-text `<input>` to a `<select>` (matching the Room/Opening fields' existing pattern), populated
from `snapshot.entity_candidates`: candidates whose `room_id` matches the currently-selected Room
listed first, then the rest, grouped by Room. A manual-entry escape hatch (e.g. a trailing
"Other (type entity_id)…" option that reveals a text input) must remain — the admin must always be
able to register any `entity_id`, not just picker-covered ones (any domain outside the allowlist,
or an entity with no resolved Area/Room), matching `core/actuator_registry_spec.md`'s "any
HA-domain entity" contract; this spec must not narrow that.

## Storage and Persistence

None. No new options key, no new persisted field. Discovery review state for accepted/rejected
actuator candidates is recorded the same way Phase L already records it for every other candidate
type (`options[OPT_DISCOVERY]`, via `_store_discovery_review`) — not a new structure.

## Admin Observability

No change beyond what `core/actuator_registry_spec.md` already specifies.

## Testing Requirements

Unit tests:

- `discover_binding_candidates()` returns an `actuator_candidate`/`category="actuator"` result for
  each of the 5 newly-allowlisted domains (`cover`, `fan`, `climate`, `humidifier`, `switch`), with
  `ambiguous=False`, and returns nothing for `light`. Extends the existing test module for this
  function — not a separate test target, since there is no separate function.
- `_apply_discovery_candidates`'s new `actuator_candidate` branch: resolves `room_id` from
  `area_id` and calls `apply_actuator_upsert` with `opening_id=None`; a candidate whose `area_id`
  has no matching Room is silently skipped; a candidate whose `entity_id` already exists in
  `options[OPT_ROOM_ACTUATORS]` is silently skipped (idempotency guard); accepting two
  `actuator_candidate`s in the same batch persists both (regression test for the `options`
  chaining note above).

Integration tests:

- `heima/actuators/snapshot`'s `entity_candidates`: includes a `cover`/`fan`/`climate`/
  `humidifier`/`switch` entity with a resolved Area, with the correct `room_id`; excludes one
  already registered as an `Actuator`; excludes one whose Area has no matching Room.
- Real-websocket e2e: seeding a `cover.*` entity in a known Area, calling
  `heima/actuators/snapshot`, asserting it appears in `entity_candidates` with the resolved
  `room_id`.

## Open Questions

None outstanding — all points raised during design discussion were resolved during spec
definition (see Resolved, below).

**Resolved:**

- **Domain allowlist scope.** `cover`, `fan`, `climate`, `humidifier`, `switch` — `switch` included
  deliberately despite its heterogeneity: an incorrect suggestion is low-cost (never auto-actuated,
  one click to delete), so precision-at-suggestion-time is not worth narrowing the allowlist for.
  `light` stays excluded (owned by Lighting's existing domain/Reaction model).
- **`ambiguous` flag.** `False` for every domain in the allowlist — domain alone fully determines
  an `Actuator`'s shape (no capability choice, per `core/actuator_registry_spec.md`'s "no kind
  field" decision), so there is no genuine binding decision to force a human through. This means
  the bulk "accept non-ambiguous" action in the existing Options Flow review UX does apply
  `actuator_candidate`s without a per-item review step — accepted as consistent with there being no
  real ambiguity to review, and with the low cost of a wrong suggestion noted above.
- **Entity picker UX.** A `<select>` dropdown (not free text with a suggestion list), matching the
  Room/Opening fields' existing pattern in `_actuatorsAddForm`, plus the manual-entry escape hatch
  described in Surface 2.
- **Re-suggesting a deleted Actuator.** Inherits Phase L's existing behavior for every other
  candidate type (e.g. an unlinked `room_occupancy_source`): no "declined" state is introduced — a
  removed Actuator's `entity_id` can resurface as a *candidate* on the next discovery run. This is
  independent of, and not in tension with, the apply-time idempotency guard added in this revision:
  that guard only prevents a *duplicate* record from being created while one already exists for
  that `entity_id`; once the existing one is deleted, nothing blocks a fresh one being created via
  the resurfaced candidate.
- **Architecture: shared function/report vs. rule-table extension.** An earlier draft of this spec
  proposed a separate `discover_actuator_candidates()` function and a separate `DiscoveryReport`,
  which broke down under review: `discover_binding_candidates()`'s existing signature has no way to
  carry a resolved `room_id`, and `DiscoveredBindingCandidate` has no field for it, while the draft
  simultaneously claimed "no new dataclass." Corrected to a plain rule-table extension (see
  Architecture) — `discovery.py` gains zero new functions, zero new fields, and zero new
  `options`-awareness; both `room_id` resolution and already-registered filtering happen in the two
  existing callers, which already hold that context.
- **"Skip already-registered" precedent claim.** An earlier draft asserted this mirrors existing
  behavior; verified against the code that it does not — no existing Phase L candidate type filters
  against already-applied config at discovery time. Corrected: candidate *generation* never checks
  Heima's own config (matches every existing candidate type); idempotency is enforced only at
  *apply* time (Surface 1) and at *display* time for the picker (Surface 2), both caller-local.

## Acceptance Criteria

- `discover_binding_candidates()` (`discovery.py`) recognizes `cover`/`fan`/`climate`/
  `humidifier`/`switch` entities as `actuator_candidate`/`category="actuator"`, `ambiguous=False` —
  via new rule-table entries only, no new function, no new dataclass field, no new `options`
  parameter.
- The Options Flow discovery step surfaces actuator candidates using the existing review UX (no new
  step/screen); accepting one resolves `room_id` via `area_id` and persists a real `Actuator` via
  `actuators.apply_actuator_upsert`, guarded against creating a duplicate for an already-registered
  `entity_id`.
- `heima/actuators/snapshot` includes `entity_candidates`, computed live, additive to the existing
  response shape, already filtered to entities with a resolved Room and not already registered.
- The Actuators admin-panel editor's Entity ID field prioritizes known-room entities while still
  allowing any arbitrary `entity_id` to be entered (parity with today's free-text field, not a
  narrowing).
- Zero changes to `actuators.py`'s persisted schema or its "no `homeassistant` import" rule; zero
  new `options`-awareness added to `discovery.py`.
- Covered by unit and integration tests per Testing Requirements.
