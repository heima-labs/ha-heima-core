"""Tests for AR4's coordinator-level room topology admin-editor entry points."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.coordinator import HeimaCoordinator


class _FakeConfigEntries:
    def async_update_entry(self, entry, *, options):
        entry.options = dict(options)


def _coordinator(options: dict) -> HeimaCoordinator:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(options=dict(options))
    coordinator.hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    return coordinator


def _base_options() -> dict:
    return {
        "rooms": [
            {"room_id": "kitchen", "room_type": "indoor"},
            {"room_id": "garage", "room_type": "garage"},
        ],
        "room_openings": [],
        "room_connections": [],
    }


async def test_set_room_topology_fields_updates_existing_room():
    coordinator = _coordinator(_base_options())

    applied, issues = await coordinator.async_set_room_topology_fields(
        room_id="kitchen", room_type="balcony", floor=2
    )

    assert applied is True
    assert issues == ()
    room = coordinator.entry.options["rooms"][0]
    assert room["room_type"] == "balcony"
    assert room["floor"] == 2


async def test_set_room_topology_fields_rejects_unknown_room():
    coordinator = _coordinator(_base_options())

    applied, issues = await coordinator.async_set_room_topology_fields(room_id="missing")

    assert applied is False
    assert issues == ()
    assert coordinator.entry.options == _base_options()


async def test_upsert_room_opening_persists_and_generates_id():
    coordinator = _coordinator(_base_options())

    applied, issues = await coordinator.async_upsert_room_opening(
        opening_id=None,
        room_id="kitchen",
        opening_type="door",
    )

    assert applied is True
    assert issues == ()
    openings = coordinator.entry.options["room_openings"]
    assert len(openings) == 1
    assert openings[0]["room_id"] == "kitchen"
    assert openings[0]["opening_id"]


async def test_upsert_room_connection_persists():
    options = _base_options()
    options["room_openings"] = [{"opening_id": "op1", "room_id": "kitchen", "type": "door"}]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_upsert_room_connection(
        connection_id="c1",
        opening_id="op1",
        room_b="garage",
    )

    assert applied is True
    assert issues == ()
    connections = coordinator.entry.options["room_connections"]
    assert connections == [
        {
            "connection_id": "c1",
            "opening_id": "op1",
            "room_b": "garage",
            "access_type": "direct",
            "connection_type_override": None,
        }
    ]


async def test_upsert_room_opening_with_existing_id_edits_in_place():
    # The admin panel's "Edit" button re-submits upsert_opening with the row's existing
    # opening_id: this must replace that record, not append a second one alongside it.
    options = _base_options()
    options["room_openings"] = [
        {"opening_id": "op1", "room_id": "kitchen", "type": "door", "orientation": "north"}
    ]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_upsert_room_opening(
        opening_id="op1",
        room_id="kitchen",
        opening_type="window",
        orientation="south",
    )

    assert applied is True
    assert issues == ()
    openings = coordinator.entry.options["room_openings"]
    assert len(openings) == 1
    assert openings[0] == {
        "opening_id": "op1",
        "room_id": "kitchen",
        "type": "window",
        "orientation": "south",
        "entity_id": None,
    }


async def test_upsert_room_connection_with_existing_id_edits_in_place():
    options = _base_options()
    options["room_openings"] = [{"opening_id": "op1", "room_id": "kitchen", "type": "door"}]
    options["room_connections"] = [
        {
            "connection_id": "c1",
            "opening_id": "op1",
            "room_b": "garage",
            "access_type": "direct",
            "connection_type_override": None,
        }
    ]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_upsert_room_connection(
        connection_id="c1",
        opening_id="op1",
        room_b="garage",
        access_type="stairs",
    )

    assert applied is True
    assert issues == ()
    connections = coordinator.entry.options["room_connections"]
    assert len(connections) == 1
    assert connections[0]["access_type"] == "stairs"


async def test_upsert_room_connection_rejects_conflicting_shared_entity():
    options = {
        "rooms": [
            {"room_id": "living_room", "room_type": "indoor"},
            {"room_id": "hallway", "room_type": "indoor"},
            {"room_id": "garage", "room_type": "garage"},
        ],
        "room_openings": [
            {
                "opening_id": "op1",
                "room_id": "living_room",
                "type": "door",
                "entity_id": "binary_sensor.shared",
            },
            {
                "opening_id": "op2",
                "room_id": "hallway",
                "type": "door",
                "entity_id": "binary_sensor.shared",
            },
        ],
        "room_connections": [
            {"connection_id": "c1", "opening_id": "op1", "room_b": "garage"},
        ],
    }
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_upsert_room_connection(
        connection_id="c2",
        opening_id="op2",
        room_b="living_room",
    )

    assert applied is False
    assert any(
        issue["key"] == "topology.entity.binary_sensor.shared.shared_conflict" for issue in issues
    )
    # Rejected mutation must not have been persisted.
    assert len(coordinator.entry.options["room_connections"]) == 1


async def test_delete_room_opening_persists():
    options = _base_options()
    options["room_openings"] = [{"opening_id": "op1", "room_id": "kitchen", "type": "door"}]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_delete_room_opening(opening_id="op1")

    assert applied is True
    assert issues == ()
    assert coordinator.entry.options["room_openings"] == []


async def test_delete_room_opening_blocked_while_referenced_by_connection():
    options = _base_options()
    options["room_openings"] = [{"opening_id": "op1", "room_id": "kitchen", "type": "door"}]
    options["room_connections"] = [{"connection_id": "c1", "opening_id": "op1", "room_b": "garage"}]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_delete_room_opening(opening_id="op1")

    assert applied is False
    assert any(issue["key"] == "topology.connection.c1.dangling_opening" for issue in issues)
    # Unchanged: still one opening.
    assert len(coordinator.entry.options["room_openings"]) == 1


async def test_delete_room_connection_persists():
    options = _base_options()
    options["room_openings"] = [{"opening_id": "op1", "room_id": "kitchen", "type": "door"}]
    options["room_connections"] = [{"connection_id": "c1", "opening_id": "op1", "room_b": "garage"}]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_delete_room_connection(connection_id="c1")

    assert applied is True
    assert issues == ()
    assert coordinator.entry.options["room_connections"] == []
