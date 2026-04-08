"""Tests for HeimaReaction framework (Phase 7 R1)."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.reactions.base import HeimaReaction
from custom_components.heima.runtime.snapshot import DecisionSnapshot

# ---------------------------------------------------------------------------
# HeimaReaction base class
# ---------------------------------------------------------------------------


def test_reaction_id_defaults_to_class_name():
    class MyReaction(HeimaReaction):
        pass

    assert MyReaction().reaction_id == "MyReaction"


def test_evaluate_returns_empty_list():
    assert HeimaReaction().evaluate([]) == []


def test_evaluate_with_history_returns_empty_list():
    history = [DecisionSnapshot.empty()]
    assert HeimaReaction().evaluate(history) == []


def test_on_options_reloaded_is_noop():
    HeimaReaction().on_options_reloaded({})  # must not raise


def test_reset_learning_state_is_noop():
    HeimaReaction().reset_learning_state()  # must not raise


def test_diagnostics_returns_empty_dict():
    assert HeimaReaction().diagnostics() == {}


# ---------------------------------------------------------------------------
# Engine integration helpers
# ---------------------------------------------------------------------------


def _make_engine():
    from custom_components.heima.runtime.engine import HeimaEngine

    hass = MagicMock()
    hass.states.get.return_value = None
    hass.services.async_services.return_value = {}
    entry = MagicMock()
    entry.entry_id = "test"
    entry.options = {}
    return HeimaEngine(hass, entry)


class _StepCapture(HeimaReaction):
    """Returns a fixed ApplyStep on evaluate."""

    def __init__(self, step: ApplyStep) -> None:
        self._step = step
        self.call_count = 0
        self.last_history: list[DecisionSnapshot] = []

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        self.call_count += 1
        self.last_history = list(history)
        return [self._step]


class _FaultyReaction(HeimaReaction):
    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# register_reaction
# ---------------------------------------------------------------------------


def test_register_reaction_appended():
    engine = _make_engine()
    r = _StepCapture(ApplyStep(domain="lighting", target="x", action="light.turn_off"))
    engine.register_reaction(r)
    assert r in engine._reactions


# ---------------------------------------------------------------------------
# _dispatch_reactions
# ---------------------------------------------------------------------------


def test_dispatch_reactions_returns_steps():
    engine = _make_engine()
    step = ApplyStep(domain="lighting", target="area.living", action="light.turn_off")
    engine.register_reaction(_StepCapture(step))
    result = engine._dispatch_reactions([])
    assert len(result) == 1


def test_dispatch_reactions_tags_source():
    engine = _make_engine()

    class TaggedReaction(HeimaReaction):
        def evaluate(self, history):
            return [ApplyStep(domain="lighting", target="x", action="light.turn_off")]

    engine.register_reaction(TaggedReaction())
    result = engine._dispatch_reactions([])
    assert result[0].source == "reaction:TaggedReaction"


def test_dispatch_reactions_passes_history():
    engine = _make_engine()
    snap = DecisionSnapshot.empty()
    r = _StepCapture(ApplyStep(domain="lighting", target="x", action="light.turn_off"))
    engine.register_reaction(r)
    engine._dispatch_reactions([snap])
    assert r.last_history == [snap]


def test_faulty_reaction_does_not_propagate():
    engine = _make_engine()
    engine.register_reaction(_FaultyReaction())
    result = engine._dispatch_reactions([])  # must not raise
    assert result == []


def test_multiple_reactions_all_called():
    engine = _make_engine()
    step = ApplyStep(domain="lighting", target="x", action="light.turn_off")
    r1, r2 = _StepCapture(step), _StepCapture(step)
    engine.register_reaction(r1)
    engine.register_reaction(r2)
    engine._dispatch_reactions([])
    assert r1.call_count == 1
    assert r2.call_count == 1


def test_multiple_reactions_steps_merged():
    engine = _make_engine()
    step = ApplyStep(domain="lighting", target="x", action="light.turn_off")
    engine.register_reaction(_StepCapture(step))
    engine.register_reaction(_StepCapture(step))
    result = engine._dispatch_reactions([])
    assert len(result) == 2


# ---------------------------------------------------------------------------
# source tag preservation
# ---------------------------------------------------------------------------


def test_source_tag_does_not_overwrite_other_fields():
    engine = _make_engine()
    original = ApplyStep(
        domain="heating", target="climate.t", action="climate.set_temperature", reason="test"
    )
    engine.register_reaction(_StepCapture(original))
    result = engine._dispatch_reactions([])
    assert result[0].domain == "heating"
    assert result[0].reason == "test"
    assert result[0].source.startswith("reaction:")


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------


def test_diagnostics_includes_reactions():
    engine = _make_engine()
    engine.register_reaction(
        _StepCapture(ApplyStep(domain="lighting", target="x", action="light.turn_off"))
    )
    diag = engine.diagnostics()
    assert "_StepCapture" in diag["reactions"]
