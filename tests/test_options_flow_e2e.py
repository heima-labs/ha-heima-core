from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heima.config_flow import HeimaOptionsFlowHandler
from custom_components.heima.config_flow._steps_reactions import _ReactionsStepsMixin
from custom_components.heima.const import (
    DEFAULT_CALENDAR_CACHE_TTL_HOURS,
    DEFAULT_CALENDAR_LOOKAHEAD_DAYS,
    DOMAIN,
)
from custom_components.heima.runtime.analyzers.base import ReactionProposal


class _FakeAreaRegistry:
    def __init__(self, areas: list[tuple[str, str]] | None = None) -> None:
        self.areas = {
            area_id: SimpleNamespace(id=area_id, name=name) for area_id, name in (areas or [])
        }

    def async_list_areas(self):
        return list(self.areas.values())

    def async_get_area(self, area_id: str):
        return self.areas.get(area_id)

    def async_create(self, name: str):
        area_id = name.lower().replace(" ", "_")
        area = SimpleNamespace(id=area_id, name=name)
        self.areas[area_id] = area
        return area

    def async_update(self, area_id: str, *, name: str):
        area = self.areas[area_id]
        updated = SimpleNamespace(id=area.id, name=name)
        self.areas[area_id] = updated
        return updated

    def async_delete(self, area_id: str):
        self.areas.pop(area_id, None)


class _FakeStates:
    def __init__(self, states: list[SimpleNamespace] | None = None) -> None:
        self._states = list(states or [])

    def async_all(self):
        return list(self._states)

    def get(self, entity_id: str):
        for state in self._states:
            if getattr(state, "entity_id", None) == entity_id:
                return state
        return None


def _state(entity_id: str, friendly_name: str | None = None) -> SimpleNamespace:
    attrs = {}
    if friendly_name is not None:
        attrs["friendly_name"] = friendly_name
    return SimpleNamespace(entity_id=entity_id, attributes=attrs, name=friendly_name or entity_id)


def _fake_hass(*, is_admin: bool = True, states: list[SimpleNamespace] | None = None):
    async def _async_get_user(user_id: str):
        return SimpleNamespace(id=user_id, is_admin=is_admin)

    return SimpleNamespace(
        services=SimpleNamespace(async_services=lambda: {"notify": {}}),
        config=SimpleNamespace(time_zone="Europe/Rome", language="it"),
        data={},
        auth=SimpleNamespace(async_get_user=_async_get_user),
        states=_FakeStates(states),
    )


def _flow(
    options: dict | None = None,
    *,
    is_admin: bool = True,
    states: list[SimpleNamespace] | None = None,
) -> HeimaOptionsFlowHandler:
    flow = HeimaOptionsFlowHandler(SimpleNamespace(options=options or {}, entry_id="entry-1"))
    flow.hass = _fake_hass(is_admin=is_admin, states=states)
    flow.context = {"user_id": "user-1"}
    return flow


@pytest.mark.asyncio
async def test_rooms_flow_persists_actuation_only_room_with_save_and_close():
    flow = _flow()

    result = await flow.async_step_rooms_add(
        {
            "room_id": "soggiorno",
            "display_name": "Soggiorno",
            "area_id": "soggiorno",
            "occupancy_mode": "none",
            "occupancy_sources": [],
            "learning_sources": [],
            "logic": "any_of",
            "on_dwell_s": 0,
            "off_dwell_s": 120,
            "max_on_s": None,
        }
    )
    assert result["type"] == "menu"

    saved = await flow.async_step_rooms_save()
    assert saved["type"] == "create_entry"
    room = saved["data"]["rooms"][0]
    assert room["room_id"] == "soggiorno"
    assert room["occupancy_mode"] == "none"
    assert room["occupancy_sources"] == []
    assert room["learning_sources"] == []


@pytest.mark.asyncio
async def test_init_bootstraps_people_from_ha_person_entities():
    flow = _flow(states=[_state("person.alex", "Alex"), _state("person.laura", "Laura")])

    result = await flow.async_step_init()

    assert result["type"] == "menu"
    assert [p["slug"] for p in flow.options["people_named"]] == ["alex", "laura"]
    assert flow.options["people_named"][0]["person_entity"] == "person.alex"


@pytest.mark.asyncio
async def test_init_bootstraps_rooms_from_ha_areas(monkeypatch):
    flow = _flow()
    area_reg = _FakeAreaRegistry([("living", "Living"), ("studio", "Studio")])
    monkeypatch.setattr(
        "custom_components.heima.config_flow._steps_rooms.ar.async_get",
        lambda hass: area_reg,
    )

    result = await flow.async_step_init()

    assert result["type"] == "menu"
    assert [r["room_id"] for r in flow.options["rooms"]] == ["living", "studio"]


def test_people_menu_summary_prefers_ha_backed_status_counts():
    flow = _flow(
        {
            "people_named": [
                {"slug": "alex", "ha_sync_status": "new"},
                {"slug": "laura", "ha_sync_status": "configured"},
                {"slug": "old", "ha_sync_status": "orphaned"},
            ]
        }
    )

    summary = flow._people_menu_summary()

    assert "nuove 1" in summary
    assert "configurate 1" in summary
    assert "orfane 1" in summary


def test_rooms_menu_summary_prefers_ha_backed_status_counts():
    flow = _flow(
        {
            "rooms": [
                {"room_id": "living", "ha_sync_status": "new"},
                {"room_id": "studio", "ha_sync_status": "configured"},
            ]
        }
    )

    summary = flow._rooms_menu_summary()

    assert "nuove 1" in summary
    assert "configurate 1" in summary


def test_rooms_menu_summary_includes_new_and_orphaned_labels():
    flow = _flow(
        {
            "rooms": [
                {"room_id": "living", "display_name": "Living", "ha_sync_status": "new"},
                {"room_id": "studio", "display_name": "Studio", "ha_sync_status": "orphaned"},
                {"room_id": "bathroom", "display_name": "Bathroom", "ha_sync_status": "configured"},
            ]
        }
    )

    summary = flow._rooms_menu_summary()

    assert "nuove: Living" in summary
    assert "orfane: Studio" in summary


@pytest.mark.asyncio
async def test_general_flow_persists_house_signal_bindings():
    flow = _flow()

    result = await flow.async_step_general(
        {
            "engine_enabled": True,
            "timezone": "Europe/Rome",
            "language": "it",
            "lighting_apply_mode": "scene",
            "vacation_mode_entity": "input_boolean.vacation_mode",
            "guest_mode_entity": "",
            "sleep_window_entity": "binary_sensor.sleep_window",
            "relax_mode_entity": "binary_sensor.relax_mode",
            "work_window_entity": "binary_sensor.work_window",
            "media_active_entities": ["media_player.cineforum"],
            "sleep_charging_entities": ["binary_sensor.phone_charging"],
            "workday_entity": "binary_sensor.workday_sensor",
            "sleep_enter_min": 12,
            "sleep_exit_min": 3,
            "work_enter_min": 6,
            "relax_enter_min": 1,
            "relax_exit_min": 15,
            "sleep_requires_media_off": True,
            "sleep_charging_min_count": 2,
        }
    )
    assert result["type"] == "menu"
    assert flow.options["house_signals"] == {
        "vacation_mode": "input_boolean.vacation_mode",
        "sleep_window": "binary_sensor.sleep_window",
        "relax_mode": "binary_sensor.relax_mode",
        "work_window": "binary_sensor.work_window",
    }
    assert flow.options["house_state_config"] == {
        "media_active_entities": ["media_player.cineforum"],
        "sleep_charging_entities": ["binary_sensor.phone_charging"],
        "workday_entity": "binary_sensor.workday_sensor",
        "sleep_enter_min": 12,
        "sleep_exit_min": 3,
        "work_enter_min": 6,
        "relax_enter_min": 1,
        "relax_exit_min": 15,
        "sleep_requires_media_off": True,
        "sleep_charging_min_count": 2,
    }


@pytest.mark.asyncio
async def test_learning_flow_persists_enabled_plugin_families():
    flow = _flow()

    result = await flow.async_step_learning(
        {
            "outdoor_lux_entity": "sensor.outdoor_lux",
            "outdoor_temp_entity": "",
            "weather_entity": "",
            "context_signal_entities": ["media_player.projector"],
            "enabled_plugin_families": ["presence", "lighting"],
        }
    )

    assert result["type"] == "menu"
    assert flow.options["learning"] == {
        "outdoor_lux_entity": "sensor.outdoor_lux",
        "outdoor_temp_entity": None,
        "weather_entity": None,
        "context_signal_entities": ["media_player.projector"],
        "enabled_plugin_families": ["presence", "lighting"],
    }


@pytest.mark.asyncio
async def test_update_options_merges_on_fresh_entry_snapshot_when_flow_state_is_stale():
    flow = _flow(
        {
            "learning": {"outdoor_lux_entity": "sensor.old_lux"},
            "reactions": {
                "configured": {"r_old": {"reaction_class": "ContextConditionedLightingReaction"}},
                "labels": {"r_old": "Old"},
            },
        }
    )
    config_entries = MagicMock()

    def _async_update_entry(entry, *, options):
        entry.options = dict(options)

    config_entries.async_update_entry.side_effect = _async_update_entry
    flow.hass.config_entries = config_entries

    flow._config_entry.options = {
        "learning": {"outdoor_lux_entity": "sensor.external_lux"},
        "reactions": {
            "configured": {"r_new": {"reaction_class": "RoomLightingAssistReaction"}},
            "labels": {"r_new": "New"},
        },
    }

    await flow.async_step_learning(
        {
            "outdoor_lux_entity": "sensor.updated_lux",
            "outdoor_temp_entity": "",
            "weather_entity": "",
            "context_signal_entities": [],
            "enabled_plugin_families": ["presence", "lighting"],
        }
    )

    updated = flow._config_entry.options
    assert updated["learning"]["outdoor_lux_entity"] == "sensor.updated_lux"
    assert updated["reactions"]["configured"] == {
        "r_new": {"reaction_class": "RoomLightingAssistReaction"}
    }
    assert updated["reactions"]["labels"] == {"r_new": "New"}


@pytest.mark.asyncio
async def test_save_preserves_configured_reactions_and_labels():
    flow = _flow(
        {
            "reactions": {
                "muted": ["lighting"],
                "configured": {
                    "reaction-1": {
                        "reaction_class": "VacationPresenceSimulationReaction",
                        "reaction_type": "vacation_presence_simulation",
                        "enabled": True,
                    }
                },
                "labels": {"reaction-1": "Presence simulation"},
            }
        }
    )

    result = await flow.async_step_save()

    assert result["type"] == "create_entry"
    assert result["data"]["reactions"] == {
        "muted": ["lighting"],
        "configured": {
            "reaction-1": {
                "reaction_class": "VacationPresenceSimulationReaction",
                "reaction_type": "vacation_presence_simulation",
                "enabled": True,
            }
        },
        "labels": {"reaction-1": "Presence simulation"},
    }


@pytest.mark.asyncio
async def test_reactions_step_preserves_configured_reactions_and_labels_when_updating_muted():
    flow = _flow(
        {
            "reactions": {
                "muted": ["reaction-1"],
                "configured": {
                    "reaction-1": {
                        "reaction_class": "VacationPresenceSimulationReaction",
                        "reaction_type": "vacation_presence_simulation",
                        "enabled": True,
                    }
                },
                "labels": {"reaction-1": "Presence simulation"},
            }
        }
    )

    result = await flow.async_step_reactions({"muted_reactions": []})

    assert result["type"] == "menu"
    assert flow.options["reactions"] == {
        "muted": [],
        "configured": {
            "reaction-1": {
                "reaction_class": "VacationPresenceSimulationReaction",
                "reaction_type": "vacation_presence_simulation",
                "enabled": True,
            }
        },
        "labels": {"reaction-1": "Presence simulation"},
    }


@pytest.mark.asyncio
async def test_security_step_preserves_camera_evidence_sources():
    flow = _flow(
        {
            "security": {
                "enabled": True,
                "security_state_entity": "alarm_control_panel.home",
                "armed_away_value": "armed_away",
                "armed_home_value": "armed_home",
                "camera_evidence_sources": [
                    {
                        "id": "garage_cam",
                        "enabled": True,
                        "role": "garage",
                        "person_entity": "binary_sensor.garage_person",
                    }
                ],
            }
        }
    )

    result = await flow.async_step_security(
        {
            "enabled": True,
            "security_state_entity": "alarm_control_panel.home",
            "armed_away_value": "armed_away",
            "armed_home_value": "armed_home",
        }
    )

    assert result["type"] == "menu"
    assert flow.options["security"]["camera_evidence_sources"] == [
        {
            "id": "garage_cam",
            "enabled": True,
            "role": "garage",
            "person_entity": "binary_sensor.garage_person",
        }
    ]


@pytest.mark.asyncio
async def test_security_step_accepts_camera_evidence_sources_from_user_input():
    flow = _flow()

    result = await flow.async_step_security(
        {
            "enabled": True,
            "security_state_entity": "alarm_control_panel.home",
            "armed_away_value": "armed_away",
            "armed_home_value": "armed_home",
            "camera_evidence_sources": [
                {
                    "id": "entry_cam",
                    "display_name": "Front Door Camera",
                    "enabled": True,
                    "role": "entry",
                    "person_entity": "binary_sensor.front_cam_person",
                    "contact_entity": "binary_sensor.front_door_contact",
                    "return_home_contributor": True,
                    "security_priority": "high",
                }
            ],
        }
    )

    assert result["type"] == "menu"
    assert flow.options["security"]["camera_evidence_sources"] == [
        {
            "id": "entry_cam",
            "display_name": "Front Door Camera",
            "enabled": True,
            "role": "entry",
            "person_entity": "binary_sensor.front_cam_person",
            "contact_entity": "binary_sensor.front_door_contact",
            "return_home_contributor": True,
            "security_priority": "high",
        }
    ]


@pytest.mark.asyncio
async def test_security_step_normalizes_object_editor_camera_sources():
    flow = _flow()

    result = await flow.async_step_security(
        {
            "enabled": True,
            "security_state_entity": "alarm_control_panel.home",
            "armed_away_value": "armed_away",
            "armed_home_value": "armed_home",
            "camera_evidence_sources": {
                "entry_cam": {
                    "display_name": "Front Door Camera",
                    "enabled": True,
                    "role": "entry",
                    "person_entity": "binary_sensor.front_cam_person",
                }
            },
        }
    )

    assert result["type"] == "menu"
    assert flow.options["security"]["camera_evidence_sources"] == [
        {
            "id": "entry_cam",
            "display_name": "Front Door Camera",
            "enabled": True,
            "role": "entry",
            "person_entity": "binary_sensor.front_cam_person",
        }
    ]


@pytest.mark.asyncio
async def test_security_step_rejects_camera_source_without_role():
    flow = _flow()

    result = await flow.async_step_security(
        {
            "enabled": True,
            "security_state_entity": "alarm_control_panel.home",
            "armed_away_value": "armed_away",
            "armed_home_value": "armed_home",
            "camera_evidence_sources": [
                {
                    "id": "entry_cam",
                    "person_entity": "binary_sensor.front_cam_person",
                }
            ],
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "security"
    assert result["errors"]["camera_evidence_sources"] == "required"


@pytest.mark.asyncio
async def test_security_step_rejects_camera_source_without_any_evidence_entity():
    flow = _flow()

    result = await flow.async_step_security(
        {
            "enabled": True,
            "security_state_entity": "alarm_control_panel.home",
            "armed_away_value": "armed_away",
            "armed_home_value": "armed_home",
            "camera_evidence_sources": [
                {
                    "id": "entry_cam",
                    "role": "entry",
                }
            ],
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "security"
    assert result["errors"]["camera_evidence_sources"] == "required"


@pytest.mark.asyncio
async def test_security_step_shows_camera_evidence_help_text():
    flow = _flow()

    result = await flow.async_step_security()

    assert result["type"] == "form"
    assert result["step_id"] == "security"
    help_text = result["description_placeholders"]["camera_sources_help"]
    assert "entry" in help_text
    assert "garage" in help_text
    assert "person_entity" in help_text
    assert "security_priority" in help_text


@pytest.mark.asyncio
async def test_people_debug_aliases_step_persists_alias_mapping():
    flow = _flow(states=[_state("person.alex", "Alex")])

    result = await flow.async_step_people_debug_aliases(
        {
            "enabled": True,
            "aliases": {
                "demo_alex": {
                    "mode": "alias_person",
                    "person_entity": "person.alex",
                    "display_name": "Demo Alex",
                },
                "guest_test": {
                    "mode": "synthetic",
                    "display_name": "Guest Test",
                    "synthetic_state": "home",
                },
            },
        }
    )

    assert result["type"] == "menu"
    assert flow.options["people_debug_aliases"] == {
        "enabled": True,
        "aliases": {
            "demo_alex": {
                "mode": "alias_person",
                "person_entity": "person.alex",
                "display_name": "Demo Alex",
            },
            "guest_test": {
                "mode": "synthetic",
                "display_name": "Guest Test",
                "synthetic_state": "home",
            },
        },
    }


@pytest.mark.asyncio
async def test_people_debug_aliases_step_rejects_unknown_person_entity():
    flow = _flow(states=[_state("person.stefano", "Stefano")])

    result = await flow.async_step_people_debug_aliases(
        {
            "enabled": True,
            "aliases": {
                "demo_alex": {
                    "mode": "alias_person",
                    "person_entity": "person.missing",
                    "display_name": "Demo Alex",
                }
            },
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "people_debug_aliases"
    assert result["errors"]["aliases"] == "unknown_person"


@pytest.mark.asyncio
async def test_people_debug_aliases_step_rejects_invalid_mode():
    flow = _flow(states=[_state("person.stefano", "Stefano")])

    result = await flow.async_step_people_debug_aliases(
        {
            "enabled": True,
            "aliases": {
                "demo_alex": {
                    "mode": "bad_mode",
                    "person_entity": "person.stefano",
                    "display_name": "Demo Alex",
                }
            },
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "people_debug_aliases"
    assert result["errors"]["aliases"] == "invalid_selection"


@pytest.mark.asyncio
async def test_lighting_room_edit_flow_can_clear_scenes_and_persist_on_save():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "soggiorno",
                    "display_name": "Soggiorno",
                    "area_id": "soggiorno",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                }
            ],
            "lighting_rooms": [
                {
                    "room_id": "soggiorno",
                    "scene_evening": "scene.lettura",
                    "scene_relax": "scene.relax",
                    "scene_night": "scene.night",
                    "scene_off": "scene.off",
                    "enable_manual_hold": True,
                }
            ],
        }
    )

    selected = await flow.async_step_lighting_rooms_edit({"room": "soggiorno"})
    assert selected["type"] == "form"
    assert selected["step_id"] == "lighting_rooms_edit_form"

    edited = await flow.async_step_lighting_rooms_edit_form(
        {
            "room_id": "soggiorno",
            "enable_manual_hold": True,
        }
    )
    assert edited["type"] == "menu"

    saved = await flow.async_step_lighting_rooms_save()
    assert saved["type"] == "create_entry"
    room_map = saved["data"]["lighting_rooms"][0]
    assert room_map["room_id"] == "soggiorno"
    assert room_map["enable_manual_hold"] is True
    assert "scene_evening" not in room_map
    assert "scene_relax" not in room_map
    assert "scene_night" not in room_map
    assert "scene_off" not in room_map


@pytest.mark.asyncio
async def test_lighting_room_edit_form_exposes_room_lights_inventory(monkeypatch):
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "area_id": "studio",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                }
            ],
            "lighting_rooms": [
                {
                    "room_id": "studio",
                    "enable_manual_hold": True,
                }
            ],
        }
    )
    flow._editing_lighting_room_id = "studio"
    entity_registry = SimpleNamespace(
        entities={
            "e1": SimpleNamespace(entity_id="light.studio_main", area_id="studio", device_id=None),
            "e2": SimpleNamespace(entity_id="light.studio_spot", area_id="", device_id="device-1"),
            "e3": SimpleNamespace(entity_id="sensor.studio_lux", area_id="studio", device_id=None),
        }
    )
    device_registry = SimpleNamespace(devices={"device-1": SimpleNamespace(area_id="studio")})
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get",
        lambda _hass: entity_registry,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get",
        lambda _hass: device_registry,
    )

    result = await flow.async_step_lighting_rooms_edit_form()

    assert result["type"] == "form"
    placeholders = result["description_placeholders"]
    assert placeholders["area_label"] == "studio"
    assert placeholders["inventory_entity_total"] == "3"
    assert placeholders["suggested_lighting"] == "light.studio_main, light.studio_spot"


