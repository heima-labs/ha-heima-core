# Actuator Registry Spec

**Status:** Planned — not implemented on `main`
**Date:** 2026-08-24
**Scope:** A generic per-entity actuator inventory — which room, optionally which opening, an
arbitrary HA-domain entity (`cover.*`, `fan.*`, `climate.*`, and future equipment classes) is
physically located at. Explicitly excludes any command/capability model (reuses the existing
`entity_steps`/`ApplyStep` contract unchanged, see Non-Goals) and excludes any change to Lighting's
existing scene/area-based domain flow (see Why This Doesn't Touch Lighting).
**Related specs:** `core/room_topology_spec.md` (Room/Opening this spec references and depends on;
same preprocessing-layer category and admin-panel/websocket precedent), `core/apply_step_contract.md`
(`ApplyStep`/`entity_steps` contract reused unchanged), `core/reactive_behavior_spec.md` (Reaction
framework that consumes this registry), `core/admin_observability_panel_spec.md` (panel/websocket
precedent), `domains/heating_spec.md` (existing outdoor-temp-driven Reaction precedent this
generalizes to room/opening-aware comfort reactions)

## Purpose

Heima can already reason about a room's physical exposure (`Opening.orientation`, `Room.exposure`,
`Connection.connection_type` — `core/room_topology_spec.md`) and about household-level outdoor
conditions (`ExternalContext`: `outdoor_temp`, `outdoor_humidity`, `wind_speed`, `rain_*`,
`weather_condition`). What it cannot do yet is know *which equipment* is available to act on that
information — a cover, a fan, a climate unit — or *where that equipment physically is* relative to
the topology it already understands.

This spec closes that gap with a minimal registry: an `Actuator` is a location fact (an HA entity_id,
which room, optionally which opening) — never a command. A reaction deciding "too much sun on the
south side, and there's a shutter there" needs exactly this fact to resolve "there" into a concrete
`entity_id`; everything about *what to send it* already exists (HA's own per-domain service
contract, already used generically via `entity_steps`/`ApplyStep`).

## Product Principle

Normative rule:

> An `Actuator` record answers "what is this device and where is it", never "what should it do."
> Placement (`room_id`, `opening_id`) is the only thing this spec adds to the data model. Commands
> stay exactly where they already live today — in the Reaction that decides to send them.

This mirrors the split `core/room_topology_spec.md` already draws between structural facts
(derived, declared) and runtime decisions (never made by that layer). It is deliberate, not an
oversight: HA's own per-domain service contract (`cover.set_cover_position`, `light.turn_on`,
`climate.set_temperature`, …) is already a complete, generic "action + parameters" model. Heima does
not need — and must not build — a second one.

## Non-Goals

- **A command/capability schema.** No `action`, `params`, or per-domain capability fields on
  `Actuator`. Reactions keep expressing commands exactly as they do today, via `entity_steps`
  (`entity_id`, `action`, and domain-specific optional fields such as `brightness`/`rgb_color`).
- **Any change to Lighting's existing scene/area-based flow.** See Why This Doesn't Touch Lighting.
- **Migrating lighting Reactions' `entity_steps` to reference `actuator_id`.** Structurally possible
  later (both already share the "explicit `entity_id` + `room_id`" shape) without touching
  brightness/color handling, but explicitly deferred — a decision for dev-plan phase sequencing, not
  part of this spec.
- **Multi-room actuators** (one physical device intentionally serving more than one `Room` — e.g. a
  ducted A/C unit feeding two open-plan rooms through shared ductwork, or a ceiling fan mounted at
  the boundary between two rooms with no dividing wall). `Actuator.room_id` is single-valued, for the
  same reason `Opening.room_id` already is: allowing multi-valued membership reopens the "how much of
  each room does this affect" question with no natural stopping point (a basement furnace "affects"
  every room in the house via ducting). Lighting's `OPT_LIGHTING_ZONES` already solves a structurally
  similar many-to-many problem with a tested conflict-resolution policy; if a real need for
  multi-room actuators emerges later, adapting that existing pattern is the right path, not adding an
  ad hoc list field here. Until then: register the device under its physically primary room; a
  Reaction that also needs to reason about a secondary room can still reference the same `entity_id`
  directly.
- **Building any specific comfort/climate Reaction** (the "close the windows" notification, the
  auto-actuate-a-shutter reaction, a house-wide "cool the house" reaction spanning multiple rooms).
  This spec only makes the registry those reactions would read available; see Future Consumers.
