from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.runtime.normalization.service import InputNormalizer
from custom_components.heima.runtime.room_context import (
    RoomDeviceContext,
    RoomDeviceContextBuilder,
    deserialize_room_device_context,
    serialize_room_device_context,
)


class _FakeHass:
    def __init__(self, states: dict[str, str] | None = None) -> None:
        self.states = SimpleNamespace(get=lambda entity_id: _state(states or {}, entity_id))


def _state(states: dict[str, str], entity_id: str):
    if entity_id not in states:
        return None
    return SimpleNamespace(entity_id=entity_id, state=states[entity_id], attributes={})


def _patch_registries(monkeypatch, entity_entries: dict[str, object], devices=None) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.room_context.er.async_get",
        lambda _hass: SimpleNamespace(entities=entity_entries),
    )
    monkeypatch.setattr(
        "custom_components.heima.runtime.room_context.dr.async_get",
        lambda _hass: SimpleNamespace(devices=devices or {}),
    )


def test_room_device_context_round_trips_serialization() -> None:
    context = {"studio": RoomDeviceContext("studio", media_on=True, work_activity=True)}

    serialized = serialize_room_device_context(context)
    assert serialized["studio"]["media_on"] is True

    restored = deserialize_room_device_context(serialized)
    assert restored == context


def test_room_context_builder_maps_direct_entity_area(monkeypatch) -> None:
    _patch_registries(
        monkeypatch,
        {
            "media_player.projector": SimpleNamespace(
                entity_id="media_player.projector",
                area_id="living",
                device_id=None,
            )
        },
    )
    hass = _FakeHass({"media_player.projector": "playing"})
    builder = RoomDeviceContextBuilder(hass, InputNormalizer(hass))

    context = builder.compute(
        options={
            "rooms": [{"room_id": "living_room", "area_id": "living"}],
            "house_state_config": {"media_active_entities": ["media_player.projector"]},
        }
    )

    assert context["living_room"].media_on is True
    assert builder.entity_to_room == {"media_player.projector": "living_room"}


def test_room_context_builder_maps_device_area_fallback(monkeypatch) -> None:
    _patch_registries(
        monkeypatch,
        {
            "binary_sensor.mac_active": SimpleNamespace(
                entity_id="binary_sensor.mac_active",
                area_id="",
                device_id="dev-1",
            )
        },
        {"dev-1": SimpleNamespace(area_id="studio")},
    )
    hass = _FakeHass({"binary_sensor.mac_active": "on"})
    builder = RoomDeviceContextBuilder(hass, InputNormalizer(hass))

    context = builder.compute(
        options={
            "rooms": [{"room_id": "studio", "area_id": "studio"}],
            "house_state_config": {"work_activity_entities": ["binary_sensor.mac_active"]},
        }
    )

    assert context["studio"].work_activity is True


def test_room_context_builder_ignores_unmapped_entities(monkeypatch) -> None:
    _patch_registries(
        monkeypatch,
        {
            "media_player.projector": SimpleNamespace(
                entity_id="media_player.projector",
                area_id="living",
                device_id=None,
            )
        },
    )
    hass = _FakeHass({"media_player.projector": "playing"})
    builder = RoomDeviceContextBuilder(hass, InputNormalizer(hass))

    context = builder.compute(
        options={
            "rooms": [{"room_id": "studio", "area_id": "studio"}],
            "house_state_config": {"media_active_entities": ["media_player.projector"]},
        }
    )

    assert context == {}


def test_room_context_builder_aggregates_configured_roles(monkeypatch) -> None:
    _patch_registries(
        monkeypatch,
        {
            "media_player.monitor": SimpleNamespace(
                entity_id="media_player.monitor",
                area_id="studio",
                device_id=None,
            ),
            "binary_sensor.work": SimpleNamespace(
                entity_id="binary_sensor.work",
                area_id="studio",
                device_id=None,
            ),
            "sensor.pc_power": SimpleNamespace(
                entity_id="sensor.pc_power",
                area_id="studio",
                device_id=None,
            ),
            "light.studio": SimpleNamespace(
                entity_id="light.studio",
                area_id="studio",
                device_id=None,
            ),
        },
    )
    hass = _FakeHass(
        {
            "media_player.monitor": "playing",
            "binary_sensor.work": "on",
            "sensor.pc_power": "60",
            "light.studio": "on",
        }
    )
    builder = RoomDeviceContextBuilder(hass, InputNormalizer(hass))

    context = builder.compute(
        options={
            "rooms": [{"room_id": "studio", "area_id": "studio"}],
            "house_state_config": {
                "media_active_entities": ["media_player.monitor"],
                "work_activity_entities": ["binary_sensor.work"],
            },
            "activity_bindings": {"pc_active": {"entity_id": "sensor.pc_power"}},
        },
        lights_on={"light.studio": True},
    )

    assert context["studio"] == RoomDeviceContext(
        room_id="studio",
        media_on=True,
        lights_on=True,
        work_activity=True,
        pc_active=True,
    )


def test_room_context_builder_rebuilds_after_mark_stale(monkeypatch) -> None:
    entity = SimpleNamespace(entity_id="media_player.tv", area_id="living", device_id=None)
    _patch_registries(monkeypatch, {"media_player.tv": entity})
    hass = _FakeHass({"media_player.tv": "playing"})
    builder = RoomDeviceContextBuilder(hass, InputNormalizer(hass))
    options = {
        "rooms": [
            {"room_id": "living_room", "area_id": "living"},
            {"room_id": "studio", "area_id": "studio"},
        ],
        "house_state_config": {"media_active_entities": ["media_player.tv"]},
    }

    assert "living_room" in builder.compute(options=options)
    entity.area_id = "studio"
    assert "living_room" in builder.compute(options=options)

    builder.mark_stale()
    context = builder.compute(options=options)
    assert "studio" in context
    assert "living_room" not in context
