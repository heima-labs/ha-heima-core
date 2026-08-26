"""Room topology data model: derivation and pure validation core (Phase AR1).

No `homeassistant` import here by design: this module is the single source of
truth for topology parsing, `connection_type`/`exposure` derivation, and
structural validation, consumed — never reimplemented — by the cache builder
(AR3, defensive/best-effort mode), Installation Validation (AR2, plus its own
HA-registry-only checks), and the admin editor's save-time blocking (AR4). See
`docs/specs/core/room_topology_spec.md` and `docs/v2_dev_plan.md` Phase AR.

Deliberately no top-level import of `.validation` either: `validation.py` has a
heavy transitive import chain (`runtime.activity_detectors` -> ... ->
`runtime.inference`) that contains a pre-existing, order-sensitive circular
import elsewhere in that chain. This module is imported very early (by
`coordinator.py`, before `runtime.engine`), so pulling that chain in here would
surface it. `ValidationIssue` is imported under `TYPE_CHECKING` for annotations
and locally inside `validate_topology()` where it's actually constructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .const import OPT_ROOM_CONNECTIONS, OPT_ROOM_OPENINGS, OPT_ROOMS

if TYPE_CHECKING:
    from .validation import ValidationIssue

OUTSIDE = "outside"

ROOM_TYPES: frozenset[str] = frozenset(
    {"indoor", "balcony", "garage", "basement", "outdoor", "external", "transit"}
)
OPENING_TYPES: frozenset[str] = frozenset({"door", "window", "door_window"})
ORIENTATIONS: frozenset[str] = frozenset(
    {"north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"}
)
CONNECTION_TYPES: frozenset[str] = frozenset({"indoor", "outdoor", "separate"})
ACCESS_TYPES: frozenset[str] = frozenset({"direct", "stairs", "elevator"})
DOOR_LIKE_OPENING_TYPES: frozenset[str] = frozenset({"door", "door_window"})
WINDOW_LIKE_OPENING_TYPES: frozenset[str] = frozenset({"window", "door_window"})

DEFAULT_ROOM_TYPE = "indoor"
DEFAULT_FLOOR = 0
DEFAULT_ACCESS_TYPE = "direct"

# room_type values that may legitimately be a disconnected topology component
# (detached garage, guest house). indoor/balcony/transit are always expected
# to be reachable, so isolation there is warned on.
_ISOLATION_EXEMPT_ROOM_TYPES = frozenset({"garage", "basement", "outdoor", "external"})
_SEPARATE_ROOM_TYPES = frozenset({"garage", "basement"})
_OUTDOOR_ROOM_TYPES = frozenset({"balcony", "outdoor"})

_VALIDATION_CAPABILITY = "room_topology"


@dataclass(frozen=True)
class Opening:
    """A door, window, or door-window declared against exactly one owner room."""

    opening_id: str
    room_id: str
    type: str
    orientation: str | None = None
    entity_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "opening_id": self.opening_id,
            "room_id": self.room_id,
            "type": self.type,
            "orientation": self.orientation,
            "entity_id": self.entity_id,
        }


@dataclass(frozen=True)
class Connection:
    """A graph edge: a door/door_window Opening linking its room to another room or outside."""

    connection_id: str
    opening_id: str
    room_b: str
    access_type: str = DEFAULT_ACCESS_TYPE
    connection_type_override: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "opening_id": self.opening_id,
            "room_b": self.room_b,
            "access_type": self.access_type,
            "connection_type_override": self.connection_type_override,
        }


@dataclass(frozen=True)
class ResolvedConnection:
    """A Connection with its derived, never-independently-stored connection_type."""

    connection: Connection
    room_a: str
    connection_type: str

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.connection.as_dict(),
            "room_a": self.room_a,
            "connection_type": self.connection_type,
        }


@dataclass(frozen=True)
class TopologyGraph:
    """Best-effort derived topology: structurally broken entries are excluded, never raised on."""

    openings: tuple[Opening, ...]
    connections: tuple[ResolvedConnection, ...]
    exposure_by_room: dict[str, tuple[str, ...]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "openings": [opening.as_dict() for opening in self.openings],
            "connections": [connection.as_dict() for connection in self.connections],
            "exposure_by_room": {
                room_id: list(orientations)
                for room_id, orientations in self.exposure_by_room.items()
            },
        }


def room_type_of(room: dict[str, Any]) -> str:
    """Return a room's topology room_type, defaulting to indoor when absent/invalid."""
    raw = str(room.get("room_type") or "").strip()
    return raw if raw in ROOM_TYPES else DEFAULT_ROOM_TYPE


