"""Per-cycle domain result accumulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class DomainResultBag:
    """Immutable view of current-cycle upstream domain results."""

    _results: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_results", MappingProxyType(dict(self._results)))

    @classmethod
    def empty(cls) -> "DomainResultBag":
        """Return an empty result bag."""
        return cls()

    def with_result(self, domain_id: str, result: Any) -> "DomainResultBag":
        """Return a new bag containing one additional domain result."""
        next_results = dict(self._results)
        next_results[domain_id] = result
        return DomainResultBag(next_results)

    def get(self, domain_id: str, default: Any = None) -> Any:
        """Return a domain result if present."""
        return self._results.get(domain_id, default)

    def require(self, domain_id: str) -> Any:
        """Return a domain result or raise when the dependency is unavailable."""
        try:
            return self._results[domain_id]
        except KeyError as err:
            raise KeyError(f"Missing domain result: {domain_id}") from err

    def as_dict(self) -> dict[str, Any]:
        """Return a shallow copy for diagnostics."""
        return dict(self._results)
