"""The Heima integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS, STRUCTURAL_OPTION_KEYS
from .coordinator import HeimaCoordinator
from .entities.registry import build_registry
from .room_sources import (
    autopopulate_room_signals,
    migrate_burst_signal_configs_and_reactions,
    migrate_room_darkness_reactions_to_primary_bucket,
)
from .runtime.reactions import normalize_reaction_options_payload
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Heima (YAML not supported in v1)."""
    hass.data.setdefault(DOMAIN, {})

    if not hass.data[DOMAIN].get("services_registered"):
        await async_register_services(hass)
        hass.data[DOMAIN]["services_registered"] = True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heima from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    normalized_options, signal_changed = autopopulate_room_signals(
        dict(entry.options),
        state_getter=hass.states.get,
    )
    normalized_options, bucket_changed = migrate_room_darkness_reactions_to_primary_bucket(
        normalized_options
    )
    normalized_options, burst_changed = migrate_burst_signal_configs_and_reactions(
        normalized_options
    )
    normalized_options, reaction_changed = normalize_reaction_options_payload(normalized_options)
    changed = signal_changed or bucket_changed or burst_changed or reaction_changed
    if changed:
        hass.config_entries.async_update_entry(entry, options=normalized_options)

    coordinator = HeimaCoordinator(hass=hass, entry=entry)
    await coordinator.async_initialize()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    await _async_cleanup_stale_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    _LOGGER.info("Set up %s (entry_id=%s)", DOMAIN, entry.entry_id)
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update with selective reload.

    - Structural keys (people, rooms, zones): full HA reload to rebuild entity sets.
    - Runtime keys (heating, security, calendar, etc.): in-place coordinator reload.
    """
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
    if coordinator is None:
        _LOGGER.debug("No coordinator found for %s, skipping update", entry.entry_id)
        return

    states = getattr(hass, "states", None)
    state_getter = getattr(states, "get", None)
    normalized_options, signals_changed = autopopulate_room_signals(
        dict(entry.options),
        state_getter=state_getter,
    )
    normalized_options, bucket_changed = migrate_room_darkness_reactions_to_primary_bucket(
        normalized_options
    )
    normalized_options, burst_changed = migrate_burst_signal_configs_and_reactions(
        normalized_options
    )
    normalized_options, reactions_changed = normalize_reaction_options_payload(normalized_options)
    if signals_changed or bucket_changed or burst_changed or reactions_changed:
        hass.config_entries.async_update_entry(entry, options=normalized_options)
        # Do NOT update last_options_snapshot here: the next invocation (scheduled by
        # async_update_entry) will detect the delta between the old snapshot and the
        # normalized options, and call async_reload_options to rebuild reactions.
        return

    prev = coordinator.last_options_snapshot
    new = dict(entry.options)
    changed = {k for k in (prev.keys() | new.keys()) if prev.get(k) != new.get(k)}
    is_structural = bool(changed & STRUCTURAL_OPTION_KEYS)

    coordinator.last_options_snapshot = new

    if is_structural:
        _LOGGER.debug(
            "Structural options changed (%s), reloading entry %s",
            changed & STRUCTURAL_OPTION_KEYS,
            entry.entry_id,
        )
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        _LOGGER.debug(
            "Runtime options changed (%s), reloading coordinator %s", changed, entry.entry_id
        )
        await coordinator.async_reload_options(changed_keys=changed)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data and "coordinator" in data:
            coordinator: HeimaCoordinator = data["coordinator"]
            await coordinator.async_shutdown()
    return unload_ok


async def _async_cleanup_stale_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stale Heima canonical entities left behind by structural option changes."""
    registry = er.async_get(hass)
    expected = _expected_entity_index(entry)
    stale_entity_ids: list[str] = []
    rename_pairs: list[tuple[str, str]] = []

    for reg_entry in registry.entities.values():
        config_entry_ids: list[str] | str = reg_entry.config_entry_id or []
        if isinstance(config_entry_ids, str):
            config_entry_ids = [config_entry_ids]
        if entry.entry_id not in set(config_entry_ids):
            continue
        unique_id = str(reg_entry.unique_id or "")
        if not unique_id.startswith(f"{entry.entry_id}_heima_"):
            continue
        if ".heima_" not in reg_entry.entity_id:
            continue
        expected_entity_id = expected.get(unique_id)
        if expected_entity_id is None:
            stale_entity_ids.append(reg_entry.entity_id)
        elif reg_entry.entity_id != expected_entity_id:
            rename_pairs.append((reg_entry.entity_id, expected_entity_id))

    for entity_id in stale_entity_ids:
        _LOGGER.debug("Removing stale Heima entity from registry: %s", entity_id)
        registry.async_remove(entity_id)

    for current_entity_id, expected_entity_id in rename_pairs:
        _LOGGER.debug(
            "Renaming Heima entity in registry: %s -> %s",
            current_entity_id,
            expected_entity_id,
        )
        registry.async_update_entity(current_entity_id, new_entity_id=expected_entity_id)


def _expected_entity_index(entry: ConfigEntry) -> dict[str, str]:
    """Return expected canonical entity ids keyed by unique_id for the current entry."""
    registry = build_registry(entry)
    expected: dict[str, str] = {}

    for desc in registry.sensors:
        key = desc.key if desc.key.startswith("heima_") else f"heima_{desc.key}"
        expected[f"{entry.entry_id}_{key}"] = f"sensor.{key}"

    for desc in registry.binary_sensors:
        key = desc.key if desc.key.startswith("heima_") else f"heima_{desc.key}"
        expected[f"{entry.entry_id}_{key}"] = f"binary_sensor.{key}"

    for desc in registry.selects:
        key = desc.key if desc.key.startswith("heima_") else f"heima_{desc.key}"
        expected[f"{entry.entry_id}_{key}"] = f"select.{key}"

    return expected
