"""Pure candidate composition; bindings are metadata, never source authority."""

from dataclasses import dataclass
from typing import Final

from ..contracts.canonical_json import canonical_json_bytes
from ..contracts.fact_types import (
    FactEmissionKind,
    FactTypeClaim,
    fact_type_matches,
    validate_fact_type,
    validate_fact_type_claims,
)
from ..contracts.location import Location, location_key_json

CORE_FACT_TYPE_CLAIMS: Final = (
    FactTypeClaim("manual_hold.lifecycle", "layer0.divergence_hold", "event"),
    FactTypeClaim("actuator.resident_control", "layer0.resident_control_ingress", "event"),
    FactTypeClaim("actuator.channel_state.*", "layer0.channel_observation", "state"),
    FactTypeClaim("actuator.correction", "layer5.correction_attribution", "event"),
    FactTypeClaim("actuator.target_lifecycle", "layer5.target_evidence", "event"),
    FactTypeClaim("reaction.decision.*", "layer5.reaction_decision", "state"),
    FactTypeClaim("reaction.managed_episode.*", "layer5.managed_episode", "state"),
    FactTypeClaim("reaction.follow_up", "layer6.reaction_follow_up", "event"),
    FactTypeClaim("automation.availability", "layer6.availability", "event"),
    FactTypeClaim("reaction.advisory", "layer6.reaction_advisory", "event"),
    FactTypeClaim("recovery.confirmation_request", "layer6.recovery_confirmation", "event"),
    FactTypeClaim("reaction.action_notice", "layer6.reaction_action_notice", "event"),
    FactTypeClaim("proposal.review_pending", "layer6.proposal_review", "event"),
    FactTypeClaim("reaction.consent_request", "layer6.consent_request", "event"),
    FactTypeClaim("reaction.advisory_feedback", "layer5.advisory_feedback", "event"),
)


def _owner(owner_id: str) -> None:
    if type(owner_id) is not str:
        raise TypeError("Producer owner requires a primitive string")
    canonical_json_bytes(owner_id)


@dataclass(frozen=True, slots=True)
class StaticStateClaim:
    fact_type: str
    where: Location
    owner_id: str

    def __post_init__(self) -> None:
        validate_fact_type(self.fact_type)
        _owner(self.owner_id)
        if not isinstance(self.where, Location):
            raise TypeError("Static state claim requires a Location")
        where = Location(
            self.where.scope, self.where.room_id, self.where.zone_id, self.where.room_ids
        )
        location_key_json(where)
        object.__setattr__(self, "where", where)


@dataclass(frozen=True, slots=True, init=False)
class FactTypeBinding:
    fact_type: str
    owner_id: str
    emission_kind: FactEmissionKind

    def __init__(self) -> None:
        raise TypeError("Resolve a fact type through composed producer staging")


@dataclass(frozen=True, slots=True, init=False)
class ComposedFactProducers:
    type_claims: tuple[FactTypeClaim, ...]
    state_claims: tuple[StaticStateClaim, ...]

    def __init__(self) -> None:
        raise TypeError("Use compose_fact_producers")

    def resolve_type(self, fact_type: str, owner_id: str) -> FactTypeBinding:
        """Staging only: resolve metadata once for a producer-specific future port.

        This does not verify actor/source authority, a runtime generation, or an
        invocation's Location. It must not be a per-fact evaluation-path lookup.
        """
        return _resolve_type(self.type_claims, fact_type, owner_id)


def _resolve_type(
    claims: tuple[FactTypeClaim, ...], fact_type: str, owner_id: str
) -> FactTypeBinding:
    validate_fact_type(fact_type)
    _owner(owner_id)
    for claim in claims:
        if fact_type_matches(claim.fact_type_pattern, fact_type):
            if claim.owner_id != owner_id:
                raise ValueError("Fact type belongs to another producer owner")
            binding = object.__new__(FactTypeBinding)
            object.__setattr__(binding, "fact_type", fact_type)
            object.__setattr__(binding, "owner_id", owner_id)
            object.__setattr__(binding, "emission_kind", claim.emission_kind)
            return binding
    raise ValueError("Fact type has no composed producer claim")


def _inventory(ids: frozenset[str]) -> None:
    if type(ids) is not frozenset:
        raise TypeError("Producer location inventory requires a frozenset")
    for identifier in ids:
        if type(identifier) is not str:
            raise TypeError("Producer inventory identifiers must be primitive strings")
        if not identifier:
            raise ValueError("Producer inventory identifiers must be nonempty")
    canonical_json_bytes(sorted(ids))


def _resolve_location(where: Location, rooms: frozenset[str], zones: frozenset[str]) -> None:
    if where.scope == "room":
        if where.room_id not in rooms:
            raise ValueError("Producer room is not registered")
    elif where.scope == "zone":
        if where.zone_id not in zones:
            raise ValueError("Producer zone is not registered")
    elif where.scope == "rooms":
        assert where.room_ids is not None
        if not where.room_ids.issubset(rooms):
            raise ValueError("Producer rooms are not all registered")


def compose_fact_producers(
    *,
    type_claims: tuple[FactTypeClaim, ...],
    state_claims: tuple[StaticStateClaim, ...],
    room_ids: frozenset[str],
    zone_ids: frozenset[str],
) -> ComposedFactProducers:
    """Validate one candidate without publishing or mutating an active generation.

    Inventories come from the candidate's registry owners. This checks references,
    not Room/Zone definitions or the authenticity/completeness of their snapshots.
    Reserved claims are always included, even with no instantiated core producers.
    """
    validate_fact_type_claims(type_claims)
    if type(state_claims) is not tuple:
        raise TypeError("Static state claim snapshot requires a tuple")
    _inventory(room_ids)
    _inventory(zone_ids)
    claims = CORE_FACT_TYPE_CLAIMS + tuple(
        FactTypeClaim(claim.fact_type_pattern, claim.owner_id, claim.emission_kind)
        for claim in type_claims
    )
    validate_fact_type_claims(claims)
    accepted: list[StaticStateClaim] = []
    seen: set[tuple[str, Location]] = set()
    for state in state_claims:
        if type(state) is not StaticStateClaim:
            raise TypeError("Static producer composition requires concrete state claims")
        owned = StaticStateClaim(state.fact_type, state.where, state.owner_id)
        key = (owned.fact_type, owned.where)
        if key in seen:
            raise ValueError("Duplicate static state producer identity")
        seen.add(key)
        _resolve_location(owned.where, room_ids, zone_ids)
        binding = _resolve_type(claims, owned.fact_type, owned.owner_id)
        if binding.emission_kind != "state":
            raise ValueError("Static state producer cannot claim an event type")
        accepted.append(owned)
    result = object.__new__(ComposedFactProducers)
    object.__setattr__(result, "type_claims", claims)
    object.__setattr__(result, "state_claims", tuple(accepted))
    return result
