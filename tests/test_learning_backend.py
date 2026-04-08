"""Tests for ILearningBackend and NaiveLearningBackend (Phase 7 R3)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.reactions.builtin import ConsecutiveStateReaction
from custom_components.heima.runtime.reactions.learning import NaiveLearningBackend
from custom_components.heima.runtime.snapshot import DecisionSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snap(house_state: str = "away") -> DecisionSnapshot:
    return replace(DecisionSnapshot.empty(), house_state=house_state)


def _step() -> ApplyStep:
    return ApplyStep(domain="heating", target="climate.t", action="climate.set_temperature")


def _backend(override_threshold: int = 3, reset_cycles: int = 20) -> NaiveLearningBackend:
    return NaiveLearningBackend(override_threshold=override_threshold, reset_cycles=reset_cycles)


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------


def test_invalid_override_threshold_raises():
    with pytest.raises(ValueError):
        NaiveLearningBackend(override_threshold=0)


def test_invalid_reset_cycles_raises():
    with pytest.raises(ValueError):
        NaiveLearningBackend(reset_cycles=0)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_confidence_is_one():
    b = _backend()
    assert b.confidence("r1") == 1.0


def test_initial_diagnostics():
    b = _backend(override_threshold=3, reset_cycles=20)
    d = b.diagnostics("r1")
    assert d["confidence"] == 1.0
    assert d["consecutive_overrides"] == 0
    assert d["cycles_since_last_override"] == 0


# ---------------------------------------------------------------------------
# observe() — cycles_since_last_override increments on fired=True
# ---------------------------------------------------------------------------


def test_observe_fired_increments_cycles():
    b = _backend()
    b.observe("r1", fired=True, steps=[_step()])
    assert b.diagnostics("r1")["cycles_since_last_override"] == 1


def test_observe_not_fired_does_not_increment():
    b = _backend()
    b.observe("r1", fired=False, steps=[])
    assert b.diagnostics("r1")["cycles_since_last_override"] == 0


def test_observe_fired_multiple_times_accumulates():
    b = _backend()
    for _ in range(5):
        b.observe("r1", fired=True, steps=[_step()])
    assert b.diagnostics("r1")["cycles_since_last_override"] == 5


# ---------------------------------------------------------------------------
# record_override() — consecutive_overrides counter and confidence decay
# ---------------------------------------------------------------------------


def test_single_override_below_threshold_no_decay():
    b = _backend(override_threshold=3)
    b.record_override("r1")
    assert b.confidence("r1") == 1.0
    assert b.diagnostics("r1")["consecutive_overrides"] == 1


def test_two_overrides_below_threshold_no_decay():
    b = _backend(override_threshold=3)
    b.record_override("r1")
    b.record_override("r1")
    assert b.confidence("r1") == 1.0


def test_threshold_overrides_decays_confidence():
    b = _backend(override_threshold=3)
    for _ in range(3):
        b.record_override("r1")
    # penalty = 1/3 ≈ 0.333; confidence = 1.0 - 0.333 ≈ 0.667
    conf = b.confidence("r1")
    assert conf < 1.0
    assert conf > 0.0


def test_confidence_never_below_zero():
    b = _backend(override_threshold=1)
    for _ in range(20):
        b.record_override("r1")
    assert b.confidence("r1") >= 0.0


def test_override_resets_consecutive_counter_after_penalty():
    b = _backend(override_threshold=3)
    for _ in range(3):
        b.record_override("r1")
    # After penalty, consecutive_overrides resets
    assert b.diagnostics("r1")["consecutive_overrides"] == 0


def test_override_resets_cycles_since_last_override():
    b = _backend()
    b.observe("r1", fired=True, steps=[_step()])
    b.observe("r1", fired=True, steps=[_step()])
    b.record_override("r1")
    assert b.diagnostics("r1")["cycles_since_last_override"] == 0


# ---------------------------------------------------------------------------
# Confidence recovery after reset_cycles
# ---------------------------------------------------------------------------


def test_confidence_restored_after_reset_cycles():
    b = _backend(override_threshold=1, reset_cycles=5)
    b.record_override("r1")  # confidence decays
    conf_after_override = b.confidence("r1")
    assert conf_after_override < 1.0

    # Fire reset_cycles times → confidence restored
    for _ in range(5):
        b.observe("r1", fired=True, steps=[_step()])
    assert b.confidence("r1") == 1.0


def test_confidence_not_restored_before_reset_cycles():
    b = _backend(override_threshold=1, reset_cycles=10)
    b.record_override("r1")
    for _ in range(9):
        b.observe("r1", fired=True, steps=[_step()])
    assert b.confidence("r1") < 1.0


# ---------------------------------------------------------------------------
# Independent per reaction_id state
# ---------------------------------------------------------------------------


def test_different_reaction_ids_independent():
    b = _backend(override_threshold=1)
    b.record_override("r1")
    assert b.confidence("r1") < 1.0
    assert b.confidence("r2") == 1.0


# ---------------------------------------------------------------------------
# ConsecutiveStateReaction + NaiveLearningBackend integration
# ---------------------------------------------------------------------------


def _make_reaction(backend: NaiveLearningBackend) -> ConsecutiveStateReaction:
    return ConsecutiveStateReaction(
        predicate=lambda s: s.house_state == "away",
        consecutive_n=1,
        steps=[_step()],
        reaction_id="test_reaction",
        learning_backend=backend,
        confidence_threshold=0.5,
    )


def test_reaction_fires_at_full_confidence():
    b = _backend()
    r = _make_reaction(b)
    result = r.evaluate([_snap("away")])
    assert len(result) == 1


def test_reaction_suppressed_below_confidence_threshold():
    b = _backend(override_threshold=1)
    r = _make_reaction(b)
    # Record enough overrides to push confidence below 0.5
    for _ in range(3):
        b.record_override("test_reaction")
    result = r.evaluate([_snap("away")])
    assert result == []


def test_suppressed_count_increments_when_silenced():
    b = _backend(override_threshold=1)
    r = _make_reaction(b)
    for _ in range(3):
        b.record_override("test_reaction")
    r.evaluate([_snap("away")])
    r.evaluate([_snap("away")])
    assert r.diagnostics()["suppressed_count"] == 2


def test_reaction_recovers_after_reset_cycles():
    b = _backend(override_threshold=1, reset_cycles=3)
    r = _make_reaction(b)
    b.record_override("test_reaction")

    # Force confidence recovery by firing 3 times via observe
    for _ in range(3):
        b.observe("test_reaction", fired=True, steps=[_step()])

    assert b.confidence("test_reaction") == 1.0
    result = r.evaluate([_snap("away")])
    assert len(result) == 1


def test_reaction_diagnostics_includes_learning():
    b = _backend()
    r = _make_reaction(b)
    r.evaluate([_snap("away")])
    d = r.diagnostics()
    assert "learning" in d
    assert "confidence" in d["learning"]


def test_reaction_without_backend_always_fires():
    r = ConsecutiveStateReaction(
        predicate=lambda s: s.house_state == "away",
        consecutive_n=1,
        steps=[_step()],
    )
    result = r.evaluate([_snap("away")])
    assert len(result) == 1
    assert "learning" not in r.diagnostics()
