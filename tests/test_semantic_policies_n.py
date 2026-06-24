"""Tests for Phase N semantic policy suggestions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.runtime.semantic_policies import (
    BUILTIN_SEMANTIC_RULES,
    SemanticRule,
)


class _ServicesStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, bool]] = []

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict,
        *,
        blocking: bool,
    ) -> None:
        self.calls.append((domain, service, data, blocking))


def _rule(rule_id: str) -> SemanticRule:
    for rule in BUILTIN_SEMANTIC_RULES:
        if rule.rule_id == rule_id:
            return rule
    raise AssertionError(f"Unknown rule: {rule_id}")


def _base_options() -> dict:
    return {
        "security": {"security_state_entity": "alarm_control_panel.home"},
        "rooms": [
            {
                "room_id": "living",
                "light_entities": ["light.living_main", "light.living_spot"],
            }
        ],
        "lighting_rooms": [
            {
                "room_id": "studio",
                "light_entities": ["light.studio_desk", "switch.not_a_light"],
            }
        ],
        "heating": {"climate_entity": "climate.hall"},
    }


def test_builtin_semantic_rules_expose_expected_catalog():
    assert [rule.rule_id for rule in BUILTIN_SEMANTIC_RULES] == [
        "alarm_away_lights_off",
        "alarm_triggered_lights_on",
        "alarm_away_climate_off",
        "alarm_night_climate_sleep",
        "alarm_night_camera_privacy",
    ]


def test_unknown_semantic_rule_returns_none():
    assert SemanticRule("unknown", "Unknown").evaluate(_base_options()) is None


def test_alarm_away_lights_off_returns_none_without_alarm_entity():
    options = _base_options()
    options["security"] = {}

    assert _rule("alarm_away_lights_off").evaluate(options) is None


def test_alarm_away_lights_off_returns_none_without_light_entities():
    options = _base_options()
    options["rooms"] = [{"room_id": "living"}]
    options["lighting_rooms"] = [{"room_id": "studio", "light_entities": ["switch.bad"]}]

    assert _rule("alarm_away_lights_off").evaluate(options) is None


def test_alarm_away_lights_off_returns_admin_authored_proposal():
    proposal = _rule("alarm_away_lights_off").evaluate(_base_options())

    assert proposal is not None
    assert proposal.analyzer_id == "semantic_policy_suggestions"
    assert proposal.reaction_type == "alarm_state_action"
    assert proposal.origin == "admin_authored"
    assert proposal.identity_key == "alarm_away_lights_off"
    assert proposal.confidence == 1.0
    assert proposal.suggested_reaction_config == {
        "reaction_type": "alarm_state_action",
        "alarm_states": ["armed_away"],
        "steps": [
            {
                "domain": "light",
                "target": "light.living_main",
                "action": "light.turn_off",
                "params": {"entity_id": "light.living_main"},
            },
            {
                "domain": "light",
                "target": "light.living_spot",
                "action": "light.turn_off",
                "params": {"entity_id": "light.living_spot"},
            },
            {
                "domain": "light",
                "target": "light.studio_desk",
                "action": "light.turn_off",
                "params": {"entity_id": "light.studio_desk"},
            },
        ],
        "skip_house_states": [],
    }


def test_alarm_triggered_lights_on_uses_triggered_state_and_turn_on():
    proposal = _rule("alarm_triggered_lights_on").evaluate(_base_options())

    assert proposal is not None
    assert proposal.identity_key == "alarm_triggered_lights_on"
    assert proposal.suggested_reaction_config["alarm_states"] == ["triggered"]
    assert {step["action"] for step in proposal.suggested_reaction_config["steps"]} == {
        "light.turn_on"
    }


def test_alarm_away_climate_off_returns_none_without_alarm_entity():
    options = _base_options()
    options["security"] = {"security_state_entity": ""}

    assert _rule("alarm_away_climate_off").evaluate(options) is None


def test_alarm_away_climate_off_returns_none_without_climate_entity():
    options = _base_options()
    options["heating"] = {}

    assert _rule("alarm_away_climate_off").evaluate(options) is None


def test_alarm_away_climate_off_returns_admin_authored_proposal():
    proposal = _rule("alarm_away_climate_off").evaluate(_base_options())

    assert proposal is not None
    assert proposal.origin == "admin_authored"
    assert proposal.identity_key == "alarm_away_climate_off"
    assert proposal.suggested_reaction_config == {
        "reaction_type": "alarm_state_action",
        "alarm_states": ["armed_away"],
        "steps": [
            {
                "domain": "climate",
                "target": "climate.hall",
                "action": "climate.set_hvac_mode",
                "params": {"entity_id": "climate.hall", "hvac_mode": "off"},
            }
        ],
        "skip_house_states": [],
    }


def test_alarm_night_climate_sleep_returns_sleep_preset_proposal():
    proposal = _rule("alarm_night_climate_sleep").evaluate(_base_options())

    assert proposal is not None
    assert proposal.identity_key == "alarm_night_climate_sleep"
    assert proposal.suggested_reaction_config == {
        "reaction_type": "alarm_state_action",
        "alarm_states": ["armed_night"],
        "steps": [
            {
                "domain": "climate",
                "target": "climate.hall",
                "action": "climate.set_preset_mode",
                "params": {"entity_id": "climate.hall", "preset_mode": "sleep"},
            }
        ],
        "skip_house_states": [],
    }


def test_semantic_rule_evaluate_is_deterministic_for_same_options():
    rule = _rule("alarm_away_lights_off")

    first = rule.evaluate(_base_options())
    second = rule.evaluate(_base_options())

    assert first is not None
    assert second is not None
    assert first.identity_key == second.identity_key
    assert first.suggested_reaction_config == second.suggested_reaction_config


def test_alarm_night_camera_privacy_returns_none_without_camera_privacy_entities():
    options = _base_options()
    # No camera_evidence_sources with privacy_entity
    assert _rule("alarm_night_camera_privacy").evaluate(options) is None


def test_alarm_night_camera_privacy_returns_none_without_alarm_entity():
    options = _base_options()
    options["security"]["security_state_entity"] = ""
    options["security"]["camera_evidence_sources"] = [
        {"id": "cam1", "role": "entry", "privacy_entity": "switch.cam1_privacy"}
    ]
    assert _rule("alarm_night_camera_privacy").evaluate(options) is None


def test_alarm_night_camera_privacy_returns_proposal_with_skip_states():
    options = _base_options()
    options["security"]["camera_evidence_sources"] = [
        {"id": "cam1", "role": "entry", "privacy_entity": "switch.cam1_privacy"},
        {"id": "cam2", "role": "entry", "privacy_entity": "switch.cam2_privacy"},
    ]
    proposal = _rule("alarm_night_camera_privacy").evaluate(options)
    assert proposal is not None
    assert proposal.identity_key == "alarm_night_camera_privacy"
    assert proposal.suggested_reaction_config["alarm_states"] == ["armed_night"]
    assert proposal.suggested_reaction_config["skip_house_states"] == ["guest", "vacation"]
    assert len(proposal.suggested_reaction_config["steps"]) == 2
    assert {
        step["target"] for step in proposal.suggested_reaction_config["steps"]
    } == {"switch.cam1_privacy", "switch.cam2_privacy"}
    assert all(step["action"] == "switch.turn_on" for step in proposal.suggested_reaction_config["steps"])


@pytest.mark.asyncio
async def test_coordinator_evaluates_semantic_policies_and_notifies_new_proposals():
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(options=_base_options())
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_identity_key=MagicMock(return_value=None),
        async_withdraw=AsyncMock(return_value=False),
        async_submit_proposal=AsyncMock(
            side_effect=[
                "proposal-semantic-1",
                "proposal-semantic-2",
                "proposal-semantic-3",
                "proposal-semantic-4",
            ]
        ),
    )
    services = _ServicesStub()
    coordinator.hass = SimpleNamespace(services=services)
    coordinator._notified_installer_alert_keys = set()

    await coordinator._async_evaluate_semantic_policies()

    assert coordinator._proposal_engine.async_submit_proposal.await_count == 4
    submitted = coordinator._proposal_engine.async_submit_proposal.await_args_list
    assert {call.args[0].identity_key for call in submitted} == {
        "alarm_away_lights_off",
        "alarm_triggered_lights_on",
        "alarm_away_climate_off",
        "alarm_night_climate_sleep",
    }
    assert len(services.calls) == 4
    assert {call[2]["notification_id"] for call in services.calls} == {
        "heima_installer_semantic_policy_alarm_away_lights_off",
        "heima_installer_semantic_policy_alarm_triggered_lights_on",
        "heima_installer_semantic_policy_alarm_away_climate_off",
        "heima_installer_semantic_policy_alarm_night_climate_sleep",
    }


@pytest.mark.asyncio
async def test_coordinator_does_not_notify_existing_semantic_proposals():
    existing = object()
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(options=_base_options())
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_identity_key=MagicMock(return_value=existing),
        async_withdraw=AsyncMock(return_value=False),
        async_submit_proposal=AsyncMock(return_value="proposal-semantic"),
    )
    services = _ServicesStub()
    coordinator.hass = SimpleNamespace(services=services)
    coordinator._notified_installer_alert_keys = set()

    await coordinator._async_evaluate_semantic_policies()

    coordinator._proposal_engine.async_submit_proposal.assert_not_awaited()
    assert services.calls == []


@pytest.mark.asyncio
async def test_coordinator_skips_semantic_policies_when_topology_is_incomplete():
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(options={"security": {"security_state_entity": ""}})
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_identity_key=MagicMock(return_value=None),
        async_withdraw=AsyncMock(return_value=True),
        async_submit_proposal=AsyncMock(return_value="proposal-semantic"),
    )
    services = _ServicesStub()
    coordinator.hass = SimpleNamespace(services=services)
    coordinator._notified_installer_alert_keys = set()

    await coordinator._async_evaluate_semantic_policies()

    coordinator._proposal_engine.async_submit_proposal.assert_not_awaited()
    assert coordinator._proposal_engine.async_withdraw.await_count == 5
    assert {
        call.args[0] for call in coordinator._proposal_engine.async_withdraw.await_args_list
    } == {
        "alarm_away_lights_off",
        "alarm_triggered_lights_on",
        "alarm_away_climate_off",
        "alarm_night_climate_sleep",
        "alarm_night_camera_privacy",
    }
    assert services.calls == []
