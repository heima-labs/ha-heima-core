"""Pure universal fact construction; runtime owns source authority and diagnostics."""

from collections.abc import Mapping
from dataclasses import dataclass

from .canonical_json import canonical_json_bytes
from .fact_sources import FactSource, validate_runtime_source_shape
from .instants import EvidenceInstant, parse_instant
from .location import Location, location_key_json
from .payloads import PayloadDiagnostic, freeze_house_fact_value, prepare_evidence

_OMITTED = object()


@dataclass(frozen=True, slots=True, init=False, eq=False)
class Provenance:
    confidence: float | None
    source: FactSource
    available: bool
    evidence: Mapping[str, object]

    def __init__(self) -> None:
        raise TypeError("Construct provenance through build_house_fact")

    def __eq__(self, other: object) -> bool:
        if type(other) is not Provenance:
            return NotImplemented
        return canonical_json_bytes(self) == canonical_json_bytes(other)

    def __hash__(self) -> int:
        return hash(canonical_json_bytes(self))


@dataclass(frozen=True, slots=True, init=False, eq=False)
class HouseFact:
    fact_type: str
    value: object
    where: Location
    when: EvidenceInstant
    how: Provenance

    def __init__(self) -> None:
        raise TypeError("Construct facts through build_house_fact")

    def __eq__(self, other: object) -> bool:
        if type(other) is not HouseFact:
            return NotImplemented
        return house_fact_canonical_bytes(self) == house_fact_canonical_bytes(other)

    def __hash__(self) -> int:
        return hash(house_fact_canonical_bytes(self))


@dataclass(frozen=True, slots=True)
class FactBuildResult:
    fact: HouseFact
    diagnostics: tuple[PayloadDiagnostic, ...]


def _confidence_pair(confidence: float | None, available: bool) -> None:
    if type(available) is not bool:
        raise TypeError("Fact availability must be boolean")
    if available != (confidence is not None):
        raise ValueError("Fact confidence and availability are inconsistent")
    if confidence is None:
        return
    if type(confidence) not in (int, float):
        raise TypeError("Fact confidence must be a primitive number")
    # Bounds also reject infinities/NaN without converting an arbitrary large int.
    if not 0 <= confidence <= 1:
        raise ValueError("Fact confidence is outside its finite unit interval")


def build_house_fact(
    *,
    fact_type: str,
    value: object,
    where: Location,
    when: EvidenceInstant,
    source: FactSource,
    confidence: float | None,
    available: bool = True,
    evidence: object = _OMITTED,
    test_mode: bool = False,
) -> FactBuildResult:
    """Prepare once, return an immutable fact and bounded evidence diagnostics.

    Source shape/mode checks grant no producer, generation or actor authority.
    The runtime must verify admission and consume diagnostics before accepting it.
    """
    if type(fact_type) is not str:
        raise TypeError("Fact type must be a primitive string")
    if "*" in fact_type or any(not segment for segment in fact_type.split(".")):
        raise ValueError("Fact type must have nonempty concrete dotted segments")
    canonical_json_bytes(fact_type)
    parse_instant(when)
    _confidence_pair(confidence, available)
    if not isinstance(where, Location):
        raise TypeError("Fact location must be a Location")
    location = Location(where.scope, where.room_id, where.zone_id, where.room_ids)
    location_key_json(location)
    validate_runtime_source_shape(source, test_mode=test_mode)
    if type(source) is not FactSource:
        raise TypeError("A fact requires a fact-side source")
    owned_source = FactSource(
        source.kind,
        source.source_id,
        source.source_type,
        source.configuration_fingerprint,
        source.route_fingerprint,
        source.actor_type,
        source.correlation_id,
    )
    canonical_json_bytes(owned_source)
    prepared_value = freeze_house_fact_value(value)
    prepared_evidence = prepare_evidence({} if evidence is _OMITTED else evidence)
    how = object.__new__(Provenance)
    object.__setattr__(how, "confidence", confidence)
    object.__setattr__(how, "source", owned_source)
    object.__setattr__(how, "available", available)
    object.__setattr__(how, "evidence", prepared_evidence.payload.value)
    fact = object.__new__(HouseFact)
    object.__setattr__(fact, "fact_type", fact_type)
    object.__setattr__(fact, "value", prepared_value.value)
    object.__setattr__(fact, "where", location)
    object.__setattr__(fact, "when", when)
    object.__setattr__(fact, "how", how)
    return FactBuildResult(fact, prepared_evidence.diagnostics)


def house_fact_canonical_bytes(fact: HouseFact) -> bytes:
    """Encode a builder output; this is not untrusted-input admission/decoding."""
    if type(fact) is not HouseFact:
        raise TypeError("Fact encoding requires a concrete HouseFact")
    location = fact.where
    return canonical_json_bytes(
        {
            "fact_type": fact.fact_type,
            "value": fact.value,
            "where": {
                "scope": location.scope,
                "room_id": location.room_id,
                "zone_id": location.zone_id,
                "room_ids": None if location.room_ids is None else sorted(location.room_ids),
            },
            "when": fact.when,
            "how": fact.how,
        }
    )
