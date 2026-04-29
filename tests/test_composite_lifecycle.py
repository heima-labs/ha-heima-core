"""Focused tests for composite lifecycle follow-up suppression."""

from __future__ import annotations

from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.analyzers.lifecycle import (
    composite_room_assist_lifecycle_hooks,
)


def _proposal(reaction_type: str, cfg: dict) -> ReactionProposal:
    return ReactionProposal(
        reaction_type=reaction_type,
        suggested_reaction_config=cfg,
    )


def test_composite_lifecycle_suppresses_room_cooling_followup_when_structure_matches():
    hooks = composite_room_assist_lifecycle_hooks()
    accepted = _proposal(
        "room_cooling_assist",
        {
            "room_id": "studio",
            "primary_signal_name": "room_temperature",
            "primary_signal_entities": ["sensor.studio_temperature"],
            "corroboration_signal_name": "room_humidity",
            "corroboration_signal_entities": ["sensor.studio_humidity"],
            "steps": [{"domain": "fan", "target": "fan.studio", "action": "fan.turn_on"}],
        },
    )
    candidate = _proposal(
        "room_cooling_assist",
        {
            "room_id": "studio",
            "primary_signal_name": "room_temperature",
            "primary_signal_entities": ["sensor.studio_temperature"],
            "corroboration_signal_name": "room_humidity",
            "corroboration_signal_entities": ["sensor.studio_humidity"],
            "steps": [{"domain": "fan", "target": "fan.studio", "action": "fan.turn_on"}],
            "primary_threshold": 999,
            "corroboration_threshold": 999,
        },
    )

    assert hooks.should_suppress_followup(candidate, accepted) is True


def test_composite_lifecycle_does_not_suppress_room_cooling_when_steps_count_changes():
    hooks = composite_room_assist_lifecycle_hooks()
    accepted = _proposal(
        "room_cooling_assist",
        {
            "room_id": "studio",
            "primary_signal_name": "room_temperature",
            "primary_signal_entities": ["sensor.studio_temperature"],
            "corroboration_signal_name": "room_humidity",
            "corroboration_signal_entities": ["sensor.studio_humidity"],
            "steps": [{"domain": "fan", "target": "fan.studio", "action": "fan.turn_on"}],
        },
    )
    candidate = _proposal(
        "room_cooling_assist",
        {
            "room_id": "studio",
            "primary_signal_name": "room_temperature",
            "primary_signal_entities": ["sensor.studio_temperature"],
            "corroboration_signal_name": "room_humidity",
            "corroboration_signal_entities": ["sensor.studio_humidity"],
            "steps": [
                {"domain": "fan", "target": "fan.studio", "action": "fan.turn_on"},
                {"domain": "switch", "target": "switch.aux", "action": "switch.turn_on"},
            ],
        },
    )

    assert hooks.should_suppress_followup(candidate, accepted) is False


def test_composite_lifecycle_suppresses_room_signal_followup_when_buckets_match():
    hooks = composite_room_assist_lifecycle_hooks()
    accepted = _proposal(
        "room_signal_assist",
        {
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [{"domain": "script", "target": "script.fan_on", "action": "script.turn_on"}],
        },
    )
    candidate = _proposal(
        "room_signal_assist",
        {
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [{"domain": "script", "target": "script.fan_on", "action": "script.turn_on"}],
            "primary_threshold": 8.0,
        },
    )

    assert hooks.should_suppress_followup(candidate, accepted) is True


def test_composite_lifecycle_does_not_suppress_room_signal_when_corroboration_bucket_differs():
    hooks = composite_room_assist_lifecycle_hooks()
    accepted = _proposal(
        "room_signal_assist",
        {
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [{"domain": "script", "target": "script.fan_on", "action": "script.turn_on"}],
        },
    )
    candidate = _proposal(
        "room_signal_assist",
        {
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "primary_bucket": "high",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "hot",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [{"domain": "script", "target": "script.fan_on", "action": "script.turn_on"}],
        },
    )

    assert hooks.should_suppress_followup(candidate, accepted) is False


def test_composite_lifecycle_suppresses_vacancy_lighting_when_delay_and_steps_match():
    hooks = composite_room_assist_lifecycle_hooks()
    accepted = _proposal(
        "room_vacancy_lighting_off",
        {
            "room_id": "studio",
            "vacancy_delay_s": 300,
            "entity_steps": [
                {"entity_id": "light.studio_window", "action": "off"},
                {"entity_id": "light.studio_door", "action": "off"},
            ],
        },
    )
    candidate = _proposal(
        "room_vacancy_lighting_off",
        {
            "room_id": "studio",
            "vacancy_delay_s": 330,
            "entity_steps": [
                {"entity_id": "light.studio_door", "action": "off"},
                {"entity_id": "light.studio_window", "action": "off"},
            ],
            "episodes_observed": 18,
        },
    )

    assert hooks.should_suppress_followup(candidate, accepted) is True


def test_composite_lifecycle_does_not_suppress_vacancy_lighting_when_steps_change():
    hooks = composite_room_assist_lifecycle_hooks()
    accepted = _proposal(
        "room_vacancy_lighting_off",
        {
            "room_id": "studio",
            "vacancy_delay_s": 300,
            "entity_steps": [
                {"entity_id": "light.studio_window", "action": "off"},
                {"entity_id": "light.studio_door", "action": "off"},
            ],
        },
    )
    candidate = _proposal(
        "room_vacancy_lighting_off",
        {
            "room_id": "studio",
            "vacancy_delay_s": 300,
            "entity_steps": [
                {"entity_id": "light.studio_window", "action": "off"},
                {"entity_id": "light.studio_door", "action": "off"},
                {"entity_id": "light.studio_led", "action": "off"},
            ],
        },
    )

    assert hooks.should_suppress_followup(candidate, accepted) is False
