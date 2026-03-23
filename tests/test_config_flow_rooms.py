from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.config_flow import HeimaOptionsFlowHandler


def _flow(options: dict | None = None) -> HeimaOptionsFlowHandler:
    return HeimaOptionsFlowHandler(SimpleNamespace(options=options or {}))


def test_room_validation_allows_sources_empty_when_occupancy_mode_none():
    flow = _flow()
    payload = {
        "room_id": "soggiorno",
        "display_name": "Soggiorno",
        "area_id": "soggiorno",
        "occupancy_mode": "none",
        "occupancy_sources": [],
        "learning_sources": [],
        "logic": "any_of",
    }
    assert flow._validate_room_payload(payload, is_edit=False) == {}


def test_room_validation_requires_sources_when_occupancy_mode_derived():
    flow = _flow()
    payload = {
        "room_id": "studio",
        "display_name": "Studio",
        "area_id": "studio",
        "occupancy_mode": "derived",
        "occupancy_sources": [],
        "learning_sources": [],
        "logic": "any_of",
    }
    errors = flow._validate_room_payload(payload, is_edit=False)
    assert errors == {"occupancy_sources": "required"}


def test_finalize_options_backfills_empty_legacy_room_as_occupancy_none():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "soggiorno",
                    "display_name": "Soggiorno",
                    "area_id": "soggiorno",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                }
            ]
        }
    )

    finalized = flow._finalize_options()

    assert finalized["rooms"][0]["occupancy_mode"] == "none"


def test_room_normalization_parses_weighted_quorum_source_weights():
    flow = _flow()

    payload = flow._normalize_room_payload(
        {
            "room_id": "studio",
            "occupancy_mode": "derived",
            "occupancy_sources": ["binary_sensor.a", "binary_sensor.b"],
            "logic": "weighted_quorum",
            "weight_threshold": "1.5",
            "source_weights": "binary_sensor.a=1.2\nbinary_sensor.b=0.4",
        }
    )

    assert payload["weight_threshold"] == 1.5
    assert payload["source_weights"] == {
        "binary_sensor.a": 1.2,
        "binary_sensor.b": 0.4,
    }
    assert flow._validate_room_payload(payload, is_edit=False) == {}


def test_room_normalization_persists_separate_learning_sources():
    flow = _flow()

    payload = flow._normalize_room_payload(
        {
            "room_id": "studio",
            "occupancy_mode": "derived",
            "occupancy_sources": ["binary_sensor.motion"],
            "learning_sources": ["sensor.studio_lux", "switch.studio_fan"],
            "logic": "any_of",
        }
    )

    assert payload["occupancy_sources"] == ["binary_sensor.motion"]
    assert payload["learning_sources"] == ["sensor.studio_lux", "switch.studio_fan"]


def test_room_normalization_keeps_structured_sources_on_finalize():
    flow = _flow()

    payload = flow._normalize_room_payload(
        {
            "room_id": "studio",
            "occupancy_mode": "derived",
            "sources": [
                {"entity_id": "binary_sensor.motion", "learning_enabled": False},
                {"entity_id": "sensor.studio_lux", "learning_enabled": True},
            ],
            "logic": "any_of",
        }
    )

    assert payload["occupancy_sources"] == ["binary_sensor.motion", "sensor.studio_lux"]
    assert payload["learning_sources"] == ["sensor.studio_lux"]


def test_room_normalization_drops_weighted_quorum_fields_for_other_logic():
    flow = _flow()

    payload = flow._normalize_room_payload(
        {
            "room_id": "studio",
            "occupancy_mode": "derived",
            "occupancy_sources": ["binary_sensor.a", "binary_sensor.b"],
            "logic": "any_of",
            "weight_threshold": "1.5",
            "source_weights": "binary_sensor.a=1.2",
        }
    )

    assert "weight_threshold" not in payload
    assert "source_weights" not in payload


def test_room_validation_rejects_invalid_weighted_quorum_source_weights():
    flow = _flow()

    payload = {
        "room_id": "studio",
        "occupancy_mode": "derived",
        "occupancy_sources": ["binary_sensor.a", "binary_sensor.b"],
        "logic": "weighted_quorum",
        "weight_threshold": 1.0,
        "source_weights": {"binary_sensor.other": 1.0},
    }

    errors = flow._validate_room_payload(payload, is_edit=False)

    assert errors == {"source_weights": "invalid_mapping"}