@pytest.mark.asyncio
async def test_notifications_step_rejects_group_members_not_in_recipients():
    flow = _flow()

    result = await flow.async_step_notifications(
        {
            "recipients": {"mobile_alex": "notify.mobile_app_alex"},
            "recipient_groups": {"family": ["mobile_alex", "mobile_laura"]},
            "route_targets": ["family"],
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "notifications"
    assert result["errors"]["recipient_groups"] == "unknown_recipient"


@pytest.mark.asyncio
async def test_notifications_step_rejects_unknown_route_target():
    flow = _flow()

    result = await flow.async_step_notifications(
        {
            "recipients": {"mobile_alex": "notify.mobile_app_alex"},
            "recipient_groups": {"family": ["mobile_alex"]},
            "route_targets": ["missing_target"],
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "notifications"
    assert result["errors"]["route_targets"] == "unknown_target"


@pytest.mark.asyncio
async def test_lighting_rooms_edit_redirects_to_zones_when_no_rooms():
    flow = _flow({"rooms": []})

    result = await flow.async_step_lighting_rooms_edit()

    assert result["type"] == "menu"
    assert result["step_id"] == "lighting_zones_menu"


@pytest.mark.asyncio
async def test_lighting_room_edit_form_rejects_unknown_room():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "area_id": "studio",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                }
            ]
        }
    )
    flow._editing_lighting_room_id = "studio"

    result = await flow.async_step_lighting_rooms_edit_form(
        {
            "room_id": "living",
            "enable_manual_hold": True,
        }
    )

    assert result["type"] == "form"
    assert result["errors"]["room_id"] == "unknown_room"


@pytest.mark.asyncio
async def test_lighting_zones_add_rejects_duplicate_zone_id():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                }
            ],
            "lighting_zones": [
                {"zone_id": "living_zone", "display_name": "Living Zone", "rooms": ["living"]}
            ],
        }
    )

    result = await flow.async_step_lighting_zones_add(
        {"zone_id": "living_zone", "display_name": "Again", "rooms": ["living"]}
    )

    assert result["type"] == "form"
    assert result["errors"]["zone_id"] == "duplicate"


@pytest.mark.asyncio
async def test_lighting_zones_add_rejects_unknown_rooms():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                }
            ]
        }
    )

    result = await flow.async_step_lighting_zones_add(
        {"zone_id": "living_zone", "display_name": "Living Zone", "rooms": ["missing"]}
    )

    assert result["type"] == "form"
    assert result["errors"]["rooms"] == "unknown_room"


@pytest.mark.asyncio
async def test_lighting_zone_remove_confirm_cancel_keeps_zone():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                }
            ],
            "lighting_zones": [
                {"zone_id": "living_zone", "display_name": "Living Zone", "rooms": ["living"]}
            ],
        }
    )

    await flow.async_step_lighting_zones_remove({"zone": "living_zone"})
    cancelled = await flow.async_step_lighting_zones_remove_confirm({"confirm": False})

    assert cancelled["type"] == "menu"
    assert flow.options["lighting_zones"] == [
        {"zone_id": "living_zone", "display_name": "Living Zone", "rooms": ["living"]}
    ]


@pytest.mark.asyncio
async def test_rooms_flow_persists_weighted_quorum_room_source_weights():
    flow = _flow()

    result = await flow.async_step_rooms_add(
        {
            "room_id": "studio",
            "display_name": "Studio",
            "area_id": "studio",
            "occupancy_mode": "derived",
            "occupancy_sources": ["binary_sensor.motion", "binary_sensor.mmwave"],
            "learning_sources": [],
            "logic": "weighted_quorum",
            "weight_threshold": 1.2,
            "source_weights": "binary_sensor.motion=0.4\nbinary_sensor.mmwave=0.8",
            "on_dwell_s": 0,
            "off_dwell_s": 120,
            "max_on_s": None,
        }
    )
    assert result["type"] == "menu"

    saved = await flow.async_step_rooms_save()
    assert saved["type"] == "create_entry"
    room = saved["data"]["rooms"][0]
    assert room["logic"] == "weighted_quorum"
    assert room["weight_threshold"] == 1.2
    assert room["source_weights"] == {
        "binary_sensor.motion": 0.4,
        "binary_sensor.mmwave": 0.8,
    }


@pytest.mark.asyncio
async def test_rooms_flow_persists_separate_learning_sources():
    flow = _flow()

    result = await flow.async_step_rooms_add(
        {
            "room_id": "studio",
            "display_name": "Studio",
            "area_id": "studio",
            "occupancy_mode": "derived",
            "occupancy_sources": ["binary_sensor.motion"],
            "learning_sources": ["sensor.studio_lux", "switch.studio_fan"],
            "logic": "any_of",
            "on_dwell_s": 0,
            "off_dwell_s": 120,
            "max_on_s": None,
        }
    )
    assert result["type"] == "menu"

    saved = await flow.async_step_rooms_save()
    room = saved["data"]["rooms"][0]
    assert room["occupancy_sources"] == ["binary_sensor.motion"]
    assert room["learning_sources"] == ["sensor.studio_lux", "switch.studio_fan"]


@pytest.mark.asyncio
async def test_rooms_flow_persists_structured_room_signals():
    flow = _flow()

    result = await flow.async_step_rooms_add(
        {
            "room_id": "studio",
            "display_name": "Studio",
            "area_id": "studio",
            "occupancy_mode": "derived",
            "occupancy_sources": ["binary_sensor.motion"],
            "learning_sources": ["sensor.studio_lux"],
            "signals": """
            [
              {
                "entity_id": "sensor.studio_lux",
                "signal_name": "room_lux",
                "device_class": "illuminance",
                "buckets": [
                  {"label": "dark", "upper_bound": 30},
                  {"label": "dim", "upper_bound": 100},
                  {"label": "bright", "upper_bound": null}
                ]
              }
            ]
            """,
            "logic": "any_of",
            "on_dwell_s": 0,
            "off_dwell_s": 120,
            "max_on_s": None,
        }
    )

    assert result["type"] == "menu"
    room = flow.options["rooms"][0]
    assert room["signals"] == [
        {
            "entity_id": "sensor.studio_lux",
            "signal_name": "room_lux",
            "device_class": "illuminance",
            "buckets": [
                {"label": "dark", "upper_bound": 30.0},
                {"label": "dim", "upper_bound": 100.0},
                {"label": "bright", "upper_bound": None},
            ],
        }
    ]


@pytest.mark.asyncio
async def test_rooms_flow_rejects_invalid_room_signals_json():
    flow = _flow()

    result = await flow.async_step_rooms_add(
        {
            "room_id": "studio",
            "display_name": "Studio",
            "area_id": "studio",
            "occupancy_mode": "derived",
            "occupancy_sources": ["binary_sensor.motion"],
            "learning_sources": [],
            "signals": "{not-json}",
            "logic": "any_of",
            "on_dwell_s": 0,
            "off_dwell_s": 120,
            "max_on_s": None,
        }
    )

    assert result["type"] == "form"
    assert result["errors"] == {"signals": "invalid_json"}


@pytest.mark.asyncio
async def test_rooms_flow_rejects_duplicate_signal_names():
    flow = _flow()

    result = await flow.async_step_rooms_add(
        {
            "room_id": "studio",
            "display_name": "Studio",
            "area_id": "studio",
            "occupancy_mode": "derived",
            "occupancy_sources": ["binary_sensor.motion"],
            "learning_sources": [],
            "signals": """
            [
              {
                "entity_id": "sensor.studio_lux",
                "signal_name": "room_lux",
                "device_class": "illuminance",
                "buckets": [{"label": "dark", "upper_bound": 30}]
              },
              {
                "entity_id": "sensor.studio_lux_aux",
                "signal_name": "room_lux",
                "device_class": "illuminance",
                "buckets": [{"label": "dark", "upper_bound": 30}]
              }
            ]
            """,
            "logic": "any_of",
            "on_dwell_s": 0,
            "off_dwell_s": 120,
            "max_on_s": None,
        }
    )

    assert result["type"] == "form"
    assert result["errors"] == {"signals": "duplicate_signal_name"}


@pytest.mark.asyncio
async def test_rooms_edit_form_exposes_inventory_suggestions_in_description(monkeypatch):
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "area_id": "studio",
                    "occupancy_sources": ["binary_sensor.studio_motion"],
                    "learning_sources": [],
                }
            ]
        }
    )
    flow._editing_room_id = "studio"
    entity_registry = SimpleNamespace(
        entities={
            "e1": SimpleNamespace(
                entity_id="binary_sensor.studio_motion", area_id="studio", device_id=None
            ),
            "e2": SimpleNamespace(entity_id="sensor.studio_lux", area_id="studio", device_id=None),
            "e3": SimpleNamespace(entity_id="light.studio_main", area_id="", device_id="device-1"),
        }
    )
    device_registry = SimpleNamespace(devices={"device-1": SimpleNamespace(area_id="studio")})
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get",
        lambda _hass: entity_registry,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get",
        lambda _hass: device_registry,
    )

    result = await flow.async_step_rooms_edit_form()

    assert result["type"] == "form"
    placeholders = result["description_placeholders"]
    assert placeholders["area_label"] == "studio"
    assert placeholders["inventory_entity_total"] == "3"
    assert placeholders["suggested_occupancy"] == "binary_sensor.studio_motion"
    assert placeholders["suggested_learning"] == "sensor.studio_lux"
    assert placeholders["suggested_lighting"] == "light.studio_main"
    assert placeholders["configured_mismatch"] == "—"
    assert "burst_threshold" in placeholders["signals_help"]
    assert '"signal_name": "room_temperature"' in placeholders["signals_example"]
    schema_keys = {str(key.schema) for key in result["data_schema"].schema}
    assert "use_suggested_occupancy_sources" not in schema_keys
    assert "use_suggested_learning_sources" not in schema_keys


@pytest.mark.asyncio
async def test_rooms_edit_form_orders_learning_before_occupancy_logic(monkeypatch):
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "area_id": "studio",
                    "occupancy_mode": "derived",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                    "on_dwell_s": 0,
                    "off_dwell_s": 120,
                    "max_on_s": None,
                }
            ]
        }
    )
    flow._editing_room_id = "studio"
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get",
        lambda _hass: SimpleNamespace(entities={}),
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get",
        lambda _hass: SimpleNamespace(devices={}),
    )

    result = await flow.async_step_rooms_edit_form()

    ordered_keys = [str(key.schema) for key in result["data_schema"].schema]
    assert ordered_keys.index("learning_sources") < ordered_keys.index("occupancy_sources")
    assert ordered_keys.index("occupancy_sources") < ordered_keys.index("logic")


@pytest.mark.asyncio
async def test_rooms_edit_form_persists_explicit_inventory_bindings(monkeypatch):
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "area_id": "studio",
                    "occupancy_mode": "derived",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                    "on_dwell_s": 0,
                    "off_dwell_s": 120,
                    "max_on_s": None,
                }
            ]
        }
    )
    flow._editing_room_id = "studio"
    entity_registry = SimpleNamespace(
        entities={
            "e1": SimpleNamespace(
                entity_id="binary_sensor.studio_motion", area_id="studio", device_id=None
            ),
            "e2": SimpleNamespace(entity_id="sensor.studio_lux", area_id="studio", device_id=None),
        }
    )
    device_registry = SimpleNamespace(devices={})
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get",
        lambda _hass: entity_registry,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get",
        lambda _hass: device_registry,
    )

    result = await flow.async_step_rooms_edit_form(
        {
            "room_id": "studio",
            "display_name": "Studio",
            "area_id": "studio",
            "occupancy_mode": "derived",
            "occupancy_sources": ["binary_sensor.studio_motion"],
            "learning_sources": ["sensor.studio_lux"],
            "logic": "any_of",
            "on_dwell_s": 0,
            "off_dwell_s": 120,
            "max_on_s": None,
        }
    )

    assert result["type"] == "menu"
    stored = flow.options["rooms"][0]
    assert stored["occupancy_sources"] == ["binary_sensor.studio_motion"]
    assert stored["learning_sources"] == ["sensor.studio_lux"]


@pytest.mark.asyncio
async def test_people_edit_shows_status_labels_for_imported_people():
    flow = _flow(
        {
            "people_named": [
                {"slug": "alex", "display_name": "Alex", "ha_sync_status": "new"},
                {"slug": "laura", "display_name": "Laura", "ha_sync_status": "orphaned"},
            ]
        }
    )

    result = await flow.async_step_people_edit()
    options = result["data_schema"].schema["person"].container

    assert "Alex [new]" in options
    assert "Laura [orphaned]" in options


@pytest.mark.asyncio
async def test_people_edit_accepts_selected_label_from_ui():
    flow = _flow(
        {
            "people_named": [
                {
                    "slug": "stefano",
                    "display_name": "Stefano",
                    "presence_method": "ha_person",
                    "person_entity": "person.stefano",
                    "ha_sync_status": "new",
                }
            ]
        },
        states=[_state("person.stefano", "Stefano")],
    )

    result = await flow.async_step_people_edit({"person": "Stefano [new]"})

    assert result["type"] == "form"
    assert result["step_id"] == "people_edit_form"
    assert flow._editing_person_slug == "stefano"


@pytest.mark.asyncio
async def test_people_menu_does_not_expose_add_or_remove_actions():
    flow = _flow(states=[_state("person.alex", "Alex")])

    result = await flow.async_step_people_menu()

    assert result["type"] == "menu"
    assert "people_add" not in result["menu_options"]
    assert "people_remove" not in result["menu_options"]
    assert "people_edit" in result["menu_options"]
    assert "people_debug_aliases" in result["menu_options"]


@pytest.mark.asyncio
async def test_people_edit_form_absorbs_auto_imported_duplicate_placeholder():
    flow = _flow(
        {
            "people_named": [
                {
                    "slug": "stefano",
                    "display_name": "Stefano",
                    "presence_method": "ha_person",
                    "person_entity": "",
                    "ha_sync_status": "orphaned",
                    "heima_reviewed": True,
                },
                {
                    "slug": "stefano_2",
                    "display_name": "Stefano",
                    "presence_method": "ha_person",
                    "person_entity": "person.stefano",
                    "ha_sync_status": "new",
                    "heima_reviewed": False,
                },
            ]
        },
        states=[_state("person.stefano", "Stefano")],
    )
    flow._editing_person_slug = "stefano"

    result = await flow.async_step_people_edit_form(
        {
            "slug": "stefano",
            "display_name": "Stefano",
            "presence_method": "ha_person",
            "person_entity": "person.stefano",
        }
    )

    assert result["type"] == "menu"
    assert [person["slug"] for person in flow.options["people_named"]] == ["stefano"]
    assert flow.options["people_named"][0]["person_entity"] == "person.stefano"
    assert flow.options["people_named"][0]["ha_sync_status"] == "configured"
    assert flow.options["people_named"][0]["presence_rule"] == "resident"


@pytest.mark.asyncio
async def test_people_edit_form_persists_presence_rule():
    flow = _flow(
        {
            "people_named": [
                {
                    "slug": "tablet_home",
                    "display_name": "Tablet Home",
                    "presence_method": "ha_person",
                    "person_entity": "person.tablet_home",
                    "presence_rule": "resident",
                    "ha_sync_status": "configured",
                    "heima_reviewed": True,
                }
            ]
        },
        states=[_state("person.tablet_home", "Tablet Home")],
    )
    flow._editing_person_slug = "tablet_home"

    result = await flow.async_step_people_edit_form(
        {
            "slug": "tablet_home",
            "display_name": "Tablet Home",
            "presence_method": "ha_person",
            "presence_rule": "observer",
            "person_entity": "person.tablet_home",
        }
    )

    assert result["type"] == "menu"
    assert flow.options["people_named"][0]["presence_rule"] == "observer"


