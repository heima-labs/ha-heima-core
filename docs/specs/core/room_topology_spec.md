# Room Topology Spec

**Status:** Planned — not implemented on `main`
**Date:** 2026-08-18
**Scope:** Spatial topology of rooms — adjacency graph, openings (doors/windows), orientation.
Consumed by Security, Occupancy, and HouseState as configuration; named as a motivating future input
for sun/weather-aware automations and Lighting. Explicitly excludes any 2D/3D floorplan
visualization, which is deferred (see Non-Goals).
**Related specs:** `learning/room_context_spec.md` (sibling `rooms.*` CanonicalState preprocessing
pattern this spec follows), `core/manual_hold_framework_spec.md` (admin-only mutation boundary
precedent), `core/admin_observability_panel_spec.md` (panel/websocket precedent, decision-trace
explainability), `core/events_and_notifications_spec.md` (constraint on any future
topology-derived notification), `core/apply_step_contract.md` (`blocked_by` convention reused by
Security below), `domains/house_state_spec.md`, `domains/security_presence_simulation_spec.md`

## Purpose

Heima currently imports rooms and devices from Home Assistant (Area Registry, Entity Registry) but
has no spatial awareness: it does not know how rooms connect to each other, where doors and windows
are relative to rooms, or which openings are interior vs. exterior vs. independent-access. This
limits Security (cannot distinguish an external door from an internal one for alarm logic),
Occupancy (cannot weight presence by room type), HouseState (cannot resolve finer-grained states
like "home but garage open"), and any future orientation-aware automation.

This spec defines a declarative, admin-authored topology graph — rooms as nodes, openings as
room-level attributes, connections as edges — that closes this gap without introducing a dependency
on any third-party floorplan tool and without requiring geometric/pixel data.

## Product Principle

Normative rule:

> Heima's spatial model is a relational graph declared by the admin, not a computed or imported
> floorplan. Geometry is an explicitly deferred, additive extension, never a dependency of this
> spec.

The graph is sufficient for every use case in this spec (Security, Occupancy, HouseState) without
coordinates, polygons, or a `north_angle` rotation. Orientation is a per-opening declared label
(cardinal direction), not a computed geometric value.

## Non-Goals

- 2D/3D floorplan rendering, or any pixel/CAD coordinate system. Deferred to a future phase, not
  scoped or numbered here (see Architecture Integration — `geometry` hook).
- Automatic inference of rooms/connections from any geometric floorplan file (e.g. easy-floorplan).
  If a future phase adds optional import from such a tool, it populates this spec's data model once,
  as a convenience; it is never a runtime dependency and never the source of truth.
- Per-person room-level presence tracking or display. Topology-derived room state is aggregate
  (`occupied: bool`), never per-person — matches the documented multi-person learning limitation.
- Heating zone or branch logic based on topology. Heating is not a consumer of this spec.
- Building the "close the window, it's windy" class of notification. This spec keeps the data model
  (`Opening.orientation`, `Opening.entity_id: None`) able to support it later; the notification
  feature itself, if built, must route through the existing Notification Delivery Policy (AP) —
  family/audience/persistence/burst limits — not a bespoke channel. Not built in this phase.
- A public third-party plugin API for topology. Mirrors the Room Context Model's (Phase X) decision
  to keep its provider interface internal-only while the contract is still settling.
- Vertical occupancy-flow reasoning ("resident moved from ground floor to first floor"). `floor` and
  `access_type` on connections make this representable later; no such logic is built now.

## Architecture Integration

### Not a domain: this is a preprocessing layer

"Preprocessing layer" means a computation step that runs *before* the core DAG evaluates domains,
producing data domains then read as input. It does not itself make runtime decisions, emit apply
steps, or sit as a node in the fixed core DAG (`People -> Occupancy -> Activity -> HouseState`, then
plugins) or as a plugin ordered by dependency. It is not a core domain and not a plugin — same
category as the Runtime Scheduler and Manual Hold Manager (cross-cutting facilities outside the
DAG), and, more directly, the same category as the Room Context Model below.

### Same category as the Room Context Model, different cadence

Heima already has exactly this kind of component: the Room Context Model (Phase X,
`learning/room_context_spec.md`). It computes per-room device activity (media on, work activity,
etc.) and writes it to `CanonicalState["rooms.device_context"]` before house-state resolution — a
preprocessing layer, explicitly not a DAG domain. Room topology is architecturally the same kind of
thing, applied to different data.

