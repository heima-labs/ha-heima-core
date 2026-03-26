from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.heima.config_flow import HeimaOptionsFlowHandler
from custom_components.heima.const import DOMAIN
from custom_components.heima.runtime.analyzers.base import ReactionProposal


def _fake_hass():
    return SimpleNamespace(
        services=SimpleNamespace(async_services=lambda: {"notify": {}}),
        config=SimpleNamespace(time_zone="Europe/Rome", language="it"),
        data={},
    )


def _flow(options: dict | None = None) -> HeimaOptionsFlowHandler:
    flow = HeimaOptionsFlowHandler(SimpleNamespace(options=options or {}, entry_id="entry-1"))
    flow.hass = _fake_hass()
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
            "on_dwell_s": 5,
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
            "on_dwell_s": 5,
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
            "on_dwell_s": 5,
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
            "primary_threshold": 120.0,
            "primary_threshold_mode": "below",
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
    flow.hass.data = {DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}}

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert getattr(flow, "_pending_action_configs", []) == []
    stored = flow.options["reactions"]["configured"]["proposal-darkness"]
    assert stored["reaction_class"] == "RoomLightingAssistReaction"


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


def test_proposal_review_label_includes_context_confidence_and_last_seen():
    flow = _flow()
    proposal = ReactionProposal(
        proposal_id="proposal-1",
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="lighting_scene_schedule",
        description="living: Monday ~20:00 — test_heima_living_main on",
        confidence=0.92,
        last_observed_at="2026-03-26T10:27:51.561727+00:00",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "reaction_class": "LightingScheduleReaction",
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
    flow.hass.data = {DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}}

    result = await flow.async_step_proposals()

    assert result["type"] == "form"
    assert result["step_id"] == "proposals"
    placeholders = result["description_placeholders"]
    assert placeholders["current_position"] == "1/1"
    assert "Mercoledì: arrivo tipico" in placeholders["proposal_label"]
    assert "Pattern osservato: Wednesday: typical arrival around 12:38." in placeholders["proposal_details"]
    assert "Evidenza: 5 osservazioni, 2 settimane" in placeholders["proposal_details"]


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
        reaction_type="lighting_scene_schedule",
        description="Second",
        confidence=0.9,
        suggested_reaction_config={"room_id": "living", "reaction_class": "LightingScheduleReaction"},
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal_1, proposal_2],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}}

    result = await flow.async_step_proposals({"review_action": "skip"})

    assert result["type"] == "form"
    assert result["step_id"] == "proposals"
    assert "Luci living" in result["description_placeholders"]["proposal_label"]


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
        reaction_type="lighting_scene_schedule",
        description="Living lights",
        confidence=0.9,
        suggested_reaction_config={
            "reaction_class": "LightingScheduleReaction",
            "room_id": "living",
            "weekday": 0,
        },
    )
    proposal_engine = SimpleNamespace(
        pending_proposals=lambda: [proposal_1, proposal_2],
        async_accept_proposal=AsyncMock(),
        async_reject_proposal=AsyncMock(),
    )
    flow.hass.data = {DOMAIN: {"entry-1": {"coordinator": SimpleNamespace(proposal_engine=proposal_engine)}}}
    flow._proposal_review_queue = ["proposal-1", "proposal-2"]

    result = await flow.async_step_proposals({"review_action": "accept"})

    assert result["type"] == "form"
    assert result["step_id"] == "proposal_configure_action"

    resumed = await flow.async_step_proposal_configure_action(
        {
            "action_entities": ["scene.arrival"],
            "pre_condition_min": 15,
        }
    )

    assert resumed["type"] == "form"
    assert resumed["step_id"] == "proposals"
    assert "Luci living" in resumed["description_placeholders"]["proposal_label"]


def test_init_status_block_includes_pending_proposals_summary(monkeypatch):
    flow = _flow()
    monkeypatch.setattr(flow, "_pending_proposals_summary", lambda: "1")

    placeholders = flow._init_status_block()

    assert placeholders["pending_proposals_summary"] == "1"
