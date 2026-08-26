"""Tests for the Heima admin panel registration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.heima import async_setup, async_setup_entry, async_unload_entry
from custom_components.heima.const import DOMAIN
from custom_components.heima.panel import (
    PANEL_MODULE,
    PANEL_MODULE_BASE,
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
            "config": {"snapshotCommand": "heima/observability/snapshot"},
        }
    ]
    assert PANEL_MODULE.startswith(f"{PANEL_MODULE_BASE}?v=")
    assert len(PANEL_MODULE.rsplit("?v=", 1)[1]) == 12


@pytest.mark.asyncio
async def test_register_admin_panel_noops_without_http(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_register_panel(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(
        "custom_components.heima.panel.panel_custom.async_register_panel",
        fake_register_panel,
    )
    hass = SimpleNamespace(http=None)

    await async_register_admin_panel(hass)

    assert calls == []


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


@pytest.mark.asyncio
async def test_async_setup_entry_reregisters_admin_panel_after_structural_reload(
    monkeypatch,
) -> None:
    # Regression test: hass.config_entries.async_reload (triggered by a structural options
    # change, e.g. editing a room's topology fields) calls async_unload_entry, which
    # unregisters the panel and clears admin_panel_registered — but only calls
    # async_setup_entry again, never the component-level async_setup that normally does the
    # (re-)registration. Without the guard in async_setup_entry, the panel stays gone from
    # the sidebar until a full HA restart.
    panel_calls = 0

    async def fake_panel(hass: Any) -> None:
        nonlocal panel_calls
        panel_calls += 1

    monkeypatch.setattr("custom_components.heima.async_register_admin_panel", fake_panel)

    class _FakeCoordinator:
        def __init__(self, hass: Any, entry: Any) -> None:
            self.hass = hass
            self.entry = entry

        async def async_initialize(self) -> None:
            return None

    monkeypatch.setattr("custom_components.heima.HeimaCoordinator", _FakeCoordinator)

    async def fake_cleanup(hass: Any, entry: Any) -> None:
        return None

    monkeypatch.setattr("custom_components.heima._async_cleanup_stale_entities", fake_cleanup)

    async def fake_forward_entry_setups(entry: Any, platforms: Any) -> bool:
        return True

    entry = SimpleNamespace(
        entry_id="entry-1",
        options={},
        async_on_unload=lambda callback: None,
        add_update_listener=lambda callback: lambda: None,
    )
    hass = SimpleNamespace(
        data={DOMAIN: {}},  # admin_panel_registered already cleared, as after unload
        states=SimpleNamespace(get=lambda entity_id: None),
        config_entries=SimpleNamespace(
            async_update_entry=lambda entry, options=None: None,
            async_forward_entry_setups=fake_forward_entry_setups,
        ),
    )

    result = await async_setup_entry(hass, entry)

    assert result is True
    assert panel_calls == 1
    assert hass.data[DOMAIN]["admin_panel_registered"] is True


def test_admin_panel_asset_declares_expected_webcomponent() -> None:
    asset = Path("custom_components/heima/frontend/heima-admin-panel.js")
    text = asset.read_text()

    assert 'customElements.define("heima-admin-panel", HeimaAdminPanel)' in text
    assert "heima/observability/snapshot" in text
    assert "callWS" in text
    assert "Reaction Inspector" in text
    assert "House State" in text
    assert "Search house-state candidates" in text
    assert "_houseStateCandidateRows" in text
    assert "Manual Hold Center" in text
    assert "Runtime Confirmation Center" in text
    assert "Notification Routing Inspector" in text
    assert "Learning Monitor" in text
    assert "Proposal Backlog Inspector" in text
    assert "Entity Impact" in text
    assert "Entity Detail" in text
    assert "Search entities" in text
    assert "heima/observability/action" in text
    assert "heima/observability/why_not_now" in text
    assert "Why not now?" in text
    assert "Why Not Now" in text
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
    assert "heima/topology/snapshot" in text
    assert "heima/topology/action" in text
    assert "data-details-id" in text
    # "Add opening"/"add connection" forms must persist their in-progress values via the
    # same data-filter-section mechanism as the search boxes, not plain uncontrolled inputs,
    # or an unrelated re-render (e.g. the 15s observability poll) silently resets them.
    assert 'data-filter-section="topology_new_opening"' in text
    assert 'data-filter-section="topology_new_connection"' in text
    # The Rooms table's inline room_type/floor editors have the identical problem (auto-save
    # on change, but a re-render before that change fires would otherwise discard whatever
    # wasn't saved yet) and must be protected the same way.
    assert 'data-filter-section="topology_room_field"' in text
    # The 15s observability poll must not fire (and force a full DOM replace, which forcibly
    # closes any open native <select>) while the admin is on the topology or actuators route,
    # since neither route renders observability data.
    assert 'if (this._route !== "topology" && this._route !== "actuators") {' in text
    # Openings/connections must be editable in place, not just delete-and-recreate: the same
    # add-form is reused, pre-filled with the existing record's id, so upsert_opening/
    # upsert_connection replace it instead of creating a new one.
    assert 'data-topology-action="edit_opening"' in text
    assert 'data-topology-action="edit_connection"' in text
    assert 'data-topology-action="cancel_edit_opening"' in text
    assert 'data-topology-action="cancel_edit_connection"' in text
    # room_type is not self-explanatory (garage vs. basement vs. external vs. outdoor all sound
    # similar); the admin editor must explain what each value means, not just offer the enum.
    assert "What do the room types mean?" in text
    # Actuator Registry (AU4): its own snapshot/action websocket commands, its own route with
    # the same poll-skip and in-progress-form persistence as Topology, edit-in-place from the
    # start (not delete-only like Topology's own opening/connection forms started with).
    assert "heima/actuators/snapshot" in text
    assert "heima/actuators/action" in text
    assert "Actuator Registry" in text
    assert 'filterSection: "actuators_new_actuator"' in text
    assert 'data-actuators-action="edit_actuator"' in text
    assert 'data-actuators-action="delete_actuator"' in text
    assert 'data-actuators-action="cancel_edit_actuator"' in text
    assert 'data-actuators-action="add_actuator"' in text
    # Edit appears inline, right below the clicked row (own _filters section,
    # actuators_edit_actuator, separate from the "add" form's actuators_new_actuator) — not in a
    # shared form at the bottom of the section, which required scrolling past a potentially long,
    # room-grouped actuator list to find.
    assert 'filterSection: "actuators_edit_actuator"' in text
    assert 'class="actuator-edit-row"' in text
    assert 'data-actuators-action="save_actuator_edit"' in text
    assert "_actuatorsFormFieldsHtml" in text
    # Opening entity_id must be an autocomplete field (datalist bound to the text input, not a
    # bare text box), populated from the topology snapshot's room-resolved entity_candidates.
    assert "topology-new-opening-entity-list" in text
    assert 'list="${entityListId}"' in text
    assert "_entityCandidateOptions" in text
    # The Connections table's Opening column must show a human-readable label (type/orientation/
    # entity_id), not the bare opening_id UUID, which has no inherent meaning to an admin.
    assert "_topologyConnectionRow(connection, openings)" in text
    assert "const opening = (openings || []).find(" in text
    assert 'title="${this._escape(connection.opening_id)}"' in text
    # Refocusing an input after a keystroke-triggered full re-render must not let the browser's
    # default scroll-into-view behavior fire against the freshly-rebuilt, not-yet-settled DOM —
    # that's what was scrolling the whole page to the top on every character typed.
    assert "input.focus({ preventScroll: true })" in text
    # preventScroll isn't honored by every browser, and a full shadow-DOM rebuild can also
    # trigger scroll adjustments unrelated to focus (e.g. scroll anchoring losing its reference
    # node). The panel must also force-restore the pre-render scroll position as a fallback.
    assert "this._scrollPosition = { x: window.scrollX, y: window.scrollY }" in text
    assert "window.scrollTo(this._scrollPosition.x, this._scrollPosition.y)" in text
    # Actuators Entity ID (AV3): a <select> of room-aware picker candidates when any exist,
    # with a "__manual__" escape-hatch option that reveals a free-text input — the admin must
    # still be able to register any entity_id, not just picker-covered ones.
    assert 'id="${idPrefix}-entity"' in text
    assert '<option value="__manual__"' in text
    assert 'id="${idPrefix}-entity-manual"' in text
    assert "hasEntityCandidates" in text
    # Actuators table is grouped by Room and collapsed by default (an installation can have a
    # large number of actuators, and a single flat table becomes unwieldy to scan). Persisted
    # open/closed state reuses the same data-details-id/_openDetailIds mechanism as the Topology
    # room-type legend.
    assert "_actuatorsGroupedByRoom" in text
    assert 'class="actuator-room-group"' in text
    assert 'data-details-id="${this._escape(key)}"' in text
    assert "<strong>external</strong>" in text
    assert "<strong>outdoor</strong>" in text
    assert "<strong>indoor</strong>" in text
