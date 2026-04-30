"""Tests for domain plugin DAG resolution."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.heima.runtime.dag import (
    HeimaDomainCycleError,
    HeimaMissingDependencyError,
    resolve_dag,
)
from custom_components.heima.runtime.domain_result_bag import DomainResultBag
from custom_components.heima.runtime.domains.heating import HeatingDomain
from custom_components.heima.runtime.domains.lighting import LightingDomain
from custom_components.heima.runtime.domains.security import SecurityDomain
from custom_components.heima.runtime.normalization.service import InputNormalizer
from custom_components.heima.runtime.plugin_contracts import IDomainPlugin


@dataclass
class DummyPlugin:
    domain_id: str
    depends_on: list[str]

    def compute(self, *_args: Any, **_kwargs: Any) -> object:
        return object()

    def reset(self) -> None:
        return None

    def diagnostics(self) -> dict[str, Any]:
        return {}


def test_resolve_dag_orders_plugins_after_dependencies() -> None:
    plugins = [
        DummyPlugin("security", ["heating"]),
        DummyPlugin("lighting", ["house_state"]),
        DummyPlugin("heating", ["lighting"]),
    ]

    resolved = resolve_dag(plugins)

    assert [plugin.domain_id for plugin in resolved] == [
        "lighting",
        "heating",
        "security",
    ]


def test_resolve_dag_allows_core_domain_dependencies() -> None:
    plugins = [
        DummyPlugin("lighting", ["house_state"]),
        DummyPlugin("security", ["occupancy", "people"]),
    ]

    resolved = resolve_dag(plugins)

    assert [plugin.domain_id for plugin in resolved] == ["lighting", "security"]


def test_resolve_dag_raises_for_single_missing_dependency() -> None:
    plugins = [DummyPlugin("lighting", ["unknown_domain"])]

    with pytest.raises(HeimaMissingDependencyError, match="lighting: unknown_domain"):
        resolve_dag(plugins)


def test_resolve_dag_raises_for_multiple_missing_dependencies() -> None:
    plugins = [
        DummyPlugin("lighting", ["missing_a"]),
        DummyPlugin("security", ["missing_b"]),
    ]

    with pytest.raises(HeimaMissingDependencyError) as err:
        resolve_dag(plugins)

    assert "lighting: missing_a" in str(err.value)
    assert "security: missing_b" in str(err.value)


def test_resolve_dag_raises_for_two_plugin_cycle() -> None:
    plugins = [
        DummyPlugin("lighting", ["security"]),
        DummyPlugin("security", ["lighting"]),
    ]

    with pytest.raises(HeimaDomainCycleError, match="lighting"):
        resolve_dag(plugins)


def test_resolve_dag_raises_for_three_plugin_cycle() -> None:
    plugins = [
        DummyPlugin("lighting", ["security"]),
        DummyPlugin("heating", ["lighting"]),
        DummyPlugin("security", ["heating"]),
    ]

    with pytest.raises(HeimaDomainCycleError, match="heating"):
        resolve_dag(plugins)


def test_domain_result_bag_is_immutable_and_requires_results() -> None:
    bag = DomainResultBag.empty().with_result("lighting", {"intent": "auto"})

    assert bag.require("lighting") == {"intent": "auto"}
    assert bag.as_dict() == {"lighting": {"intent": "auto"}}
    with pytest.raises(KeyError, match="Missing domain result: heating"):
        bag.require("heating")


def test_builtin_control_domains_satisfy_domain_plugin_protocol() -> None:
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda _entity_id: None))
    normalizer = InputNormalizer(hass)

    assert isinstance(LightingDomain(hass, normalizer), IDomainPlugin)
    assert isinstance(HeatingDomain(hass, normalizer), IDomainPlugin)
    assert isinstance(SecurityDomain(hass, normalizer), IDomainPlugin)