- **Any change to `core/room_topology_spec.md`'s own module, schema, or validation.** `Actuator`
  references `Room`/`Opening` but never mutates or extends them — see Architecture Integration.

## Why This Doesn't Touch Lighting

Lighting was the obvious candidate for unifying "how Heima tracks actuators," and was evaluated and
rejected for this phase — not because it wouldn't be tidy in the abstract, but because it doesn't
actually fit:

- **`LightingDomain`'s scene flow has no per-entity binding to migrate.** `OPT_LIGHTING_ROOMS`
  entries store four scene `entity_id`s and a hold flag — never a light entity list. Member
  `light.*` entities are resolved dynamically from the HA Area bound to the room
  (`LightingDomain.expected_room_light_entities`), and the apply action is `scene.turn_on` /
  area-level `light.turn_off` — a group/area operation, not a per-device command. Forcing this into
  an `Actuator{entity_id, room_id, opening_id}` shape would either lose scene atomicity (one HA
  service call coordinating N fixtures) or leave most of the schema unused by this side.
- **`OPT_LIGHTING_ZONES` groups rooms, not devices** (many-to-many, with a tested first-wins conflict
  policy) — a different axis than "where is this one device."
- **Lighting *Reactions* (`RoomLightingAssistReaction` and siblings) already have an explicit
  per-entity binding** (`entity_steps: [{entity_id, action, brightness?, rgb_color?,
  color_temp_kelvin?}]`, keyed by the reaction's own `room_id`) that is structurally close to what
  `Actuator` provides — this is the one surface named as a plausible future migration (see
  Non-Goals), specifically because it already shares the shape, not because it needs one.

Migrating the ~107 test-covered `OPT_LIGHTING_ROOMS`/`OPT_LIGHTING_ZONES` occurrences across 10 files
for uniformity alone, with no functional gap it closes, contradicts the additive/low-blast-radius
approach `core/room_topology_spec.md` itself established.

## Architecture Integration

### Not a domain: same preprocessing-layer category as Room Topology

Same category as `core/room_topology_spec.md`'s own placement: not a core domain, not a plugin, not
part of the fixed DAG. Admin-declared, low-churn, cached — the identical cadence argument
`core/room_topology_spec.md` §Architecture Integration already makes for itself applies here
unchanged (recomputed only on options/registry change, not every cycle).

### CanonicalState Exposure

Computed and cached under `CanonicalState["rooms.actuators"]`, a new sibling key to
`CanonicalState["rooms.topology"]` and `CanonicalState["rooms.device_context"]` — same publication
mechanism, same invalidation triggers:

- `options[OPT_ROOM_ACTUATORS]` changes;
- `EVENT_AREA_REGISTRY_UPDATED` or `EVENT_ENTITY_REGISTRY_UPDATED` fires.

A separate key and a separate cache instance from `rooms.topology`, mirroring the separate-module
decision below — not folded into the existing `TopologyGraphCache`/`build_topology_graph` output.

`Actuator` records are exposed as parsed, validated facts only — `entity_id`, `room_id`,
`opening_id`. `orientation` is deliberately **not** duplicated onto the exposed record even when
`opening_id` is set: a Reaction that needs it reads `CanonicalState["rooms.topology"]` and joins on
`opening_id` itself. This keeps `Opening.orientation` the single source of truth, consistent with
every other derived-vs-stored decision in `core/room_topology_spec.md` (e.g. `connection_type`,
`exposure`).

### Separate module, not an extension of `room_topology.py`

`Actuator` is implemented in its own module (`actuators.py`), not added to `room_topology.py`. This
is deliberate, not incidental: `room_topology.py` (AR1–AR4) is already implemented and extensively
tested; `Actuator` only *references* `Room`/`Opening` (by `room_id`/`opening_id`), it never needs to
change how they're parsed, derived, or validated. Keeping it a separate, purely additive module means
zero risk of regressing the existing Room Topology test suite. `actuators.py` follows the same
import-hygiene rule `room_topology.py` documents for itself: no `homeassistant` import, and
`ValidationIssue` imported from `.validation` only under `TYPE_CHECKING` plus locally inside its
validation function, to avoid the same order-sensitive circular import `room_topology.py` was built
to avoid.

### Referential integrity crosses the module boundary at the coordinator, not inside either module

`room_topology.py`'s `apply_room_opening_delete()` already blocks deletion when a `Connection`
references the `Opening` (via its own `validate_topology()` choke point). It must **also** block
when an `Actuator` references that `opening_id` — but `room_topology.py` cannot know about
`actuators.py` without breaking the module boundary above.

Resolution: the check is performed one layer up, in `coordinator.py`, which already imports both
modules. `HeimaCoordinator.async_delete_room_opening()` consults `actuators.py`'s own
`is_opening_referenced_by_actuator(options, opening_id)` predicate *before* delegating to
`apply_room_opening_delete()`, and refuses (not-applied, same UX as the existing Connection-blocks
case) if any `Actuator` references it. Neither module is aware of the other; only the coordinator
orchestrates across both.

`Room` deletion is **not** blocked and **not** cascaded for `Actuator`, for the same reason it
already isn't for `Opening`/`Connection` today (verified: the Options Flow's `rooms_remove_confirm`
step only cascades cleanup for `OPT_LIGHTING_ROOMS`/`OPT_LIGHTING_ZONES`; `Opening`/`Connection`
referencing a deleted room are left dangling and caught by `validate_topology()`'s existing
`dangling_room` warning after the fact). `Actuator` inherits this same, already-accepted behavior —
not a new gap.

