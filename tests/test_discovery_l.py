from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.heima.config_flow import HeimaOptionsFlowHandler
from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.discovery import discover_binding_candidates


class _FakeStates:
    def __init__(self, states: list[SimpleNamespace] | None = None) -> None:
        self._states = list(states or [])

    def async_all(self):
        return list(self._states)


class _FakeAreaRegistry:
    def __init__(self, areas: list[tuple[str, str]] | None = None) -> None:
        self.areas = {
            area_id: SimpleNamespace(id=area_id, name=name) for area_id, name in (areas or [])
        }

    def async_list_areas(self):
        return list(self.areas.values())


def _entry(entity_id: str, **attrs) -> SimpleNamespace:
    return SimpleNamespace(entity_id=entity_id, **attrs)


def _state(entity_id: str, **attributes) -> SimpleNamespace:
    return SimpleNamespace(entity_id=entity_id, attributes=attributes)


def _flow(options: dict | None = None) -> HeimaOptionsFlowHandler:
    flow = HeimaOptionsFlowHandler(SimpleNamespace(options=options or {}, entry_id="entry-1"))
    flow.hass = SimpleNamespace(
        data={},
        states=_FakeStates(),
        config=SimpleNamespace(language="en", time_zone="UTC"),
    )
    flow.context = {"user_id": "user-1"}
    return flow


def test_options_flow_localizes_discovery_choice_labels() -> None:
    flow = _flow({"language": "it"})

    labels = flow._localized_labels(
        {
            "en": {"accept_non_ambiguous": "Accept non-ambiguous"},
            "it": {"accept_non_ambiguous": "Accetta non ambigue"},
        }
    )

    assert labels["accept_non_ambiguous"] == "Accetta non ambigue"


def test_discovery_maps_device_classes_to_grouped_candidates() -> None:
    report = discover_binding_candidates(
        entity_entries=[
            _entry("binary_sensor.kitchen_motion", device_class="motion", area_id="kitchen"),
            _entry("binary_sensor.front_door", device_class="door", area_id="entry"),
            _entry("sensor.washer_power", device_class="power", area_id="utility"),
            _entry("sensor.bath_humidity", device_class="humidity", area_id="bathroom"),
            _entry("media_player.living_tv", area_id="living"),
        ],
        area_entries={
            "kitchen": SimpleNamespace(id="kitchen", name="Kitchen"),
            "entry": SimpleNamespace(id="entry", name="Entry"),
            "utility": SimpleNamespace(id="utility", name="Utility"),
            "bathroom": SimpleNamespace(id="bathroom", name="Bathroom"),
            "living": SimpleNamespace(id="living", name="Living"),
        },
    )

    by_binding = {candidate.suggested_binding: candidate for candidate in report.candidates}
    assert by_binding["room_occupancy_source"].reason
    assert by_binding["security_contact"].category == "security"
    assert by_binding["activity_power_candidate"].ambiguous is True
    assert by_binding["activity_power_candidate"].reason.startswith("Power/energy")
    assert by_binding["activity_shower_humidity"].ambiguous is False
    assert by_binding["activity_media_candidate"].ambiguous is True


@pytest.mark.asyncio
async def test_coordinator_async_discover_entities_reads_ha_registries(monkeypatch) -> None:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.hass = SimpleNamespace(states=_FakeStates([_state("sensor.washer_power")]))
    entity_registry = SimpleNamespace(
        entities={
            "1": _entry("sensor.washer_power", device_class="power", area_id="utility"),
        }
    )
    device_registry = SimpleNamespace(devices={})
    area_registry = _FakeAreaRegistry([("utility", "Utility")])
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get", lambda _hass: entity_registry
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get", lambda _hass: device_registry
    )
    monkeypatch.setattr(
        "homeassistant.helpers.area_registry.async_get", lambda _hass: area_registry
    )

    report = await coordinator.async_discover_entities()

    assert len(report.candidates) == 1
    assert report.candidates[0].suggested_binding == "activity_power_candidate"
    assert report.candidates[0].area_name == "Utility"


@pytest.mark.asyncio
async def test_options_flow_discovery_shows_reasons_and_accepts_non_ambiguous(
    monkeypatch,
) -> None:
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "bathroom",
                    "display_name": "Bathroom",
                    "area_id": "bathroom",
                    "occupancy_sources": [],
                    "learning_sources": [],
                }
            ]
        }
    )
    entity_registry = SimpleNamespace(
        entities={
            "motion": _entry(
                "binary_sensor.bath_motion", device_class="motion", area_id="bathroom"
            ),
            "humidity": _entry("sensor.bath_humidity", device_class="humidity", area_id="bathroom"),
            "power": _entry("sensor.washer_power", device_class="power", area_id="utility"),
        }
    )
    device_registry = SimpleNamespace(devices={})
    area_registry = _FakeAreaRegistry([("bathroom", "Bathroom"), ("utility", "Utility")])
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get", lambda _hass: entity_registry
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get", lambda _hass: device_registry
    )
    monkeypatch.setattr(
        "homeassistant.helpers.area_registry.async_get", lambda _hass: area_registry
    )

    shown = await flow.async_step_discovery()

    assert shown["type"] == "form"
    placeholders = shown["description_placeholders"]
    assert "Power/energy sensors may indicate appliance activity" in placeholders["suggestions"]
    assert "Binary sensor device_class 'motion'" in placeholders["suggestions"]

    result = await flow.async_step_discovery({"action": "accept_non_ambiguous"})

    assert result["type"] == "menu"
    room = flow.options["rooms"][0]
    assert room["occupancy_sources"] == ["binary_sensor.bath_motion"]
    assert flow.options["activity_bindings"]["shower_running"]["bathroom_humidity_entity"] == (
        "sensor.bath_humidity"
    )
    accepted = set(flow.options["discovery"]["accepted_candidate_ids"])
    assert "room_occupancy_source:binary_sensor.bath_motion" in accepted
    assert "activity_shower_humidity:sensor.bath_humidity" in accepted
    assert "activity_power_candidate:sensor.washer_power" not in accepted


@pytest.mark.asyncio
async def test_options_flow_discovery_accept_all_records_ambiguous_without_mutation(
    monkeypatch,
) -> None:
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "bathroom",
                    "display_name": "Bathroom",
                    "area_id": "bathroom",
                    "occupancy_sources": [],
                    "learning_sources": [],
                }
            ]
        }
    )
    entity_registry = SimpleNamespace(
        entities={
            "motion": _entry(
                "binary_sensor.bath_motion", device_class="motion", area_id="bathroom"
            ),
            "power": _entry("sensor.washer_power", device_class="power", area_id="utility"),
        }
    )
    device_registry = SimpleNamespace(devices={})
    area_registry = _FakeAreaRegistry([("bathroom", "Bathroom"), ("utility", "Utility")])
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get", lambda _hass: entity_registry
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get", lambda _hass: device_registry
    )
    monkeypatch.setattr(
        "homeassistant.helpers.area_registry.async_get", lambda _hass: area_registry
    )

    result = await flow.async_step_discovery({"action": "accept_all"})

    assert result["type"] == "menu"
    assert flow.options["rooms"][0]["occupancy_sources"] == ["binary_sensor.bath_motion"]
    assert "activity_bindings" not in flow.options
    accepted = set(flow.options["discovery"]["accepted_candidate_ids"])
    assert "room_occupancy_source:binary_sensor.bath_motion" in accepted
    assert "activity_power_candidate:sensor.washer_power" in accepted
