"""Tests for the constraints layer (apply_filter, _compute_active_constraints)."""

from __future__ import annotations

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.engine import HeimaEngine, _constraint_blocker

# ---------------------------------------------------------------------------
# _compute_active_constraints
# ---------------------------------------------------------------------------


def test_no_constraints_when_security_unknown():
    assert HeimaEngine._compute_active_constraints("unknown") == set()


def test_no_constraints_when_security_disarmed():
    assert HeimaEngine._compute_active_constraints("disarmed") == set()


def test_no_constraints_when_security_armed_home():
    assert HeimaEngine._compute_active_constraints("armed_home") == set()


def test_armed_away_adds_constraint():
    assert HeimaEngine._compute_active_constraints("armed_away") == {"security.armed_away"}


# ---------------------------------------------------------------------------
# _constraint_blocker
# ---------------------------------------------------------------------------


def _lighting_step(action: str) -> ApplyStep:
    return ApplyStep(domain="lighting", target="area.living", action=action)


def _heating_step() -> ApplyStep:
    return ApplyStep(domain="heating", target="climate.test", action="climate.set_temperature")


def test_blocker_scene_turn_on_blocked_when_armed_away():
    step = _lighting_step("scene.turn_on")
    assert _constraint_blocker(step, {"security.armed_away"}) == "security.armed_away"


def test_blocker_light_turn_off_not_blocked_when_armed_away():
    step = _lighting_step("light.turn_off")
    assert _constraint_blocker(step, {"security.armed_away"}) == ""


def test_blocker_heating_not_blocked_when_armed_away():
    step = _heating_step()
    assert _constraint_blocker(step, {"security.armed_away"}) == ""


def test_blocker_no_constraints():
    step = _lighting_step("scene.turn_on")
    assert _constraint_blocker(step, set()) == ""


# ---------------------------------------------------------------------------
# _apply_filter
# ---------------------------------------------------------------------------


def test_apply_filter_marks_blocked_steps():
    steps = [
        _lighting_step("scene.turn_on"),
        _lighting_step("light.turn_off"),
        _heating_step(),
    ]
    filtered = HeimaEngine._apply_filter(steps, {"security.armed_away"})
    assert filtered[0].blocked_by == "security.armed_away"
    assert filtered[1].blocked_by == ""
    assert filtered[2].blocked_by == ""


def test_apply_filter_no_constraints_passthrough():
    steps = [_lighting_step("scene.turn_on"), _heating_step()]
    filtered = HeimaEngine._apply_filter(steps, set())
    assert all(s.blocked_by == "" for s in filtered)


def test_apply_filter_preserves_step_count():
    steps = [_lighting_step("scene.turn_on"), _lighting_step("light.turn_off")]
    filtered = HeimaEngine._apply_filter(steps, {"security.armed_away"})
    assert len(filtered) == len(steps)