@pytest.mark.asyncio
async def test_people_menu_reconciles_legacy_person_before_edit():
    flow = _flow(
        {
            "people_named": [
                {
                    "slug": "stefano",
                    "display_name": "",
                    "presence_method": "ha_person",
                    "person_entity": "",
                    "ha_sync_status": "orphaned",
                    "heima_reviewed": True,
                }
            ]
        },
        states=[_state("person.stefano", "Stefano")],
    )

    result = await flow.async_step_people_menu()

    assert result["type"] == "menu"
    assert flow.options["people_named"][0]["display_name"] == "Stefano"
    assert flow.options["people_named"][0]["person_entity"] == "person.stefano"
    assert flow.options["people_named"][0]["ha_sync_status"] == "configured"


def test_people_menu_summary_includes_new_and_orphaned_labels():
    flow = _flow(
        {
            "people_named": [
                {"slug": "alex", "display_name": "Alex", "ha_sync_status": "new"},
                {"slug": "laura", "display_name": "Laura", "ha_sync_status": "orphaned"},
                {"slug": "mario", "display_name": "Mario", "ha_sync_status": "configured"},
            ]
        }
    )

    summary = flow._people_menu_summary()

    assert "nuove: Alex" in summary
    assert "orfane: Laura" in summary


@pytest.mark.asyncio
async def test_rooms_edit_shows_status_labels_for_imported_rooms():
    flow = _flow(
        {
            "rooms": [
                {"room_id": "living", "display_name": "Living", "ha_sync_status": "new"},
                {"room_id": "studio", "display_name": "Studio", "ha_sync_status": "configured"},
            ]
        }
    )

    result = await flow.async_step_rooms_edit()
    options = result["data_schema"].schema["room"].container

    assert "Living [new]" in options
    assert "Studio [configured]" in options


@pytest.mark.asyncio
async def test_rooms_edit_accepts_selected_label_from_ui():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "ha_sync_status": "new",
                }
            ]
        }
    )

    result = await flow.async_step_rooms_edit({"room": "Living [new]"})

    assert result["type"] == "menu"
    assert result["step_id"] == "rooms_edit_actions"
    assert flow._editing_room_id == "living"


@pytest.mark.asyncio
async def test_rooms_edit_actions_can_open_lighting_config_for_same_room():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "ha_sync_status": "configured",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                }
            ]
        }
    )
    flow._editing_room_id = "living"

    result = await flow.async_step_rooms_edit_lighting()

    assert result["type"] == "form"
    assert result["step_id"] == "lighting_rooms_edit_form"
    assert flow._editing_lighting_room_id == "living"


@pytest.mark.asyncio
async def test_rooms_add_creates_linked_ha_area_when_missing(monkeypatch):
    flow = _flow()
    area_reg = _FakeAreaRegistry()
    monkeypatch.setattr(
        "custom_components.heima.config_flow._steps_rooms.ar.async_get",
        lambda hass: area_reg,
    )

    result = await flow.async_step_rooms_add(
        {
            "room_id": "living",
            "display_name": "Living",
            "occupancy_mode": "none",
            "occupancy_sources": [],
            "learning_sources": [],
            "logic": "any_of",
            "on_dwell_s": 0,
            "off_dwell_s": 120,
            "max_on_s": None,
        }
    )

    assert result["type"] == "menu"
    assert flow.options["rooms"][0]["area_id"] == "living"
    assert area_reg.async_get_area("living").name == "Living"


@pytest.mark.asyncio
async def test_rooms_edit_updates_linked_ha_area_name(monkeypatch):
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                    "on_dwell_s": 0,
                    "off_dwell_s": 120,
                    "max_on_s": None,
                }
            ]
        }
    )
    area_reg = _FakeAreaRegistry([("living", "Living")])
    monkeypatch.setattr(
        "custom_components.heima.config_flow._steps_rooms.ar.async_get",
        lambda hass: area_reg,
    )
    flow._editing_room_id = "living"

    result = await flow.async_step_rooms_edit_form(
        {
            "room_id": "living",
            "display_name": "Living Room",
            "area_id": "living",
            "occupancy_mode": "none",
            "occupancy_sources": [],
            "learning_sources": [],
            "logic": "any_of",
            "on_dwell_s": 0,
            "off_dwell_s": 120,
            "max_on_s": None,
        }
    )

    assert result["type"] == "menu"
    assert area_reg.async_get_area("living").name == "Living Room"
    assert flow.options["rooms"][0]["display_name"] == "Living Room"


@pytest.mark.asyncio
async def test_rooms_remove_requires_confirmation_and_deletes_linked_ha_area(monkeypatch):
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                    "on_dwell_s": 0,
                    "off_dwell_s": 120,
                    "max_on_s": None,
                }
            ]
        }
    )
    area_reg = _FakeAreaRegistry([("living", "Living")])
    monkeypatch.setattr(
        "custom_components.heima.config_flow._steps_rooms.ar.async_get",
        lambda hass: area_reg,
    )

    result = await flow.async_step_rooms_remove({"room": "living"})

    assert result["type"] == "form"
    assert result["step_id"] == "rooms_remove_confirm"
    assert "living" in area_reg.areas

    confirmed = await flow.async_step_rooms_remove_confirm({"confirm": True})

    assert confirmed["type"] == "menu"
    assert flow.options["rooms"] == []
    assert "living" not in area_reg.areas


@pytest.mark.asyncio
async def test_heating_flow_persists_general_config_and_branch_mapping():
    flow = _flow()

    result = await flow.async_step_heating(
        {
            "climate_entity": "climate.termostato",
            "apply_mode": "delegate_to_scheduler",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "outdoor_temperature_entity": "sensor.outdoor_temp",
            "vacation_hours_from_start_entity": "sensor.hours_from",
            "vacation_hours_to_end_entity": "sensor.hours_to",
            "vacation_total_hours_entity": "sensor.hours_total",
            "vacation_is_long_entity": "binary_sensor.vacation_is_long",
        }
    )
    assert result["type"] == "menu"
    assert result["step_id"] == "heating_branches_menu"

    selected = await flow.async_step_heating_branches_edit({"house_state": "vacation"})
    assert selected["type"] == "form"
    assert selected["step_id"] == "heating_branch_select"

    params_form = await flow.async_step_heating_branch_select({"branch": "vacation_curve"})
    assert params_form["type"] == "form"
    assert params_form["step_id"] == "heating_branch_edit_form"

    updated = await flow.async_step_heating_branch_edit_form(
        {
            "vacation_ramp_down_h": 8,
            "vacation_ramp_up_h": 10,
            "vacation_min_temp": 16.5,
            "vacation_comfort_temp": 19.5,
            "vacation_min_total_hours_for_ramp": 24,
        }
    )
    assert updated["type"] == "menu"
    assert updated["step_id"] == "heating_branches_menu"

    saved = await flow.async_step_heating_branches_save()
    assert saved["type"] == "menu"
    assert saved["step_id"] == "init"

    heating = flow.options["heating"]
    assert heating["climate_entity"] == "climate.termostato"
    assert heating["temperature_step"] == 0.5
    assert heating["override_branches"]["vacation"]["branch"] == "vacation_curve"
    assert heating["override_branches"]["vacation"]["vacation_min_temp"] == 16.5


@pytest.mark.asyncio
async def test_proposal_configure_action_normalizes_scene_and_script_steps():
    flow = _flow(
        {
            "reactions": {
                "configured": {
                    "proposal-1": {
                        "reaction_class": "PresencePatternReaction",
                        "weekday": 0,
                        "median_arrival_min": 480,
                        "steps": [],
                    }
                },
                "labels": {"proposal-1": "Arrival proposal"},
            }
        }
    )
    flow._pending_action_configs = ["proposal-1"]

    result = await flow.async_step_proposal_configure_action(
        {
            "action_entities": ["scene.arrival", "script.preheat_home"],
            "pre_condition_min": 15,
        }
    )

    assert result["type"] == "menu"
    cfg = flow.options["reactions"]["configured"]["proposal-1"]
    assert cfg["pre_condition_min"] == 15
    assert cfg["steps"] == [
        {
            "domain": "lighting",
            "target": "scene.arrival",
            "action": "scene.turn_on",
            "params": {"entity_id": "scene.arrival"},
        },
        {
            "domain": "script",
            "target": "script.preheat_home",
            "action": "script.turn_on",
            "params": {"entity_id": "script.preheat_home"},
        },
    ]


@pytest.mark.asyncio
async def test_proposal_configure_action_returns_init_when_queue_is_empty():
    flow = _flow()

    result = await flow.async_step_proposal_configure_action(
        {
            "action_entities": ["scene.arrival"],
            "pre_condition_min": 15,
        }
    )

    assert result["type"] == "menu"
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_proposal_configure_action_legacy_queue_rejects_redacted_payload():
    flow = _flow(
        {
            "reactions": {
                "configured": {
                    "proposal-1": {
                        "reaction_class": "PresencePatternReaction",
                        "weekday": 0,
                        "median_arrival_min": 480,
                        "steps": [],
                        "source_proposal_identity_key": "**REDACTED**",
                    }
                },
                "labels": {"proposal-1": "Arrival proposal"},
            }
        }
    )
    flow._pending_action_configs = ["proposal-1"]

    result = await flow.async_step_proposal_configure_action(
        {
            "action_entities": ["scene.arrival"],
            "pre_condition_min": 15,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "proposal_configure_action"
    assert result["errors"]["base"] == "redacted_payload"
    assert flow.options["reactions"]["configured"]["proposal-1"]["steps"] == []


@pytest.mark.asyncio
async def test_reaction_label_from_room_signal_assist_config_is_readable():
    flow = _flow()

    label = flow._reaction_label_from_config(
        "proposal-bathroom",
        {
            "reaction_class": "RoomSignalAssistReaction",
            "room_id": "bathroom",
            "trigger_signal_entities": ["sensor.bathroom_humidity"],
            "temperature_signal_entities": ["sensor.bathroom_temperature"],
            "episodes_observed": 5,
        },
        {},
    )

    assert label == "Assist bathroom — hum:1 — temp:1 — 5 episodi"


@pytest.mark.asyncio
async def test_proposal_human_label_for_room_signal_assist_includes_primary_signal():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-signal",
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_signal_assist",
        description="bathroom learned assist",
        confidence=0.88,
        suggested_reaction_config={
            "reaction_class": "RoomSignalAssistReaction",
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
        },
    )

    label = flow._proposal_human_label(proposal)

    assert label == "Assist bathroom · humidity"


@pytest.mark.asyncio
async def test_proposal_human_label_for_room_lighting_assist_includes_primary_signal():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-darkness",
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_darkness_lighting_assist",
        description="studio darkness",
        confidence=0.9,
        suggested_reaction_config={
            "reaction_class": "RoomLightingAssistReaction",
            "room_id": "studio",
            "primary_signal_name": "room_lux",
        },
    )

    label = flow._proposal_human_label(proposal)

    assert label == "Luci studio · room_lux"


