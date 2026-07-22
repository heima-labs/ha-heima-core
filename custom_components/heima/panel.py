"""Home Assistant admin panel registration for Heima."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

PANEL_URL_PATH = "heima-observability"
PANEL_WEBCOMPONENT = "heima-admin-panel"
PANEL_STATIC_URL = "/heima_static"

_PANEL_ASSET_DIR = Path(__file__).parent / "frontend"
_PANEL_ASSET_FILE = _PANEL_ASSET_DIR / "heima-admin-panel.js"


def _panel_asset_version() -> str:
    try:
        return hashlib.sha256(_PANEL_ASSET_FILE.read_bytes()).hexdigest()[:12]
    except OSError:
        return "dev"


PANEL_MODULE_BASE = f"{PANEL_STATIC_URL}/{_PANEL_ASSET_FILE.name}"
PANEL_MODULE = f"{PANEL_MODULE_BASE}?v={_panel_asset_version()}"


async def async_register_admin_panel(hass: HomeAssistant) -> None:
    """Register the Heima custom admin panel."""
    http = getattr(hass, "http", None)
    register_static_paths = getattr(http, "async_register_static_paths", None)
    if not callable(register_static_paths):
        return

    await register_static_paths(
        [StaticPathConfig(PANEL_STATIC_URL, str(_PANEL_ASSET_DIR), cache_headers=False)]
    )
    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_WEBCOMPONENT,
        sidebar_title="Heima Monitor",
        sidebar_icon="mdi:home-analytics",
        module_url=PANEL_MODULE,
        embed_iframe=False,
        require_admin=True,
        config={
            "snapshotCommand": "heima/observability/snapshot",
        },
    )


def async_unregister_admin_panel(hass: HomeAssistant) -> None:
    """Unregister the Heima custom admin panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