def room_floor_of(room: dict[str, Any]) -> int:
    """Return a room's floor, defaulting to 0 when absent/invalid."""
    try:
        return int(room.get("floor") or 0)
    except (TypeError, ValueError):
        return DEFAULT_FLOOR


def parse_openings(options: dict[str, Any]) -> tuple[Opening, ...]:
    """Parse options[OPT_ROOM_OPENINGS] into Opening records, skipping malformed entries."""
    raw_list = options.get(OPT_ROOM_OPENINGS)
    parsed: list[Opening] = []
    seen_ids: set[str] = set()
    for raw in raw_list if isinstance(raw_list, list) else []:
        if not isinstance(raw, dict):
            continue
        opening_id = str(raw.get("opening_id") or "").strip()
        room_id = str(raw.get("room_id") or "").strip()
        opening_type = str(raw.get("type") or "").strip()
        if not opening_id or opening_id in seen_ids or not room_id:
            continue
        if opening_type not in OPENING_TYPES:
            continue
        seen_ids.add(opening_id)
        orientation = str(raw.get("orientation") or "").strip()
        entity_id = str(raw.get("entity_id") or "").strip()
        parsed.append(
            Opening(
                opening_id=opening_id,
                room_id=room_id,
                type=opening_type,
                orientation=orientation if orientation in ORIENTATIONS else None,
                entity_id=entity_id or None,
            )
        )
    return tuple(parsed)


def parse_connections(options: dict[str, Any]) -> tuple[Connection, ...]:
    """Parse options[OPT_ROOM_CONNECTIONS] into Connection records, skipping malformed entries."""
    raw_list = options.get(OPT_ROOM_CONNECTIONS)
    parsed: list[Connection] = []
    seen_ids: set[str] = set()
    for raw in raw_list if isinstance(raw_list, list) else []:
        if not isinstance(raw, dict):
            continue
        connection_id = str(raw.get("connection_id") or "").strip()
        opening_id = str(raw.get("opening_id") or "").strip()
        room_b = str(raw.get("room_b") or "").strip()
        if not connection_id or connection_id in seen_ids or not opening_id or not room_b:
            continue
        seen_ids.add(connection_id)
        access_type = str(raw.get("access_type") or "").strip()
        override = str(raw.get("connection_type_override") or "").strip()
        parsed.append(
            Connection(
                connection_id=connection_id,
                opening_id=opening_id,
                room_b=room_b,
                access_type=access_type if access_type in ACCESS_TYPES else DEFAULT_ACCESS_TYPE,
                connection_type_override=override if override in CONNECTION_TYPES else None,
            )
        )
    return tuple(parsed)


def derive_connection_type(
    *,
    room_a_type: str,
    room_b_type: str | None,
    override: str | None,
) -> str:
    """Derive connection_type per the spec's priority rule; room_b_type=None means "outside"."""
    if override in CONNECTION_TYPES:
        return override
    if room_b_type is None or room_a_type == "external" or room_b_type == "external":
        return "separate"
    if room_a_type in _SEPARATE_ROOM_TYPES or room_b_type in _SEPARATE_ROOM_TYPES:
        return "separate"
    if room_a_type in _OUTDOOR_ROOM_TYPES or room_b_type in _OUTDOOR_ROOM_TYPES:
        return "outdoor"
    return "indoor"


def derive_exposure(room_id: str, openings: tuple[Opening, ...]) -> tuple[str, ...]:
    """Derive a room's exposure as the sorted union of its window-bearing openings' orientations."""
    values = {
        opening.orientation
        for opening in openings
        if opening.room_id == room_id
        and opening.type in WINDOW_LIKE_OPENING_TYPES
        and opening.orientation is not None
    }
    return tuple(sorted(values))