### Recovery / Critical-Entity Tracking

`Engine._recovery_critical_entity_ids()` gains two additive loops:

1. `Opening.entity_id` from `options[OPT_ROOM_OPENINGS]` — closes a pre-existing gap (Opening's
   monitor-sensor entities are not walked today, independent of this spec).
2. `Actuator.entity_id` from `options[OPT_ROOM_ACTUATORS]`.

Both are additive to the existing method; no existing loop changes. Commanding an actuator that
Recovery doesn't know is unavailable is a more concrete failure mode than losing a status sensor
read, which is why both are included together rather than deferring the Opening fix again.

## Terminology

### Actuator

A record declaring that one HA entity (any domain — `cover.*`, `fan.*`, `climate.*`, `switch.*`, …)
is physically located in one `Room`, optionally at one `Opening`. Not a new registry of *rooms* or
*openings* — it only references the existing ones from `core/room_topology_spec.md`.

### Position-aware / position-unaware

Informal terms used in this spec and in design discussion, not stored fields: an `Actuator` is
"position-aware" when `opening_id` is set (a Reaction can resolve its `orientation` transitively via
`rooms.topology`) and "position-unaware" when it is `null` (the actuator serves the room as a whole —
a fan, an A/C unit — with no single opening it corresponds to).

## Data Model

### Actuator — `options[OPT_ROOM_ACTUATORS]`

New flat list, sibling to `options[OPT_ROOM_OPENINGS]`/`options[OPT_ROOM_CONNECTIONS]`:

```yaml
actuator_id: string             # generated (uuid4) if not supplied, same convention as Opening/Connection
entity_id: string                # any HA domain; the domain prefix implies capability, never stored separately
room_id: string                  # required, must reference an existing Room
opening_id: string | null        # optional, must belong to the same room_id when set
display_name: string | null      # optional, admin-panel readability only
```

No "kind"/capability field: what an actuator can do is already fully described by its HA
`entity_id`'s domain (`cover.` implies position/tilt, `climate.` implies hvac_mode/temperature,
`fan.` implies speed/oscillation, …) — storing a redundant classification would only create a second
source of truth that can drift from the entity's actual domain.

Cardinality: multiple `Actuator`s may reference the same `opening_id` (e.g. an interior curtain and
an exterior shutter on the same window) and multiple `Actuator`s may reference the same `room_id`
with no `opening_id` (e.g. a fan and a climate unit in the same room). No uniqueness constraint on
either. Disambiguating between several actuators available for the same purpose (which of two covers
to close, which of a fan vs. a climate unit to use) is Reaction-authoring logic — typically via the
HA entity's own `device_class` attribute — not a schema concern.

## Derivation Rules

None. `Actuator` records are flat, validated, stored facts — there is nothing derived, unlike
`Room`/`Opening`/`Connection` in `core/room_topology_spec.md` (`connection_type`, `exposure`). The
closest thing to derivation is the transitive join a Reaction performs itself
(`actuator.opening_id` → `rooms.topology` → `Opening.orientation`), which is explicitly not
materialized onto the `Actuator` record (see CanonicalState Exposure).

## Storage and Persistence

