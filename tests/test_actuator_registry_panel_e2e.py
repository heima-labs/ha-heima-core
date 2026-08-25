"""End-to-end tests for the actuator registry admin editor, through a real Home Assistant core
instance (pytest-homeassistant-custom-component), not hand-built fakes. Mirrors
tests/test_room_topology_panel_e2e.py's approach for AR4.
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
    """See tests/test_room_topology_panel_e2e.py's identical fixture for the full rationale:
    pre-warms aiohttp's DNS resolver thread once per module so it isn't flagged as a per-test
    thread leak by pytest_homeassistant_custom_component's verify_cleanup.
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


def _entry(rooms: list[dict], openings: list[dict] | None = None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Heima",
        data={},
        options={
            "rooms": rooms,
            "room_openings": openings or [],
            "room_connections": [],
            "room_actuators": [],
        },
    )


async def test_e2e_actuators_snapshot_and_action_round_trip_via_real_websocket(
    hass: HomeAssistant,
    enable_custom_integrations,
    hass_ws_client,
):
    entry = _entry(
        [{"room_id": "kitchen", "room_type": "indoor"}],
        [{"opening_id": "op1", "room_id": "kitchen", "type": "window"}],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "heima/actuators/snapshot"})
    response = await client.receive_json()
    assert response["success"] is True
    assert {room["room_id"] for room in response["result"]["rooms"]} == {"kitchen"}
    assert response["result"]["actuators"] == []

    await client.send_json_auto_id(
        {
            "type": "heima/actuators/action",
            "action": "upsert_actuator",
            "payload": {
                "actuator_id": "a1",
                "entity_id": "cover.kitchen_shutter",
                "room_id": "kitchen",
                "opening_id": "op1",
            },
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["ok"] is True
    assert len(response["result"]["snapshot"]["actuators"]) == 1

    await client.send_json_auto_id(
        {
            "type": "heima/actuators/action",
            "action": "delete_actuator",
            "payload": {"actuator_id": "a1"},
        }
    )
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["snapshot"]["actuators"] == []

    entry_options = hass.config_entries.async_get_entry(entry.entry_id).options
    assert entry_options["room_actuators"] == []
    await client.close()
    await client.client.close()


async def test_e2e_actuators_action_validation_failure_over_real_websocket(
    hass: HomeAssistant,
    enable_custom_integrations,
    hass_ws_client,
):
    entry = _entry(
        [{"room_id": "kitchen", "room_type": "indoor"}, {"room_id": "garage"}],
        [{"opening_id": "op1", "room_id": "kitchen", "type": "window"}],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client()

    await client.send_json_auto_id(
        {
            "type": "heima/actuators/action",
            "action": "upsert_actuator",
            "payload": {"entity_id": "cover.x", "room_id": "garage", "opening_id": "op1"},
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "validation_failed"

    entry_options = hass.config_entries.async_get_entry(entry.entry_id).options
    assert entry_options["room_actuators"] == []

    await client.close()
    await client.client.close()


async def test_e2e_actuators_action_rejected_for_non_admin_user(
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
            "type": "heima/actuators/action",
            "action": "delete_actuator",
            "payload": {"actuator_id": "a1"},
        }
    )
    response = await client.receive_json()
    assert response["success"] is False

    await client.send_json_auto_id({"type": "heima/actuators/snapshot"})
    response = await client.receive_json()
    assert response["success"] is False


async def test_e2e_delete_room_opening_blocked_when_referenced_by_actuator(
    hass: HomeAssistant,
    enable_custom_integrations,
    hass_ws_client,
):
    entry = _entry(
        [{"room_id": "kitchen", "room_type": "indoor"}],
        [{"opening_id": "op1", "room_id": "kitchen", "type": "window"}],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client()

    await client.send_json_auto_id(
        {
            "type": "heima/actuators/action",
            "action": "upsert_actuator",
            "payload": {
                "actuator_id": "a1",
                "entity_id": "cover.kitchen_shutter",
                "room_id": "kitchen",
                "opening_id": "op1",
            },
        }
    )
    response = await client.receive_json()
    assert response["success"] is True

    await client.send_json_auto_id(
        {
            "type": "heima/topology/action",
            "action": "delete_opening",
            "payload": {"opening_id": "op1"},
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "validation_failed"
    assert "referenced by an Actuator" in response["error"]["message"]

    entry_options = hass.config_entries.async_get_entry(entry.entry_id).options
    assert len(entry_options["room_openings"]) == 1
    await client.close()
    await client.client.close()