The one thing that differs is *how often* it needs to be recomputed, because the underlying data
has different volatility:

| | Room Context Model | Room Topology |
|---|---|---|
| What it computes | per-room device activity (media/work/pc) | room adjacency graph, openings, orientation |
| Changes | every evaluation cycle (live entity states) | only when the admin edits it in the panel |
| Recomputation | every cycle | cached; invalidated only on options/registry change |

This is also why room topology needs no "Architecture Integration" section as elaborate as runtime
recovery state's (`core/runtime_checkpoint_and_power_recovery_spec.md`), which *is* recomputed every
cycle from live data and therefore needed an explicit pre-DAG-context rule. Topology's cadence is
closer to plain configuration than to per-cycle state.

### CanonicalState Exposure

Not to be confused with the `Room.exposure` field defined in Terminology below (cardinal directions
a room faces) — this section is about where the computed topology is published for domains to read.

Computed topology is cached and exposed under `CanonicalState["rooms.topology"]`, a sibling
namespace to `CanonicalState["rooms.device_context"]` — same publication mechanism as the Room
Context Model, different key, different recomputation cadence (see table above). The cache is
invalidated and rebuilt only when:

- `options[OPT_ROOMS]`, `options[OPT_ROOM_OPENINGS]`, or `options[OPT_ROOM_CONNECTIONS]` change
  (options update, same reload path as every other options-backed contract);
- `EVENT_AREA_REGISTRY_UPDATED` or `EVENT_ENTITY_REGISTRY_UPDATED` fires — the same staleness
  pattern already used by the Room Context Model's entity-to-room mapping.

### Why this is not an `InferenceSignal`

Heima's inference engine has a separate, unrelated contract for a different purpose:
`InferenceSignal` (`runtime/inference/signals.py`) carries `confidence` (how sure Heima is) and
`ttl_s` (how long the prediction stays valid before it must be recomputed/discarded) — it exists to
represent probabilistic, time-decaying *predictions* (e.g. a predicted house state). Room topology
is neither probabilistic nor time-decaying: it is a deterministic fact the admin configured, true
until they change it — there is no "confidence" that a room is a garage, and no expiry after which
that stops being true. Modeling it as an `InferenceSignal` would force it through a pipeline built
for a different kind of data and gain nothing.

Concretely: domains read `CanonicalState["rooms.topology"]` directly as configuration, the same way
`OccupancyDomain` already reads `room_occupancy_mode` — not through the inference/signal pipeline.

### `geometry` — the Phase 2 hook

