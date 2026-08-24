"""End-to-end tests for the room topology admin editor, through a real Home Assistant core
instance (pytest-homeassistant-custom-component), not hand-built fakes.

These exist specifically to catch what tests/test_room_topology_websocket.py and
tests/test_room_topology_coordinator.py structurally cannot: real websocket schema
validation/dispatch, real config entry reload behavior (hass.config_entries.async_reload vs.
async_update_entry), and whether the admin panel actually survives that reload — the exact class
of bug reported and fixed in this session (panel vanishing after a "rooms" structural reload,
and that reload being heavier than necessary for topology-only field edits).
"""

from __future__ import annotations

import asyncio

import pytest
from aiohttp.resolver import AsyncResolver
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.heima.const import DOMAIN


@pytest.fixture(scope="module", autouse=True)
def _warm_up_aiohttp_dns_resolver_thread():
    """aiohttp's default async DNS resolver (pycares) lazily spawns a background thread on
    its first use. Every test below opens a real HTTP/websocket connection via hass_ws_client,
    and whichever one runs first in the session pays that one-time cost — the test harness's
    per-test thread-leak check (pytest_homeassistant_custom_component's verify_cleanup) then
    flags it as a "new" thread leaked by that test, even though it's a process-wide first-use
    cost, not a real per-test leak. Force it here, once per module, before any test's
    before/after thread snapshot is taken, so every test in this file sees it as pre-existing.
    """

    async def _warm_up() -> None:
        resolver = AsyncResolver()
        try:
            await resolver.resolve("localhost")
        except Exception:
            pass
        finally:
            await resolver.close()

    asyncio.run(_warm_up())
    yield


def _entry(rooms: list[dict]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Heima",
        data={},
        options={"rooms": rooms, "room_openings": [], "room_connections": []},
    )


def _coordinator(hass: HomeAssistant, entry_id: str):
    return hass.data[DOMAIN][entry_id]["coordinator"]


async def test_e2e_topology_snapshot_and_action_round_trip_via_real_websocket(
    hass: HomeAssistant,
    enable_custom_integrations,
    hass_ws_client,
):
    entry = _entry(
        [
            {"room_id": "kitchen", "room_type": "indoor"},
            {"room_id": "garage", "room_type": "garage"},
        ]
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "heima/topology/snapshot"})
    response = await client.receive_json()
    assert response["success"] is True
    assert {room["room_id"] for room in response["result"]["rooms"]} == {"kitchen", "garage"}
    assert response["result"]["openings"] == []

    await client.send_json_auto_id(
        {
            "type": "heima/topology/action",
            "action": "upsert_opening",
            "payload": {"room_id": "kitchen", "type": "door", "opening_id": "op1"},
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["ok"] is True
    assert len(response["result"]["snapshot"]["openings"]) == 1

    await client.send_json_auto_id(
        {
            "type": "heima/topology/action",
            "action": "upsert_connection",
            "payload": {"opening_id": "op1", "room_b": "garage", "connection_id": "c1"},
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["snapshot"]["connections"][0]["connection_type"] == "separate"

    entry_options = hass.config_entries.async_get_entry(entry.entry_id).options
    assert len(entry_options["room_openings"]) == 1
    assert len(entry_options["room_connections"]) == 1
    await client.close()
    await client.client.close()


async def test_e2e_topology_action_validation_failure_over_real_websocket(
    hass: HomeAssistant,
    enable_custom_integrations,
    hass_ws_client,
):
    entry = _entry([{"room_id": "kitchen", "room_type": "indoor"}])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client()

    await client.send_json_auto_id(
        {
            "type": "heima/topology/action",
            "action": "upsert_connection",
            "payload": {"opening_id": "does_not_exist", "room_b": "kitchen"},
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    # AR1's validation core rejects the dangling opening_id reference; the websocket layer
    # surfaces it as validation_failed (not a generic not_found), with the issue description.
    assert response["error"]["code"] == "validation_failed"
    assert "does_not_exist" in response["error"]["message"]

    entry_options = hass.config_entries.async_get_entry(entry.entry_id).options
    assert entry_options["room_connections"] == []

    await client.close()
    await client.client.close()


async def test_e2e_topology_action_rejected_for_non_admin_user(
    hass: HomeAssistant,
    enable_custom_integrations,
    hass_ws_client,
    hass_read_only_access_token,
):
    entry = _entry([{"room_id": "kitchen", "room_type": "indoor"}])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(access_token=hass_read_only_access_token)

    await client.send_json_auto_id(
        {
            "type": "heima/topology/action",
            "action": "delete_opening",
            "payload": {"opening_id": "op1"},
        }
    )
    response = await client.receive_json()
    assert response["success"] is False

    await client.send_json_auto_id({"type": "heima/topology/snapshot"})
    response = await client.receive_json()
    assert response["success"] is False


async def test_e2e_room_type_edit_keeps_same_coordinator_and_panel_registered(
    hass: HomeAssistant,
    enable_custom_integrations,
    hass_ws_client,
):
    entry = _entry(
        [
            {"room_id": "kitchen", "room_type": "indoor", "area_id": "area.kitchen"},
        ]
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator_before = _coordinator(hass, entry.entry_id)
    assert hass.data[DOMAIN].get("admin_panel_registered") is True

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "heima/topology/action",
            "action": "set_room_fields",
            "payload": {"room_id": "kitchen", "room_type": "garage"},
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    await hass.async_block_till_done()

    # Light reload path: same coordinator instance, no full entry teardown/rebuild.
    assert _coordinator(hass, entry.entry_id) is coordinator_before
    assert hass.data[DOMAIN].get("admin_panel_registered") is True
    assert hass.config_entries.async_get_entry(entry.entry_id).options["rooms"][0]["room_type"] == (
        "garage"
    )


async def test_e2e_room_area_id_change_triggers_full_reload_but_panel_survives(
    hass: HomeAssistant,
    enable_custom_integrations,
):
    # Reproduces the exact reported bug end-to-end: a genuinely structural "rooms" change
    # (area_id rebinding, not exposed through AR4's action set — done directly, as the
    # Options Flow room editor would) must still trigger a full entry reload, and the admin
    # panel must still be registered afterward (previously it silently vanished until a full
    # HA restart).
    entry = _entry([{"room_id": "kitchen", "room_type": "indoor", "area_id": "area.kitchen"}])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator_before = _coordinator(hass, entry.entry_id)
    assert hass.data[DOMAIN].get("admin_panel_registered") is True

    new_options = dict(entry.options)
    new_options["rooms"] = [{"room_id": "kitchen", "room_type": "indoor", "area_id": "area.other"}]
    hass.config_entries.async_update_entry(entry, options=new_options)
    await hass.async_block_till_done()

    # Full reload path: a brand new coordinator instance was constructed.
    assert _coordinator(hass, entry.entry_id) is not coordinator_before
    # The regression this session fixed: the panel must survive the reload.
    assert hass.data[DOMAIN].get("admin_panel_registered") is True
