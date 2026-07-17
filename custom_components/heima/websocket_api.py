"""Websocket API for Heima admin observability."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .observability import build_observability_snapshot

WS_TYPE_OBSERVABILITY_SNAPSHOT = "heima/observability/snapshot"


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register Heima websocket commands."""
    websocket_api.async_register_command(hass, websocket_observability_snapshot)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_OBSERVABILITY_SNAPSHOT,
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_observability_snapshot(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the read-only admin observability snapshot."""
    coordinator = _coordinator_for_message(hass, msg)
    if coordinator is None:
        connection.send_error(
            msg["id"],
            "not_found",
            "No active Heima config entry found for the requested observability snapshot.",
        )
        return
    connection.send_result(msg["id"], build_observability_snapshot(coordinator))


def _coordinator_for_message(hass: HomeAssistant, msg: dict[str, Any]) -> Any | None:
    domain_data = hass.data.get(DOMAIN, {})
    entry_id = str(msg.get("entry_id") or "").strip()
    if entry_id:
        data = domain_data.get(entry_id)
        return data.get("coordinator") if isinstance(data, dict) else None
    for data in domain_data.values():
        if isinstance(data, dict) and data.get("coordinator") is not None:
            return data["coordinator"]
    return None
