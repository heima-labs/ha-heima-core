"""Tests for AU4's coordinator-level actuator registry admin-editor entry points."""

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
        "room_openings": [{"opening_id": "op1", "room_id": "kitchen", "type": "window"}],
        "room_connections": [],
        "room_actuators": [],
    }


async def test_upsert_actuator_persists_and_generates_id():
    coordinator = _coordinator(_base_options())

    applied, issues = await coordinator.async_upsert_actuator(
        actuator_id=None,
        entity_id="cover.kitchen_shutter",
        room_id="kitchen",
    )

    assert applied is True
    assert issues == ()
    actuators = coordinator.entry.options["room_actuators"]
    assert len(actuators) == 1
    assert actuators[0]["entity_id"] == "cover.kitchen_shutter"
    assert actuators[0]["actuator_id"]


async def test_upsert_actuator_with_existing_id_edits_in_place():
    options = _base_options()
    options["room_actuators"] = [
        {
            "actuator_id": "a1",
            "entity_id": "cover.old",
            "room_id": "kitchen",
            "opening_id": None,
            "display_name": None,
        }
    ]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_upsert_actuator(
        actuator_id="a1",
        entity_id="cover.new",
        room_id="kitchen",
        opening_id="op1",
        display_name="Kitchen shutter",
    )

    assert applied is True
    assert issues == ()
    actuators = coordinator.entry.options["room_actuators"]
    assert len(actuators) == 1
    assert actuators[0] == {
        "actuator_id": "a1",
        "entity_id": "cover.new",
        "room_id": "kitchen",
        "opening_id": "op1",
        "display_name": "Kitchen shutter",
    }


async def test_upsert_actuator_rejects_opening_in_different_room():
    options = _base_options()
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_upsert_actuator(
        actuator_id=None,
        entity_id="cover.x",
        room_id="garage",
        opening_id="op1",
    )

    assert applied is False
    assert any(issue["key"].endswith(".opening_room_mismatch") for issue in issues)
    assert coordinator.entry.options["room_actuators"] == []


async def test_delete_actuator_persists():
    options = _base_options()
    options["room_actuators"] = [
        {
            "actuator_id": "a1",
            "entity_id": "cover.x",
            "room_id": "kitchen",
            "opening_id": None,
            "display_name": None,
        }
    ]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_delete_actuator(actuator_id="a1")

    assert applied is True
    assert issues == ()
    assert coordinator.entry.options["room_actuators"] == []


async def test_delete_room_opening_blocked_while_referenced_by_actuator():
    options = _base_options()
    options["room_actuators"] = [
        {
            "actuator_id": "a1",
            "entity_id": "cover.x",
            "room_id": "kitchen",
            "opening_id": "op1",
            "display_name": None,
        }
    ]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_delete_room_opening(opening_id="op1")

    assert applied is False
    assert any(issue["key"] == "topology.opening.op1.referenced_by_actuator" for issue in issues)
    # Unchanged: still one opening.
    assert len(coordinator.entry.options["room_openings"]) == 1


async def test_delete_room_opening_still_succeeds_when_not_referenced_by_actuator():
    # Regression guard for AU4's change to async_delete_room_opening: an unrelated Actuator
    # (different opening_id) must not block deletion.
    options = _base_options()
    options["room_openings"].append({"opening_id": "op2", "room_id": "kitchen", "type": "door"})
    options["room_actuators"] = [
        {
            "actuator_id": "a1",
            "entity_id": "cover.x",
            "room_id": "kitchen",
            "opening_id": "op2",
            "display_name": None,
        }
    ]
    coordinator = _coordinator(options)

    applied, issues = await coordinator.async_delete_room_opening(opening_id="op1")

    assert applied is True
    assert issues == ()