@pytest.mark.asyncio
async def test_proposals_step_skips_manual_action_for_room_lighting_assist():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-darkness",
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_darkness_lighting_assist",
        description="Living darkness lighting replay",
        confidence=0.91,
        suggested_reaction_config={
            "reaction_class": "RoomLightingAssistReaction",
            "room_id": "living",
            "primary_signal_entities": ["sensor.living_room_lux"],
            "primary_bucket": "ok",
            "entity_steps": [
                {
                    "entity_id": "light.living_main",
                    "action": "on",
                    "brightness": 144,
                    "color_temp_kelvin": 2900,
                    "rgb_color": None,
                }
            ],
            "learning_diagnostics": {
                "pattern_id": "room_darkness_lighting_assist",
                "episodes_observed": 5,
                "weeks_observed": 2,
            },
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert getattr(flow, "_pending_action_configs", []) == []
    stored = flow.options["reactions"]["configured"]["proposal-darkness"]
    assert stored["reaction_type"] == "room_darkness_lighting_assist"
    assert stored["origin"] == "learned"
    assert stored["author_kind"] == "heima"
    assert stored["source_request"] == "learned_pattern"
    assert stored["source_proposal_id"] == "proposal-darkness"


@pytest.mark.asyncio
async def test_reaction_label_from_room_lighting_assist_config_is_readable():
    flow = _flow()

    label = flow._reaction_label_from_config(
        "proposal-darkness",
        {
            "reaction_class": "RoomLightingAssistReaction",
            "room_id": "living",
            "primary_signal_entities": ["sensor.living_room_lux"],
            "entity_steps": [
                {"entity_id": "light.living_main", "action": "on", "brightness": 144},
                {"entity_id": "light.corner", "action": "on", "brightness": 96},
            ],
        },
        {},
    )

    assert label == "Luce living — lux:1 — 2 entità"


@pytest.mark.asyncio
async def test_proposals_step_accepts_contextual_improvement_by_replacing_darkness_target():
    flow = _flow(
        options={
            "reactions": {
                "configured": {
                    "darkness-1": {
                        "reaction_type": "room_darkness_lighting_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "entity_steps": [
                            {
                                "entity_id": "light.studio_main",
                                "action": "on",
                                "brightness": 144,
                            }
                        ],
                        "created_at": "2026-03-01T08:00:00+00:00",
                    }
                },
                "labels": {"darkness-1": "Luce studio"},
            }
        }
    )
    proposal = ReactionProposal(
        proposal_id="proposal-contextual-upgrade",
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_contextual_lighting_assist",
        description="studio contextual upgrade",
        confidence=0.86,
        followup_kind="improvement",
        target_reaction_id="darkness-1",
        target_reaction_type="room_darkness_lighting_assist",
        target_reaction_origin="learned",
        improves_reaction_type="room_darkness_lighting_assist",
        improvement_reason="contextual_variation",
        suggested_reaction_config={
            "reaction_type": "room_contextual_lighting_assist",
            "room_id": "studio",
            "primary_signal_name": "room_lux",
            "primary_bucket": "dim",
            "primary_bucket_match_mode": "lte",
            "followup_window_s": 900,
            "profiles": {
                "day_generic": {
                    "entity_steps": [
                        {
                            "entity_id": "light.studio_main",
                            "action": "on",
                            "brightness": 140,
                            "color_temp_kelvin": 3600,
                        }
                    ]
                }
            },
            "rules": [{"profile": "day_generic"}],
            "default_profile": "day_generic",
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    proposal_engine.async_accept_proposal.assert_awaited_once_with("proposal-contextual-upgrade")
    stored = flow.options["reactions"]["configured"]["darkness-1"]
    assert stored["reaction_type"] == "room_contextual_lighting_assist"
    assert stored["improved_from_reaction_type"] == "room_darkness_lighting_assist"
    assert stored["improvement_reason"] == "contextual_variation"
    assert stored["improvement_acceptance_strategy"] == "convert_replace"
    assert stored["default_profile"] == "day_generic"
    assert "entity_steps" not in stored


@pytest.mark.asyncio
async def test_proposals_step_accepts_cooling_improvement_by_replacing_signal_target():
    flow = _flow(
        options={
            "reactions": {
                "configured": {
                    "signal-1": {
                        "reaction_type": "room_signal_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_temperature",
                        "primary_signal_entities": ["sensor.studio_temperature"],
                        "steps": [
                            {
                                "entity_id": "fan.studio_fan",
                                "service": "fan.turn_on",
                                "service_data": {"entity_id": "fan.studio_fan"},
                            }
                        ],
                        "created_at": "2026-03-01T08:00:00+00:00",
                    }
                },
                "labels": {"signal-1": "Ventola studio"},
            }
        }
    )
    proposal = ReactionProposal(
        proposal_id="proposal-cooling-upgrade",
        analyzer_id="RoomCoolingPatternAnalyzer",
        reaction_type="room_cooling_assist",
        description="studio cooling upgrade",
        confidence=0.84,
        followup_kind="improvement",
        target_reaction_id="signal-1",
        target_reaction_type="room_signal_assist",
        target_reaction_origin="learned",
        improves_reaction_type="room_signal_assist",
        improvement_reason="cooling_specialization",
        suggested_reaction_config={
            "reaction_type": "room_cooling_assist",
            "room_id": "studio",
            "primary_signal_name": "room_temperature",
            "primary_signal_entities": ["sensor.studio_temperature"],
            "corroboration_signal_name": "room_humidity",
            "corroboration_signal_entities": ["sensor.studio_humidity"],
            "steps": [
                {
                    "entity_id": "fan.studio_fan",
                    "service": "fan.turn_on",
                    "service_data": {"entity_id": "fan.studio_fan"},
                }
            ],
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    proposal_engine.async_accept_proposal.assert_awaited_once_with("proposal-cooling-upgrade")
    stored = flow.options["reactions"]["configured"]["signal-1"]
    assert stored["reaction_type"] == "room_cooling_assist"
    assert stored["improved_from_reaction_type"] == "room_signal_assist"
    assert stored["improvement_reason"] == "cooling_specialization"
    assert stored["improvement_acceptance_strategy"] == "convert_replace"
    assert stored["corroboration_signal_name"] == "room_humidity"


@pytest.mark.asyncio
async def test_proposals_step_accept_reuses_existing_same_slot_composite_reaction():
    flow = _flow(
        options={
            "reactions": {
                "configured": {
                    "cooling-existing": {
                        "reaction_type": "room_cooling_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_temperature",
                        "primary_signal_entities": ["sensor.studio_temperature"],
                        "corroboration_signal_name": "room_humidity",
                        "corroboration_signal_entities": ["sensor.studio_humidity"],
                        "episodes_observed": 5,
                        "origin": "learned",
                    }
                },
                "labels": {"cooling-existing": "Raffrescamento studio"},
            }
        }
    )
    proposal = ReactionProposal(
        proposal_id="proposal-cooling-duplicate-slot",
        analyzer_id="RoomCoolingPatternAnalyzer",
        reaction_type="room_cooling_assist",
        description="studio cooling assist",
        confidence=0.82,
        suggested_reaction_config={
            "reaction_type": "room_cooling_assist",
            "room_id": "studio",
            "primary_signal_name": "room_temperature",
            "primary_signal_entities": ["sensor.studio_temperature"],
            "corroboration_signal_name": "room_humidity",
            "corroboration_signal_entities": ["sensor.studio_humidity"],
            "episodes_observed": 6,
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    configured = flow.options["reactions"]["configured"]
    assert "proposal-cooling-duplicate-slot" not in configured
    assert list(configured) == ["cooling-existing"]
    stored = configured["cooling-existing"]
    assert stored["reaction_type"] == "room_cooling_assist"
    assert stored["episodes_observed"] == 6
    assert stored["last_tuned_at"] == proposal.updated_at


def test_reaction_label_from_config_distinguishes_cooling_variants():
    labels_map: dict[str, str] = {}

    home_label = _ReactionsStepsMixin._reaction_label_from_config(
        "r-home",
        {
            "reaction_type": "room_cooling_assist",
            "room_id": "studio",
            "primary_signal_name": "room_temperature",
            "corroboration_signal_name": "room_humidity",
            "house_state_filter": "home",
            "episodes_observed": 5,
        },
        labels_map,
    )
    generic_label = _ReactionsStepsMixin._reaction_label_from_config(
        "r-generic",
        {
            "reaction_type": "room_cooling_assist",
            "room_id": "studio",
            "primary_signal_name": "room_temperature",
            "corroboration_signal_name": "room_humidity",
            "episodes_observed": 5,
        },
        labels_map,
    )

    assert (
        home_label
        == "Raffrescamento studio — room_temperature + room_humidity — stato:home — 5 episodi"
    )
    assert generic_label == "Raffrescamento studio — room_temperature + room_humidity — 5 episodi"


def test_proposal_review_label_includes_context_confidence_and_last_seen():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-1",
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="context_conditioned_lighting_scene",
        description="living: Monday ~20:00 — test_heima_living_main on",
        confidence=0.92,
        last_observed_at="2026-03-26T10:27:51.561727+00:00",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "reaction_class": "ContextConditionedLightingReaction",
        },
    )

    label = flow._proposal_review_label(proposal)

    assert "living: Monday ~20:00" in label
    assert "(room:living)" in label
    assert "[92% | seen 2026-03-26]" in label


def test_proposals_step_summary_includes_pending_count_and_top_labels():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-1",
        analyzer_id="PresencePatternAnalyzer",
        reaction_type="presence_preheat",
        description="Wednesday: typical arrival around 12:38.",
        confidence=1.0,
        last_observed_at="2026-03-26T10:27:51.561727+00:00",
        suggested_reaction_config={"weekday": 2},
    )

    summary = flow._proposals_step_summary([proposal])

    assert summary == "1 proposta pendente"


def test_init_status_block_uses_operational_calendar_summary_when_runtime_available():
    next_vacation = SimpleNamespace(summary="Ferie agosto")
    flow = _flow(
        options={"language": "it", "calendar": {"calendar_entities": ["calendar.personal"]}}
    )
    flow.hass.data = {
        DOMAIN: {
            "entry-1": {
                "coordinator": SimpleNamespace(
                    engine=SimpleNamespace(
                        _state=SimpleNamespace(
                            calendar_result=SimpleNamespace(
                                is_vacation_active=False,
                                is_office_today=False,
                                is_wfh_today=True,
                                next_vacation=next_vacation,
                            )
                        )
                    )
                )
            }
        }
    }

    placeholders = flow._init_status_block()

    assert placeholders["calendar_summary"] == "WFH oggi"


@pytest.mark.asyncio
async def test_calendar_step_uses_defaults_when_config_missing():
    flow = _flow(options={"language": "it"})

    result = await flow.async_step_calendar()

    assert result["type"] == "form"

    saved = await flow.async_step_calendar(
        {
            "calendar_entities": [],
            "lookahead_days": DEFAULT_CALENDAR_LOOKAHEAD_DAYS,
            "cache_ttl_hours": DEFAULT_CALENDAR_CACHE_TTL_HOURS,
            "calendar_keywords": {},
            "priority_text": "",
        }
    )

    assert saved["type"] == "menu"
    assert flow.options["calendar"]["lookahead_days"] == DEFAULT_CALENDAR_LOOKAHEAD_DAYS
    assert flow.options["calendar"]["cache_ttl_hours"] == DEFAULT_CALENDAR_CACHE_TTL_HOURS


@pytest.mark.asyncio
async def test_calendar_step_normalizes_keywords_and_extends_priority():
    flow = _flow(options={"language": "it"})

    result = await flow.async_step_calendar(
        {
            "calendar_entities": "calendar.personal",
            "lookahead_days": 5,
            "cache_ttl_hours": 3,
            "calendar_keywords": {
                "vacation": "mare, ferie",
                "medical": ["dentista", " visita ", ""],
            },
            "priority_text": "medical",
        }
    )

    assert result["type"] == "menu"
    calendar = flow.options["calendar"]
    assert calendar["calendar_entities"] == ["calendar.personal"]
    assert calendar["lookahead_days"] == 5
    assert calendar["cache_ttl_hours"] == 3
    assert calendar["calendar_keywords"] == {
        "vacation": ["mare", "ferie"],
        "medical": ["dentista", "visita"],
    }
    assert calendar["category_priority"] == ["medical", "vacation"]


def test_calendar_menu_summary_falls_back_to_configured_entities():
    flow = _flow(
        options={
            "language": "en",
            "calendar": {"calendar_entities": ["calendar.personal", "calendar.work"]},
        }
    )

    assert flow._calendar_menu_summary() == "2: calendar.personal, calendar.work"


def test_calendar_menu_summary_uses_next_vacation_when_runtime_available():
    next_vacation = SimpleNamespace(summary="Summer break")
    flow = _flow(
        options={"language": "en", "calendar": {"calendar_entities": ["calendar.personal"]}}
    )
    flow.hass.data = {
        DOMAIN: {
            "entry-1": {
                "coordinator": SimpleNamespace(
                    engine=SimpleNamespace(
                        _state=SimpleNamespace(
                            calendar_result=SimpleNamespace(
                                is_vacation_active=False,
                                is_office_today=False,
                                is_wfh_today=False,
                                next_vacation=next_vacation,
                            )
                        )
                    )
                )
            }
        }
    }

    assert flow._calendar_menu_summary() == "next vacation: Summer break"


def test_init_status_block_uses_operational_security_presence_summary_when_runtime_available():
    flow = _flow(
        options={
            "language": "it",
            "security": {"enabled": True, "security_state_entity": "alarm_control_panel.home"},
        }
    )
    flow.hass.data = {
        DOMAIN: {
            "entry-1": {
                "coordinator": SimpleNamespace(
                    engine=SimpleNamespace(
                        _state=SimpleNamespace(
                            get_sensor=lambda key: 2 if key == "heima_reactions_active" else None,
                            get_sensor_attributes=lambda key: (
                                {
                                    "reactions": {
                                        "sec1": {
                                            "reaction_class": "VacationPresenceSimulationReaction",
                                            "reaction_type": "vacation_presence_simulation",
                                            "allowed_rooms": ["living"],
                                            "source_rooms": ["living"],
                                            "active_tonight": True,
                                            "blocked_reason": "",
                                            "tonight_plan_count": 2,
                                        },
                                        "sec2": {
                                            "reaction_class": "VacationPresenceSimulationReaction",
                                            "reaction_type": "vacation_presence_simulation",
                                            "allowed_rooms": ["studio"],
                                            "source_rooms": ["studio"],
                                            "active_tonight": False,
                                            "blocked_reason": "outside_not_dark",
                                            "tonight_plan_count": 0,
                                        },
                                    },
                                    "total": 2,
                                    "muted_total": 0,
                                }
                                if key == "heima_reactions_active"
                                else None
                            ),
                        )
                    )
                )
            }
        }
    }

    placeholders = flow._init_status_block()

    assert placeholders["security_summary"] == "simulazioni 2 | pronte 1 | bloccate 1"


@pytest.mark.asyncio
async def test_proposals_step_shows_guided_review_placeholders():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-1",
        analyzer_id="PresencePatternAnalyzer",
        reaction_type="presence_preheat",
        description="Wednesday: typical arrival around 12:38.",
        confidence=1.0,
        identity_key="presence_preheat|weekday=2",
        last_observed_at="2026-03-26T10:27:51.561727+00:00",
        suggested_reaction_config={
            "weekday": 2,
            "learning_diagnostics": {"observations_count": 5, "weeks_observed": 2},
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals()

    assert result["type"] == "form"
    assert result["step_id"] == "proposals"
    placeholders = result["description_placeholders"]
    assert placeholders["current_position"] == "1/1"
    assert "Mercoledì: arrivo tipico" in placeholders["proposal_label"]
    assert (
        "Pattern osservato: Wednesday: typical arrival around 12:38."
        in placeholders["proposal_details"]
    )
    assert "Evidenza: 5 osservazioni, 2 settimane" in placeholders["proposal_details"]


@pytest.mark.asyncio
async def test_proposals_step_tolerates_legacy_non_dict_config():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-legacy",
        analyzer_id="PresencePatternAnalyzer",
        reaction_type="presence_preheat",
        description="Legacy proposal",
        confidence=0.8,
        suggested_reaction_config=["bad"],  # type: ignore[arg-type]
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals()

    assert result["type"] == "form"
    placeholders = result["description_placeholders"]
    assert placeholders["proposal_label"] == "Legacy proposal"
    assert "Affidabilità: 80%" in placeholders["proposal_details"]


@pytest.mark.asyncio
async def test_proposals_step_marks_room_signal_assist_followup_as_tuning_with_bounded_diff():
    flow = _flow(
        {
            "language": "it",
            "reactions": {
                "configured": {
                    "reaction-signal-1": {
                        "reaction_class": "RoomSignalAssistReaction",
                        "room_id": "bathroom",
                        "origin": "admin_authored",
                        "source_template_id": "room.signal_assist.basic",
                        "source_proposal_identity_key": "room_signal_assist|room=bathroom|primary=room_humidity",
                        "primary_signal_name": "room_humidity",
                        "primary_bucket": "high",
                        "primary_signal_entities": ["sensor.bathroom_humidity"],
                        "corroboration_signal_name": "room_temperature",
                        "corroboration_bucket": "warm",
                        "corroboration_signal_entities": ["sensor.bathroom_temperature"],
                        "steps": [],
                    }
                }
            },
        }
    )
    proposal = ReactionProposal(
        proposal_id="proposal-signal-followup-1",
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_signal_assist",
        description="Bathroom humidity assist refined",
        confidence=0.91,
        identity_key="room_signal_assist|room=bathroom|primary=room_humidity",
        followup_kind="tuning_suggestion",
        suggested_reaction_config={
            "reaction_class": "RoomSignalAssistReaction",
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "primary_signal_entities": [
                "sensor.bathroom_humidity",
                "sensor.bathroom_humidity_aux",
            ],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "hot",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [
                {
                    "domain": "fan",
                    "target": "fan.bathroom",
                    "action": "fan.turn_on",
                    "params": {"entity_id": "fan.bathroom"},
                }
            ],
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals()

    placeholders = result["description_placeholders"]
    assert placeholders["proposal_label"].startswith(
        "Affinamento assist: Assist bathroom · humidity"
    )
    assert (
        "Tipo proposta: affinamento di una automazione esistente"
        in placeholders["proposal_details"]
    )
    assert "Automazione target: Assist bathroom" in placeholders["proposal_details"]
    assert "Template target: room.signal_assist.basic" in placeholders["proposal_details"]
    assert (
        "Bucket primario:" not in placeholders["proposal_details"]
        or "Bucket primario:  -> high" not in placeholders["proposal_details"]
    )
    assert "Entità primarie: 1 -> 2" in placeholders["proposal_details"]
    assert "Bucket corroborante: warm -> hot" in placeholders["proposal_details"]
    assert "Azioni: 0 -> 1" in placeholders["proposal_details"]


@pytest.mark.asyncio
async def test_proposals_step_marks_room_lighting_assist_followup_as_tuning_with_bounded_diff():
    flow = _flow(
        {
            "language": "it",
            "reactions": {
                "configured": {
                    "reaction-darkness-1": {
                        "reaction_class": "RoomLightingAssistReaction",
                        "room_id": "living",
                        "origin": "admin_authored",
                        "source_template_id": "room.darkness_lighting_assist.basic",
                        "source_proposal_identity_key": "room_darkness_lighting_assist|room=living|primary=room_lux",
                        "primary_signal_name": "room_lux",
                        "primary_bucket": "ok",
                        "primary_signal_entities": ["sensor.living_lux"],
                        "corroboration_signal_name": "projector",
                        "corroboration_threshold_mode": "switch_on",
                        "corroboration_threshold": 1.0,
                        "corroboration_signal_entities": ["binary_sensor.projector_power"],
                        "entity_steps": [
                            {"entity_id": "light.living_main", "action": "on", "brightness": 144}
                        ],
                    }
                }
            },
        }
    )
    proposal = ReactionProposal(
        proposal_id="proposal-darkness-followup-1",
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_darkness_lighting_assist",
        description="Living darkness assist refined",
        confidence=0.92,
        identity_key="room_darkness_lighting_assist|room=living|primary=room_lux",
        followup_kind="tuning_suggestion",
        suggested_reaction_config={
            "reaction_class": "RoomLightingAssistReaction",
            "room_id": "living",
            "primary_signal_name": "room_lux",
            "primary_bucket": "dim",
            "primary_signal_entities": ["sensor.living_lux", "sensor.living_lux_aux"],
            "corroboration_signal_name": "projector",
            "corroboration_threshold_mode": "state_change",
            "corroboration_threshold": 1.0,
            "corroboration_signal_entities": [
                "binary_sensor.projector_power",
                "binary_sensor.media_mode",
            ],
            "entity_steps": [
                {"entity_id": "light.living_main", "action": "on", "brightness": 144},
                {"entity_id": "light.living_spot", "action": "off"},
            ],
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals()

    placeholders = result["description_placeholders"]
    assert placeholders["proposal_label"].startswith("Affinamento luce: Luci living · room_lux")
    assert (
        "Template target: room.darkness_lighting_assist.basic" in placeholders["proposal_details"]
    )
    assert "Bucket: ok -> dim" in placeholders["proposal_details"]
    assert "Entità primarie: 1 -> 2" in placeholders["proposal_details"]
    assert "Modo corroborante: switch_on -> state_change" in placeholders["proposal_details"]
    assert "Entità corroboranti: 1 -> 2" in placeholders["proposal_details"]
    assert "Entità attuali: light.living_main" in placeholders["proposal_details"]
    assert (
        "Entità proposte: light.living_main, light.living_spot" in placeholders["proposal_details"]
    )
    assert "Luci: 1 -> 2" in placeholders["proposal_details"]
    assert "Entità aggiunte: light.living_spot" in placeholders["proposal_details"]


@pytest.mark.asyncio
async def test_proposals_step_marks_room_vacancy_lighting_off_followup_with_entity_diffs():
    flow = _flow(
        {
            "language": "it",
            "reactions": {
                "configured": {
                    "reaction-vacancy-1": {
                        "reaction_class": "RoomLightingVacancyOffReaction",
                        "room_id": "studio",
                        "origin": "admin_authored",
                        "source_template_id": "room.vacancy_lighting_off.basic",
                        "source_proposal_identity_key": "room_vacancy_lighting_off|room=studio",
                        "vacancy_delay_s": 300,
                        "entity_steps": [
                            {"entity_id": "light.studio_main", "action": "off"},
                        ],
                    }
                }
            },
        }
    )
    proposal = ReactionProposal(
        proposal_id="proposal-vacancy-followup-1",
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_vacancy_lighting_off",
        description="studio: vacancy lights-off assist refined",
        confidence=0.71,
        identity_key="room_vacancy_lighting_off|room=studio",
        followup_kind="tuning_suggestion",
        suggested_reaction_config={
            "reaction_class": "RoomLightingVacancyOffReaction",
            "room_id": "studio",
            "vacancy_delay_s": 420,
            "entity_steps": [
                {"entity_id": "light.studio_main", "action": "off"},
                {"entity_id": "light.studio_spot", "action": "off"},
                {"entity_id": "light.studio_desk", "action": "off"},
            ],
            "learning_diagnostics": {"episodes_observed": 35, "weeks_observed": 2},
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals()

    placeholders = result["description_placeholders"]
    assert placeholders["proposal_label"].startswith("Affinamento spegnimento luci:")
    assert (
        "Tipo proposta: affinamento di una automazione esistente"
        in placeholders["proposal_details"]
    )
    assert "Automazione target: Spegni studio dopo 5m" in placeholders["proposal_details"]
    assert "Template target: room.vacancy_lighting_off.basic" in placeholders["proposal_details"]
    assert "Ritardo spegnimento: 5 -> 7 minuti" in placeholders["proposal_details"]
    assert "Entità attuali: light.studio_main" in placeholders["proposal_details"]
    assert (
        "Entità proposte: light.studio_desk, light.studio_main, light.studio_spot"
        in placeholders["proposal_details"]
    )
    assert "Luci: 1 -> 3" in placeholders["proposal_details"]
    assert (
        "Entità aggiunte: light.studio_desk, light.studio_spot" in placeholders["proposal_details"]
    )


@pytest.mark.asyncio
async def test_proposals_step_marks_lighting_discovery_as_new_automation():
    flow = _flow({})
    proposal = ReactionProposal(
        proposal_id="proposal-lighting-new-1",
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="context_conditioned_lighting_scene",
        description="Living evening lights",
        confidence=0.88,
        identity_key="context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200",
        suggested_reaction_config={
            "reaction_class": "ContextConditionedLightingReaction",
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1200,
            "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
            "learning_diagnostics": {"observations_count": 5, "weeks_observed": 2},
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals()

    placeholders = result["description_placeholders"]
    assert "living" in placeholders["proposal_label"]
    assert "Luci coinvolte: 1" in placeholders["proposal_details"]


@pytest.mark.asyncio
async def test_proposals_step_skip_advances_to_next_proposal():
    flow = _flow()
    proposal_1 = ReactionProposal(
        proposal_id="proposal-1",
        analyzer_id="PresencePatternAnalyzer",
        reaction_type="presence_preheat",
        description="First",
        confidence=1.0,
        suggested_reaction_config={"weekday": 2},
    )
    proposal_2 = ReactionProposal(
        proposal_id="proposal-2",
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="context_conditioned_lighting_scene",
        description="Second",
        confidence=0.9,
        suggested_reaction_config={
            "room_id": "living",
            "reaction_class": "ContextConditionedLightingReaction",
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal_1, proposal_2],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "skip"})

    assert result["type"] == "form"
    assert result["step_id"] == "proposals"
    assert "living" in result["description_placeholders"]["proposal_label"]


@pytest.mark.asyncio
async def test_admin_authored_create_lists_supported_templates():
    flow = _flow({"rooms": [{"room_id": "living", "display_name": "Living", "area_id": "living"}]})

    result = await flow.async_step_admin_authored_create()

    assert result["type"] == "form"
    assert result["step_id"] == "admin_authored_create"
    assert "template_id" in result["data_schema"].schema
    options = result["data_schema"].schema["template_id"].container
    assert "scheduled_routine.basic" in options


@pytest.mark.asyncio
async def test_admin_authored_create_marks_security_presence_simulation_unavailable_without_lighting_source():
    flow = _flow({"rooms": [{"room_id": "living", "display_name": "Living", "area_id": "living"}]})

    result = await flow.async_step_admin_authored_create()

    options = result["data_schema"].schema["template_id"].container
    assert "security.vacation_presence_simulation.basic" in options
    assert "non disponibile" in options["security.vacation_presence_simulation.basic"].lower()
    assert (
        "routine luci già accettate"
        in result["description_placeholders"]["availability_notes"].lower()
    )


@pytest.mark.asyncio
async def test_admin_authored_security_presence_simulation_template_unavailable_returns_reason():
    flow = _flow({"rooms": [{"room_id": "living", "display_name": "Living", "area_id": "living"}]})

    result = await flow.async_step_admin_authored_create(
        {"template_id": "security.vacation_presence_simulation.basic"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "admin_authored_create"
    assert result["errors"] == {"base": "template_unavailable"}
    assert "profilo credibile" in result["description_placeholders"]["availability_notes"].lower()


@pytest.mark.asyncio
async def test_admin_authored_security_presence_simulation_creates_pending_proposal_when_lighting_source_exists():
    flow = _flow(
        {
            "rooms": [{"room_id": "living", "display_name": "Living", "area_id": "living"}],
            "reactions": {
                "configured": {
                    "light-src-1": {
                        "reaction_class": "ContextConditionedLightingReaction",
                        "reaction_type": "context_conditioned_lighting_scene",
                        "room_id": "living",
                        "weekday": 0,
                        "scheduled_min": 1200,
                        "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
                        "context_conditions": [
                            {"signal_name": "projector_context", "state_in": ["active"]}
                        ],
                    }
                }
            },
        }
    )

    result = await flow.async_step_admin_authored_security_presence_simulation(
        {
            "enabled": True,
            "allowed_rooms": {"living": True},
            "allowed_entities": ["light.living_main"],
            "requires_dark_outside": True,
            "simulation_aggressiveness": "medium",
            "min_jitter_override_min": 5,
            "max_jitter_override_min": 20,
            "max_events_per_evening_override": 3,
            "latest_end_time_override": "23:30",
            "skip_if_presence_detected": True,
        }
    )

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    configured = flow.options["reactions"]["configured"]
    reaction = next(
        (
            cfg
            for cfg in configured.values()
            if cfg.get("reaction_type") == "vacation_presence_simulation"
        ),
        None,
    )
    assert reaction is not None
    assert reaction["origin"] == "admin_authored"
    assert reaction["source_template_id"] == "security.vacation_presence_simulation.basic"
    assert reaction["dynamic_policy"] is True


@pytest.mark.asyncio
async def test_admin_authored_room_signal_assist_creates_pending_proposal_and_opens_review():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "bathroom",
                    "display_name": "Bathroom",
                    "area_id": "bathroom",
                    "signals": [
                        {
                            "entity_id": "sensor.bathroom_humidity",
                            "signal_name": "room_humidity",
                            "device_class": "humidity",
                            "buckets": [
                                {"label": "ok", "upper_bound": 60},
                                {"label": "high", "upper_bound": None},
                            ],
                        },
                        {
                            "entity_id": "sensor.bathroom_temperature",
                            "signal_name": "room_temperature",
                            "device_class": "temperature",
                            "buckets": [
                                {"label": "cool", "upper_bound": 22},
                                {"label": "warm", "upper_bound": None},
                            ],
                        },
                    ],
                },
            ],
            "learning": {"enabled_plugin_families": ["composite_room_assist"]},
        }
    )

    result = await flow.async_step_admin_authored_room_signal_assist(
        {
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
            "corroboration_bucket_match_mode": "gte",
            "action_entities": ["script.bathroom_ventilation"],
        }
    )

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    configured = flow.options["reactions"]["configured"]
    reaction = next(
        (cfg for cfg in configured.values() if cfg.get("reaction_type") == "room_signal_assist"),
        None,
    )
    assert reaction is not None
    assert reaction["origin"] == "admin_authored"
    assert reaction["source_template_id"] == "room.signal_assist.basic"
    assert reaction["primary_signal_entities"] == ["sensor.bathroom_humidity"]
    assert reaction["primary_signal_name"] == "room_humidity"
    assert reaction["primary_bucket"] == "high"
    assert reaction["primary_bucket_match_mode"] == "eq"
    assert reaction["corroboration_signal_entities"] == ["sensor.bathroom_temperature"]
    assert reaction["corroboration_signal_name"] == "room_temperature"
    assert reaction["corroboration_bucket"] == "warm"
    assert reaction["corroboration_bucket_match_mode"] == "gte"


@pytest.mark.asyncio
async def test_admin_authored_room_darkness_lighting_assist_creates_pending_proposal_and_opens_review():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "area_id": "studio",
                    "signals": [
                        {
                            "entity_id": "sensor.studio_lux",
                            "signal_name": "room_lux",
                            "device_class": "illuminance",
                            "buckets": [
                                {"label": "dark", "upper_bound": 30},
                                {"label": "dim", "upper_bound": 100},
                                {"label": "bright", "upper_bound": None},
                            ],
                        },
                    ],
                },
            ],
            "learning": {"enabled_plugin_families": ["composite_room_assist"]},
        }
    )

    result = await flow.async_step_admin_authored_room_darkness_lighting_assist(
        {
            "room_id": "studio",
            "primary_signal_name": "room_lux",
            "primary_bucket": "dim",
            "primary_bucket_match_mode": "eq",
            "light_entities": ["light.studio_main", "light.studio_spot"],
            "action": "on",
            "brightness": 190,
            "color_temp_kelvin": 2850,
        }
    )

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    configured = flow.options["reactions"]["configured"]
    reaction = next(
        (
            cfg
            for cfg in configured.values()
            if cfg.get("reaction_type") == "room_darkness_lighting_assist"
        ),
        None,
    )
    assert reaction is not None
    assert reaction["origin"] == "admin_authored"
    assert reaction["source_template_id"] == "room.darkness_lighting_assist.basic"
    assert reaction["primary_signal_entities"] == ["sensor.studio_lux"]
    assert reaction["primary_bucket"] == "dim"
    assert reaction["primary_bucket_match_mode"] == "eq"
    assert len(reaction["entity_steps"]) == 2


@pytest.mark.asyncio
async def test_room_darkness_lighting_create_and_edit_forms_share_common_fields():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "area_id": "studio",
                    "signals": [
                        {
                            "entity_id": "sensor.studio_lux",
                            "signal_name": "room_lux",
                            "device_class": "illuminance",
                            "buckets": [
                                {"label": "dark", "upper_bound": 30},
                                {"label": "dim", "upper_bound": 100},
                                {"label": "bright", "upper_bound": None},
                            ],
                        },
                    ],
                },
            ],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_class": "RoomLightingAssistReaction",
                        "reaction_type": "room_darkness_lighting_assist",
                        "enabled": True,
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "primary_signal_entities": ["sensor.studio_lux"],
                        "primary_bucket": "dim",
                        "primary_bucket_match_mode": "eq",
                        "entity_steps": [
                            {
                                "entity_id": "light.studio_main",
                                "action": "on",
                                "brightness": 144,
                                "color_temp_kelvin": 2900,
                                "rgb_color": None,
                            }
                        ],
                    }
                },
                "labels": {"r1": "Studio darkness"},
            },
            "learning": {"enabled_plugin_families": ["composite_room_assist"]},
        }
    )

    create_result = await flow.async_step_admin_authored_room_darkness_lighting_assist()
    flow._editing_reaction_id = "r1"
    edit_result = await flow.async_step_reactions_edit_form()

    create_keys = {str(key.schema) for key in create_result["data_schema"].schema}
    edit_keys = {str(key.schema) for key in edit_result["data_schema"].schema}

    assert {
        "primary_signal_name",
        "primary_bucket",
        "primary_bucket_match_mode",
        "light_entities",
        "action",
        "brightness",
        "color_temp_kelvin",
    } <= create_keys
    assert {
        "primary_signal_name",
        "primary_bucket",
        "primary_bucket_match_mode",
        "light_entities",
        "action",
        "brightness",
        "color_temp_kelvin",
    } <= edit_keys
    assert "room_id" in create_keys
    assert "room_id" not in edit_keys
    assert "enabled" not in create_keys
    assert "enabled" in edit_keys
    assert "delete_reaction" not in create_keys
    assert "delete_reaction" in edit_keys


