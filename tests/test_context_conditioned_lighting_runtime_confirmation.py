from __future__ import annotations

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.reactions.context_conditioned_lighting import (
    ContextConditionedLightingReaction,
    create_context_conditioned_lighting_runtime_confirmation_descriptor,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def test_context_conditioned_lighting_descriptor_builds_occurrence_key() -> None:
    reaction = ContextConditionedLightingReaction(
        room_id="studio",
        weekday=6,
        scheduled_min=22 * 60,
        entity_steps=[{"entity_id": "light.studio", "action": "off"}],
        context_conditions=[{"signal_name": "activity", "state_in": ["reading"]}],
        reaction_id="reaction-1",
    )
    descriptor = create_context_conditioned_lighting_runtime_confirmation_descriptor()
    snapshot = DecisionSnapshot.empty()

    key = descriptor.occurrence_key(
        reaction,
        snapshot,
        [
            ApplyStep(
                domain="lighting",
                target="studio",
                action="light.turn_off",
                params={"entity_id": "light.studio"},
            )
        ],
    )

    assert key.startswith("context_conditioned_lighting_scene:reaction-1:studio:6:1320")
    assert "light.studio" in key


def test_context_conditioned_lighting_descriptor_renders_mixed_scene() -> None:
    reaction = ContextConditionedLightingReaction(
        room_id="studio",
        weekday=6,
        scheduled_min=22 * 60,
        entity_steps=[
            {"entity_id": "light.desk", "action": "off"},
            {"entity_id": "light.shelf", "action": "on", "brightness": 12},
        ],
        context_conditions=[{"signal_name": "activity", "state_in": ["reading"]}],
        reaction_id="reaction-1",
    )
    descriptor = create_context_conditioned_lighting_runtime_confirmation_descriptor()

    rendered = descriptor.render_request(
        reaction,
        [
            ApplyStep(
                domain="lighting",
                target="studio",
                action="light.turn_off",
                params={"entity_id": "light.desk"},
            ),
            ApplyStep(
                domain="lighting",
                target="studio",
                action="light.turn_on",
                params={"entity_id": "light.shelf", "brightness": 12},
            ),
        ],
        "en",
    )

    assert rendered.title == "Apply contextual lighting in studio?"
    assert "turn off light.desk" in rendered.message
    assert "set light.shelf to brightness 12" in rendered.message