Each `Room` has a `geometry: dict | None` field, always `null` under this spec. This is the same
forward-compatibility pattern already used for `Activity.context: dict[str, Any]` (architecture
non-negotiable #12): declared now so a future floorplan-visualization phase is additive, not a
breaking schema migration.

## Terminology

### Room

An existing Heima room record (`options[OPT_ROOMS][*]`, `room_inventory.py`, reconciled with HA
Areas via `_reconcile_rooms()` in `reconciliation.py`), extended with topology fields. Not a new
registry.

### Opening

A door, window, or door-window, declared against exactly one owner `Room`. May or may not have a
bound HA entity.

### Connection

A graph edge: a door-type or door-window-type `Opening` linking its owner room to another room (or
to the literal outside world).

### Connection Type

`indoor | outdoor | separate` — derived from the room types on both sides of a `Connection` (see
Derivation Rules). Governs Security's alarm-boundary treatment of that connection.

### Access Type

`direct | stairs | elevator` — describes how a `Connection` is physically traversed. Independent of
`connection_type`.

### Exposure

The set of cardinal directions a `Room` faces, derived from the `orientation` of its window-bearing
`Opening`s. Never independently declared.

## Data Model

### Room — extends `options[OPT_ROOMS][*]`

New fields on the existing room record:

```yaml
room_type: indoor | balcony | garage | basement | outdoor | external | transit  # default: indoor
floor: int                                                                       # default: 0
geometry: null                                                                   # reserved, see above
```

`room_type: transit` is for spaces (stairwell, elevator cabin) **promoted** to their own `Room` only
when they have sensors/actuators to bind (motion detector, cabin presence, lighting, call button).
If a staircase or elevator has no sensors, it stays represented purely as `access_type` on a
`Connection` (see below) — no promotion needed.

Not stored, not derived as intermediate fields: `is_outdoor` / `is_separate`. Earlier drafts of this
model carried these as derived booleans; they added no value once every consumer (occupancy weight,
`connection_type` derivation) can key directly off `room_type`. Each consumer keeps its own small
`room_type`-keyed lookup table instead of sharing an intermediate abstraction.

### Opening — `options[OPT_ROOM_OPENINGS]`

New flat list, sibling to `options[OPT_ROOMS]`:

```yaml
opening_id: string
room_id: string            # owner room
type: door | window | door_window
orientation: north | northeast | east | southeast | south | southwest | west | northwest | null
entity_id: string | null   # explicitly optional
```

`entity_id` is optional by design: an `Opening` with no bound entity is not monitorable by Security
or Occupancy, but remains a valid geographic reference for future orientation-aware use (see
Non-Goals). Validation must surface, not hide, the distinction between "no sensor configured" and
"sensor configured" (see Validation and Reconciliation).

The same `entity_id` **may** be referenced by more than one `Opening`. Real cases: alarm contact
sensors wired in series/parallel across multiple physical windows; a `door_window` and a
neighboring `window` sharing one contact in some installations. This is never a validation error —
at most a non-blocking warning.

`door_window` (porta-finestra) behaves as both `door` (may be referenced by a `Connection`) and
`window` (contributes `orientation` to the owner room's `exposure`). It is a single `Opening`
record, not two.

### Connection — `options[OPT_ROOM_CONNECTIONS]`

New flat list:

```yaml
connection_id: string
opening_id: string                          # must reference a door or door_window Opening
room_b: string | "outside"                  # the other side; room_a is opening.room_id
access_type: direct | stairs | elevator     # default: direct
connection_type_override: indoor | outdoor | separate | null   # default: null (derived)
```

`room_b: "outside"` is a sentinel for "the connection's other side is the outside world, not
modeled as a distinct `Room`" — it avoids forcing the admin to create an `external`-type `Room` just
to represent a single front door. An `external` `Room` remains available when there is a reason to
model it explicitly (for example, binding a doorbell entity to it).

`room_a` is never stored independently; it is always the referenced `Opening`'s `room_id`. This
keeps `room_a` and the `Opening`'s ownership from ever drifting apart.

## Derivation Rules

### `connection_type`

Computed from the `room_type` of both connection endpoints (`room_a`'s room, and `room_b`'s room —
or the `external` treatment if `room_b == "outside"`), in this priority order — first rule that
matches wins:

1. Either endpoint is `external`, or `room_b == "outside"` → `separate`.
2. Either endpoint is `garage` or `basement` → `separate`.
3. Either endpoint is `balcony` or `outdoor` → `outdoor`.
4. Otherwise (`indoor` and/or `transit` on both sides) → `indoor`.

`connection_type_override`, when set, wins over this derivation unconditionally. Overrides exist
for the anomalous case an admin needs to represent but the priority rule doesn't fit (for example, a
garage that shares full interior access and should alarm like an interior door).

### `exposure`

`Room.exposure = sorted({ o.orientation for o in openings if o.room_id == room.room_id and
o.type in (window, door_window) and o.orientation is not None })`. Recomputed whenever the
underlying `Opening`s change; never independently declared.

### Occupancy weight

Not part of this spec's data model — `room_type` is exposed; the room-type-to-weight mapping (e.g.
indoor=1.0, balcony=0.5, garage=0.3, basement=0.2, outdoor=0.0, transit=low, external=0.0) is owned
and configured by `OccupancyDomain` itself, the same way `room_occupancy_mode` already is.

## Storage and Persistence

- Persisted via the existing `config_entries.async_update_entry(entry, options=...)` boundary
  already used from `coordinator.py` in multiple places (not new capability, an established
  pattern).
- Scoped per config entry implicitly, by virtue of living in `ConfigEntry.options` — no separate
  storage design needed (unlike the runtime checkpoint, which needed its own HA `Store`).
- `Room.room_type` defaults to `indoor` when absent, so existing configured rooms load without
  requiring a one-time migration step.

## Admin Editor

A new panel section (reusing the AO panel/websocket infrastructure — `core/admin_observability_panel_spec.md`),
admin-only:

