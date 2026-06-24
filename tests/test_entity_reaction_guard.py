"""Tests for EntityReactionGuardBehavior."""

from __future__ import annotations

import pytest

from custom_components.heima.runtime.behaviors.entity_reaction_guard import (
    EntityReactionGuardBehavior,
)
from custom_components.heima.runtime.contracts import ApplyPlan, ApplyStep


class _MockState:
    """Mock state object for testing."""

    def __init__(self, binary_values: dict[str, bool]) -> None:
        self._binary = binary_values

    def get_binary(self, entity_id: str) -> bool:
        return self._binary.get(entity_id, False)


@pytest.fixture
def mock_state() -> _MockState:
    """Fixture for mock state."""
    return _MockState({})


@pytest.fixture
def default_behavior(mock_state: _MockState) -> EntityReactionGuardBehavior:
    """Fixture for EntityReactionGuardBehavior with default settings."""
    return EntityReactionGuardBehavior(
        state=mock_state,
        options={},
        hold_entity_pattern="heima_{domain}_manual_hold",
        target_domain="switch",
    )


class TestEntityReactionGuardBehavior:
    """Tests for EntityReactionGuardBehavior blocking logic."""

    def test_no_block_when_no_hold(self, default_behavior: EntityReactionGuardBehavior) -> None:
        """Steps should not be blocked when no hold is active."""
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="switch",
                    target="switch.camera1_privacy",
                    action="turn_on",
                    reason="test",
                ),
            ]
        )
        filtered = default_behavior.apply_filter(plan, None)
        assert filtered.steps[0].blocked_by == ""

    def test_global_hold_blocks_all_switches(self, mock_state: _MockState) -> None:
        """Global hold should block all steps for the target domain."""
        mock_state._binary["heima_switch_manual_hold"] = True
        behavior = EntityReactionGuardBehavior(
            state=mock_state,
            options={},
            hold_entity_pattern="heima_{domain}_manual_hold",
            target_domain="switch",
        )
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="switch",
                    target="switch.camera1_privacy",
                    action="turn_on",
                    reason="test",
                ),
                ApplyStep(
                    domain="switch",
                    target="switch.camera2_privacy",
                    action="turn_off",
                    reason="test",
                ),
            ]
        )
        filtered = behavior.apply_filter(plan, None)
        assert filtered.steps[0].blocked_by == "switch.manual_hold:global"
        assert filtered.steps[1].blocked_by == "switch.manual_hold:global"
        assert behavior._blocked_total == 2
        assert behavior._blocked_by_entity["global"] == 2

    def test_per_entity_hold_blocks_only_that_entity(self, mock_state: _MockState) -> None:
        """Per-entity hold should block only the corresponding entity."""
        mock_state._binary["heima_switch_manual_hold_camera1_privacy"] = True
        behavior = EntityReactionGuardBehavior(
            state=mock_state,
            options={},
            hold_entity_pattern="heima_switch_manual_hold",
            target_domain="switch",
        )
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="switch",
                    target="switch.camera1_privacy",
                    action="turn_on",
                    reason="test",
                ),
                ApplyStep(
                    domain="switch",
                    target="switch.camera2_privacy",
                    action="turn_off",
                    reason="test",
                ),
            ]
        )
        filtered = behavior.apply_filter(plan, None)
        assert filtered.steps[0].blocked_by == "switch.manual_hold:camera1_privacy"
        assert filtered.steps[1].blocked_by == ""

    def test_base_entity_hold_blocks_with_suffix(self, mock_state: _MockState) -> None:
        """Hold entity without suffix (e.g., camera1) should block camera1_privacy."""
        mock_state._binary["heima_switch_manual_hold_camera1"] = True
        behavior = EntityReactionGuardBehavior(
            state=mock_state,
            options={},
            hold_entity_pattern="heima_switch_manual_hold",
            target_domain="switch",
        )
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="switch",
                    target="switch.camera1_privacy",
                    action="turn_on",
                    reason="test",
                ),
            ]
        )
        filtered = behavior.apply_filter(plan, None)
        # Should match camera1 (without _privacy suffix)
        assert filtered.steps[0].blocked_by == "switch.manual_hold:camera1"

    def test_different_domain_not_blocked(self, mock_state: _MockState) -> None:
        """Steps for other domains should not be blocked."""
        mock_state._binary["heima_switch_manual_hold"] = True
        behavior = EntityReactionGuardBehavior(
            state=mock_state,
            options={},
            hold_entity_pattern="heima_{domain}_manual_hold",
            target_domain="switch",
        )
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="light",
                    target="light.living",
                    action="turn_on",
                    reason="test",
                ),
            ]
        )
        filtered = behavior.apply_filter(plan, None)
        assert filtered.steps[0].blocked_by == ""

    def test_already_blocked_step_not_reblocked(self, mock_state: _MockState) -> None:
        """Steps already blocked by another guard should not be reblocked."""
        mock_state._binary["heima_switch_manual_hold"] = True
        behavior = EntityReactionGuardBehavior(
            state=mock_state,
            options={},
            hold_entity_pattern="heima_{domain}_manual_hold",
            target_domain="switch",
        )
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="switch",
                    target="switch.camera1_privacy",
                    action="turn_on",
                    reason="test",
                    blocked_by="some_other_guard",
                ),
            ]
        )
        filtered = behavior.apply_filter(plan, None)
        assert filtered.steps[0].blocked_by == "some_other_guard"

    def test_invalid_target_format_not_blocked(self, mock_state: _MockState) -> None:
        """Steps with invalid target format should not be blocked."""
        mock_state._binary["heima_switch_manual_hold"] = True
        behavior = EntityReactionGuardBehavior(
            state=mock_state,
            options={},
            hold_entity_pattern="heima_{domain}_manual_hold",
            target_domain="switch",
        )
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="switch",
                    target="invalid_target_no_dot",
                    action="turn_on",
                    reason="test",
                ),
            ]
        )
        filtered = behavior.apply_filter(plan, None)
        assert filtered.steps[0].blocked_by == ""

    def test_diagnostics(self, default_behavior: EntityReactionGuardBehavior) -> None:
        """Diagnostics should return correct structure."""
        diagnostics = default_behavior.diagnostics()
        assert "hold_entity_pattern" in diagnostics
        assert "target_domain" in diagnostics
        assert "blocked_total" in diagnostics
        assert "blocked_by_entity" in diagnostics
        # Pattern is formatted with domain at init time
        assert diagnostics["hold_entity_pattern"] == "heima_switch_manual_hold"
        assert diagnostics["target_domain"] == "switch"
        assert diagnostics["blocked_total"] == 0
        assert diagnostics["blocked_by_entity"] == {}

    def test_custom_pattern_and_domain(self, mock_state: _MockState) -> None:
        """Custom hold pattern and target domain should work."""
        mock_state._binary["custom_light_hold"] = True
        behavior = EntityReactionGuardBehavior(
            state=mock_state,
            options={},
            hold_entity_pattern="custom_{domain}_hold",
            target_domain="light",
        )
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="light",
                    target="light.living",
                    action="turn_on",
                    reason="test",
                ),
            ]
        )
        filtered = behavior.apply_filter(plan, None)
        # The pattern is formatted with domain="light" -> "custom_light_hold"
        assert filtered.steps[0].blocked_by == "light.manual_hold:global"

    def test_works_for_cover_domain(self, mock_state: _MockState) -> None:
        """Behavior should work for cover domain."""
        mock_state._binary["heima_cover_manual_hold"] = True
        behavior = EntityReactionGuardBehavior(
            state=mock_state,
            options={},
            hold_entity_pattern="heima_{domain}_manual_hold",
            target_domain="cover",
        )
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="cover",
                    target="cover.window1",
                    action="close",
                    reason="test",
                ),
            ]
        )
        filtered = behavior.apply_filter(plan, None)
        assert filtered.steps[0].blocked_by == "cover.manual_hold:global"


