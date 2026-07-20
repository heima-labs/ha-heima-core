"""Home Assistant admin panel registration for Heima."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_URL_PATH = "heima-observability"
PANEL_WEBCOMPONENT = "heima-admin-panel"
PANEL_STATIC_URL = "/heima_static"
PANEL_MODULE = f"{PANEL_STATIC_URL}/heima-admin-panel.js"

_PANEL_ASSET_DIR = Path(__file__).parent / "frontend"


async def async_register_admin_panel(hass: HomeAssistant) -> None:
    """Register the Heima custom admin panel."""
    await hass.http.async_register_static_paths(
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
        config_panel_domain=DOMAIN,
        config={
            "snapshotCommand": "heima/observability/snapshot",
        },
    )


def async_unregister_admin_panel(hass: HomeAssistant) -> None:
    """Unregister the Heima custom admin panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