@pytest.mark.asyncio
async def test_admin_authored_room_darkness_lighting_assist_allows_historical_non_pending_duplicate():
    # Con il nuovo flusso diretto non c'è più il concetto di "storico pending":
    # la reaction viene scritta direttamente in configured, quindi una seconda
    # submission con la stessa identity_key viene bloccata come duplicate.
    flow = _flow(
        {
            "rooms": [
                {"room_id": "studio", "display_name": "Studio", "area_id": "studio"},
            ],
            "learning": {"enabled_plugin_families": ["composite_room_assist"]},
        }
    )

    result = await flow.async_step_admin_authored_room_darkness_lighting_assist(
        {
            "room_id": "studio",
            "primary_signal_entities": ["sensor.studio_lux"],
            "primary_signal_name": "room_lux",
            "primary_bucket": "dim",
            "light_entities": ["light.studio_main"],
            "action": "on",
            "brightness": 190,
            "color_temp_kelvin": 2850,
        }
    )

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    configured = flow.options["reactions"]["configured"]
    assert any(
        cfg.get("reaction_type") == "room_darkness_lighting_assist" for cfg in configured.values()
    )


@pytest.mark.asyncio
async def test_admin_authored_room_darkness_lighting_assist_rejects_redacted_payload():
    flow = _flow(
        {
            "rooms": [
                {"room_id": "studio", "display_name": "Studio", "area_id": "studio"},
            ],
            "learning": {"enabled_plugin_families": ["composite_room_assist"]},
        }
    )

    result = await flow.async_step_admin_authored_room_darkness_lighting_assist(
        {
            "room_id": "studio",
            "primary_signal_entities": ["sensor.studio_lux"],
            "primary_signal_name": "room_lux",
            "primary_bucket": "dim",
            "light_entities": ["**REDACTED**"],
            "action": "on",
            "brightness": 190,
            "color_temp_kelvin": 2850,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "admin_authored_room_darkness_lighting_assist"
    # sentinel stripped before validation → empty list → "required" error (not "redacted_payload")
    assert result["errors"]["light_entities"] == "required"
    assert flow.options.get("reactions", {}).get("configured", {}) == {}


@pytest.mark.asyncio
async def test_admin_authored_room_darkness_lighting_assist_rejects_existing_configured_identity():
    flow = _flow(
        {
            "rooms": [
                {"room_id": "studio", "display_name": "Studio", "area_id": "studio"},
            ],
            "learning": {"enabled_plugin_families": ["composite_room_assist"]},
            "reactions": {
                "configured": {
                    "reaction-1": {
                        "reaction_class": "RoomLightingAssistReaction",
                        "source_proposal_identity_key": (
                            "room_darkness_lighting_assist|room=studio|primary=room_lux"
                        ),
                    }
                }
            },
        }
    )

    result = await flow.async_step_admin_authored_room_darkness_lighting_assist(
        {
            "room_id": "studio",
            "primary_signal_entities": ["sensor.studio_lux"],
            "primary_signal_name": "room_lux",
            "primary_bucket": "dim",
            "light_entities": ["light.studio_main"],
            "action": "on",
            "brightness": 190,
            "color_temp_kelvin": 2850,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "admin_authored_room_darkness_lighting_assist"
    assert result["errors"]["base"] == "duplicate"


@pytest.mark.asyncio
async def test_proposals_accept_rejects_redacted_config_payload():
    proposal = ReactionProposal(
        analyzer_id="RoomDarknessLightingAnalyzer",
        reaction_type="room_darkness_lighting_assist",
        description="studio: when room_lux drops too low, apply 1 light action",
        confidence=0.8,
        origin="learned",
        identity_key="room_darkness_lighting_assist|room=studio|primary=room_lux",
        fingerprint="room_darkness_lighting_assist|room=studio|primary=room_lux",
        suggested_reaction_config={
            "reaction_type": "room_darkness_lighting_assist",
            "room_id": "studio",
            "primary_signal_entities": ["sensor.studio_lux"],
            "primary_bucket": "dim",
            "primary_signal_name": "room_lux",
            "entity_steps": [{"entity_id": "**REDACTED**", "action": "on"}],
        },
    )
    coordinator = SimpleNamespace(
        proposal_engine=SimpleNamespace(
            pending_proposals=lambda: [proposal],
            async_accept_proposal=AsyncMock(),
            async_reject_proposal=AsyncMock(),
        )
    )
    flow = _flow(
        {
            "learning": {"enabled_plugin_families": ["composite_room_assist"]},
        }
    )
    flow.hass.data = {DOMAIN: {"entry-1": {"coordinator": coordinator}}}

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "form"
    assert result["step_id"] == "proposals"
    assert result["errors"]["base"] == "redacted_payload"
    coordinator.proposal_engine.async_accept_proposal.assert_not_awaited()
    assert flow.options.get("reactions", {}).get("configured", {}) == {}


@pytest.mark.asyncio
async def test_admin_authored_room_darkness_lighting_assist_rejects_existing_pending_identity_even_if_history_lookup_is_accepted():
    # Con il nuovo flusso diretto il duplicate check si basa su configured.
    # Equivalente del vecchio test: configured contiene già la stessa identity_key.
    flow = _flow(
        {
            "rooms": [
                {"room_id": "studio", "display_name": "Studio", "area_id": "studio"},
            ],
            "learning": {"enabled_plugin_families": ["composite_room_assist"]},
            "reactions": {
                "configured": {
                    "reaction-existing": {
                        "reaction_class": "RoomLightingAssistReaction",
                        "source_proposal_identity_key": (
                            "room_darkness_lighting_assist|room=studio|primary=room_lux"
                        ),
                    }
                }
            },
        }
    )

    result = await flow.async_step_admin_authored_room_darkness_lighting_assist(
        {
            "room_id": "studio",
            "primary_signal_entities": ["sensor.studio_lux"],
            "primary_signal_name": "room_lux",
            "primary_bucket": "dim",
            "light_entities": ["light.studio_main"],
            "action": "on",
            "brightness": 190,
            "color_temp_kelvin": 2850,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "admin_authored_room_darkness_lighting_assist"
    assert result["errors"]["base"] == "duplicate"


@pytest.mark.asyncio
async def test_admin_authored_room_vacancy_lighting_off_creates_pending_proposal_and_opens_review():
    flow = _flow(
        {
            "rooms": [
                {"room_id": "studio", "display_name": "Studio", "area_id": "studio"},
            ],
            "learning": {"enabled_plugin_families": ["composite_room_assist"]},
        }
    )

    result = await flow.async_step_admin_authored_room_vacancy_lighting_off(
        {
            "room_id": "studio",
            "light_entities": ["light.studio_main", "light.studio_spot"],
            "vacancy_delay_min": 7,
        }
    )

    assert result["type"] == "create_entry"
    configured = result["data"]["reactions"]["configured"]
    reaction = next(
        (
            cfg
            for cfg in configured.values()
            if cfg.get("reaction_type") == "room_vacancy_lighting_off"
        ),
        None,
    )
    assert reaction is not None
    assert reaction["origin"] == "admin_authored"
    assert reaction["source_template_id"] == "room.vacancy_lighting_off.basic"
    assert reaction["vacancy_delay_s"] == 420
    assert len(reaction["entity_steps"]) == 2


@pytest.mark.asyncio
async def test_admin_authored_scheduled_routine_creates_configured_reaction():
    flow = _flow()

    result = await flow.async_step_admin_authored_scheduled_routine(
        {
            "weekday": "2",
            "scheduled_time": "21:15",
            "routine_kind": "entity_action",
            "target_entities": ["switch.fountain", "input_boolean.night_mode"],
            "entity_action": "turn_off",
            "house_state_in": ["vacation"],
            "skip_if_anyone_home": True,
        }
    )

    assert result["type"] == "create_entry"
    configured = result["data"]["reactions"]["configured"]
    reaction = next(
        (cfg for cfg in configured.values() if cfg.get("reaction_type") == "scheduled_routine"),
        None,
    )
    assert reaction is not None
    assert reaction["origin"] == "admin_authored"
    assert reaction["source_template_id"] == "scheduled_routine.basic"
    assert reaction["weekday"] == 2
    assert reaction["scheduled_min"] == 21 * 60 + 15
    assert reaction["house_state_in"] == ["vacation"]
    assert reaction["skip_if_anyone_home"] is True
    assert reaction["steps"] == [
        {
            "domain": "switch",
            "target": "switch.fountain",
            "action": "switch.turn_off",
            "params": {"entity_id": "switch.fountain"},
        },
        {
            "domain": "input_boolean",
            "target": "input_boolean.night_mode",
            "action": "input_boolean.turn_off",
            "params": {"entity_id": "input_boolean.night_mode"},
        },
    ]


@pytest.mark.asyncio
async def test_admin_authored_scheduled_routine_survives_init_sync_and_save():
    flow = _flow(states=[_state("person.alex", "Alex")])
    init = await flow.async_step_init()
    assert init["type"] == "menu"

    result = await flow.async_step_admin_authored_scheduled_routine(
        {
            "weekday": "2",
            "scheduled_time": "21:15",
            "routine_kind": "entity_action",
            "target_entities": ["switch.fountain"],
            "entity_action": "turn_on",
            "house_state_in": [],
            "skip_if_anyone_home": False,
        }
    )

    assert result["type"] == "create_entry"
    configured = result["data"]["reactions"]["configured"]
    reaction = next(
        (cfg for cfg in configured.values() if cfg.get("reaction_type") == "scheduled_routine"),
        None,
    )
    assert reaction is not None
    assert reaction["source_template_id"] == "scheduled_routine.basic"
    assert reaction["steps"] == [
        {
            "domain": "switch",
            "target": "switch.fountain",
            "action": "switch.turn_on",
            "params": {"entity_id": "switch.fountain"},
        }
    ]
    assert result["data"]["people_named"][0]["slug"] == "alex"


@pytest.mark.asyncio
async def test_admin_authored_accept_persists_reaction_provenance():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-admin",
        analyzer_id="AdminAuthoredLightingTemplate",
        reaction_type="context_conditioned_lighting_scene",
        description="Admin lighting draft",
        confidence=1.0,
        origin="admin_authored",
        identity_key="context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200",
        created_at="2026-03-30T10:00:00+00:00",
        suggested_reaction_config={
            "reaction_class": "ContextConditionedLightingReaction",
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1200,
            "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
            "admin_authored_template_id": "room.darkness_lighting_assist.basic",
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["proposal-admin"]
    assert stored["origin"] == "admin_authored"
    assert stored["author_kind"] == "admin"
    assert stored["source_request"] == "template:room.darkness_lighting_assist.basic"
    assert stored["source_template_id"] == "room.darkness_lighting_assist.basic"
    assert stored["source_proposal_id"] == "proposal-admin"
    assert stored["source_proposal_identity_key"] == proposal.identity_key
    assert stored["created_at"] == "2026-03-30T10:00:00+00:00"


def test_proposal_review_label_marks_admin_authored_origin():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-admin",
        analyzer_id="AdminAuthoredLightingTemplate",
        reaction_type="context_conditioned_lighting_scene",
        description="living: Monday ~20:00 — 2 entities",
        confidence=1.0,
        origin="admin_authored",
        last_observed_at="2026-03-26T10:27:51.561727+00:00",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "reaction_class": "ContextConditionedLightingReaction",
            "admin_authored_template_id": "room.darkness_lighting_assist.basic",
        },
    )

    label = flow._proposal_review_label(proposal)

    assert "[admin | 100% | seen 2026-03-26]" in label


@pytest.mark.asyncio
async def test_admin_authored_room_signal_assist_accept_skips_action_configuration():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-room-signal-admin",
        analyzer_id="AdminAuthoredRoomSignalAssistTemplate",
        reaction_type="room_signal_assist",
        description="bathroom: when humidity changes quickly, trigger 1 action",
        confidence=1.0,
        origin="admin_authored",
        suggested_reaction_config={
            "reaction_class": "RoomSignalAssistReaction",
            "room_id": "bathroom",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
            "steps": [
                {
                    "domain": "script",
                    "target": "script.bathroom_ventilation",
                    "action": "script.turn_on",
                    "params": {"entity_id": "script.bathroom_ventilation"},
                }
            ],
            "admin_authored_template_id": "room.signal_assist.basic",
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    stored = flow.options["reactions"]["configured"]["proposal-room-signal-admin"]
    assert stored["origin"] == "admin_authored"
    assert stored["source_template_id"] == "room.signal_assist.basic"
    assert stored["steps"][0]["action"] == "script.turn_on"


@pytest.mark.asyncio
async def test_admin_authored_room_darkness_lighting_assist_accept_skips_action_configuration():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-room-darkness-admin",
        analyzer_id="AdminAuthoredRoomDarknessLightingTemplate",
        reaction_type="room_darkness_lighting_assist",
        description="studio: when room_lux drops too low, apply 2 light actions",
        confidence=1.0,
        origin="admin_authored",
        suggested_reaction_config={
            "reaction_class": "RoomLightingAssistReaction",
            "room_id": "studio",
            "primary_signal_entities": ["sensor.studio_lux"],
            "primary_signal_name": "room_lux",
            "primary_bucket": "ok",
            "entity_steps": [
                {"entity_id": "light.studio_main", "action": "on", "brightness": 190},
                {"entity_id": "light.studio_spot", "action": "on", "brightness": 160},
            ],
            "admin_authored_template_id": "room.darkness_lighting_assist.basic",
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    stored = flow.options["reactions"]["configured"]["proposal-room-darkness-admin"]
    assert stored["origin"] == "admin_authored"
    assert stored["source_template_id"] == "room.darkness_lighting_assist.basic"
    assert len(stored["entity_steps"]) == 2


@pytest.mark.asyncio
async def test_admin_authored_room_vacancy_lighting_off_accept_skips_action_configuration():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-room-vacancy-admin",
        analyzer_id="AdminAuthoredRoomVacancyLightingOffTemplate",
        reaction_type="room_vacancy_lighting_off",
        description="studio: when vacancy persists for 7 minutes, turn off 2 lights",
        confidence=1.0,
        origin="admin_authored",
        suggested_reaction_config={
            "reaction_class": "RoomLightingVacancyOffReaction",
            "room_id": "studio",
            "vacancy_delay_s": 420,
            "entity_steps": [
                {"entity_id": "light.studio_main", "action": "off"},
                {"entity_id": "light.studio_spot", "action": "off"},
            ],
            "admin_authored_template_id": "room.vacancy_lighting_off.basic",
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    stored = flow.options["reactions"]["configured"]["proposal-room-vacancy-admin"]
    assert stored["origin"] == "admin_authored"
    assert stored["source_template_id"] == "room.vacancy_lighting_off.basic"
    assert stored["reaction_type"] == "room_vacancy_lighting_off"
    assert stored["vacancy_delay_s"] == 420


@pytest.mark.asyncio
async def test_admin_authored_security_presence_simulation_accept_skips_action_configuration():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-security-presence-admin",
        analyzer_id="AdminAuthoredSecurityPresenceSimulationTemplate",
        reaction_type="vacation_presence_simulation",
        description="Vacation presence simulation using learned lighting routines as source profile",
        confidence=1.0,
        origin="admin_authored",
        suggested_reaction_config={
            "reaction_class": "VacationPresenceSimulationReaction",
            "enabled": True,
            "allowed_rooms": ["living"],
            "requires_dark_outside": False,
            "simulation_aggressiveness": "medium",
            "skip_if_presence_detected": True,
            "dynamic_policy": True,
            "source_profile_kind": "accepted_lighting_reactions",
            "admin_authored_template_id": "security.vacation_presence_simulation.basic",
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    stored = flow.options["reactions"]["configured"]["proposal-security-presence-admin"]
    assert stored["origin"] == "admin_authored"
    assert stored["source_template_id"] == "security.vacation_presence_simulation.basic"
    assert stored["reaction_type"] == "vacation_presence_simulation"
    assert stored["dynamic_policy"] is True


@pytest.mark.asyncio
async def test_proposal_configure_action_resumes_guided_review():
    flow = _flow()
    proposal_1 = ReactionProposal(
        proposal_id="proposal-1",
        analyzer_id="PresencePatternAnalyzer",
        reaction_type="presence_preheat",
        description="Arrival proposal",
        confidence=1.0,
        suggested_reaction_config={
            "reaction_class": "PresencePatternReaction",
            "weekday": 0,
            "median_arrival_min": 480,
            "steps": [],
        },
    )
    proposal_2 = ReactionProposal(
        proposal_id="proposal-2",
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="context_conditioned_lighting_scene",
        description="Living lights",
        confidence=0.9,
        suggested_reaction_config={
            "reaction_class": "ContextConditionedLightingReaction",
            "room_id": "living",
            "weekday": 0,
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal_1, proposal_2],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }
    flow._proposal_review_queue = ["proposal-1", "proposal-2"]

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "form"
    assert result["step_id"] == "proposal_configure_action"
    assert proposal_engine.async_accept_proposal.await_count == 0
    assert flow.options.get("reactions", {}).get("configured", {}) == {}

    resumed = await flow.async_step_proposal_configure_action(
        {
            "action_entities": ["scene.arrival"],
            "pre_condition_min": 15,
        }
    )

    assert resumed["type"] == "form"
    assert resumed["step_id"] == "proposals"
    assert "living" in resumed["description_placeholders"]["proposal_label"]
    proposal_engine.async_accept_proposal.assert_awaited_once_with("proposal-1")
    stored = flow.options["reactions"]["configured"]["proposal-1"]
    assert stored["pre_condition_min"] == 15
    assert stored["steps"] == [
        {
            "domain": "lighting",
            "target": "scene.arrival",
            "action": "scene.turn_on",
            "params": {"entity_id": "scene.arrival"},
        }
    ]


@pytest.mark.asyncio
async def test_proposal_configure_action_rejects_redacted_payload_without_accepting_proposal():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-redacted",
        analyzer_id="PresencePatternAnalyzer",
        reaction_type="presence_preheat",
        description="Arrival proposal",
        confidence=1.0,
        suggested_reaction_config={
            "reaction_class": "PresencePatternReaction",
            "weekday": 0,
            "median_arrival_min": 480,
            "steps": [],
        },
    )
    proposal_engine = SimpleNamespace(
        async_accept_proposal=AsyncMock(),
    )
    flow.hass.data = {
        DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}
    }
    flow._pending_action_drafts = [
        {
            "proposal": proposal,
            "proposal_id": "proposal-redacted",
            "target_id": "proposal-redacted",
            "existing_config": {"source_proposal_identity_key": "**REDACTED**"},
            "label": "Arrival proposal",
        }
    ]

    result = await flow.async_step_proposal_configure_action(
        {
            "action_entities": ["scene.arrival"],
            "pre_condition_min": 15,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "proposal_configure_action"
    assert result["errors"]["base"] == "redacted_payload"
    proposal_engine.async_accept_proposal.assert_not_awaited()
    assert flow.options.get("reactions", {}).get("configured", {}) == {}


@pytest.mark.asyncio
async def test_reactions_edit_form_for_room_lighting_assist_uses_lux_and_light_fields():
    flow = _flow(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_class": "RoomLightingAssistReaction",
                        "reaction_type": "room_darkness_lighting_assist",
                        "enabled": True,
                        "room_id": "studio",
                        "primary_signal_entities": ["sensor.studio_lux"],
                        "primary_bucket": "dim",
                        "entity_steps": [
                            {
                                "entity_id": "light.studio_main",
                                "action": "on",
                                "brightness": 144,
                                "color_temp_kelvin": 2900,
                                "rgb_color": None,
                            }
                        ],
                    }
                },
                "labels": {"r1": "Studio darkness"},
            }
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form()

    assert result["type"] == "form"
    assert result["step_id"] == "reactions_edit_form"
    schema_keys = {str(key.schema) for key in result["data_schema"].schema}
    assert "primary_signal_name" in schema_keys
    assert "primary_bucket" in schema_keys
    assert "primary_bucket_match_mode" in schema_keys
    assert "light_entities" in schema_keys
    assert "action" in schema_keys
    assert "primary_signal_entities" not in schema_keys
    assert "pre_condition_min" not in schema_keys
    assert "action_entities" not in schema_keys


@pytest.mark.asyncio
async def test_reactions_edit_form_returns_init_when_reaction_missing():
    flow = _flow({"reactions": {"configured": {}, "labels": {}}})
    flow._editing_reaction_id = "missing"

    result = await flow.async_step_reactions_edit_form()

    assert result["type"] == "menu"
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_reactions_edit_form_updates_room_lighting_assist_config():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "area_id": "studio",
                    "signals": [
                        {
                            "entity_id": "sensor.studio_lux",
                            "signal_name": "room_lux",
                            "device_class": "illuminance",
                            "buckets": [
                                {"label": "dark", "upper_bound": 30},
                                {"label": "dim", "upper_bound": 100},
                                {"label": "bright", "upper_bound": None},
                            ],
                        },
                    ],
                },
            ],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_class": "RoomLightingAssistReaction",
                        "reaction_type": "room_darkness_lighting_assist",
                        "enabled": True,
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "primary_signal_entities": ["sensor.studio_lux"],
                        "primary_bucket": "dim",
                        "primary_bucket_match_mode": "eq",
                        "entity_steps": [
                            {
                                "entity_id": "light.studio_main",
                                "action": "on",
                                "brightness": 144,
                                "color_temp_kelvin": 2900,
                                "rgb_color": None,
                            }
                        ],
                    }
                },
                "labels": {"r1": "Studio darkness"},
            },
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": False,
            "primary_signal_name": "room_lux",
            "primary_bucket": "dark",
            "primary_bucket_match_mode": "lte",
            "light_entities": ["light.studio_main", "light.studio_spot"],
            "action": "on",
            "brightness": 180,
            "color_temp_kelvin": 3000,
            "delete_reaction": False,
        }
    )

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["enabled"] is False
    # entity derived from room.signals[room_lux].entity_id
    assert stored["primary_signal_entities"] == ["sensor.studio_lux"]
    assert stored["primary_bucket"] == "dark"
    assert stored["primary_bucket_match_mode"] == "lte"
    assert stored["entity_steps"] == [
        {
            "entity_id": "light.studio_main",
            "action": "on",
            "brightness": 180,
            "color_temp_kelvin": 3000,
            "rgb_color": None,
        },
        {
            "entity_id": "light.studio_spot",
            "action": "on",
            "brightness": 180,
            "color_temp_kelvin": 3000,
            "rgb_color": None,
        },
    ]