def _rooms_by_id(options: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in options.get(OPT_ROOMS) or []:
        if not isinstance(raw, dict):
            continue
        room_id = str(raw.get("room_id") or "").strip()
        if room_id:
            result[room_id] = raw
    return result


def _resolve_topology_graph(
    rooms_by_id: dict[str, dict[str, Any]],
    openings: tuple[Opening, ...],
    connections: tuple[Connection, ...],
) -> TopologyGraph:
    openings_by_id = {opening.opening_id: opening for opening in openings}
    resolved: list[ResolvedConnection] = []
    for connection in connections:
        opening = openings_by_id.get(connection.opening_id)
        if opening is None or opening.type not in DOOR_LIKE_OPENING_TYPES:
            continue
        room_a = rooms_by_id.get(opening.room_id)
        if room_a is None:
            continue
        if connection.room_b == OUTSIDE:
            room_b_type = None
        else:
            room_b = rooms_by_id.get(connection.room_b)
            if room_b is None:
                continue
            room_b_type = room_type_of(room_b)
        connection_type = derive_connection_type(
            room_a_type=room_type_of(room_a),
            room_b_type=room_b_type,
            override=connection.connection_type_override,
        )
        resolved.append(
            ResolvedConnection(
                connection=connection,
                room_a=opening.room_id,
                connection_type=connection_type,
            )
        )
    exposure_by_room = {room_id: derive_exposure(room_id, openings) for room_id in rooms_by_id}
    return TopologyGraph(
        openings=openings,
        connections=tuple(resolved),
        exposure_by_room=exposure_by_room,
    )


_EMPTY_TOPOLOGY_GRAPH = TopologyGraph(openings=(), connections=(), exposure_by_room={})


class TopologyGraphCache:
    """Caches the derived topology graph; invalidated only by an explicit `mark_stale()`.

    Mirrors `RoomDeviceContextBuilder`'s staleness pattern (`runtime/room_context.py`): the engine
    calls `mark_stale()` unconditionally on every options reload, and the coordinator calls it on
    `EVENT_AREA_REGISTRY_UPDATED`/`EVENT_ENTITY_REGISTRY_UPDATED` — the same triggers, same
    lifecycle. Unlike the Room Context Model, nothing here is recomputed per-cycle: the whole graph
    is cached until one of those triggers fires.
    """

    def __init__(self) -> None:
        self._stale = True
        self._graph: TopologyGraph = _EMPTY_TOPOLOGY_GRAPH

    def mark_stale(self) -> None:
        """Force a rebuild on the next `get_graph()` call."""
        self._stale = True

    def get_graph(self, options: dict[str, Any]) -> TopologyGraph:
        """Return the cached graph, rebuilding first if stale."""
        if self._stale:
            self._graph = build_topology_graph(options)
            self._stale = False
        return self._graph


def build_topology_graph(options: dict[str, Any]) -> TopologyGraph:
    """Build the best-effort topology graph: structurally broken entries excluded, never raises.

    Consumed by AR3's CanonicalState cache. Malformed/dangling entries are silently excluded here;
    they are still surfaced as diagnostics by `validate_topology` — never both hidden and unreported.
    """
    rooms_by_id = _rooms_by_id(options)
    openings = parse_openings(options)
    connections = parse_connections(options)
    return _resolve_topology_graph(rooms_by_id, openings, connections)


def _referenced_room_ids(graph: TopologyGraph) -> set[str]:
    referenced: set[str] = set()
    for resolved in graph.connections:
        referenced.add(resolved.room_a)
        if resolved.connection.room_b != OUTSIDE:
            referenced.add(resolved.connection.room_b)
    return referenced


def validate_topology(options: dict[str, Any]) -> tuple[ValidationIssue, ...]:
    """Pure structural validation: referential integrity within `options`, no HA dependency.

    Registry-backed checks (HA Area/Entity Registry removal, `entity_unavailable`) are not this
    module's concern — they require `hass` and are added by AR2 alongside these checks.
    """
    from .validation import ValidationIssue  # local: see module docstring

    rooms_by_id = _rooms_by_id(options)
    openings = parse_openings(options)
    openings_by_id = {opening.opening_id: opening for opening in openings}
    connections = parse_connections(options)
    graph = _resolve_topology_graph(rooms_by_id, openings, connections)
    connection_type_by_opening_id = {
        resolved.connection.opening_id: resolved.connection_type for resolved in graph.connections
    }

    issues: list[ValidationIssue] = []

    for opening in openings:
        if opening.room_id in rooms_by_id:
            continue
        issues.append(
            ValidationIssue(
                key=f"topology.opening.{opening.opening_id}.dangling_room",
                severity="error",
                title="Opening references a missing room",
                description=(
                    f"Opening '{opening.opening_id}' references room_id '{opening.room_id}', "
                    "which no longer exists."
                ),
                capability=_VALIDATION_CAPABILITY,
                missing=(opening.room_id,),
            )
        )

    for connection in connections:
        referenced_opening = openings_by_id.get(connection.opening_id)
        if referenced_opening is None:
            issues.append(
                ValidationIssue(
                    key=f"topology.connection.{connection.connection_id}.dangling_opening",
                    severity="error",
                    title="Connection references a missing opening",
                    description=(
                        f"Connection '{connection.connection_id}' references opening_id "
                        f"'{connection.opening_id}', which no longer exists."
                    ),
                    capability=_VALIDATION_CAPABILITY,
                    missing=(connection.opening_id,),
                )
            )
        elif referenced_opening.type not in DOOR_LIKE_OPENING_TYPES:
            issues.append(
                ValidationIssue(
                    key=f"topology.connection.{connection.connection_id}.invalid_opening_type",
                    severity="error",
                    title="Connection references a non-door opening",
                    description=(
                        f"Connection '{connection.connection_id}' references opening "
                        f"'{referenced_opening.opening_id}' of type '{referenced_opening.type}'; "
                        "only 'door' or 'door_window' openings may be connections."
                    ),
                    capability=_VALIDATION_CAPABILITY,
                    missing=(),
                )
            )
        if connection.room_b != OUTSIDE and connection.room_b not in rooms_by_id:
            issues.append(
                ValidationIssue(
                    key=f"topology.connection.{connection.connection_id}.dangling_room_b",
                    severity="error",
                    title="Connection references a missing room",
                    description=(
                        f"Connection '{connection.connection_id}' references room_b "
                        f"'{connection.room_b}', which no longer exists."
                    ),
                    capability=_VALIDATION_CAPABILITY,
                    missing=(connection.room_b,),
                )
            )

    # Isolation is only a meaningful signal once the household has started declaring topology at
    # all. Skipping it while both lists are empty avoids flooding every pre-AR installation (whose
    # rooms/openings/connections are all unset) with a warning nobody asked for.
    referenced_room_ids = _referenced_room_ids(graph) if (openings or connections) else None
    for room_id, room in rooms_by_id.items():
        if referenced_room_ids is None:
            continue
        room_type = room_type_of(room)
        if room_type in _ISOLATION_EXEMPT_ROOM_TYPES:
            continue
        if room_id in referenced_room_ids:
            continue
        issues.append(
            ValidationIssue(
                key=f"topology.room.{room_id}.isolated",
                severity="warning",
                title="Room has no topology connections",
                description=(
                    f"Room '{room_id}' (type '{room_type}') has no Connection linking it to "
                    "another room or the outside."
                ),
                capability=_VALIDATION_CAPABILITY,
                missing=("connection",),
            )
        )

    entity_to_opening_ids: dict[str, list[str]] = {}
    for opening in openings:
        if opening.entity_id:
            entity_to_opening_ids.setdefault(opening.entity_id, []).append(opening.opening_id)

    for entity_id, opening_ids in entity_to_opening_ids.items():
        if len(opening_ids) < 2:
            continue
        connection_types = {
            connection_type_by_opening_id[opening_id]
            for opening_id in opening_ids
            if opening_id in connection_type_by_opening_id
        }
        if len(connection_types) > 1:
            issues.append(
                ValidationIssue(
                    key=f"topology.entity.{entity_id}.shared_conflict",
                    severity="error",
                    title="Shared entity spans conflicting security boundaries",
                    description=(
                        f"entity_id '{entity_id}' is bound to openings whose connections resolve "
                        f"to different connection_type values ({', '.join(sorted(connection_types))}"
                        "); Security cannot determine which boundary applies."
                    ),
                    capability=_VALIDATION_CAPABILITY,
                    missing=(),
                )
            )
        else:
            issues.append(
                ValidationIssue(
                    key=f"topology.entity.{entity_id}.shared",
                    severity="warning",
                    title="Entity shared across multiple openings",
                    description=(
                        f"entity_id '{entity_id}' is bound to {len(opening_ids)} openings. "
                        "Supported for same-boundary sensors wired in series/parallel."
                    ),
                    capability=_VALIDATION_CAPABILITY,
                    missing=(),
                )
            )

    return tuple(issues)


# --- AR4: admin editor support — read-only snapshot and pure mutation functions ---
#
# Every mutation below follows the same shape: build the candidate options, run
# validate_topology() against them, and reject (return None, blocking_issues) if any
# error-severity issue results. This is the single choke point for "save-time blocking
# on error-severity only" (see the spec's resolved Open Questions) — the admin editor
# websocket layer (coordinator.py, websocket_api.py) never re-implements this check.


def build_room_topology_snapshot(options: dict[str, Any]) -> dict[str, Any]:
    """Read-only snapshot for the admin editor: rooms, openings, connections, and issues."""
    rooms = [room for room in options.get(OPT_ROOMS, []) or [] if isinstance(room, dict)]
    graph = build_topology_graph(options)
    issues = validate_topology(options)
    return {
        "rooms": [
            {
                "room_id": room_id,
                "display_name": str(room.get("display_name") or room_id),
                "room_type": room_type_of(room),
                "floor": room_floor_of(room),
                "exposure": list(graph.exposure_by_room.get(room_id, ())),
            }
            for room in rooms
            for room_id in (str(room.get("room_id") or ""),)
            if room_id
        ],
        "openings": [opening.as_dict() for opening in graph.openings],
        "connections": [connection.as_dict() for connection in graph.connections],
        "issues": [issue.as_dict() for issue in issues],
        "enums": {
            "room_types": sorted(ROOM_TYPES),
            "opening_types": sorted(OPENING_TYPES),
            "orientations": sorted(ORIENTATIONS),
            "connection_types": sorted(CONNECTION_TYPES),
            "access_types": sorted(ACCESS_TYPES),
        },
    }


def _apply_and_validate(
    options: dict[str, Any],
    key: str,
    updated_list: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, tuple[ValidationIssue, ...]]:
    new_options = dict(options)
    new_options[key] = updated_list
    blocking = tuple(issue for issue in validate_topology(new_options) if issue.severity == "error")
    if blocking:
        return None, blocking
    return new_options, ()


def apply_room_topology_fields(
    options: dict[str, Any],
    *,
    room_id: str,
    room_type: str | None = None,
    floor: int | None = None,
) -> tuple[dict[str, Any] | None, tuple[ValidationIssue, ...]]:
    """Set topology fields on an existing Room. Returns (None, ()) if room_id is unknown."""
    room_id = str(room_id or "").strip()
    if not room_id:
        return None, ()
    if room_type is not None and room_type not in ROOM_TYPES:
        return None, ()
    rooms = list(options.get(OPT_ROOMS) or [])
    found = False
    updated_rooms: list[Any] = []
    for raw in rooms:
        if isinstance(raw, dict) and str(raw.get("room_id") or "") == room_id:
            found = True
            room = dict(raw)
            if room_type is not None:
                room["room_type"] = room_type
            if floor is not None:
                room["floor"] = floor
            updated_rooms.append(room)
        else:
            updated_rooms.append(raw)
    if not found:
        return None, ()
    return _apply_and_validate(options, OPT_ROOMS, updated_rooms)


def apply_room_opening_upsert(
    options: dict[str, Any],
    *,
    opening_id: str | None,
    room_id: str,
    type: str,
    orientation: str | None = None,
    entity_id: str | None = None,
) -> tuple[dict[str, Any] | None, tuple[ValidationIssue, ...]]:
    """Create or replace one Opening by opening_id (generated if not provided)."""
    room_id = str(room_id or "").strip()
    opening_type = str(type or "").strip()
    if not room_id or opening_type not in OPENING_TYPES:
        return None, ()
    if orientation is not None and orientation not in ORIENTATIONS:
        return None, ()
    # Not checked against existing opening_ids: a uuid4 collision with one already present
    # would silently overwrite it via the replace-by-id upsert below (same as an explicit
    # edit). Not defended against — the collision probability is negligible (2^122 space) and
    # not a realistic risk for a per-household list of at most a few hundred entries.
    resolved_id = str(opening_id or "").strip() or str(uuid4())
    record = {
        "opening_id": resolved_id,
        "room_id": room_id,
        "type": opening_type,
        "orientation": orientation,
        "entity_id": str(entity_id).strip() if entity_id else None,
    }
    existing = [o for o in (options.get(OPT_ROOM_OPENINGS) or []) if isinstance(o, dict)]
    replaced = [o for o in existing if str(o.get("opening_id") or "") != resolved_id]
    replaced.append(record)
    return _apply_and_validate(options, OPT_ROOM_OPENINGS, replaced)


def apply_room_opening_delete(
    options: dict[str, Any],
    *,
    opening_id: str,
) -> tuple[dict[str, Any] | None, tuple[ValidationIssue, ...]]:
    """Delete one Opening. Blocked (via validate_topology) if a Connection still references it."""
    opening_id = str(opening_id or "").strip()
    if not opening_id:
        return None, ()
    existing = [o for o in (options.get(OPT_ROOM_OPENINGS) or []) if isinstance(o, dict)]
    remaining = [o for o in existing if str(o.get("opening_id") or "") != opening_id]
    if len(remaining) == len(existing):
        return None, ()
    return _apply_and_validate(options, OPT_ROOM_OPENINGS, remaining)


def apply_room_connection_upsert(
    options: dict[str, Any],
    *,
    connection_id: str | None,
    opening_id: str,
    room_b: str,
    access_type: str | None = None,
    connection_type_override: str | None = None,
) -> tuple[dict[str, Any] | None, tuple[ValidationIssue, ...]]:
    """Create or replace one Connection by connection_id (generated if not provided)."""
    opening_id = str(opening_id or "").strip()
    room_b = str(room_b or "").strip()
    if not opening_id or not room_b:
        return None, ()
    if access_type is not None and access_type not in ACCESS_TYPES:
        return None, ()
    if connection_type_override is not None and connection_type_override not in CONNECTION_TYPES:
        return None, ()
    # See apply_room_opening_upsert's identical note: a generated id colliding with an
    # existing connection_id is not checked for and would silently overwrite it.
    resolved_id = str(connection_id or "").strip() or str(uuid4())
    record = {
        "connection_id": resolved_id,
        "opening_id": opening_id,
        "room_b": room_b,
        "access_type": access_type or DEFAULT_ACCESS_TYPE,
        "connection_type_override": connection_type_override,
    }
    existing = [c for c in (options.get(OPT_ROOM_CONNECTIONS) or []) if isinstance(c, dict)]
    replaced = [c for c in existing if str(c.get("connection_id") or "") != resolved_id]
    replaced.append(record)
    return _apply_and_validate(options, OPT_ROOM_CONNECTIONS, replaced)


def apply_room_connection_delete(
    options: dict[str, Any],
    *,
    connection_id: str,
) -> tuple[dict[str, Any] | None, tuple[ValidationIssue, ...]]:
    """Delete one Connection."""
    connection_id = str(connection_id or "").strip()
    if not connection_id:
        return None, ()
    existing = [c for c in (options.get(OPT_ROOM_CONNECTIONS) or []) if isinstance(c, dict)]
    remaining = [c for c in existing if str(c.get("connection_id") or "") != connection_id]
    if len(remaining) == len(existing):
        return None, ()
    return _apply_and_validate(options, OPT_ROOM_CONNECTIONS, remaining)


# room_type/floor/geometry never affect entity registry/platform setup (unlike area_id,
# occupancy sources, etc.), so a change limited to these fields doesn't need the full
# hass.config_entries.async_reload the other options[OPT_ROOMS] fields do — see __init__.py's
# _async_entry_updated, which calls this to decide between the light and heavy reload path.
_ROOM_TOPOLOGY_FIELDS = frozenset({"room_type", "floor", "geometry"})


def is_room_options_change_topology_only(prev_rooms: Any, new_rooms: Any) -> bool:
    """True if the only differences between two options[OPT_ROOMS] lists are edits to
    room_type/floor/geometry on already-existing rooms — no room added/removed, and no other
    field (area_id, occupancy config, ...) changed on any room.
    """
    if not isinstance(prev_rooms, list) or not isinstance(new_rooms, list):
        return False
    prev_by_id = {
        str(room.get("room_id")): room
        for room in prev_rooms
        if isinstance(room, dict) and room.get("room_id")
    }
    new_by_id = {
        str(room.get("room_id")): room
        for room in new_rooms
        if isinstance(room, dict) and room.get("room_id")
    }
    if set(prev_by_id) != set(new_by_id):
        return False
    for room_id, prev_room in prev_by_id.items():
        new_room = new_by_id[room_id]
        prev_rest = {k: v for k, v in prev_room.items() if k not in _ROOM_TOPOLOGY_FIELDS}
        new_rest = {k: v for k, v in new_room.items() if k not in _ROOM_TOPOLOGY_FIELDS}
        if prev_rest != new_rest:
            return False
    return True
