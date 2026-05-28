"""Tests for Phase V signal discovery inventory classification."""

from __future__ import annotations

from custom_components.heima.runtime.signal_discovery import (
    HAEntityDescriptor,
    SignalDiscoveryAudit,
)


def _entity(
    entity_id: str,
    *,
    domain: str = "sensor",
    device_class: str | None = "illuminance",
    unit: str | None = None,
    area_name: str | None = "Studio",
) -> HAEntityDescriptor:
    return HAEntityDescriptor(
        entity_id=entity_id,
        domain=domain,
        device_class=device_class,
        unit_of_measurement=unit,
        area_id="area_studio" if area_name else None,
        area_name=area_name,
        current_state="on",
    )


def test_signal_discovery_classifies_illuminance_room_signal() -> None:
    suggestions = SignalDiscoveryAudit().run(
        [
            _entity(
                "sensor.studio_lux",
                device_class="illuminance",
                unit="lx",
            )
        ],
        [{"room_id": "studio"}],
    )

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.entity_id == "sensor.studio_lux"
    assert suggestion.room_id == "studio"
    assert suggestion.role == "room_signal"
    assert suggestion.signal_name == "room_lux"
    assert suggestion.device_class == "illuminance"
    assert suggestion.confidence == 0.95
    assert suggestion.identity_key == "signal_discovery:sensor.studio_lux"
    assert suggestion.suggestion_id
    assert suggestion.options_patch.room_id == "studio"
    assert suggestion.options_patch.role == "room_signal"
    assert suggestion.options_patch.payload == {
        "signal_name": "room_lux",
        "entity_id": "sensor.studio_lux",
        "device_class": "illuminance",
        "buckets": [
            {"label": "dark", "upper_bound": 30},
            {"label": "dim", "upper_bound": 100},
            {"label": "ok", "upper_bound": 300},
            {"label": "bright", "upper_bound": None},
        ],
    }
    assert "device_class=illuminance" in suggestion.evidence
    assert "unit=lx" in suggestion.evidence
    assert "matched room: studio (area: Studio)" in suggestion.evidence


def test_signal_discovery_classifies_co2_and_humidity_buckets() -> None:
    suggestions = SignalDiscoveryAudit().run(
        [
            _entity("sensor.bathroom_humidity", device_class="humidity", area_name="Bagno"),
            _entity("sensor.studio_co2", device_class="carbon_dioxide", area_name="Studio"),
        ],
        [{"room_id": "studio"}, {"room_id": "bagno"}],
    )

    by_signal = {suggestion.signal_name: suggestion for suggestion in suggestions}
    assert by_signal["room_co2"].options_patch.payload["buckets"] == [
        {"label": "ok", "upper_bound": 800},
        {"label": "elevated", "upper_bound": 1200},
        {"label": "high", "upper_bound": None},
    ]
    assert by_signal["room_humidity"].options_patch.payload["buckets"] == [
        {"label": "low", "upper_bound": 40},
        {"label": "ok", "upper_bound": 70},
        {"label": "high", "upper_bound": None},
    ]
    assert by_signal["room_humidity"].confidence == 0.90


def test_signal_discovery_classifies_media_player_as_learning_source() -> None:
    suggestions = SignalDiscoveryAudit().run(
        [
            _entity(
                "media_player.projector",
                domain="media_player",
                device_class=None,
                area_name="Living Room",
            )
        ],
        [{"room_id": "living_room"}],
    )

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.role == "learning_source"
    assert suggestion.signal_name is None
    assert suggestion.confidence == 0.80
    assert suggestion.options_patch.payload == {"entity_id": "media_player.projector"}
    assert "domain=media_player" in suggestion.evidence


def test_signal_discovery_uses_longest_room_match_and_skips_ties() -> None:
    matched = SignalDiscoveryAudit().run(
        [_entity("sensor.studio_lux", area_name="Studio")],
        [{"room_id": "studio"}, {"room_id": "studio_corner"}],
    )
    tied = SignalDiscoveryAudit().run(
        [_entity("sensor.lux", area_name="Studio")],
        [{"room_id": "north_studio"}, {"room_id": "south_studio"}],
    )

    assert matched[0].room_id == "studio_corner"
    assert tied == []


def test_signal_discovery_skips_unmapped_unsupported_and_existing_config() -> None:
    suggestions = SignalDiscoveryAudit().run(
        [
            _entity("sensor.unmapped_lux", area_name=None),
            _entity("sensor.temperature", device_class="temperature"),
            _entity("sensor.studio_lux", device_class="illuminance"),
            _entity("media_player.projector", domain="media_player", device_class=None),
        ],
        [
            {
                "room_id": "studio",
                "signals": [{"signal_name": "room_lux", "entity_id": "sensor.old_lux"}],
                "learning_sources": ["media_player.projector"],
            }
        ],
    )

    assert suggestions == []


def test_signal_discovery_limits_to_first_50_matches_by_entity_id() -> None:
    descriptors = [
        _entity(f"sensor.room_lux_{index:02d}", area_name=f"Room {index:02d}")
        for index in range(60)
    ]
    rooms = [{"room_id": f"room_{index:02d}"} for index in range(60)]

    suggestions = SignalDiscoveryAudit().run(descriptors, rooms)

    assert len(suggestions) == 50
    assert suggestions[0].entity_id == "sensor.room_lux_00"
    assert suggestions[-1].entity_id == "sensor.room_lux_49"
