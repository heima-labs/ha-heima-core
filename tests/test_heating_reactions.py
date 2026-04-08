from __future__ import annotations

from dataclasses import replace

from custom_components.heima.runtime.reactions.heating import (
    HeatingEcoReaction,
    HeatingPreferenceReaction,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snap(
    *,
    house_state: str = "home",
    heating_setpoint: float | None = 20.0,
) -> DecisionSnapshot:
    return replace(
        DecisionSnapshot.empty(),
        house_state=house_state,
        heating_setpoint=heating_setpoint,
    )


def test_heating_preference_reaction_fires_on_house_state_entry():
    reaction = HeatingPreferenceReaction(
        climate_entity="climate.test",
        house_state="home",
        target_temperature=21.5,
        reaction_id="hp1",
    )

    steps = reaction.evaluate(
        [
            _snap(house_state="away", heating_setpoint=16.0),
            _snap(house_state="home", heating_setpoint=19.0),
        ]
    )

    assert len(steps) == 1
    assert steps[0].domain == "heating"
    assert steps[0].action == "climate.set_temperature"
    assert steps[0].params["entity_id"] == "climate.test"
    assert steps[0].params["temperature"] == 21.5


def test_heating_preference_reaction_no_repeat_within_same_state():
    reaction = HeatingPreferenceReaction(
        climate_entity="climate.test",
        house_state="home",
        target_temperature=21.5,
    )

    steps = reaction.evaluate(
        [
            _snap(house_state="home", heating_setpoint=19.0),
            _snap(house_state="home", heating_setpoint=19.0),
        ]
    )

    assert steps == []


def test_heating_eco_reaction_fires_on_away_entry():
    reaction = HeatingEcoReaction(
        climate_entity="climate.test",
        eco_target_temperature=16.0,
        reaction_id="eco1",
    )

    steps = reaction.evaluate(
        [
            _snap(house_state="home", heating_setpoint=21.0),
            _snap(house_state="away", heating_setpoint=20.0),
        ]
    )

    assert len(steps) == 1
    assert steps[0].domain == "heating"
    assert steps[0].params["temperature"] == 16.0


def test_heating_eco_reaction_skips_if_already_at_target():
    reaction = HeatingEcoReaction(
        climate_entity="climate.test",
        eco_target_temperature=16.0,
    )

    steps = reaction.evaluate(
        [
            _snap(house_state="home", heating_setpoint=21.0),
            _snap(house_state="away", heating_setpoint=16.0),
        ]
    )

    assert steps == []
