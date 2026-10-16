"""Fixed-source state builders fenced by the coordinator's active generation."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..contracts.canonical_json import canonical_json_bytes
from ..contracts.fact_sources import (
    FactSource,
    FactSourceFingerprint,
    validate_runtime_source_shape,
)
from ..contracts.generations import ComposedGenerationManifest
from ..contracts.house_facts import FactBuildResult, build_house_fact
from ..contracts.instants import EvidenceInstant
from ..contracts.location import Location
from .producer_staging import ComposedFactProducers, StaticStateClaim

_OMITTED = object()
type _StateKey = tuple[str, Location]
type ActiveStateGeneration = Callable[[], PreparedStateProducerGeneration | None]


class InactiveProducerGeneration(RuntimeError):
    """The captured generation is not the coordinator's installed snapshot."""


@dataclass(frozen=True, slots=True)
class FixedStateProducerRegistration:
    claim: StaticStateClaim
    source: FactSourceFingerprint

    def __post_init__(self) -> None:
        if type(self.claim) is not StaticStateClaim:
            raise TypeError("Fixed-source producer requires a concrete static claim")
        if type(self.source) is not FactSourceFingerprint:
            raise TypeError("Fixed-source producer requires a source fingerprint")
        FactSourceFingerprint.__post_init__(self.source)
        source = self.source
        validate_runtime_source_shape(
            FactSource(
                source.kind,
                source.source_id,
                source.source_type,
                source.configuration_fingerprint,
                source.route_fingerprint,
                source.actor_type,
                correlation_id="staging",
            )
        )
        canonical_json_bytes(source)


@dataclass(frozen=True, slots=True, init=False)
class PreparedStateProducerGeneration:
    manifest: ComposedGenerationManifest
    composition: ComposedFactProducers
    _producers: Mapping[_StateKey, FixedStateProducerRegistration]

    def __init__(self) -> None:
        raise TypeError("Use prepare_state_producer_generation")

    def bind(
        self, claim: StaticStateClaim, read_active: ActiveStateGeneration
    ) -> FixedSourceStateProducer:
        """Staging only; read_active belongs to the serialized runtime coordinator.

        Preparing/binding a snapshot never activates it. The coordinator installs
        it only through the durable composed commit and cycle-boundary swap.
        """
        if type(claim) is not StaticStateClaim:
            raise TypeError("Producer binding requires a concrete static claim")
        registration = self._producers.get((claim.fact_type, claim.where))
        if registration is None:
            raise ValueError("Fixed-source producer was not prepared")
        if registration.claim != claim:
            raise ValueError("Producer claim differs from its prepared declaration")
        if not callable(read_active):
            raise TypeError("Producer binding requires an active-generation reader")
        port = object.__new__(FixedSourceStateProducer)
        object.__setattr__(port, "_generation", self)
        object.__setattr__(port, "_registration", registration)
        object.__setattr__(port, "_read_active", read_active)
        return port


@dataclass(frozen=True, slots=True, init=False)
class FixedSourceStateProducer:
    _generation: PreparedStateProducerGeneration
    _registration: FixedStateProducerRegistration
    _read_active: ActiveStateGeneration

    def __init__(self) -> None:
        raise TypeError("Bind a producer through a prepared generation")

    def _require_active(self) -> None:
        if self._read_active() is not self._generation:
            raise InactiveProducerGeneration("Producer generation is not active")

    def build(
        self,
        *,
        value: object,
        when: EvidenceInstant,
        correlation_id: str,
        confidence: float | None,
        available: bool = True,
        evidence: object = _OMITTED,
    ) -> FactBuildResult:
        """Build on the coordinator thread; no await, acceptance or publication.

        The owning runtime supplies the cycle instant and causal origin explicitly.
        Source fields are taken only from trusted core staging, never an input fact.
        Variable-route fusion and per-edge actor assignment need their own ports.
        """
        self._require_active()
        registration = self._registration
        source = registration.source
        result = build_house_fact(
            fact_type=registration.claim.fact_type,
            where=registration.claim.where,
            value=value,
            when=when,
            source=FactSource(
                source.kind,
                source.source_id,
                source.source_type,
                source.configuration_fingerprint,
                source.route_fingerprint,
                source.actor_type,
                correlation_id,
            ),
            confidence=confidence,
            available=available,
            evidence={} if evidence is _OMITTED else evidence,
        )
        # Payload field access can reenter core code; fence again before returning.
        self._require_active()
        return result


def prepare_state_producer_generation(
    manifest: ComposedGenerationManifest,
    composition: ComposedFactProducers,
    registrations: tuple[FixedStateProducerRegistration, ...],
) -> PreparedStateProducerGeneration:
    """Prepare a fixed-source subset; core registry owners assign its source data.

    This is not an API for imported/untrusted provenance. Shape checks never prove
    actor permissions, authentic digests, commit completion or active status.
    The composition/layer definitions must belong to this candidate manifest.
    """
    if type(manifest) is not ComposedGenerationManifest:
        raise TypeError("Producer generation requires a concrete manifest")
    ComposedGenerationManifest.__post_init__(manifest)
    if type(composition) is not ComposedFactProducers:
        raise TypeError("Producer generation requires composed declarations")
    if type(registrations) is not tuple:
        raise TypeError("Fixed-source registrations require an immutable tuple")
    producers: dict[_StateKey, FixedStateProducerRegistration] = {}
    declared = frozenset(composition.state_claims)
    for registration in registrations:
        if type(registration) is not FixedStateProducerRegistration:
            raise TypeError("Fixed-source registrations require concrete records")
        FixedStateProducerRegistration.__post_init__(registration)
        claim = registration.claim
        owned_claim = StaticStateClaim(claim.fact_type, claim.where, claim.owner_id)
        if owned_claim not in declared:
            raise ValueError("Fixed-source producer has no matching static declaration")
        key = (owned_claim.fact_type, owned_claim.where)
        if key in producers:
            raise ValueError("Fixed-source producer registered twice")
        source = registration.source
        owned_source = FactSourceFingerprint(
            source.kind,
            source.source_id,
            source.source_type,
            source.actor_type,
            source.configuration_fingerprint,
            source.route_fingerprint,
        )
        producers[key] = FixedStateProducerRegistration(owned_claim, owned_source)
    prepared = object.__new__(PreparedStateProducerGeneration)
    object.__setattr__(prepared, "manifest", manifest)
    object.__setattr__(prepared, "composition", composition)
    object.__setattr__(prepared, "_producers", MappingProxyType(producers))
    return prepared
