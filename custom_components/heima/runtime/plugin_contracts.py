"""Runtime plugin Protocols."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .domain_result_bag import DomainResultBag
from .state_store import CanonicalState

DomainResult = Any


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
