"""Tests for AR4's room topology websocket API (heima/topology/snapshot, heima/topology/action)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.exceptions import Unauthorized

from custom_components.heima.const import DOMAIN
from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.runtime.observability import RuntimeObservabilityBuffer
from custom_components.heima.websocket_api import (
    WS_TYPE_TOPOLOGY_ACTION,
    WS_TYPE_TOPOLOGY_SNAPSHOT,
    websocket_topology_action,
    websocket_topology_snapshot,
)


class _FakeConnection:
    def __init__(self, *, is_admin: bool) -> None:
        self.user = SimpleNamespace(is_admin=is_admin)
        self.results: list[tuple[int, Any]] = []
        self.errors: list[tuple[int, str, str]] = []

    def send_result(self, msg_id: int, result: Any | None = None) -> None:
        self.results.append((msg_id, result))

    def send_error(self, msg_id: int, code: str, message: str, *args: Any) -> None:
        self.errors.append((msg_id, code, message))


class _FakeHass:
    def __init__(self, coordinator: Any | None = None) -> None:
        self.tasks: list[asyncio.Task[Any]] = []
        self.data = (
            {DOMAIN: {"entry-1": {"coordinator": coordinator}}} if coordinator else {DOMAIN: {}}
        )

    def async_create_task(self, task: Any) -> asyncio.Task[Any]:
        created = asyncio.create_task(task)
        self.tasks.append(created)
        return created

    async def drain(self) -> None:
        if self.tasks:
            await asyncio.gather(*self.tasks)


class _FakeConfigEntries:
    def async_update_entry(self, entry, *, options):
        entry.options = dict(options)


def _base_options() -> dict:
    return {
        "rooms": [
            {"room_id": "kitchen", "room_type": "indoor"},
            {"room_id": "garage", "room_type": "garage"},
        ],
        "room_openings": [{"opening_id": "op1", "room_id": "kitchen", "type": "door"}],
        "room_connections": [],
    }


def _coordinator(options: dict | None = None) -> HeimaCoordinator:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(
        entry_id="entry-1", options=dict(options or _base_options())
    )
    coordinator.hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    coordinator.engine = SimpleNamespace(_observability=RuntimeObservabilityBuffer())
    return coordinator


def test_topology_snapshot_requires_admin():
    hass = _FakeHass(_coordinator())
    connection = _FakeConnection(is_admin=False)

    with pytest.raises(Unauthorized):
        websocket_topology_snapshot(
            hass, connection, {"id": 1, "type": WS_TYPE_TOPOLOGY_SNAPSHOT, "entry_id": "entry-1"}
        )


def test_topology_snapshot_returns_rooms_openings_connections():
    hass = _FakeHass(_coordinator())
    connection = _FakeConnection(is_admin=True)

    websocket_topology_snapshot(
        hass, connection, {"id": 1, "type": WS_TYPE_TOPOLOGY_SNAPSHOT, "entry_id": "entry-1"}
    )

    assert connection.errors == []
    result = connection.results[0][1]
    assert {room["room_id"] for room in result["rooms"]} == {"kitchen", "garage"}
    assert len(result["openings"]) == 1
    assert result["connections"] == []
    assert isinstance(result["issues"], list)


async def test_topology_action_requires_admin():
    hass = _FakeHass(_coordinator())
    connection = _FakeConnection(is_admin=False)

    with pytest.raises(Unauthorized):
        websocket_topology_action(
            hass,
            connection,
            {
                "id": 1,
                "type": WS_TYPE_TOPOLOGY_ACTION,
                "entry_id": "entry-1",
                "action": "delete_opening",
                "payload": {"opening_id": "op1"},
            },
        )

    assert connection.results == []
    assert connection.errors == []


async def test_topology_action_rejects_missing_required_payload_field():
    hass = _FakeHass(_coordinator())
    connection = _FakeConnection(is_admin=True)

    websocket_topology_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_TOPOLOGY_ACTION,
            "entry_id": "entry-1",
            "action": "upsert_opening",
            "payload": {"room_id": "kitchen"},  # missing "type"
        },
    )
    await hass.drain()

    assert connection.results == []
    assert connection.errors[0][1] == "invalid_payload"


async def test_topology_action_upsert_connection_returns_audited_snapshot():
    coordinator = _coordinator()
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    websocket_topology_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_TOPOLOGY_ACTION,
            "entry_id": "entry-1",
            "action": "upsert_connection",
            "payload": {"connection_id": "c1", "opening_id": "op1", "room_b": "garage"},
        },
    )
    await hass.drain()

    assert connection.errors == []
    result = connection.results[0][1]
    assert result["ok"] is True
    assert result["action"] == "upsert_connection"
    assert len(result["snapshot"]["connections"]) == 1
    assert result["snapshot"]["connections"][0]["connection_type"] == "separate"
    assert coordinator.entry.options["room_connections"] == [
        {
            "connection_id": "c1",
            "opening_id": "op1",
            "room_b": "garage",
            "access_type": "direct",
            "connection_type_override": None,
        }
    ]
    events = coordinator.engine._observability.diagnostics()["recent_events"]
    assert events[0]["category"] == "admin_action"
    assert events[0]["reason_code"] == "room_topology.upsert_connection"


async def test_topology_action_validation_failure_returns_validation_failed_error():
    options = _base_options()
    options["room_openings"].append({"opening_id": "op2", "room_id": "kitchen", "type": "door"})
    coordinator = _coordinator(options)
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    # First connection binds op1 to garage (separate); a conflicting shared entity_id across
    # op1/op2 with different connection_type would be rejected — simpler here: reference a
    # room_b that does not exist, which validate_topology flags as an error.
    websocket_topology_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_TOPOLOGY_ACTION,
            "entry_id": "entry-1",
            "action": "upsert_connection",
            "payload": {"connection_id": "c1", "opening_id": "op1", "room_b": "does_not_exist"},
        },
    )
    await hass.drain()

    assert connection.results == []
    assert connection.errors[0][1] == "validation_failed"
    assert coordinator.entry.options["room_connections"] == []