Same boundary as `core/room_topology_spec.md`: persisted via the existing
`config_entries.async_update_entry(entry, options=...)` pattern, scoped per config entry implicitly
by living in `ConfigEntry.options`. `options[OPT_ROOM_ACTUATORS]` defaults to `[]` when absent — no
migration needed for existing installations.

`OPT_ROOM_ACTUATORS` is **not** added to `STRUCTURAL_OPTION_KEYS`, matching
`OPT_ROOM_OPENINGS`/`OPT_ROOM_CONNECTIONS`: adding/editing/removing an actuator is a light reload
(`coordinator.async_reload_options()`), not a full config-entry reload.

## Admin Editor

A new panel section, mirroring `core/room_topology_spec.md`'s AR4 pattern exactly (same panel/
websocket infrastructure, same admin-only gating, same choke-point-validated mutation pattern):

- `heima/actuators/snapshot` (websocket command): current actuators joined for display with their
  room/opening display names, plus pending validation issues.
- `heima/actuators/action` (websocket command): allowlisted mutations — upsert/delete `Actuator` —
  validated, applied through `config_entries.async_update_entry`, recorded for admin observability.

Kept as its own websocket command pair and its own panel section rather than folded into
`heima/topology/*`, mirroring the separate-module decision above: the topology websocket handler
stays unaware of actuators, same as `room_topology.py` itself.

## Validation and Reconciliation

New `ValidationSection` in the existing Installation Validation framework (`validation.py`), reusing
`ValidationIssue`/`ValidationSeverity`/`ValidationReport` — not a new severity system, same as
`core/room_topology_spec.md`.

Checks:

- `opening_id` is set and references an `Opening` that belongs to a *different* `room_id` than the
  `Actuator`'s own `room_id` — `error`. Structurally impossible (an opening cannot be "on the wall
  of" a room it isn't part of), same treatment AR1 already gives other structurally-impossible
  topology states.
- `room_id` references a `room_id` that no longer exists in `options[OPT_ROOMS]` — `warning`
  (`dangling_room`), matching `Opening`'s own existing dangling-room treatment. Not an error, and not
  blocking: Room deletion is not gated on this (see Architecture Integration).
- `opening_id` is set but references an `opening_id` that no longer exists in
  `options[OPT_ROOM_OPENINGS]` — `warning` (`dangling_opening`). In practice this should only arise
  through direct options manipulation outside the AR4 admin panel, since the panel-driven Opening
  delete path is blocked when an Actuator references it (see Architecture Integration) — this check
  exists as defense in depth, not as the primary integrity mechanism.
- The same `entity_id` is referenced by more than one `Actuator` — `warning`, unconditional. Unlike
  `Opening`'s shared-`entity_id` rule, there is no `connection_type`-equivalent property on `Actuator`
  that could actually conflict between the two records, so there is no corresponding `error` case
  here — this is deliberately looser than the Opening rule, not an oversight.
- `entity_id` does not currently resolve in the HA Entity Registry — marked `entity_unavailable` in
  diagnostics, `warning`, not deleted. Same non-blocking treatment as `Opening.entity_id`: HA entities
  can be legitimately, temporarily unavailable.

## Future Consumers (named, not built in this phase)

- **Comfort/climate Reactions** (the motivating use case for this spec): a "too much sun" Reaction
  resolves a south-facing `Opening`'s actuator via `rooms.actuators` + `rooms.topology`, preferring a
  precise, opening-bound actuator and falling back to a room-level one (e.g. a fan) when no
  opening-bound actuator exists, and falling back further to a notification when no actuator exists
  at all. Not built here; the registry only makes the lookup possible.
- **House-wide Reactions spanning multiple rooms** (e.g. "open the living-room and study windows to
  cross-ventilate the house"). Requires no framework change: `HeimaReaction.evaluate()` already
  returns `list[ApplyStep]` with no single-room constraint, and `rooms.actuators` is a flat,
  cross-room-queryable list by construction. What's new is only the *shape* of such a Reaction (no
  existing built-in Reaction spans more than one room today) — worth noting for whoever builds it
  first, not a data-model gap.
- **Security** (Phase AR7, still `PLANNED`): a house-wide window-opening Reaction should plausibly
  respect the armed state Security will eventually own. Named here as a forward dependency on AR7,
  not resolved by this spec.
- **Migrating lighting Reactions' `entity_steps` to reference `actuator_id`** — see Non-Goals.

