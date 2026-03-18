"""The Heima integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS, STRUCTURAL_OPTION_KEYS
from .coordinator import HeimaCoordinator
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

    coordinator = HeimaCoordinator(hass=hass, entry=entry)
    await coordinator.async_initialize()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

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

    prev = coordinator.last_options_snapshot
    new = dict(entry.options)
    changed = {k for k in (prev.keys() | new.keys()) if prev.get(k) != new.get(k)}
    is_structural = bool(changed & STRUCTURAL_OPTION_KEYS)

    coordinator.last_options_snapshot = new

    if is_structural:
        _LOGGER.debug("Structural options changed (%s), reloading entry %s", changed & STRUCTURAL_OPTION_KEYS, entry.entry_id)
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        _LOGGER.debug("Runtime options changed (%s), reloading coordinator %s", changed, entry.entry_id)
        await coordinator.async_reload_options()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data and "coordinator" in data:
            coordinator: HeimaCoordinator = data["coordinator"]
            await coordinator.async_shutdown()
    return unload_ok