@pytest.mark.asyncio
async def test_reactions_edit_form_can_delete_configured_reaction_and_unmute_it():
    flow = _flow(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_class": "ContextConditionedLightingReaction",
                        "reaction_type": "context_conditioned_lighting_scene",
                        "enabled": True,
                        "steps": [{"service": "scene.turn_on", "target": "scene.relax"}],
                        "pre_condition_min": 20,
                    }
                },
                "labels": {"r1": "Living lights"},
                "muted": ["r1"],
            }
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "action_entities": [],
            "pre_condition_min": 20,
            "delete_reaction": True,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reactions_delete_confirm"

    confirmed = await flow.async_step_reactions_delete_confirm({"confirm": True})

    assert confirmed["type"] == "menu"
    assert confirmed["step_id"] == "init"
    assert "r1" not in flow.options["reactions"]["configured"]
    assert "r1" not in flow.options["reactions"]["labels"]
    assert "r1" not in flow.options["reactions"]["muted"]


@pytest.mark.asyncio
async def test_lighting_zone_remove_requires_confirmation():
    flow = _flow(
        {
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "occupancy_mode": "none",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "logic": "any_of",
                }
            ],
            "lighting_zones": [
                {"zone_id": "living_zone", "display_name": "Living Zone", "rooms": ["living"]}
            ],
        }
    )

    result = await flow.async_step_lighting_zones_remove({"zone": "living_zone"})

    assert result["type"] == "form"
    assert result["step_id"] == "lighting_zones_remove_confirm"

    confirmed = await flow.async_step_lighting_zones_remove_confirm({"confirm": True})

    assert confirmed["type"] == "menu"
    assert flow.options["lighting_zones"] == []


def test_init_status_block_includes_pending_proposals_summary(monkeypatch):
    flow = _flow()
    monkeypatch.setattr(flow, "_proposal_review_summary", lambda: "3")
    monkeypatch.setattr(flow, "_tuning_pending_summary", lambda: "1")
    monkeypatch.setattr(
        flow, "_composite_menu_summary", lambda: "stanze 2 | attive 1 | review 1 | tuning 1"
    )

    placeholders = flow._init_status_block()

    assert placeholders["proposal_review_summary"] == "3"
    assert placeholders["tuning_pending_summary"] == "1"
    assert placeholders["composite_summary"] == "stanze 2 | attive 1 | review 1 | tuning 1"


def test_tuning_pending_summary_counts_followup_proposals():
    flow = _flow()
    flow._pending_proposals = lambda: [
        ReactionProposal(
            proposal_id="p1",
            analyzer_id="LightingPatternAnalyzer",
            reaction_type="context_conditioned_lighting_scene",
            description="new schedule",
            confidence=1.0,
            suggested_reaction_config={},
        ),
        ReactionProposal(
            proposal_id="p2",
            analyzer_id="LightingPatternAnalyzer",
            reaction_type="context_conditioned_lighting_scene",
            description="tuning schedule",
            confidence=1.0,
            followup_kind="tuning_suggestion",
            suggested_reaction_config={},
        ),
    ]

    assert flow._proposal_review_summary() == "2"
    assert flow._tuning_pending_summary() == "1"


def test_lighting_menu_summary_is_operational() -> None:
    flow = _flow(
        {
            "rooms": [
                {"room_id": "living", "display_name": "Living"},
                {"room_id": "studio", "display_name": "Studio"},
                {"room_id": "bathroom", "display_name": "Bathroom"},
            ],
            "lighting_rooms": [
                {"room_id": "living", "enable_manual_hold": True},
                {"room_id": "studio", "enable_manual_hold": True},
            ],
            "reactions": {
                "configured": {
                    "r-light-1": {
                        "reaction_class": "ContextConditionedLightingReaction",
                        "reaction_type": "context_conditioned_lighting_scene",
                        "room_id": "living",
                        "weekday": 0,
                        "scheduled_min": 1200,
                    },
                    "r-signal-1": {
                        "reaction_class": "RoomSignalAssistReaction",
                        "room_id": "bathroom",
                    },
                }
            },
            "language": "it",
        }
    )
    flow._pending_proposals = lambda: [
        ReactionProposal(
            proposal_id="p1",
            analyzer_id="LightingPatternAnalyzer",
            reaction_type="context_conditioned_lighting_scene",
            description="new schedule",
            confidence=1.0,
            suggested_reaction_config={},
        ),
        ReactionProposal(
            proposal_id="p2",
            analyzer_id="LightingPatternAnalyzer",
            reaction_type="context_conditioned_lighting_scene",
            description="tuning schedule",
            confidence=1.0,
            followup_kind="tuning_suggestion",
            suggested_reaction_config={},
        ),
    ]

    assert flow._lighting_menu_summary() == "2/3 stanze | attive 1 | review 2 | tuning 1"


