"""Tests for the Heima admin panel registration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.heima import async_setup, async_unload_entry
from custom_components.heima.const import DOMAIN
from custom_components.heima.panel import (
    PANEL_MODULE,
    PANEL_STATIC_URL,
    PANEL_URL_PATH,
    PANEL_WEBCOMPONENT,
    async_register_admin_panel,
    async_unregister_admin_panel,
)


class _FakeHttp:
    def __init__(self) -> None:
        self.static_paths: list[Any] = []

    async def async_register_static_paths(self, paths: list[Any]) -> None:
        self.static_paths.extend(paths)


@pytest.mark.asyncio
async def test_register_admin_panel_serves_local_asset_and_requires_admin(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_register_panel(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(
        "custom_components.heima.panel.panel_custom.async_register_panel",
        fake_register_panel,
    )
    hass = SimpleNamespace(http=_FakeHttp())

    await async_register_admin_panel(hass)

    assert hass.http.static_paths[0].url_path == PANEL_STATIC_URL
    assert Path(hass.http.static_paths[0].path).name == "frontend"
    assert calls == [
        {
            "hass": hass,
            "frontend_url_path": PANEL_URL_PATH,
            "webcomponent_name": PANEL_WEBCOMPONENT,
            "sidebar_title": "Heima Monitor",
            "sidebar_icon": "mdi:home-analytics",
            "module_url": PANEL_MODULE,
            "embed_iframe": False,
            "require_admin": True,
            "config_panel_domain": DOMAIN,
            "config": {"snapshotCommand": "heima/observability/snapshot"},
        }
    ]


def test_unregister_admin_panel_removes_frontend_panel(monkeypatch) -> None:
    calls: list[tuple[Any, str, bool]] = []

    def fake_remove_panel(hass: Any, path: str, *, warn_if_unknown: bool) -> None:
        calls.append((hass, path, warn_if_unknown))

    monkeypatch.setattr(
        "custom_components.heima.panel.frontend.async_remove_panel",
        fake_remove_panel,
    )
    hass = SimpleNamespace()

    async_unregister_admin_panel(hass)

    assert calls == [(hass, PANEL_URL_PATH, False)]


@pytest.mark.asyncio
async def test_async_setup_registers_admin_panel_once(monkeypatch) -> None:
    service_calls = 0
    websocket_calls = 0
    panel_calls = 0

    async def fake_services(hass: Any) -> None:
        nonlocal service_calls
        service_calls += 1

    def fake_websocket(hass: Any) -> None:
        nonlocal websocket_calls
        websocket_calls += 1

    async def fake_panel(hass: Any) -> None:
        nonlocal panel_calls
        panel_calls += 1

    monkeypatch.setattr("custom_components.heima.async_register_services", fake_services)
    monkeypatch.setattr("custom_components.heima.async_register_websocket_api", fake_websocket)
    monkeypatch.setattr("custom_components.heima.async_register_admin_panel", fake_panel)

    hass = SimpleNamespace(data={})

    assert await async_setup(hass, {}) is True
    assert await async_setup(hass, {}) is True

    assert service_calls == 1
    assert websocket_calls == 1
    assert panel_calls == 1
    assert hass.data[DOMAIN]["admin_panel_registered"] is True


@pytest.mark.asyncio
async def test_unload_last_entry_unregisters_admin_panel(monkeypatch) -> None:
    unregister_calls = 0

    def fake_unregister(hass: Any) -> None:
        nonlocal unregister_calls
        unregister_calls += 1

    monkeypatch.setattr("custom_components.heima.async_unregister_admin_panel", fake_unregister)
    coordinator = SimpleNamespace(async_shutdown=lambda: None)

    async def async_shutdown() -> None:
        return None

    coordinator.async_shutdown = async_shutdown
    hass = SimpleNamespace(
        data={DOMAIN: {"entry-1": {"coordinator": coordinator}, "admin_panel_registered": True}},
        config_entries=SimpleNamespace(async_unload_platforms=lambda entry, platforms: True),
    )
    entry = SimpleNamespace(entry_id="entry-1")

    async def fake_unload_platforms(entry: Any, platforms: Any) -> bool:
        return True

    hass.config_entries.async_unload_platforms = fake_unload_platforms

    assert await async_unload_entry(hass, entry) is True
    assert unregister_calls == 1
    assert "admin_panel_registered" not in hass.data[DOMAIN]


def test_admin_panel_asset_declares_expected_webcomponent() -> None:
    asset = Path("custom_components/heima/frontend/heima-admin-panel.js")
    text = asset.read_text()

    assert 'customElements.define("heima-admin-panel", HeimaAdminPanel)' in text
    assert "heima/observability/snapshot" in text
    assert "callWS" in text
    assert "Reaction Inspector" in text
    assert "Manual Hold Center" in text
    assert "Runtime Confirmation Center" in text
    assert "Notification Routing Inspector" in text
    assert "Learning Monitor" in text
    assert "Proposal Backlog Inspector" in text
    assert "heima/observability/action" in text
    assert "clear_manual_hold" in text
    assert "review_runtime_promotion" in text
    assert "reset_runtime_confirmation_promotion_state" in text
    assert "review_proposal" in text
    assert "review_proposal_batch" in text
    assert "detail-panel" in text
    assert "data-detail-kind" in text
    assert "Reaction Detail" in text
    assert "Manual Hold Detail" in text
    assert "Runtime Confirmation Detail" in text
    assert "Proposal Review Detail" in text
    assert "object-id" in text
    assert "data-filter-section" in text
    assert "Search reactions" in text
    assert "data-copy-value" in text
    assert "navigator.clipboard.writeText" in text
    assert "URLSearchParams" in text
    assert "replaceState" in text
    assert 'data-export="copy"' in text
    assert 'data-export="download"' in text
    assert "_serializedSnapshot" in text
    assert "URL.createObjectURL" in text
    assert "heima-observability-" in text
