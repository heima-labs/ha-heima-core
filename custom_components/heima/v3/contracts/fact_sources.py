"""Source data and stable comparison; runtime authority is assigned at ingress."""

from dataclasses import dataclass, field
from typing import Literal, get_args
from uuid import uuid4

FactSourceKind = Literal[
    "sensor",
    "analyzer",
    "third_party_plugin",
    "semantic_resolver",
    "reaction",
    "admin_command",
    "resident_response",
    "timeout",
    "recovery",
    "system",
    "test",
    "legacy",
]
ApplyStepSourceKind = Literal[
    "reaction",
    "admin_command",
    "resident_response",
    "timeout",
    "recovery",
    "system",
    "test",
]
FactSourceActorType = Literal[
    "ha_admin",
    "resident",
    "heima",
    "scheduler",
    "service",
    "system",
    "test",
    "unknown",
]


def _text(value: object, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if type(value) is not str:
        raise TypeError("Source fields require primitive strings")


def _closed(value: object, vocabulary: tuple[object, ...]) -> None:
    _text(value)
    if value not in vocabulary:
        raise ValueError("Source vocabulary value is unknown")


def _stable_fields(
    source_id: str,
    source_type: str | None,
    configuration_fingerprint: str | None,
    actor_type: FactSourceActorType,
) -> None:
    _text(source_id)
    _text(source_type, optional=True)
    _text(configuration_fingerprint, optional=True)
    _closed(actor_type, get_args(FactSourceActorType))


@dataclass(frozen=True, slots=True)
class FactSource:
    """Structured data only; construction never proves kind or actor authority."""

    kind: FactSourceKind
    source_id: str
    source_type: str | None = None
    configuration_fingerprint: str | None = None
    route_fingerprint: str | None = None
    actor_type: FactSourceActorType = "heima"
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        _closed(self.kind, get_args(FactSourceKind))
        _stable_fields(
            self.source_id, self.source_type, self.configuration_fingerprint, self.actor_type
        )
        _text(self.route_fingerprint, optional=True)
        _text(self.correlation_id)


@dataclass(frozen=True, slots=True)
class ApplyStepSource:
    """Action-side source data; production paths explicitly propagate causal IDs."""

    kind: ApplyStepSourceKind
    source_id: str
    source_type: str | None = None
    configuration_fingerprint: str | None = None
    actor_type: FactSourceActorType = "heima"
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        _closed(self.kind, get_args(ApplyStepSourceKind))
        _stable_fields(
            self.source_id, self.source_type, self.configuration_fingerprint, self.actor_type
        )
        _text(self.correlation_id)


@dataclass(frozen=True, slots=True)
class FactSourceFingerprint:
    """Stable source contribution to write-on-change, not an authorization proof."""

    kind: FactSourceKind
    source_id: str
    source_type: str | None
    actor_type: FactSourceActorType
    configuration_fingerprint: str | None
    route_fingerprint: str | None

    def __post_init__(self) -> None:
        _closed(self.kind, get_args(FactSourceKind))
        _stable_fields(
            self.source_id, self.source_type, self.configuration_fingerprint, self.actor_type
        )
        _text(self.route_fingerprint, optional=True)


def fact_source_fingerprint(source: FactSource) -> FactSourceFingerprint:
    """Extract the stable source; revalidate correlation too, then exclude it."""
    if not isinstance(source, FactSource):
        raise TypeError("Fact source fingerprint requires a FactSource")
    FactSource.__post_init__(source)
    return FactSourceFingerprint(
        source.kind,
        source.source_id,
        source.source_type,
        source.actor_type,
        source.configuration_fingerprint,
        source.route_fingerprint,
    )


def validate_runtime_source_shape(
    source: FactSource | ApplyStepSource, *, test_mode: bool = False
) -> None:
    """Reject archive/test data for runtime use; this does not grant source trust.

    The owner must separately assign kind, identity, generation, route and actor
    from its verified boundary. Do not deserialize arbitrary source data as authority.
    """
    if type(test_mode) is not bool:
        raise TypeError("Source validation mode must be boolean")
    if not isinstance(source, (FactSource, ApplyStepSource)):
        raise TypeError("Runtime source shape requires a typed source")
    if isinstance(source, FactSource):
        FactSource.__post_init__(source)
    else:
        ApplyStepSource.__post_init__(source)
    if source.kind == "legacy":
        raise ValueError("Archive sources cannot enter the V3 runtime")
    if not test_mode and (source.kind == "test" or source.actor_type == "test"):
        raise ValueError("Test sources cannot enter production data")
