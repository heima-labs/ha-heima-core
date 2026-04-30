"""Domain plugin DAG resolution."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from .plugin_contracts import IDomainPlugin

CORE_DOMAIN_IDS = frozenset({"people", "occupancy", "activity", "house_state"})


class HeimaDomainCycleError(ValueError):
    """Raised when domain plugin dependencies contain a cycle."""


class HeimaMissingDependencyError(ValueError):
    """Raised when a domain plugin dependency cannot be resolved."""


def resolve_dag(plugins: Iterable[IDomainPlugin]) -> list[IDomainPlugin]:
    """Return plugins in dependency order using Kahn's topological sort."""
    ordered_input = list(plugins)
    by_id = {plugin.domain_id: plugin for plugin in ordered_input}
    if len(by_id) != len(ordered_input):
        raise ValueError("Duplicate domain plugin id")

    plugin_ids = set(by_id)
    missing: dict[str, list[str]] = {}
    incoming_count = dict.fromkeys(plugin_ids, 0)
    dependents: dict[str, list[str]] = {domain_id: [] for domain_id in plugin_ids}

    for plugin in ordered_input:
        for dependency in plugin.depends_on:
            if dependency in CORE_DOMAIN_IDS:
                continue
            if dependency not in plugin_ids:
                missing.setdefault(plugin.domain_id, []).append(dependency)
                continue
            incoming_count[plugin.domain_id] += 1
            dependents[dependency].append(plugin.domain_id)

    if missing:
        details = ", ".join(
            f"{domain_id}: {', '.join(dependencies)}"
            for domain_id, dependencies in sorted(missing.items())
        )
        raise HeimaMissingDependencyError(f"Missing domain plugin dependencies: {details}")

    ready = deque(
        plugin.domain_id for plugin in ordered_input if incoming_count[plugin.domain_id] == 0
    )
    resolved: list[IDomainPlugin] = []

    while ready:
        domain_id = ready.popleft()
        resolved.append(by_id[domain_id])
        for dependent_id in dependents[domain_id]:
            incoming_count[dependent_id] -= 1
            if incoming_count[dependent_id] == 0:
                ready.append(dependent_id)

    if len(resolved) != len(ordered_input):
        unresolved = sorted(domain_id for domain_id, count in incoming_count.items() if count > 0)
        raise HeimaDomainCycleError(
            f"Domain plugin dependency cycle detected: {', '.join(unresolved)}"
        )

    return resolved