- `heima/topology/snapshot` (websocket command): current rooms with topology fields, openings,
  connections, and pending validation warnings.
- `heima/topology/action` (websocket command): allowlisted mutations — upsert/delete `Room`
  topology fields, `Opening`, `Connection` — validated, applied through
  `config_entries.async_update_entry`, mirrors the AO7 admin-action pattern (payload validation,
  updated snapshot returned, action recorded for observability).

A graph/form-based editor, not an Options Flow wizard step: editing a graph (nodes + typed edges) is
a poor fit for Options Flow's linear step model, and the AO panel already establishes the pattern
for this kind of interactive admin surface.

## Validation and Reconciliation

New `ValidationSection` in the existing Installation Validation framework (Phase M,
`validation.py`), not a bespoke completeness indicator. Uses the existing `ValidationSeverity =
Literal["ok", "warning", "error"]` — this is deliberately not the unified event-severity enum
(`debug|info|warning|error|critical`); validation severity and event severity are separate,
unrelated systems (see `core/event_catalog_spec.md` for why they were kept apart).

Checks:

- An `indoor`-type `Room` with zero `Connection`s referencing it (as `room_a` or `room_b`) —
  `warning`. Non-`indoor` types (`garage`, `basement`, `outdoor`, `external`) may legitimately be a
  disconnected component (a detached garage, a guest house) — never warned on isolation alone.
- An `Opening.entity_id` referenced by more than one `Opening` — `warning`, informational only, per
  the legitimate-sharing cases above.
- A `Connection.opening_id` referencing an `Opening` that is not `door` or `door_window` — `error`.
- A `Connection.room_b` (when not `"outside"`) or an `Opening.room_id` referencing a `room_id` that
  no longer exists in `options[OPT_ROOMS]` — `error`, surfaced immediately (not silently dropped),
  hooked into the same reconciliation lifecycle as `_reconcile_rooms()`.
- An `Opening.entity_id` that no longer resolves in the HA Entity Registry — marked
  `entity_unavailable` in diagnostics; the `Opening` itself is not deleted (it remains a valid
  geographic reference even without a live sensor, consistent with `entity_id` being optional by
  design).

## Domain-Specific Notes

### Security

Reads `CanonicalState["rooms.topology"]` `Connection.connection_type` and `Opening.entity_id` to
classify actuator-backed openings for alarm logic:

- `connection_type: separate` or `outdoor` (unless explicitly configured to ignore outdoor
  openings) + `house_state: armed_away` + bound entity reporting open → alarm-eligible.
- An `Opening` with no `entity_id` is not alarm-eligible — it cannot contribute to security logic,
  only to future informational use. This must be visible in diagnostics (Installation Validation,
  above), not silently absent from alarm coverage.
- Reaction/apply blocking caused by topology-driven security classification should use the same
  `blocked_by` convention already established by `core/manual_hold_framework_spec.md` and
  `core/runtime_checkpoint_and_power_recovery_spec.md` (a short, structured reason string), not a
  new ad hoc format.

### Occupancy

`OccupancyDomain` reads `room_type` per room from `CanonicalState["rooms.topology"]` and applies its
own room-type-to-weight table (see Derivation Rules) when computing weighted presence, alongside the
existing `room_occupancy_mode` handling. This is additive configuration input, not a competing
occupancy engine.

### HouseState

Does **not** influence which `house_state` value gets resolved — the resolution logic (occupancy,
presence, calendar) is unchanged. This spec does not add new top-level `house_state` values (no
`away_garage_open`-style states) — `house_state` (`domains/house_state_spec.md`) remains a closed
enum.

Instead, after `house_state` has been resolved with the existing logic, HouseState separately
cross-references `rooms.topology`'s static structure (which `Opening`s have
`connection_type: separate` or `outdoor`) with the **live** entity state of those openings (not
part of `rooms.topology`, which is a static cache — this is a per-cycle lookup, same as any other
domain reading current entity state) to produce a fact like "an independent-access opening is
currently open."