def test_composite_menu_summary_is_operational() -> None:
    flow = _flow(
        {
            "reactions": {
                "configured": {
                    "r-signal-1": {
                        "reaction_class": "RoomSignalAssistReaction",
                        "room_id": "bathroom",
                        "reaction_type": "room_signal_assist",
                    },
                    "r-light-1": {
                        "reaction_class": "RoomLightingAssistReaction",
                        "source_proposal_identity_key": "room_darkness_lighting_assist|room=living|primary=room_lux",
                    },
                    "r-other": {
                        "reaction_class": "ContextConditionedLightingReaction",
                        "reaction_type": "context_conditioned_lighting_scene",
                        "room_id": "living",
                    },
                }
            },
            "language": "it",
        }
    )
    flow._pending_proposals = lambda: [
        ReactionProposal(
            proposal_id="p1",
            analyzer_id="CompositePatternCatalogAnalyzer",
            reaction_type="room_signal_assist",
            description="new assist",
            confidence=1.0,
            suggested_reaction_config={},
        ),
        ReactionProposal(
            proposal_id="p2",
            analyzer_id="CompositePatternCatalogAnalyzer",
            reaction_type="room_darkness_lighting_assist",
            description="tuning assist",
            confidence=1.0,
            followup_kind="tuning_suggestion",
            suggested_reaction_config={},
        ),
        ReactionProposal(
            proposal_id="p3",
            analyzer_id="LightingPatternAnalyzer",
            reaction_type="context_conditioned_lighting_scene",
            description="lighting",
            confidence=1.0,
            suggested_reaction_config={},
        ),
    ]

    assert flow._composite_menu_summary() == "stanze 2 | attive 2 | review 2 | tuning 1"


def test_signal_threshold_mode_options_include_binary_transitions():
    flow = _flow()

    options = flow._signal_threshold_mode_options()

    assert "switch_on" in options
    assert "switch_off" in options
    assert "state_change" in options


# ---- room_signal_assist edit form ----


def _flow_with_rooms(reactions: dict | None = None) -> "HeimaOptionsFlowHandler":
    """Flow with rooms and people_named set so _sync_ha_backed_bindings stays silent."""
    return _flow(
        {
            "people_named": [],
            "rooms": [_room_with_signals()],
            "reactions": reactions or {},
        }
    )


def _room_with_signals() -> dict:
    return {
        "room_id": "studio",
        "display_name": "Studio",
        "occupancy_mode": "derived",
        "occupancy_sources": ["binary_sensor.studio_motion"],
        # reconciliation fields pre-populated so _sync_ha_backed_bindings stays silent
        "source": "ha_area_registry",
        "ha_sync_status": "orphaned",
        "signals": [
            {
                "entity_id": "sensor.studio_humidity",
                "signal_name": "room_humidity",
                "device_class": "humidity",
                "buckets": [
                    {"label": "low", "upper_bound": 40.0},
                    {"label": "ok", "upper_bound": 70.0},
                    {"label": "high", "upper_bound": None},
                ],
            },
            {
                "entity_id": "sensor.studio_temperature",
                "signal_name": "room_temperature",
                "device_class": "temperature",
                "buckets": [
                    {"label": "cool", "upper_bound": 20.0},
                    {"label": "ok", "upper_bound": 24.0},
                    {"label": "warm", "upper_bound": 27.0},
                    {"label": "hot", "upper_bound": None},
                ],
            },
        ],
    }


@pytest.mark.asyncio
async def test_reactions_edit_form_for_room_signal_assist_shows_bucket_fields():
    flow = _flow(
        {
            "rooms": [_room_with_signals()],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_signal_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_humidity",
                        "primary_bucket": "high",
                        "primary_signal_entities": ["sensor.studio_humidity"],
                        "steps": [
                            {"domain": "scene", "target": "scene.relax", "action": "scene.turn_on"}
                        ],
                        "enabled": True,
                    }
                },
                "labels": {"r1": "Studio humidity assist"},
            },
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form()

    assert result["type"] == "form"
    assert result["step_id"] == "reactions_edit_form"
    schema_keys = {str(key.schema) for key in result["data_schema"].schema}
    assert "primary_signal_name" in schema_keys
    assert "primary_bucket" in schema_keys
    assert "primary_bucket_match_mode" in schema_keys
    assert "corroboration_signal_name" in schema_keys
    assert "corroboration_bucket" in schema_keys
    assert "corroboration_bucket_match_mode" in schema_keys
    assert "action_entities" in schema_keys
    assert "primary_signal_entities" not in schema_keys


@pytest.mark.asyncio
async def test_reactions_edit_form_for_room_air_quality_assist_uses_same_handler():
    flow = _flow(
        {
            "rooms": [_room_with_signals()],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_air_quality_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_humidity",
                        "primary_bucket": "high",
                        "primary_signal_entities": ["sensor.studio_humidity"],
                        "steps": [],
                        "enabled": True,
                    }
                },
                "labels": {},
            },
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form()

    assert result["type"] == "form"
    schema_keys = {str(key.schema) for key in result["data_schema"].schema}
    assert "primary_signal_name" in schema_keys
    assert "primary_bucket" in schema_keys


@pytest.mark.asyncio
async def test_reactions_edit_form_room_signal_assist_saves_with_derived_entity():
    flow = _flow_with_rooms(
        {
            "configured": {
                "r1": {
                    "reaction_type": "room_signal_assist",
                    "room_id": "studio",
                    "primary_signal_name": "room_humidity",
                    "primary_bucket": "ok",
                    "primary_bucket_match_mode": "eq",
                    "primary_signal_entities": ["sensor.studio_humidity"],
                    "steps": [],
                    "enabled": True,
                }
            },
            "labels": {},
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": False,
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "primary_bucket_match_mode": "gte",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": ["scene.relax"],
            "delete_reaction": False,
        }
    )

    assert result["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["enabled"] is False
    assert stored["primary_bucket"] == "high"
    assert stored["primary_bucket_match_mode"] == "gte"
    assert stored["primary_signal_name"] == "room_humidity"
    assert stored["primary_signal_entities"] == ["sensor.studio_humidity"]
    assert "primary_threshold" not in stored


@pytest.mark.asyncio
async def test_reactions_edit_form_room_signal_assist_rejects_invalid_signal_name():
    flow = _flow(
        {
            "rooms": [_room_with_signals()],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_signal_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_humidity",
                        "primary_bucket": "high",
                        "primary_signal_entities": ["sensor.studio_humidity"],
                        "steps": [],
                        "enabled": True,
                    }
                },
                "labels": {},
            },
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "primary_signal_name": "room_co2",
            "primary_bucket": "high",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": ["scene.relax"],
            "delete_reaction": False,
        }
    )

    assert result["type"] == "form"
    assert result["errors"].get("primary_signal_name") == "invalid_signal_name"


@pytest.mark.asyncio
async def test_reactions_edit_form_room_signal_assist_rejects_invalid_bucket():
    flow = _flow(
        {
            "rooms": [_room_with_signals()],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_signal_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_humidity",
                        "primary_bucket": "high",
                        "primary_signal_entities": ["sensor.studio_humidity"],
                        "steps": [],
                        "enabled": True,
                    }
                },
                "labels": {},
            },
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "primary_signal_name": "room_humidity",
            "primary_bucket": "medium",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": ["scene.relax"],
            "delete_reaction": False,
        }
    )

    assert result["type"] == "form"
    assert result["errors"].get("primary_bucket") == "invalid_bucket"