class TestEntityReactionGuardBehaviorIntegration:
    """Integration tests for EntityReactionGuardBehavior."""

    def test_multiple_holds_multiple_blocks(self, mock_state: _MockState) -> None:
        """Multiple hold entities should block their corresponding targets."""
        mock_state._binary = {
            "heima_switch_manual_hold": False,  # Global off
            "heima_switch_manual_hold_camera1_privacy": True,  # Block camera1
            "heima_switch_manual_hold_camera2_privacy": True,  # Block camera2
        }
        behavior = EntityReactionGuardBehavior(
            state=mock_state,
            options={},
            hold_entity_pattern="heima_switch_manual_hold",
            target_domain="switch",
        )
        plan = ApplyPlan(
            steps=[
                ApplyStep(
                    domain="switch", target="switch.camera1_privacy", action="turn_on", reason="t1"
                ),
                ApplyStep(
                    domain="switch", target="switch.camera2_privacy", action="turn_on", reason="t2"
                ),
                ApplyStep(
                    domain="switch", target="switch.camera3_privacy", action="turn_on", reason="t3"
                ),
            ]
        )
        filtered = behavior.apply_filter(plan, None)
        assert filtered.steps[0].blocked_by == "switch.manual_hold:camera1_privacy"
        assert filtered.steps[1].blocked_by == "switch.manual_hold:camera2_privacy"
        assert filtered.steps[2].blocked_by == ""  # camera3 not blocked
        assert behavior._blocked_total == 2
        assert behavior._blocked_by_entity == {"camera1_privacy": 1, "camera2_privacy": 1}
