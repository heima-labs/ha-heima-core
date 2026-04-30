"""Runtime plugin Protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from .domain_result_bag import DomainResultBag
from .event_store import EventStore
from .state_store import CanonicalState

DomainResult = Any
BehaviorFindingKind = Literal["pattern", "activity", "anomaly", "correlation"]


@dataclass(frozen=True)
class AnomalySignal:
    """Statistical anomaly emitted by offline behavior analyzers."""

    anomaly_type: str
    severity: Literal["info", "warning", "critical"]
    description: str
    confidence: float
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BehaviorFinding:
    """Typed output from an offline behavior analyzer."""

    kind: BehaviorFindingKind
    analyzer_id: str
    description: str
    confidence: float
    payload: Any


def pattern_finding(
    *, analyzer_id: str, description: str, confidence: float, payload: Any
) -> BehaviorFinding:
    """Build a pattern finding for a ReactionProposal payload."""
    return BehaviorFinding(
        kind="pattern",
        analyzer_id=analyzer_id,
        description=description,
        confidence=confidence,
        payload=payload,
    )


@runtime_checkable
class IDomainPlugin(Protocol):
    """Domain node evaluated after the fixed core domains."""

    @property
    def domain_id(self) -> str:
        """Stable domain identifier used by DAG dependencies."""
        ...

    @property
    def depends_on(self) -> list[str]:
        """Domain IDs that must be evaluated before this plugin."""
        ...

    def compute(
        self,
        canonical_state: CanonicalState,
        domain_results: DomainResultBag,
        signals: list[Any] | None = None,
    ) -> DomainResult:
        """Compute a domain result without blocking I/O."""
        ...

    def reset(self) -> None:
        """Reset transient plugin state after config reload."""
        ...

    def diagnostics(self) -> dict[str, Any]:
        """Return plugin diagnostics."""
        ...


@runtime_checkable
class IOptionsSchemaProvider(Protocol):
    """Optional provider for plugin-owned options flow schema fragments."""

    @property
    def options_schema(self) -> Any:
        """Return the plugin options schema."""
        ...

    def options_defaults(self) -> dict[str, Any]:
        """Return default options for this plugin."""
        ...


@runtime_checkable
class IBehaviorAnalyzer(Protocol):
    """Offline analyzer producing typed behavior findings."""

    @property
    def analyzer_id(self) -> str:
        """Stable analyzer identifier."""
        ...

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: Any | None = None,
    ) -> list[BehaviorFinding]:
        """Analyze persisted history and return findings."""
        ...
