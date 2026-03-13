"""Tests for IPatternDetector and ConsecutiveStateReaction (Phase 7 R2)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.reactions.builtin import ConsecutiveStateReaction
from custom_components.heima.runtime.reactions.patterns import ConsecutiveMatchDetector
from custom_components.heima.runtime.snapshot import DecisionSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snap(house_state: str = "unknown", anyone_home: bool = False) -> DecisionSnapshot:
    return replace(DecisionSnapshot.empty(), house_state=house_state, anyone_home=anyone_home)


def _away_step() -> ApplyStep:
    return ApplyStep(
        domain="heating",
        target="climate.living",
        action="climate.set_temperature",
        params={"entity_id": "climate.living", "temperature": 17.0},
        reason="eco",
    )


def _make_reaction(n: int = 3) -> ConsecutiveStateReaction:
    return ConsecutiveStateReaction(
        predicate=lambda s: s.house_state == "away",
        consecutive_n=n,
        steps=[_away_step()],
    )


# ---------------------------------------------------------------------------
# ConsecutiveMatchDetector
# ---------------------------------------------------------------------------


def test_detector_invalid_n_raises():
    with pytest.raises(ValueError):
        ConsecutiveMatchDetector(lambda s: True, consecutive_n=0)


def test_detector_empty_history_no_match():
    d = ConsecutiveMatchDetector(lambda s: True, consecutive_n=1)
    assert d.matches([]) is False


def test_detector_history_shorter_than_n_no_match():
    d = ConsecutiveMatchDetector(lambda s: s.house_state == "away", consecutive_n=3)
    assert d.matches([_snap("away"), _snap("away")]) is False


def test_detector_exact_n_all_match():
    d = ConsecutiveMatchDetector(lambda s: s.house_state == "away", consecutive_n=3)
    history = [_snap("away")] * 3
    assert d.matches(history) is True


def test_detector_more_than_n_last_n_match():
    d = ConsecutiveMatchDetector(lambda s: s.house_state == "away", consecutive_n=2)
    history = [_snap("home"), _snap("home"), _snap("away"), _snap("away")]
    assert d.matches(history) is True


def test_detector_last_snapshot_breaks_match():
    d = ConsecutiveMatchDetector(lambda s: s.house_state == "away", consecutive_n=2)
    history = [_snap("away"), _snap("away"), _snap("home")]
    assert d.matches(history) is False


def test_detector_n1_matches_single_snapshot():
    d = ConsecutiveMatchDetector(lambda s: s.anyone_home is False, consecutive_n=1)
    assert d.matches([_snap(anyone_home=False)]) is True


def test_detector_only_checks_last_n_not_older():
    d = ConsecutiveMatchDetector(lambda s: s.house_state == "away", consecutive_n=2)
    # First 5 match, last 2 don't → should NOT match
    history = [_snap("away")] * 5 + [_snap("home"), _snap("home")]
    assert d.matches(history) is False


# ---------------------------------------------------------------------------
# ConsecutiveStateReaction — construction
# ---------------------------------------------------------------------------


def test_reaction_default_id():
    r = _make_reaction()
    assert r.reaction_id == "ConsecutiveStateReaction"


def test_reaction_custom_id():
    r = ConsecutiveStateReaction(
        predicate=lambda s: True,
        consecutive_n=1,
        steps=[],
        reaction_id="eco_away",
    )
    assert r.reaction_id == "eco_away"


# ---------------------------------------------------------------------------
# ConsecutiveStateReaction — evaluate
# ---------------------------------------------------------------------------


def test_evaluate_returns_empty_when_history_too_short():
    r = _make_reaction(n=3)
    assert r.evaluate([_snap("away"), _snap("away")]) == []


def test_evaluate_fires_when_threshold_met():
    r = _make_reaction(n=3)
    result = r.evaluate([_snap("away")] * 3)
    assert len(result) == 1
    assert result[0].action == "climate.set_temperature"


def test_evaluate_fires_on_every_cycle_while_active():
    r = _make_reaction(n=2)
    history = [_snap("away")] * 5
    assert len(r.evaluate(history)) == 1
    assert len(r.evaluate(history)) == 1  # still active, still fires


def test_evaluate_stops_when_condition_breaks():
    r = _make_reaction(n=2)
    active_history = [_snap("away")] * 3
    assert len(r.evaluate(active_history)) == 1

    broken_history = active_history + [_snap("home")]
    assert r.evaluate(broken_history) == []


def test_evaluate_resumes_after_condition_resets():
    r = _make_reaction(n=2)
    # Activate
    r.evaluate([_snap("away")] * 3)
    # Break
    r.evaluate([_snap("home")] * 3)
    # Reactivate
    result = r.evaluate([_snap("away")] * 2)
    assert len(result) == 1


def test_evaluate_returns_copy_of_steps():
    r = _make_reaction(n=1)
    res1 = r.evaluate([_snap("away")])
    res2 = r.evaluate([_snap("away")])
    assert res1 is not res2


def test_evaluate_does_not_modify_history():
    r = _make_reaction(n=2)
    history = [_snap("away")] * 2
    original_len = len(history)
    r.evaluate(history)
    assert len(history) == original_len


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def test_diagnostics_before_evaluate():
    r = _make_reaction(n=3)
    d = r.diagnostics()
    assert d["consecutive_n"] == 3
    assert d["last_matched"] is False
    assert d["last_fired_ts"] is None
    assert d["fire_count"] == 0


def test_diagnostics_after_fire():
    r = _make_reaction(n=2)
    r.evaluate([_snap("away")] * 2)
    d = r.diagnostics()
    assert d["last_matched"] is True
    assert d["last_fired_ts"] is not None
    assert d["fire_count"] == 1


def test_diagnostics_fire_count_increments():
    r = _make_reaction(n=1)
    r.evaluate([_snap("away")])
    r.evaluate([_snap("away")])
    r.evaluate([_snap("away")])
    assert r.diagnostics()["fire_count"] == 3


def test_diagnostics_after_condition_breaks():
    r = _make_reaction(n=1)
    r.evaluate([_snap("away")])
    r.evaluate([_snap("home")])
    d = r.diagnostics()
    assert d["last_matched"] is False
    assert d["fire_count"] == 1


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_consecutive_match_detector_satisfies_protocol():
    """ConsecutiveMatchDetector must have a matches() method."""
    d = ConsecutiveMatchDetector(lambda s: True, consecutive_n=1)
    assert callable(getattr(d, "matches", None))
