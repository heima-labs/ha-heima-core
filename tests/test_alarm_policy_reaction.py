from __future__ import annotations

from custom_components.heima.runtime.reactions.alarm_policy import (
    AlarmStateActionReaction,
    build_alarm_state_action_reaction,
    normalize_alarm_state_action_config,
    present_admin_authored_alarm_state_action_details,
    present_alarm_state_action_label,
    present_alarm_state_action_proposal_label,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snapshot(security_state: str) -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id=f"snap-{security_state}",
        ts="2026-05-15T10:00:00+00:00",
        house_state="home",
        anyone_home=False,
        people_count=0,
        occupied_rooms=[],
        lighting_intents={},
        security_state=security_state,
        context_signals={},
    )


def _step(
    *,
    domain: str = "light",
    target: str = "light.living_room",
    action: str = "light.turn_off",
    params: dict | None = None,
) -> dict:
    return {
        "domain": domain,
        "target": target,
        "action": action,
        "params": params or {"entity_id": target},
    }


def test_alarm_state_action_fires_once_per_state_entry() -> None:
    reaction = AlarmStateActionReaction(
        alarm_states=["armed_away"],
        steps=[_step()],
        reaction_id="alarm-away-lights-off",
    )

    first = reaction.evaluate([_snapshot("armed_away")])
    second = reaction.evaluate([_snapshot("armed_away")])

    assert len(first) == 1
    assert first[0].domain == "light"
    assert first[0].target == "light.living_room"
    assert first[0].action == "light.turn_off"
    assert first[0].reason == "alarm_state_action:alarm-away-lights-off:armed_away"
    assert second == []


def test_alarm_state_action_resets_after_leaving_trigger_state() -> None:
    reaction = AlarmStateActionReaction(
        alarm_states=["armed_away"],
        steps=[_step()],
        reaction_id="alarm-away-lights-off",
    )

    assert len(reaction.evaluate([_snapshot("armed_away")])) == 1
    assert reaction.evaluate([_snapshot("disarmed")]) == []
    assert len(reaction.evaluate([_snapshot("armed_away")])) == 1


def test_alarm_state_action_can_fire_on_different_configured_state_entry() -> None:
    reaction = AlarmStateActionReaction(
        alarm_states=["armed_away", "triggered"],
        steps=[_step(action="light.turn_on")],
        reaction_id="alarm-lights",
    )

    assert len(reaction.evaluate([_snapshot("armed_away")])) == 1
    triggered = reaction.evaluate([_snapshot("triggered")])

    assert len(triggered) == 1
    assert triggered[0].reason == "alarm_state_action:alarm-lights:triggered"


def test_alarm_state_action_normalizes_climate_steps() -> None:
    cfg = normalize_alarm_state_action_config(
        {
            "alarm_states": ["armed_away", "invalid"],
            "steps": [
                _step(
                    domain="climate",
                    target="climate.living_room",
                    action="climate.set_hvac_mode",
                    params={"hvac_mode": "off"},
                ),
                _step(domain="climate", target="climate.bad", action="climate.turn_off"),
            ],
        }
    )

    assert cfg == {
        "reaction_type": "alarm_state_action",
        "alarm_states": ["armed_away"],
        "steps": [
            {
                "domain": "climate",
                "target": "climate.living_room",
                "action": "climate.set_hvac_mode",
                "params": {"hvac_mode": "off", "entity_id": "climate.living_room"},
            }
        ],
    }


def test_alarm_state_action_builder_rejects_incomplete_config() -> None:
    assert (
        build_alarm_state_action_reaction(None, "alarm-1", {"alarm_states": ["armed_away"]}) is None
    )
    assert build_alarm_state_action_reaction(None, "alarm-1", {"steps": [_step()]}) is None


def test_alarm_state_action_builder_accepts_valid_config() -> None:
    reaction = build_alarm_state_action_reaction(
        None,
        "alarm-1",
        {"alarm_states": ["armed_away"], "steps": [_step()]},
    )

    assert isinstance(reaction, AlarmStateActionReaction)
    assert reaction.reaction_id == "alarm-1"


def test_alarm_state_action_label_summarizes_states_and_steps() -> None:
    label = present_alarm_state_action_label(
        "alarm-1",
        {"alarm_states": ["armed_away"], "steps": [_step()]},
        {},
    )

    assert label == "Alarm policy: armed_away -> light.turn_off (1 target)"


def test_alarm_state_action_label_summarizes_multiple_targets_for_same_action() -> None:
    label = present_alarm_state_action_label(
        "alarm-1",
        {
            "alarm_states": ["armed_night"],
            "steps": [
                _step(
                    domain="climate",
                    target="climate.living_room",
                    action="climate.set_preset_mode",
                    params={"preset_mode": "sleep"},
                ),
                _step(
                    domain="climate",
                    target="climate.bedroom",
                    action="climate.set_preset_mode",
                    params={"preset_mode": "sleep"},
                ),
            ],
        },
        {},
    )

    assert label == "Alarm policy: armed_night -> climate.set_preset_mode (2 targets)"


def test_alarm_state_action_proposal_label_uses_flow_language() -> None:
    cfg = {
        "alarm_states": ["armed_night"],
        "steps": [
            _step(
                domain="climate",
                target="climate.living_room",
                action="climate.set_preset_mode",
                params={"preset_mode": "sleep"},
            )
        ],
    }

    assert present_alarm_state_action_proposal_label(None, None, cfg, "it") == (
        "Policy allarme: quando l'allarme passa a armed_night, "
        "imposta il termostato climate.living_room sul preset 'sleep'"
    )
    assert present_alarm_state_action_proposal_label(None, None, cfg, "en") == (
        "Alarm policy: when alarm changes to armed_night, "
        "set thermostat climate.living_room to preset 'sleep'"
    )


def test_alarm_state_action_review_details_include_trigger_action_target_and_params() -> None:
    details = present_admin_authored_alarm_state_action_details(
        None,
        None,
        {
            "alarm_states": ["armed_night"],
            "steps": [
                _step(
                    domain="climate",
                    target="climate.living_room",
                    action="climate.set_preset_mode",
                    params={"preset_mode": "sleep"},
                )
            ],
        },
        "it",
    )

    assert details == [
        "Tipo: suggerimento policy da configurazione",
        "Stati allarme: armed_night",
        "Azioni configurate: 1",
        "Azione 1: imposta il termostato climate.living_room sul preset 'sleep'",
    ]


def test_alarm_state_action_review_details_include_english_copy() -> None:
    details = present_admin_authored_alarm_state_action_details(
        None,
        None,
        {
            "alarm_states": ["armed_night"],
            "steps": [
                _step(
                    domain="climate",
                    target="climate.living_room",
                    action="climate.set_preset_mode",
                    params={"preset_mode": "sleep"},
                )
            ],
        },
        "en",
    )

    assert details == [
        "Type: semantic policy suggestion from configured topology",
        "Alarm states: armed_night",
        "Configured actions: 1",
        "Action 1: set thermostat climate.living_room to preset 'sleep'",
    ]
