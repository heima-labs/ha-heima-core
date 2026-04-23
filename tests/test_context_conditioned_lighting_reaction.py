from __future__ import annotations

from datetime import UTC, datetime

from custom_components.heima.runtime.reactions.context_conditioned_lighting import (
    ContextConditionedLightingReaction,
    present_context_conditioned_lighting_proposal_label,
    present_learned_context_conditioned_lighting_details,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snapshot(*, context_signals: dict[str, str] | None = None) -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="snap-1",
        ts="2026-04-14T18:00:00+00:00",
        house_state="home",
        anyone_home=True,
        people_count=1,
        occupied_rooms=["studio"],
        lighting_intents={},
        security_state="disarmed",
        context_signals=context_signals or {},
    )


def test_context_conditioned_lighting_reaction_requires_matching_context(monkeypatch):
    monkeypatch.setattr(
        "custom_components.heima.runtime.reactions.lighting_schedule.dt_util.now",
        lambda: datetime(2026, 4, 14, 20, 0, tzinfo=UTC),
    )
    reaction = ContextConditionedLightingReaction(
        room_id="studio",
        weekday=1,
        scheduled_min=20 * 60,
        window_half_min=10,
        entity_steps=[{"entity_id": "light.studio_spot", "action": "on"}],
        context_conditions=[{"signal_name": "projector_context", "state_in": ["active"]}],
        reaction_id="ctx-scene-1",
    )

    assert reaction.evaluate([_snapshot(context_signals={"projector_context": "inactive"})]) == []
    steps = reaction.evaluate([_snapshot(context_signals={"projector_context": "active"})])
    assert len(steps) == 1
    assert steps[0].action == "light.turn_on"


def test_context_conditioned_lighting_reaction_diagnostics_include_context_conditions(monkeypatch):
    monkeypatch.setattr(
        "custom_components.heima.runtime.reactions.lighting_schedule.dt_util.now",
        lambda: datetime(2026, 4, 14, 20, 0, tzinfo=UTC),
    )
    reaction = ContextConditionedLightingReaction(
        room_id="studio",
        weekday=1,
        scheduled_min=20 * 60,
        window_half_min=10,
        entity_steps=[{"entity_id": "light.studio_spot", "action": "on"}],
        context_conditions=[{"signal_name": "projector_context", "state_in": ["active"]}],
        reaction_id="ctx-scene-1",
    )
    diagnostics = reaction.diagnostics()
    assert diagnostics["context_conditions"] == [
        {"signal_name": "projector_context", "state_in": ["active"]}
    ]


def test_present_context_conditioned_lighting_details_include_contrast_metrics():
    class _Flow:
        @staticmethod
        def _weekday_label(value, language):  # noqa: ARG004
            return str(value)

    cfg = {
        "room_id": "studio",
        "weekday": 1,
        "scheduled_min": 1200,
        "entity_steps": [{"entity_id": "light.studio_spot", "action": "on"}],
        "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
        "learning_diagnostics": {
            "concentration": 0.8,
            "lift": 2.5,
            "negative_episode_count": 4,
            "contrast_status": "verified",
            "competing_explanation_type": "context",
        },
    }

    details = present_learned_context_conditioned_lighting_details(
        flow=_Flow(),
        proposal=None,
        cfg=cfg,
        language="it",
    )

    assert "Contesto: projector_context in [active]" in details
    assert "Concentrazione: 0.80" in details
    assert "Lift: 2.50" in details
    assert "Episodi negativi: 4" in details
    assert "Contrasto: verified" in details
    assert "Spiegazione prevalente: context" in details


def test_present_context_conditioned_lighting_proposal_label_includes_context():
    label = present_context_conditioned_lighting_proposal_label(
        flow=None,
        proposal=None,
        cfg={
            "room_id": "studio",
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
        },
        language="it",
    )

    assert label == "Luci contestuali studio · projector_context"