This fact is attached as an addition to the existing extensible diagnostics contract
(`domains/house_state_spec.md` §11, "Diagnostics Contract" — already exposes
`house_signals_trace`, `candidate_trace`, `resolution_trace`, `override`), under a new key,
`topology_context: {open_boundary_openings: [...]}`, following that section's existing pattern —
not a new diagnostics mechanism. It never changes the resolved `house_state` value and never
triggers an action by itself; it only makes the resolved state more explainable (e.g. "state: away —
garage door open" visible in diagnostics/AO).

This is unconditional (any `house_state`, not just `armed_away`) and purely explanatory, which is
what distinguishes it from Security's use of the same underlying `connection_type`/`entity_id` data
(Security's check is gated on `armed_away` and triggers an alarm; this one never triggers anything).
The two reads are independent and intentionally not shared through a common abstraction — the
overlap is a few lines each, not enough to justify one.

### Future consumers (named, not built in this phase)

- **Activity / sun-orientation automations**: `Opening.orientation` is the input a future
  weather/sun-aware automation would need (e.g. closing west-facing covers at sunset). Not built
  here; the data model must not block it later.
- **Lighting (Smart Lighting Assist, Phase AB)**: room adjacency from `Connection`s is a plausible
  future input for cross-room lighting sequencing (e.g. hallway light on movement between rooms).
  The graph as specified already supports this without further model changes; not built in this
  phase.

## Observability

Admin observability (`core/admin_observability_panel_spec.md`) gains a `topology` diagnostics
summary: room/opening/connection counts, validation warning/error counts, and unresolved
`entity_id` references — admin-only, consistent with the panel's existing sections.

Topology-driven Security decisions must be traceable in the existing AO decision-trace mechanism,
so a wrong classification (e.g. a mislabeled garage door) is diagnosable, not a silent new source of
"why didn't the alarm fire."

## Testing Requirements

Unit tests:

- `room_type` defaults to `indoor` when absent (no migration required for existing configured rooms);
- `connection_type` derivation for every priority-rule branch, including `room_b: "outside"`;
- `connection_type_override` wins over derivation;
- `exposure` recomputed correctly as `Opening`s are added/changed/removed;
- shared `entity_id` across multiple `Opening`s produces a warning, not a validation error;
- isolated `indoor` room produces a warning; isolated `garage`/`basement`/`outdoor`/`external` room
  does not.

Integration tests:

- HA Area removed/renamed: dependent `Opening`/`Connection` surfaced as validation errors, not
  silently dropped;
- HA entity removed from the Entity Registry: bound `Opening` marked `entity_unavailable`, retained;
- topology cache invalidated and rebuilt on options change and on
  `EVENT_AREA_REGISTRY_UPDATED`/`EVENT_ENTITY_REGISTRY_UPDATED`;
- `heima/topology/action` mutations are admin-gated and rejected for non-admin callers.

## Open Questions

1. Should `RoomContextSignalProvider` (Phase X's planned internal provider interface for
   entity-keyed room signals) be extended to also carry relational/graph data, or should
   `rooms.topology` remain a separate sibling namespace permanently? Leaning toward keeping them
   separate — the provider interface is entity-keyed and scalar-valued by design, topology is
   graph-shaped — but not yet decided.
2. Default occupancy weight for `room_type: transit` — proposed low (analogous to `balcony`), to be
   confirmed against a real multi-floor test case.
3. Should Installation Validation block saving an invalid topology edit in the panel UI, or only
   warn post-save? Leaning toward blocking `error`-severity issues (dangling references) at
   save-time in the editor, and only warning (non-blocking) for `warning`-severity issues (isolated
   room, shared entity).

## Acceptance Criteria

- `Room` topology fields, `Opening`, and `Connection` are persisted via the existing options
  boundary, scoped per config entry.
- `CanonicalState["rooms.topology"]` is available to domains as cached configuration, not
  recomputed every cycle, invalidated correctly on options/registry changes.
- `connection_type` and `exposure` are always derived, never independently stored, and never drift
  from their inputs.
- `entity_id` is optional on every `Opening`; sharing one `entity_id` across `Opening`s is
  supported, not flagged as an error.
- Security, Occupancy, and HouseState can consume topology as configuration input without any new
  per-cycle computation or new `InferenceSignal` type.
- `house_state`'s enum is unchanged; topology-derived facts reach HouseState as context/diagnostics
  only.
- Installation Validation reports topology completeness/integrity issues with correct severity and
  scope (no false positives on legitimately disconnected non-`indoor` rooms).
- Admin editing is panel-based, admin-only, and every mutation is traceable in admin observability.
- The implementation is covered by unit and integration tests per Testing Requirements.
