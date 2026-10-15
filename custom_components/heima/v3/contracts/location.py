"""Validated immutable places and the one canonical LocationKey representation."""

import json
from dataclasses import dataclass
from typing import Literal

from .canonical_json import canonical_json_bytes

type ScopeKind = Literal["casa", "room", "zone", "rooms"]
type LocationKey = tuple[str, ...]


def _identifier(value: object) -> None:
    if type(value) is not str:
        raise TypeError("Location identifiers must be strings")
    if not value:
        raise ValueError("Location identifiers must be nonempty")


@dataclass(frozen=True, slots=True, eq=False)
class Location:
    """Shape only; reference existence belongs to the consuming registry."""

    scope: ScopeKind
    room_id: str | None = None
    zone_id: str | None = None
    room_ids: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if type(self.scope) is not str:
            raise TypeError("Location scope must be a string")
        if self.scope not in ("casa", "room", "zone", "rooms"):
            raise ValueError("Unknown Location scope")
        actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
        expected = (self.scope == "room", self.scope == "zone", self.scope == "rooms")
        if actual != expected:
            raise ValueError("Location fields do not match its scope")
        if self.scope == "room":
            _identifier(self.room_id)
        elif self.scope == "zone":
            _identifier(self.zone_id)
        elif self.scope == "rooms":
            if type(self.room_ids) is not frozenset:
                raise TypeError("Multiple-room Location requires a frozenset")
            if len(self.room_ids) < 2:
                raise ValueError("Multiple-room Location needs at least two identifiers")
            for identifier in self.room_ids:
                _identifier(identifier)

    @property
    def key(self) -> LocationKey:
        # Also reject reconstructed invalid values at the identity/encoding boundary.
        self.__post_init__()
        if self.scope == "room":
            assert self.room_id is not None
            return ("room", self.room_id)
        if self.scope == "zone":
            assert self.zone_id is not None
            return ("zone", self.zone_id)
        if self.scope == "rooms":
            assert self.room_ids is not None
            return ("rooms", *sorted(self.room_ids))
        return ("casa",)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Location):
            return NotImplemented
        return self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)


def location_from_key(key: LocationKey) -> Location:
    """Recover the canonical key; never normalize malformed persisted identity."""
    if type(key) is not tuple:
        raise TypeError("Location key must be a tuple")
    if not key:
        raise ValueError("Location key cannot be empty")
    for item in key:
        _identifier(item)
    scope = key[0]
    if scope == "casa" and len(key) == 1:
        return Location("casa")
    if scope == "room" and len(key) == 2:
        return Location("room", room_id=key[1])
    if scope == "zone" and len(key) == 2:
        return Location("zone", zone_id=key[1])
    if scope == "rooms" and len(key) >= 3:
        result = Location("rooms", room_ids=frozenset(key[1:]))
        if result.key == key:
            return result
    raise ValueError("Invalid or noncanonical Location key")


def location_key_json(location: Location) -> str:
    """Canonical scalar key text for identity storage and follow-up projections."""
    if not isinstance(location, Location):
        raise TypeError("Location key encoding requires a Location")
    return canonical_json_bytes(location.key).decode("utf-8")


def location_from_key_json(text: str) -> Location:
    """Decode canonical persisted key text, not a general-purpose JSON document."""
    if type(text) is not str:
        raise TypeError("Location key JSON must be text")
    decoded = json.loads(text)
    if type(decoded) is not list:
        raise TypeError("Location key JSON must contain an array")
    location = location_from_key(tuple(decoded))
    if location_key_json(location) != text:
        raise ValueError("Location key JSON is not canonical")
    return location
