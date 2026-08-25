"""Actuator registry: generic per-entity actuator inventory (Phase AU1).

An `Actuator` is a location fact only — which HA entity, which room, optionally
which opening — never a command. Commands stay exactly where they already live
today, in the Reaction that decides to send them (`entity_steps`/`ApplyStep`).
See `docs/specs/core/actuator_registry_spec.md` and `docs/v2_dev_plan.md` Phase AU.

Kept as its own module, not added to `room_topology.py`: `Actuator` only
*references* `Room`/`Opening` (by `room_id`/`opening_id`, via
`room_topology.parse_openings` and `options[OPT_ROOMS]` directly) — it never
needs to change how they're parsed, derived, or validated. This keeps
`room_topology.py` (AR1-4, already merged and extensively tested) fully
untouched; `room_topology.py` itself stays unaware this module exists.

Deliberately no top-level import of `.validation`: `ValidationIssue` is
imported under `TYPE_CHECKING` for annotations and locally inside
`validate_actuators()`, mirroring `room_topology.py`'s own avoidance of
`validation.py`'s heavy transitive import chain (see that module's docstring
for the full explanation — the same order-sensitive circular import applies
here since this module is imported early, alongside `room_topology.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .const import OPT_ROOM_ACTUATORS, OPT_ROOMS
from .room_topology import parse_openings

if TYPE_CHECKING:
    from .validation import ValidationIssue

_VALIDATION_CAPABILITY = "actuator_registry"


@dataclass(frozen=True)
class Actuator:
    """A location fact: one HA entity, physically in one Room, optionally at one Opening."""

    actuator_id: str
    entity_id: str
    room_id: str
    opening_id: str | None = None
    display_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "actuator_id": self.actuator_id,
            "entity_id": self.entity_id,
            "room_id": self.room_id,
            "opening_id": self.opening_id,
            "display_name": self.display_name,
        }


def parse_actuators(options: dict[str, Any]) -> tuple[Actuator, ...]:
    """Parse options[OPT_ROOM_ACTUATORS] into Actuator records, skipping malformed entries."""
    raw_list = options.get(OPT_ROOM_ACTUATORS)
    parsed: list[Actuator] = []
    seen_ids: set[str] = set()
    for raw in raw_list if isinstance(raw_list, list) else []:
        if not isinstance(raw, dict):
            continue
        actuator_id = str(raw.get("actuator_id") or "").strip()
        entity_id = str(raw.get("entity_id") or "").strip()
        room_id = str(raw.get("room_id") or "").strip()
        if not actuator_id or actuator_id in seen_ids or not entity_id or not room_id:
            continue
        seen_ids.add(actuator_id)
        opening_id = str(raw.get("opening_id") or "").strip()
        display_name = str(raw.get("display_name") or "").strip()
        parsed.append(
            Actuator(
                actuator_id=actuator_id,
                entity_id=entity_id,
                room_id=room_id,
                opening_id=opening_id or None,
                display_name=display_name or None,
            )
        )
    return tuple(parsed)


_EMPTY_ACTUATORS: tuple[Actuator, ...] = ()


class ActuatorCache:
    """Caches parsed Actuator records; invalidated only by an explicit `mark_stale()`.

    Mirrors `room_topology.py`'s own `TopologyGraphCache`: the engine calls `mark_stale()`
    unconditionally on every options reload, and the coordinator calls it on
    `EVENT_AREA_REGISTRY_UPDATED`/`EVENT_ENTITY_REGISTRY_UPDATED` — the same triggers, same
    lifecycle, same rationale (see that class's docstring). A separate cache instance, not folded
    into `TopologyGraphCache`, per `docs/specs/core/actuator_registry_spec.md`'s CanonicalState
    Exposure section.
    """

    def __init__(self) -> None:
        self._stale = True
        self._actuators: tuple[Actuator, ...] = _EMPTY_ACTUATORS

    def mark_stale(self) -> None:
        """Force a rebuild on the next `get_actuators()` call."""
        self._stale = True

    def get_actuators(self, options: dict[str, Any]) -> tuple[Actuator, ...]:
        """Return the cached actuators, rebuilding first if stale."""
        if self._stale:
            self._actuators = parse_actuators(options)
            self._stale = False
        return self._actuators


def _room_ids(options: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for raw in options.get(OPT_ROOMS) or []:
        if not isinstance(raw, dict):
            continue
        room_id = str(raw.get("room_id") or "").strip()
        if room_id:
            ids.add(room_id)
    return ids


def is_opening_referenced_by_actuator(options: dict[str, Any], opening_id: str) -> bool:
    """True if any Actuator references opening_id.

    Consulted by the coordinator (AU4) before deleting an Opening, the same way it already
    consults `room_topology.py`'s own dangling-reference check for Connections — this module
    stays unaware of the coordinator, the coordinator orchestrates across both.
    """
    opening_id = str(opening_id or "").strip()
    if not opening_id:
        return False
    return any(actuator.opening_id == opening_id for actuator in parse_actuators(options))


def validate_actuators(options: dict[str, Any]) -> tuple[ValidationIssue, ...]:
    """Pure structural validation: referential integrity within `options`, no HA dependency.

    Registry-backed checks (`entity_unavailable`) are not this module's concern — they require
    `hass` and are added by AU2 alongside these checks, mirroring `room_topology.py`'s own split
    between `validate_topology()` and `validation.py`'s `_topology_section()`.
    """
    from .validation import ValidationIssue  # local: see module docstring

    actuators = parse_actuators(options)
    room_ids = _room_ids(options)
    openings_by_id = {opening.opening_id: opening for opening in parse_openings(options)}

    issues: list[ValidationIssue] = []

    for actuator in actuators:
        if actuator.room_id not in room_ids:
            issues.append(
                ValidationIssue(
                    key=f"actuators.actuator.{actuator.actuator_id}.dangling_room",
                    severity="warning",
                    title="Actuator references a missing room",
                    description=(
                        f"Actuator '{actuator.actuator_id}' references room_id "
                        f"'{actuator.room_id}', which no longer exists."
                    ),
                    capability=_VALIDATION_CAPABILITY,
                    missing=(actuator.room_id,),
                )
            )

        if actuator.opening_id is None:
            continue

        opening = openings_by_id.get(actuator.opening_id)
        if opening is None:
            issues.append(
                ValidationIssue(
                    key=f"actuators.actuator.{actuator.actuator_id}.dangling_opening",
                    severity="warning",
                    title="Actuator references a missing opening",
                    description=(
                        f"Actuator '{actuator.actuator_id}' references opening_id "
                        f"'{actuator.opening_id}', which no longer exists."
                    ),
                    capability=_VALIDATION_CAPABILITY,
                    missing=(actuator.opening_id,),
                )
            )
        elif opening.room_id != actuator.room_id:
            issues.append(
                ValidationIssue(
                    key=f"actuators.actuator.{actuator.actuator_id}.opening_room_mismatch",
                    severity="error",
                    title="Actuator's opening belongs to a different room",
                    description=(
                        f"Actuator '{actuator.actuator_id}' has room_id '{actuator.room_id}' but "
                        f"opening_id '{actuator.opening_id}' belongs to room '{opening.room_id}'."
                    ),
                    capability=_VALIDATION_CAPABILITY,
                    missing=(),
                )
            )

    entity_to_actuator_ids: dict[str, list[str]] = {}
    for actuator in actuators:
        entity_to_actuator_ids.setdefault(actuator.entity_id, []).append(actuator.actuator_id)
    for entity_id, actuator_ids in entity_to_actuator_ids.items():
        if len(actuator_ids) < 2:
            continue
        issues.append(
            ValidationIssue(
                key=f"actuators.entity.{entity_id}.shared",
                severity="warning",
                title="Entity shared across multiple actuators",
                description=(
                    f"entity_id '{entity_id}' is referenced by {len(actuator_ids)} Actuator "
                    "records."
                ),
                capability=_VALIDATION_CAPABILITY,
                missing=(),
            )
        )

    return tuple(issues)


def build_actuator_registry_snapshot(options: dict[str, Any]) -> dict[str, Any]:
    """Read-only snapshot for the admin editor: rooms, openings, actuators, and issues.

    Mirrors `room_topology.py`'s own `build_room_topology_snapshot()`. Rooms/openings are
    included only as reference data for the editor's dropdowns (the same objects
    `room_topology.py` itself owns) — this module remains the sole owner of `actuators`.
    """
    rooms = [room for room in options.get(OPT_ROOMS, []) or [] if isinstance(room, dict)]
    return {
        "rooms": [
            {
                "room_id": room_id,
                "display_name": str(room.get("display_name") or room_id),
            }
            for room in rooms
            for room_id in (str(room.get("room_id") or ""),)
            if room_id
        ],
        "openings": [opening.as_dict() for opening in parse_openings(options)],
        "actuators": [actuator.as_dict() for actuator in parse_actuators(options)],
        "issues": [issue.as_dict() for issue in validate_actuators(options)],
    }


# --- AU4: admin editor support — pure mutation functions ---
#
# Both functions below follow the same shape as room_topology.py's own mutation functions:
# build the candidate options, run validate_actuators() against them, and reject (return
# None, blocking_issues) if any error-severity issue results. Single choke point for
# "save-time blocking on error-severity only" — the admin editor websocket layer never
# re-implements this check.


def _apply_and_validate(
    options: dict[str, Any],
    updated_list: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, tuple[ValidationIssue, ...]]:
    new_options = dict(options)
    new_options[OPT_ROOM_ACTUATORS] = updated_list
    blocking = tuple(
        issue for issue in validate_actuators(new_options) if issue.severity == "error"
    )
    if blocking:
        return None, blocking
    return new_options, ()


def apply_actuator_upsert(
    options: dict[str, Any],
    *,
    actuator_id: str | None,
    entity_id: str,
    room_id: str,
    opening_id: str | None = None,
    display_name: str | None = None,
) -> tuple[dict[str, Any] | None, tuple[ValidationIssue, ...]]:
    """Create or replace one Actuator by actuator_id (generated if not provided)."""
    entity_id = str(entity_id or "").strip()
    room_id = str(room_id or "").strip()
    if not entity_id or not room_id:
        return None, ()
    # Same collision caveat as room_topology.py's apply_room_opening_upsert: not checked
    # against existing actuator_ids, would silently overwrite on a uuid4 collision. Not
    # defended against — negligible probability, not a realistic risk at this list size.
    resolved_id = str(actuator_id or "").strip() or str(uuid4())
    record = {
        "actuator_id": resolved_id,
        "entity_id": entity_id,
        "room_id": room_id,
        "opening_id": str(opening_id).strip() if opening_id else None,
        "display_name": str(display_name).strip() if display_name else None,
    }
    existing = [a for a in (options.get(OPT_ROOM_ACTUATORS) or []) if isinstance(a, dict)]
    replaced = [a for a in existing if str(a.get("actuator_id") or "") != resolved_id]
    replaced.append(record)
    return _apply_and_validate(options, replaced)


def apply_actuator_delete(
    options: dict[str, Any],
    *,
    actuator_id: str,
) -> tuple[dict[str, Any] | None, tuple[ValidationIssue, ...]]:
    """Delete one Actuator."""
    actuator_id = str(actuator_id or "").strip()
    if not actuator_id:
        return None, ()
    existing = [a for a in (options.get(OPT_ROOM_ACTUATORS) or []) if isinstance(a, dict)]
    remaining = [a for a in existing if str(a.get("actuator_id") or "") != actuator_id]
    if len(remaining) == len(existing):
        return None, ()
    return _apply_and_validate(options, remaining)