@pytest.mark.asyncio
async def test_reactions_edit_form_room_signal_assist_with_valid_corroboration():
    flow = _flow_with_rooms(
        {
            "configured": {
                "r1": {
                    "reaction_type": "room_signal_assist",
                    "room_id": "studio",
                    "primary_signal_name": "room_humidity",
                    "primary_bucket": "high",
                    "primary_bucket_match_mode": "eq",
                    "primary_signal_entities": ["sensor.studio_humidity"],
                    "steps": [],
                    "enabled": True,
                }
            },
            "labels": {},
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
            "corroboration_bucket_match_mode": "gte",
            "action_entities": ["scene.relax"],
            "delete_reaction": False,
        }
    )

    assert result["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["corroboration_signal_name"] == "room_temperature"
    assert stored["corroboration_bucket"] == "warm"
    assert stored["corroboration_bucket_match_mode"] == "gte"
    assert stored["corroboration_signal_entities"] == ["sensor.studio_temperature"]


# ---- admin_authored_room_signal_assist create form ----


@pytest.mark.asyncio
async def test_admin_authored_room_signal_assist_no_entity_selector_in_schema():
    flow = _flow({"rooms": [_room_with_signals()]})

    result = await flow.async_step_admin_authored_room_signal_assist()

    assert result["type"] == "form"
    schema_keys = {str(key.schema) for key in result["data_schema"].schema}
    assert "primary_signal_name" in schema_keys
    assert "primary_bucket" in schema_keys
    assert "primary_bucket_match_mode" in schema_keys
    assert "corroboration_bucket_match_mode" in schema_keys
    assert "primary_signal_entities" not in schema_keys
    assert "corroboration_signal_entities" not in schema_keys


@pytest.mark.asyncio
async def test_room_signal_assist_create_and_edit_forms_share_common_fields():
    flow = _flow_with_rooms(
        {
            "configured": {
                "r1": {
                    "reaction_type": "room_signal_assist",
                    "room_id": "studio",
                    "primary_signal_name": "room_humidity",
                    "primary_trigger_mode": "bucket",
                    "primary_bucket": "high",
                    "primary_bucket_match_mode": "eq",
                    "primary_signal_entities": ["sensor.studio_humidity"],
                    "steps": [
                        {"domain": "scene", "target": "scene.relax", "action": "scene.turn_on"}
                    ],
                    "enabled": True,
                }
            },
            "labels": {"r1": "Studio humidity assist"},
        }
    )

    create_result = await flow.async_step_admin_authored_room_signal_assist()
    flow._editing_reaction_id = "r1"
    edit_result = await flow.async_step_reactions_edit_form()

    create_keys = {str(key.schema) for key in create_result["data_schema"].schema}
    edit_keys = {str(key.schema) for key in edit_result["data_schema"].schema}

    assert {
        "primary_signal_name",
        "primary_trigger_mode",
        "primary_bucket",
        "primary_bucket_match_mode",
        "corroboration_signal_name",
        "corroboration_bucket",
        "corroboration_bucket_match_mode",
        "action_entities",
    } <= create_keys
    assert {
        "primary_signal_name",
        "primary_trigger_mode",
        "primary_bucket",
        "primary_bucket_match_mode",
        "corroboration_signal_name",
        "corroboration_bucket",
        "corroboration_bucket_match_mode",
        "action_entities",
    } <= edit_keys
    assert "room_id" in create_keys
    assert "room_id" not in edit_keys
    assert "enabled" not in create_keys
    assert "enabled" in edit_keys
    assert "delete_reaction" not in create_keys
    assert "delete_reaction" in edit_keys


@pytest.mark.asyncio
async def test_room_cooling_assist_edit_uses_signal_editor_fields():
    flow = _flow_with_rooms(
        {
            "configured": {
                "r1": {
                    "reaction_type": "room_cooling_assist",
                    "room_id": "studio",
                    "primary_signal_name": "room_temperature",
                    "primary_trigger_mode": "burst",
                    "primary_signal_entities": ["sensor.studio_temperature"],
                    "steps": [
                        {
                            "domain": "switch",
                            "target": "switch.studio_fan",
                            "action": "switch.turn_on",
                        }
                    ],
                    "enabled": True,
                }
            },
            "labels": {"r1": "Studio cooling assist"},
        }
    )

    flow._editing_reaction_id = "r1"
    result = await flow.async_step_reactions_edit_form()

    schema_keys = {str(key.schema) for key in result["data_schema"].schema}
    assert "primary_signal_name" in schema_keys
    assert "primary_trigger_mode" in schema_keys
    assert "action_entities" in schema_keys
    assert "pre_condition_min" not in schema_keys


@pytest.mark.asyncio
async def test_room_vacancy_lighting_off_edit_uses_delay_field_and_updates_delay():
    flow = _flow(
        {
            "rooms": [
                {"room_id": "studio", "display_name": "Studio", "area_id": "studio"},
            ],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_vacancy_lighting_off",
                        "enabled": True,
                        "room_id": "studio",
                        "vacancy_delay_s": 420,
                        "entity_steps": [
                            {"entity_id": "light.studio_main", "action": "off"},
                        ],
                    }
                },
                "labels": {"r1": "Spegni studio dopo 7m"},
            },
        }
    )

    flow._editing_reaction_id = "r1"
    result = await flow.async_step_reactions_edit_form()

    schema_keys = {str(key.schema) for key in result["data_schema"].schema}
    assert "vacancy_delay_min" in schema_keys
    assert "light_entities" in schema_keys
    assert "pre_condition_min" not in schema_keys
    assert "action_entities" not in schema_keys

    saved = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "light_entities": ["light.studio_main", "light.studio_spot"],
            "vacancy_delay_min": 11,
            "delete_reaction": False,
        }
    )

    assert saved["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["vacancy_delay_s"] == 660
    assert [step["entity_id"] for step in stored["entity_steps"]] == [
        "light.studio_main",
        "light.studio_spot",
    ]


@pytest.mark.asyncio
async def test_vacation_presence_simulation_edit_uses_real_contract_fields():
    flow = _flow(
        {
            "rooms": [
                {"room_id": "living", "display_name": "Living", "area_id": "living"},
                {"room_id": "studio", "display_name": "Studio", "area_id": "studio"},
            ],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "vacation_presence_simulation",
                        "enabled": True,
                        "allowed_rooms": ["living"],
                        "allowed_entities": ["light.living_main"],
                        "requires_dark_outside": True,
                        "simulation_aggressiveness": "medium",
                        "min_jitter_override_min": 5,
                        "max_jitter_override_min": 15,
                        "max_events_per_evening_override": 4,
                        "latest_end_time_override": "23:15",
                        "skip_if_presence_detected": True,
                        "dynamic_policy": True,
                        "source_profile_kind": "accepted_lighting_reactions",
                    }
                },
                "labels": {"r1": "Vacation presence simulation"},
            },
        }
    )

    flow._editing_reaction_id = "r1"
    result = await flow.async_step_reactions_edit_form()

    schema_keys = {str(key.schema) for key in result["data_schema"].schema}
    assert {
        "allowed_rooms",
        "allowed_entities",
        "requires_dark_outside",
        "simulation_aggressiveness",
        "latest_end_time_override",
    } <= schema_keys
    assert "pre_condition_min" not in schema_keys
    assert "action_entities" not in schema_keys

    saved = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "allowed_rooms": ["living", "studio"],
            "allowed_entities": ["light.living_main", "light.studio_main"],
            "requires_dark_outside": False,
            "simulation_aggressiveness": "high",
            "min_jitter_override_min": 3,
            "max_jitter_override_min": 9,
            "max_events_per_evening_override": 5,
            "latest_end_time_override": "22:45",
            "skip_if_presence_detected": False,
            "delete_reaction": False,
        }
    )

    assert saved["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["allowed_rooms"] == ["living", "studio"]
    assert stored["requires_dark_outside"] is False
    assert stored["simulation_aggressiveness"] == "high"
    assert stored["latest_end_time_override"] == "22:45"
    assert stored["skip_if_presence_detected"] is False


@pytest.mark.asyncio
async def test_scheduled_routine_edit_uses_real_contract_fields_and_updates_config():
    flow = _flow(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "scheduled_routine",
                        "enabled": True,
                        "weekday": 2,
                        "scheduled_min": 21 * 60 + 15,
                        "window_half_min": 0,
                        "routine_kind": "entity_action",
                        "target_entities": ["switch.fountain"],
                        "entity_action": "turn_off",
                        "house_state_in": ["vacation"],
                        "skip_if_anyone_home": True,
                        "steps": [
                            {
                                "domain": "switch",
                                "target": "switch.fountain",
                                "action": "switch.turn_off",
                                "params": {"entity_id": "switch.fountain"},
                            }
                        ],
                    }
                },
                "labels": {"r1": "Routine Wednesday ~21:15"},
            },
        }
    )

    flow._editing_reaction_id = "r1"
    result = await flow.async_step_reactions_edit_form()

    schema_keys = {str(key.schema) for key in result["data_schema"].schema}
    assert {
        "weekday",
        "scheduled_time",
        "routine_kind",
        "target_entities",
        "entity_action",
        "house_state_in",
        "skip_if_anyone_home",
    } <= schema_keys
    assert "pre_condition_min" not in schema_keys
    assert "action_entities" not in schema_keys

    saved = await flow.async_step_reactions_edit_form(
        {
            "enabled": False,
            "weekday": "4",
            "scheduled_time": "22:30",
            "routine_kind": "scene",
            "target_entities": ["scene.movie_time"],
            "entity_action": "turn_on",
            "house_state_in": ["home", "guest"],
            "skip_if_anyone_home": False,
            "delete_reaction": False,
        }
    )

    assert saved["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["enabled"] is False
    assert stored["weekday"] == 4
    assert stored["scheduled_min"] == 22 * 60 + 30
    assert stored["routine_kind"] == "scene"
    assert stored["target_entities"] == ["scene.movie_time"]
    assert stored["house_state_in"] == ["home", "guest"]
    assert stored["skip_if_anyone_home"] is False
    assert stored["steps"] == [
        {
            "domain": "scene",
            "target": "scene.movie_time",
            "action": "scene.turn_on",
            "params": {"entity_id": "scene.movie_time"},
        }
    ]


@pytest.mark.asyncio
async def test_admin_authored_room_signal_assist_rejects_unknown_signal():
    flow = _flow({"rooms": [_room_with_signals()]})

    result = await flow.async_step_admin_authored_room_signal_assist(
        {
            "room_id": "studio",
            "primary_signal_name": "room_co2",
            "primary_bucket": "high",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": ["scene.relax"],
        }
    )

    assert result["type"] == "form"
    assert result["errors"].get("primary_signal_name") == "invalid_signal_name"


@pytest.mark.asyncio
async def test_admin_authored_room_signal_assist_rejects_unknown_bucket():
    flow = _flow({"rooms": [_room_with_signals()]})

    result = await flow.async_step_admin_authored_room_signal_assist(
        {
            "room_id": "studio",
            "primary_signal_name": "room_humidity",
            "primary_bucket": "medium",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": ["scene.relax"],
        }
    )

    assert result["type"] == "form"
    assert result["errors"].get("primary_bucket") == "invalid_bucket"


@pytest.mark.asyncio
async def test_admin_authored_room_signal_assist_derives_entity_from_room_signals():
    flow = _flow_with_rooms()

    result = await flow.async_step_admin_authored_room_signal_assist(
        {
            "room_id": "studio",
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "primary_bucket_match_mode": "lte",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": ["scene.relax"],
        }
    )

    assert result["type"] == "menu"
    configured = flow.options["reactions"]["configured"]
    assert len(configured) == 1
    stored = next(iter(configured.values()))
    assert stored["primary_signal_entities"] == ["sensor.studio_humidity"]
    assert stored["primary_bucket"] == "high"
    assert stored["primary_bucket_match_mode"] == "lte"
    assert stored["reaction_type"] == "room_signal_assist"


@pytest.mark.asyncio
async def test_admin_authored_room_contextual_lighting_assist_persists_guided_json_contract():
    room = dict(_room_with_signals())
    room["signals"] = list(room["signals"]) + [
        {
            "entity_id": "sensor.studio_lux",
            "signal_name": "room_lux",
            "device_class": "illuminance",
            "buckets": [
                {"label": "dark", "upper_bound": 30.0},
                {"label": "dim", "upper_bound": 100.0},
                {"label": "ok", "upper_bound": 250.0},
                {"label": "bright", "upper_bound": None},
            ],
        }
    ]
    flow = _flow({"people_named": [], "rooms": [room], "reactions": {}})

    result = await flow.async_step_admin_authored_room_contextual_lighting_assist(
        {
            "room_id": "studio",
            "primary_signal_name": "room_lux",
            "primary_bucket": "ok",
            "primary_bucket_match_mode": "lte",
            "preset": "all_day_adaptive",
            "light_entities": ["light.studio_main"],
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "admin_authored_room_contextual_lighting_assist_json"
    assert "preset" in result["data_schema"].schema

    result = await flow.async_step_admin_authored_room_contextual_lighting_assist_json(
        {
            "config_json": flow._contextual_lighting_policy_json(
                preset="all_day_adaptive",
                light_entities=["light.studio_main"],
            )
        }
    )

    assert result["type"] == "menu"
    stored = next(iter(flow.options["reactions"]["configured"].values()))
    assert stored["reaction_type"] == "room_contextual_lighting_assist"
    assert stored["primary_signal_entities"] == ["sensor.studio_lux"]
    assert stored["primary_bucket"] == "ok"
    assert stored["primary_bucket_match_mode"] == "lte"
    assert stored["default_profile"] == "day_generic"
    assert sorted(stored["profiles"]) == [
        "day_generic",
        "evening_relax",
        "night_navigation",
        "workday_focus",
    ]


@pytest.mark.asyncio
async def test_admin_authored_room_contextual_lighting_assist_exposes_preset_previews():
    room = dict(_room_with_signals())
    room["signals"] = list(room["signals"]) + [
        {
            "entity_id": "sensor.studio_lux",
            "signal_name": "room_lux",
            "device_class": "illuminance",
            "buckets": [
                {"label": "dark", "upper_bound": 30.0},
                {"label": "dim", "upper_bound": 100.0},
                {"label": "ok", "upper_bound": 250.0},
                {"label": "bright", "upper_bound": None},
            ],
        }
    ]
    flow = _flow({"people_named": [], "rooms": [room], "reactions": {}})

    result = await flow.async_step_admin_authored_room_contextual_lighting_assist()

    assert result["type"] == "form"
    assert result["step_id"] == "admin_authored_room_contextual_lighting_assist"
    previews = result["description_placeholders"]["preset_previews"]
    assert "Daytime focus" in previews
    assert "Evening warmth" in previews
    assert "Night navigation" in previews
    assert "All-day adaptive" in previews


@pytest.mark.asyncio
async def test_admin_authored_room_contextual_lighting_assist_rejects_invalid_json():
    room = dict(_room_with_signals())
    room["signals"] = list(room["signals"]) + [
        {
            "entity_id": "sensor.studio_lux",
            "signal_name": "room_lux",
            "device_class": "illuminance",
            "buckets": [
                {"label": "dark", "upper_bound": 30.0},
                {"label": "dim", "upper_bound": 100.0},
                {"label": "ok", "upper_bound": 250.0},
                {"label": "bright", "upper_bound": None},
            ],
        }
    ]
    flow = _flow({"people_named": [], "rooms": [room], "reactions": {}})

    first = await flow.async_step_admin_authored_room_contextual_lighting_assist(
        {
            "room_id": "studio",
            "primary_signal_name": "room_lux",
            "primary_bucket": "ok",
            "primary_bucket_match_mode": "lte",
            "preset": "all_day_adaptive",
            "light_entities": ["light.studio_main"],
        }
    )

    assert first["type"] == "form"
    result = await flow.async_step_admin_authored_room_contextual_lighting_assist_json(
        {"config_json": "{not-json}"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"config_json": "invalid_json"}


@pytest.mark.asyncio
async def test_admin_authored_room_contextual_lighting_assist_rejects_invalid_contract():
    room = dict(_room_with_signals())
    room["signals"] = list(room["signals"]) + [
        {
            "entity_id": "sensor.studio_lux",
            "signal_name": "room_lux",
            "device_class": "illuminance",
            "buckets": [
                {"label": "dark", "upper_bound": 30.0},
                {"label": "dim", "upper_bound": 100.0},
                {"label": "ok", "upper_bound": 250.0},
                {"label": "bright", "upper_bound": None},
            ],
        }
    ]
    flow = _flow({"people_named": [], "rooms": [room], "reactions": {}})

    first = await flow.async_step_admin_authored_room_contextual_lighting_assist(
        {
            "room_id": "studio",
            "primary_signal_name": "room_lux",
            "primary_bucket": "ok",
            "primary_bucket_match_mode": "lte",
            "preset": "all_day_adaptive",
            "light_entities": ["light.studio_main"],
        }
    )

    assert first["type"] == "form"
    result = await flow.async_step_admin_authored_room_contextual_lighting_assist_json(
        {
            "config_json": json.dumps(
                {
                    "profiles": {
                        "day_generic": {
                            "entity_steps": [
                                {
                                    "entity_id": "light.studio_main",
                                    "action": "on",
                                    "brightness": 140,
                                    "color_temp_kelvin": 3600,
                                }
                            ]
                        }
                    },
                    "rules": [{"profile": "day_generic", "house_state_in": ["not-a-state"]}],
                    "default_profile": "day_generic",
                }
            )
        }
    )

    assert result["type"] == "form"
    assert result["errors"] == {"config_json": "invalid_contextual_contract"}


def _room_with_burst_signal() -> dict:
    """Room with humidity signal that has burst_threshold configured."""
    return {
        "room_id": "bathroom",
        "display_name": "Bathroom",
        "occupancy_sources": ["binary_sensor.bathroom_motion"],
        "source": "ha_area_registry",
        "ha_sync_status": "orphaned",
        "signals": [
            {
                "entity_id": "sensor.bathroom_humidity",
                "signal_name": "room_humidity",
                "device_class": "humidity",
                "buckets": [
                    {"label": "ok", "upper_bound": 70.0},
                    {"label": "high", "upper_bound": None},
                ],
                "burst_threshold": 8.0,
                "burst_window_s": 300,
                "burst_direction": "up",
            },
        ],
    }


@pytest.mark.asyncio
async def test_admin_authored_room_signal_assist_burst_mode_creates_proposal():
    flow = _flow({"rooms": [_room_with_burst_signal()]})

    result = await flow.async_step_admin_authored_room_signal_assist(
        {
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "primary_trigger_mode": "burst",
            "primary_bucket": "",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": ["script.turn_on_fan"],
        }
    )

    assert result["type"] == "menu"
    configured = flow.options["reactions"]["configured"]
    assert len(configured) == 1
    stored = next(iter(configured.values()))
    assert stored["primary_trigger_mode"] == "burst"
    assert stored["primary_bucket"] is None
    assert stored["primary_signal_name"] == "room_humidity"
    assert stored["primary_signal_entities"] == ["sensor.bathroom_humidity"]
    assert stored["reaction_type"] == "room_signal_assist"


@pytest.mark.asyncio
async def test_admin_authored_room_signal_assist_burst_mode_rejects_missing_burst_config():
    """Burst mode rejected when signal has no burst_threshold configured."""
    flow = _flow({"rooms": [_room_with_signals()]})  # studio signals have no burst_threshold

    result = await flow.async_step_admin_authored_room_signal_assist(
        {
            "room_id": "studio",
            "primary_signal_name": "room_humidity",
            "primary_trigger_mode": "burst",
            "primary_bucket": "",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": ["script.turn_on_fan"],
        }
    )

    assert result["type"] == "form"
    assert result["errors"].get("primary_trigger_mode") == "no_burst_config"


@pytest.mark.asyncio
async def test_reactions_edit_room_signal_assist_burst_mode_saves_correctly():
    flow = _flow(
        {
            "rooms": [_room_with_burst_signal()],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_signal_assist",
                        "room_id": "bathroom",
                        "primary_signal_name": "room_humidity",
                        "primary_trigger_mode": "burst",
                        "primary_bucket": None,
                        "primary_signal_entities": ["sensor.bathroom_humidity"],
                        "steps": [
                            {
                                "domain": "script",
                                "target": "script.turn_on_fan",
                                "action": "script.turn_on",
                            }
                        ],
                        "enabled": True,
                    }
                }
            },
        }
    )

    # Select reaction to edit
    result = await flow.async_step_reactions_edit({"reaction": "r1"})
    assert result["type"] == "form"

    # Submit burst mode edit
    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "primary_signal_name": "room_humidity",
            "primary_trigger_mode": "burst",
            "primary_bucket": "",
            "primary_bucket_match_mode": "eq",
            "corroboration_signal_name": "",
            "corroboration_bucket": "",
            "corroboration_bucket_match_mode": "eq",
            "action_entities": ["script.turn_on_fan"],
            "delete_reaction": False,
        }
    )

    assert result["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["primary_trigger_mode"] == "burst"
    assert stored["primary_bucket"] is None
    assert stored["primary_signal_entities"] == ["sensor.bathroom_humidity"]


@pytest.mark.asyncio
async def test_reactions_edit_contextual_lighting_assist_updates_policy_json():
    flow = _flow(
        {
            "rooms": [_room_with_signals()],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_contextual_lighting_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "primary_signal_entities": ["sensor.studio_lux"],
                        "primary_bucket": "ok",
                        "primary_bucket_match_mode": "lte",
                        "profiles": {
                            "day_generic": {
                                "entity_steps": [
                                    {
                                        "entity_id": "light.studio_main",
                                        "action": "on",
                                        "brightness": 140,
                                        "color_temp_kelvin": 3600,
                                    }
                                ]
                            },
                            "evening_relax": {
                                "entity_steps": [
                                    {
                                        "entity_id": "light.studio_main",
                                        "action": "on",
                                        "brightness": 100,
                                        "color_temp_kelvin": 2700,
                                    }
                                ]
                            },
                        },
                        "rules": [{"profile": "evening_relax"}],
                        "default_profile": "day_generic",
                        "followup_window_s": 900,
                        "enabled": True,
                    }
                }
            },
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form()
    assert result["type"] == "form"
    assert result["step_id"] == "reactions_edit_form"
    assert "preset" in result["data_schema"].schema

    payload = json.dumps(
        {
            "profiles": {
                "day_generic": {
                    "entity_steps": [
                        {
                            "entity_id": "light.studio_main",
                            "action": "on",
                            "brightness": 150,
                            "color_temp_kelvin": 3700,
                        }
                    ]
                }
            },
            "rules": [],
            "default_profile": "day_generic",
            "followup_window_s": 600,
        }
    )
    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": False,
            "config_json": payload,
            "delete_reaction": False,
        }
    )

    assert result["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["enabled"] is False
    assert stored["followup_window_s"] == 600
    assert list(stored["profiles"]) == ["day_generic"]


@pytest.mark.asyncio
async def test_reactions_edit_contextual_lighting_assist_delete_uses_public_edit_step():
    flow = _flow(
        {
            "rooms": [_room_with_signals()],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_contextual_lighting_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "primary_signal_entities": ["sensor.studio_lux"],
                        "primary_bucket": "ok",
                        "primary_bucket_match_mode": "lte",
                        "profiles": {
                            "day_generic": {
                                "entity_steps": [
                                    {
                                        "entity_id": "light.studio_main",
                                        "action": "on",
                                        "brightness": 140,
                                        "color_temp_kelvin": 3600,
                                    }
                                ]
                            }
                        },
                        "rules": [],
                        "default_profile": "day_generic",
                        "followup_window_s": 900,
                        "enabled": True,
                    }
                }
            },
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form()
    assert result["type"] == "form"
    assert result["step_id"] == "reactions_edit_form"

    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "preset": "custom",
            "config_json": flow._contextual_lighting_policy_for_form(
                flow.options["reactions"]["configured"]["r1"]
            ),
            "delete_reaction": True,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reactions_delete_confirm"


@pytest.mark.asyncio
async def test_reactions_edit_contextual_lighting_assist_can_regenerate_from_preset():
    flow = _flow(
        {
            "rooms": [_room_with_signals()],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_contextual_lighting_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "primary_signal_entities": ["sensor.studio_lux"],
                        "primary_bucket": "ok",
                        "primary_bucket_match_mode": "lte",
                        "profiles": {
                            "day_generic": {
                                "entity_steps": [
                                    {
                                        "entity_id": "light.studio_main",
                                        "action": "on",
                                        "brightness": 140,
                                        "color_temp_kelvin": 3600,
                                    }
                                ]
                            },
                            "evening_relax": {
                                "entity_steps": [
                                    {
                                        "entity_id": "light.studio_main",
                                        "action": "on",
                                        "brightness": 100,
                                        "color_temp_kelvin": 2700,
                                    }
                                ]
                            },
                            "night_navigation": {
                                "entity_steps": [
                                    {
                                        "entity_id": "light.studio_main",
                                        "action": "on",
                                        "brightness": 25,
                                        "color_temp_kelvin": 2200,
                                    }
                                ]
                            },
                            "workday_focus": {
                                "entity_steps": [
                                    {
                                        "entity_id": "light.studio_main",
                                        "action": "on",
                                        "brightness": 180,
                                        "color_temp_kelvin": 4300,
                                    }
                                ]
                            },
                        },
                        "rules": [
                            {
                                "profile": "workday_focus",
                                "house_state_in": ["working"],
                                "time_window": {"start": "08:00", "end": "18:30"},
                            },
                            {
                                "profile": "day_generic",
                                "house_state_in": ["home", "relax"],
                                "time_window": {"start": "08:00", "end": "18:30"},
                            },
                            {
                                "profile": "evening_relax",
                                "time_window": {"start": "18:30", "end": "23:30"},
                            },
                            {
                                "profile": "night_navigation",
                                "time_window": {"start": "23:30", "end": "06:30"},
                            },
                        ],
                        "default_profile": "day_generic",
                        "followup_window_s": 900,
                        "enabled": True,
                    }
                }
            },
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form()
    assert result["type"] == "form"
    config_json = flow._contextual_lighting_policy_for_form(
        flow.options["reactions"]["configured"]["r1"]
    )

    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "preset": "night_navigation",
            "config_json": config_json,
            "delete_reaction": False,
        }
    )

    assert result["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["default_profile"] == "daytime_low"
    assert sorted(stored["profiles"]) == ["daytime_low", "night_navigation"]


@pytest.mark.asyncio
async def test_reactions_edit_contextual_lighting_assist_preserves_ambient_modulation():
    flow = _flow(
        {
            "rooms": [_room_with_signals()],
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "room_contextual_lighting_assist",
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "primary_signal_entities": ["sensor.studio_lux"],
                        "primary_bucket": "ok",
                        "primary_bucket_match_mode": "lte",
                        "profiles": {
                            "day_generic": {
                                "entity_steps": [
                                    {
                                        "entity_id": "light.studio_main",
                                        "action": "on",
                                        "brightness": 140,
                                        "color_temp_kelvin": 3600,
                                    }
                                ]
                            }
                        },
                        "rules": [],
                        "default_profile": "day_generic",
                        "ambient_modulation": {
                            "source_signal_name": "outdoor_lux",
                            "mode": "brightness_multiplier",
                            "buckets": {"bright": 0.7, "dark": 1.15},
                            "clamp_min": 20,
                            "clamp_max": 255,
                        },
                        "followup_window_s": 900,
                        "enabled": True,
                    }
                }
            },
        }
    )
    flow._editing_reaction_id = "r1"

    result = await flow.async_step_reactions_edit_form()
    assert result["type"] == "form"
    config_json = flow._contextual_lighting_policy_for_form(
        flow.options["reactions"]["configured"]["r1"]
    )
    payload = json.loads(config_json)
    assert payload["ambient_modulation"]["source_signal_name"] == "outdoor_lux"

    result = await flow.async_step_reactions_edit_form(
        {
            "enabled": True,
            "config_json": config_json,
            "delete_reaction": False,
        }
    )

    assert result["type"] == "menu"
    stored = flow.options["reactions"]["configured"]["r1"]
    assert stored["ambient_modulation"]["mode"] == "brightness_multiplier"