## Observability

Admin observability (`core/admin_observability_panel_spec.md`) gains an `actuators` diagnostics
summary alongside the existing `topology` one: actuator count, validation warning/error counts, and
unresolved `entity_id` references — admin-only, same pattern.

## Testing Requirements

Unit tests:

- `Actuator` parsing skips malformed entries the same way `Opening`/`Connection` parsing does
  (missing `entity_id`/`room_id`, unknown fields ignored);
- `actuator_id` auto-generated via `uuid4` when not supplied on upsert;
- `opening_id` belonging to a different room than the `Actuator`'s `room_id` produces an `error`;
- dangling `room_id` and dangling `opening_id` each produce a `warning`, not an `error`;
- shared `entity_id` across multiple `Actuator`s always produces a `warning` (no `error` case exists
  for this rule, unlike Opening's);
- `entity_id` not resolving in the HA Entity Registry is marked `entity_unavailable`, `warning`, not
  deleted;
- no derivation logic exists to test beyond parsing/validation (see Derivation Rules).

Integration tests:

- deleting an `Opening` referenced by an `Actuator` is blocked at the coordinator level, mirroring
  the existing Connection-blocks-Opening-delete test;
- deleting a `Room` referenced by an `Actuator` is **not** blocked (matches existing Opening/
  Connection behavior) and produces a `dangling_room` warning on next validation;
- `rooms.actuators` cache invalidated and rebuilt on `options[OPT_ROOM_ACTUATORS]` change and on
  `EVENT_AREA_REGISTRY_UPDATED`/`EVENT_ENTITY_REGISTRY_UPDATED`, mirroring `rooms.topology`'s existing
  tests;
- `heima/actuators/action` mutations are admin-gated and rejected for non-admin callers, mirroring
  the existing `heima/topology/action` e2e test;
- `Opening.entity_id` and `Actuator.entity_id` both appear in
  `Engine._recovery_critical_entity_ids()`'s output.

## Open Questions

None outstanding — all points raised during design discussion were resolved during spec definition
(see Resolved, below).

**Resolved:**

- Actuator↔orientation binding: attaches to `Opening` (via `opening_id`), not duplicated onto the
  actuator record — orientation stays single-sourced on `Opening`.
- Unifying with Lighting's `OPT_LIGHTING_ROOMS`/`OPT_LIGHTING_ZONES`: rejected for this phase, see Why
  This Doesn't Touch Lighting. Migrating lighting *Reactions* (not the Lighting domain itself) to
  reference this registry is named as a deferred possibility, not decided.
- Multi-room actuators: explicit non-goal for v1, see Non-Goals.
- Opening-delete referential integrity: enforced at the coordinator layer, not inside either module —
  see Architecture Integration.
- Room-delete referential integrity: not blocked, not cascaded — inherits the existing
  Opening/Connection behavior.
- Recovery/critical-entity tracking: extended for both `Opening.entity_id` (closing a pre-existing
  gap) and `Actuator.entity_id`, together.
- House-wide (multi-room) Reactions: confirmed requires no framework or data-model change; named as a
  future consumer.

## Acceptance Criteria

- `Actuator` records are persisted via the existing options boundary, scoped per config entry,
  defaulting to `[]` with no migration required.
- `CanonicalState["rooms.actuators"]` is available as cached configuration, invalidated correctly on
  options/registry changes, computed by a module fully independent of `room_topology.py`.
- No command/capability schema is introduced; `entity_steps`/`ApplyStep` are unchanged.
- `Opening` deletion is blocked when referenced by an `Actuator`, enforced at the coordinator layer.
- `Room` deletion behavior for `Actuator` matches the existing, already-shipped behavior for
  `Opening`/`Connection` (not blocked, not cascaded, detected via a `warning` after the fact).
- `Engine._recovery_critical_entity_ids()` includes both `Opening.entity_id` and `Actuator.entity_id`.
- Lighting's existing `OPT_LIGHTING_ROOMS`/`OPT_LIGHTING_ZONES` schema, `LightingDomain`, and all
  lighting Reaction classes are untouched by this phase.
- Installation Validation reports actuator referential-integrity and availability issues with correct
  severity, reusing the existing `ValidationIssue`/`ValidationSeverity` contract.
- Admin editing is panel-based, admin-only, and every mutation is traceable in admin observability.
- The implementation is covered by unit and integration tests per Testing Requirements.
