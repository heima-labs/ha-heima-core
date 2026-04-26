from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.entities.registry import build_registry
from custom_components.heima.runtime.state_store import CanonicalState
from custom_components.heima.view_model import HeimaViewModelBuilder


def _entry(options: dict) -> SimpleNamespace:
    return SimpleNamespace(entry_id="entry-1", options=options)


def _hass(language: str | None = None) -> SimpleNamespace:
    values: dict[str, SimpleNamespace] = {}
    if language is not None:
        values["input_select.heima_language"] = SimpleNamespace(state=language)
    return SimpleNamespace(states=SimpleNamespace(get=lambda entity_id: values.get(entity_id)))


def test_entity_registry_includes_semantic_view_sensors():
    entry = _entry(
        {
            "rooms": [{"room_id": "studio", "display_name": "Studio"}],
        }
    )

    registry = build_registry(entry)
    keys = {item.key for item in registry.sensors}

    assert "heima_home_view" in keys
    assert "heima_insights_view" in keys
    assert "heima_security_view" in keys
    assert "heima_climate_view" in keys
    assert "heima_room_studio_view" in keys


def test_view_model_builder_publishes_core_non_admin_views():
    entry = _entry(
        {
            "language": "it",
            "rooms": [{"room_id": "studio", "display_name": "Studio"}],
            "lighting_rooms": [{"room_id": "studio", "enable_manual_hold": True}],
            "lighting_zones": [
                {"zone_id": "studio_zone", "display_name": "Studio", "rooms": ["studio"]}
            ],
        }
    )
    state = CanonicalState()
    state.set_sensor("heima_house_state", "relax")
    state.set_sensor("heima_house_state_reason", "Luci soft nel soggiorno")
    state.set_binary("heima_anyone_home", True)
    state.set_sensor("heima_people_count", 2)
    state.set_sensor("heima_security_state", "disarmed")
    state.set_sensor("heima_security_reason", "ok")
    state.set_sensor("heima_heating_phase", "maintaining")
    state.set_sensor("heima_heating_target_temp", 21.2)
    state.set_sensor("heima_heating_current_setpoint", 21.0)
    state.set_sensor("heima_heating_branch", "comfort_hold")
    state.set_sensor("heima_reaction_proposals", 1)
    state.set_sensor("heima_reactions_active", 3)
    state.set_binary("heima_occupancy_studio", True)
    state.set_sensor("heima_occupancy_studio_last_change", "2026-04-27T18:00:00+00:00")
    state.set_select("heima_lighting_intent_studio_zone", "scene_relax")
    state.set_binary("heima_lighting_hold_studio", True)

    HeimaViewModelBuilder(_hass(), entry).publish(state)

    assert state.get_sensor("heima_home_view") == "relax"
    home_attrs = state.get_sensor_attributes("heima_home_view")
    assert home_attrs["title"] == "Casa in relax"
    assert home_attrs["status"]["temperature"] == "21,2 °C"
    assert home_attrs["status"]["presence"] == "2 persone in casa"

    assert state.get_sensor("heima_insights_view") == "attention"
    insight_attrs = state.get_sensor_attributes("heima_insights_view")
    assert any(item["text"] == "1 proposte in attesa" for item in insight_attrs["items"])

    assert state.get_sensor("heima_security_view") == "ok"
    security_attrs = state.get_sensor_attributes("heima_security_view")
    assert security_attrs["summary"] == "Sicurezza ok"

    assert state.get_sensor("heima_climate_view") == "comfort"
    climate_attrs = state.get_sensor_attributes("heima_climate_view")
    assert climate_attrs["temperature"] == "21,0 °C"
    assert climate_attrs["summary"] == "Comfort stabile"

    assert state.get_sensor("heima_room_studio_view") == "active"
    room_attrs = state.get_sensor_attributes("heima_room_studio_view")
    assert room_attrs["title"] == "Studio"
    assert room_attrs["line1"] == "Luci: scene_relax"
    assert room_attrs["line2"] == "Controllo manuale attivo"


def test_view_model_builder_marks_security_alert_when_armed_away_with_presence():
    entry = _entry({"language": "en", "rooms": []})
    state = CanonicalState()
    state.set_sensor("heima_house_state", "home")
    state.set_sensor("heima_house_state_reason", "default")
    state.set_binary("heima_anyone_home", True)
    state.set_sensor("heima_people_count", 1)
    state.set_sensor("heima_security_state", "armed_away")
    state.set_sensor("heima_security_reason", "presence mismatch")

    HeimaViewModelBuilder(_hass(), entry).publish(state)

    assert state.get_sensor("heima_home_view") == "home"
    assert state.get_sensor_attributes("heima_home_view")["priority"] == "critical"
    assert state.get_sensor("heima_security_view") == "alert"
    assert state.get_sensor_attributes("heima_security_view")["alerts"] == ["presence mismatch"]


def test_view_model_builder_prefers_input_select_language_when_available():
    entry = _entry({"language": "en", "rooms": []})
    state = CanonicalState()
    state.set_sensor("heima_house_state", "relax")
    state.set_sensor("heima_house_state_reason", "default")
    state.set_binary("heima_anyone_home", False)
    state.set_sensor("heima_people_count", 0)
    state.set_sensor("heima_security_state", "disarmed")

    HeimaViewModelBuilder(_hass("it"), entry).publish(state)

    assert state.get_sensor_attributes("heima_home_view")["title"] == "Casa in relax"
