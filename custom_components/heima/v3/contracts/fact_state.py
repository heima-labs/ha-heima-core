"""Pure state comparison projections; callers must resolve state/event ownership."""

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from types import MappingProxyType

from .canonical_json import canonical_json_bytes
from .fact_sources import FactSourceFingerprint, fact_source_fingerprint
from .house_facts import HouseFact
from .location import Location


@dataclass(frozen=True, slots=True, init=False)
class FactIdentityKey:
    fact_type: str
    where: Location

    def __init__(self) -> None:
        raise TypeError("Extract a state identity through fact_identity_key")


@dataclass(frozen=True, slots=True, init=False, eq=False)
class FactChangeFingerprint:
    available: bool
    confidence: float | None
    value: object
    source: FactSourceFingerprint

    def __init__(self) -> None:
        raise TypeError("Extract a state fingerprint through fact_change_fingerprint")

    def __eq__(self, other: object) -> bool:
        if type(other) is not FactChangeFingerprint:
            return NotImplemented
        return canonical_json_bytes(self) == canonical_json_bytes(other)

    def __hash__(self) -> int:
        return hash(canonical_json_bytes(self))


def fact_identity_key(fact: HouseFact) -> FactIdentityKey:
    """Extract WHAT+WHERE from a builder output for a declared state claim.

    This is not producer admission or an event-kind classifier. Query-key
    construction will have its own validated boundary.
    """
    if type(fact) is not HouseFact:
        raise TypeError("State identity requires a concrete HouseFact")
    key = object.__new__(FactIdentityKey)
    object.__setattr__(key, "fact_type", fact.fact_type)
    object.__setattr__(key, "where", fact.where)
    return key


def fact_change_fingerprint(fact: HouseFact) -> FactChangeFingerprint:
    """Compare state content, excluding time, causal id and diagnostic evidence.

    Input must be a build_house_fact output, whose payload is already validated
    and immutable. Unavailable value is undefined and must not even be projected.
    """
    if type(fact) is not HouseFact:
        raise TypeError("State fingerprint requires a concrete HouseFact")
    result = object.__new__(FactChangeFingerprint)
    object.__setattr__(result, "available", fact.how.available)
    object.__setattr__(result, "confidence", fact.how.confidence)
    object.__setattr__(
        result, "value", _value_projection(fact.value) if fact.how.available else None
    )
    object.__setattr__(result, "source", fact_source_fingerprint(fact.how.source))
    return result


def _value_projection(value: object) -> object:
    """Normalize an already frozen builder value, preserving numeric primitives."""
    if is_dataclass(value):
        return MappingProxyType(
            {field.name: _value_projection(getattr(value, field.name)) for field in fields(value)}
        )
    if isinstance(value, Mapping):
        return MappingProxyType({key: _value_projection(item) for key, item in value.items()})
    if isinstance(value, tuple):
        return tuple(_value_projection(item) for item in value)
    return value
