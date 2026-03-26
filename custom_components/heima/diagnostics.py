"""Diagnostics support for Heima."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import DIAGNOSTICS_REDACT_KEYS, DOMAIN
from .runtime.analyzers import builtin_learning_pattern_plugin_descriptors
from .runtime.reactions import builtin_reaction_plugin_descriptors


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = data.get("coordinator")

    learning_plugins = _learning_plugin_diagnostics(coordinator)

    payload = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "minor_version": getattr(entry, "minor_version", None),
            "options": dict(entry.options),
        },
        "runtime": {
            "data": getattr(coordinator, "data", None),
            "engine": coordinator.engine.diagnostics() if coordinator else {},
            "scheduler": coordinator.scheduler.diagnostics() if coordinator else {},
            "event_store": coordinator._event_store.diagnostics() if coordinator else {},
            "proposals": coordinator._proposal_engine.diagnostics() if coordinator else {},
            "plugins": {
                "learning_pattern_plugins": learning_plugins,
                "reaction_plugins": [
                    {
                        "reaction_class": descriptor.reaction_class,
                        "reaction_id_strategy": descriptor.reaction_id_strategy,
                        "supported_config_contracts": list(descriptor.supported_config_contracts),
                        "supports_normalizer": descriptor.supports_normalizer,
                    }
                    for descriptor in builtin_reaction_plugin_descriptors()
                ],
            },
        },
    }

    return async_redact_data(payload, DIAGNOSTICS_REDACT_KEYS)


def _learning_plugin_diagnostics(coordinator: Any) -> list[dict[str, Any]]:
    if coordinator:
        registry = getattr(coordinator, "learning_plugin_registry", None)
        if registry is not None and hasattr(registry, "diagnostics"):
            return list(registry.diagnostics())
    return [
        {
            "plugin_id": descriptor.plugin_id,
            "analyzer_id": descriptor.analyzer_id,
            "plugin_family": descriptor.plugin_family,
            "proposal_types": list(descriptor.proposal_types),
            "reaction_targets": list(descriptor.reaction_targets),
            "enabled": True,
        }
        for descriptor in builtin_learning_pattern_plugin_descriptors()
    ]
