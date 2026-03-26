"""Tests for ProposalEngine (learning system P4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.proposal_engine import ProposalEngine


class _FakeStore:
    def __init__(self, hass, version, key):  # noqa: ANN001, D401, ARG002
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data


class _AnalyzerStub:
    def __init__(self, proposals):
        self._proposals = list(proposals)
        self._id = "stub"

    @property
    def analyzer_id(self) -> str:
        return self._id

    async def analyze(self, event_store):  # noqa: ANN001, ARG002
        return list(self._proposals)


class _EventStoreStub:
    pass


def _proposal(*, conf: float, weekday: int = 0, status: str = "pending") -> ReactionProposal:
    return ReactionProposal(
        analyzer_id="PresencePatternAnalyzer",
        reaction_type="presence_preheat",
        confidence=conf,
        status=status,  # type: ignore[arg-type]
        description="proposal",
        suggested_reaction_config={"weekday": weekday},
    )


def _lighting_proposal(*, conf: float, room_id: str, weekday: int, scheduled_min: int, fingerprint: str) -> ReactionProposal:
    return ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="lighting_scene_schedule",
        confidence=conf,
        description=f"{room_id}:{scheduled_min}",
        suggested_reaction_config={
            "reaction_class": "LightingScheduleReaction",
            "room_id": room_id,
            "weekday": weekday,
            "scheduled_min": scheduled_min,
            "entity_steps": [{"entity_id": f"light.{room_id}_main", "action": "on"}],
        },
        fingerprint=fingerprint,
    )


async def test_proposal_engine_run_and_pending(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    sensor_updates = []
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        sensor_writer=lambda count, attrs: sensor_updates.append((count, attrs)),
    )
    engine.register_analyzer(_AnalyzerStub([_proposal(conf=0.9)]))
    await engine.async_initialize()
    await engine.async_run()
    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert sensor_updates[-1][0] == 1
    proposal_attrs = sensor_updates[-1][1][pending[0].proposal_id]
    assert "created_at" in proposal_attrs
    assert "updated_at" in proposal_attrs
    assert "config_summary" in proposal_attrs
    assert "explainability" in proposal_attrs


async def test_proposal_engine_dedup_pending_updates_confidence(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    analyzer = _AnalyzerStub([_proposal(conf=0.6)])
    engine.register_analyzer(analyzer)
    await engine.async_initialize()
    await engine.async_run()

    analyzer._proposals = [_proposal(conf=0.85)]
    await engine.async_run()
    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].confidence == 0.85


async def test_proposal_engine_skip_accepted(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    analyzer = _AnalyzerStub([_proposal(conf=0.9)])
    engine.register_analyzer(analyzer)
    await engine.async_initialize()
    await engine.async_run()
    pid = engine.pending_proposals()[0].proposal_id
    assert await engine.async_accept_proposal(pid)

    analyzer._proposals = [_proposal(conf=0.4)]
    await engine.async_run()
    all_pending = engine.pending_proposals()
    assert len(all_pending) == 0


async def test_proposal_engine_reject(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine.register_analyzer(_AnalyzerStub([_proposal(conf=0.9)]))
    await engine.async_initialize()
    await engine.async_run()
    pid = engine.pending_proposals()[0].proposal_id
    assert await engine.async_reject_proposal(pid)
    assert engine.pending_proposals() == []


async def test_proposal_engine_persist_and_load_preserves_fingerprint(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine1 = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine1.register_analyzer(
        _AnalyzerStub(
            [
                _lighting_proposal(
                    conf=0.9,
                    room_id="living",
                    weekday=0,
                    scheduled_min=1200,
                    fingerprint="LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200",
                )
            ]
        )
    )
    await engine1.async_initialize()
    await engine1.async_run()

    engine2 = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine2._store._data = engine1._store._data
    await engine2.async_initialize()

    assert len(engine2._proposals) == 1
    assert engine2._proposals[0].fingerprint == "LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200"


async def test_proposal_engine_restart_dedup_uses_persisted_fingerprint(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    fp1 = "LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200"
    fp2 = "LightingPatternAnalyzer|lighting_scene_schedule|bedroom|0|1200"

    engine1 = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine1.register_analyzer(
        _AnalyzerStub(
            [
                _lighting_proposal(conf=0.7, room_id="living", weekday=0, scheduled_min=1200, fingerprint=fp1),
                _lighting_proposal(conf=0.8, room_id="bedroom", weekday=0, scheduled_min=1200, fingerprint=fp2),
            ]
        )
    )
    await engine1.async_initialize()
    await engine1.async_run()
    assert len(engine1.pending_proposals()) == 2

    engine2 = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine2._store._data = engine1._store._data
    await engine2.async_initialize()
    analyzer = _AnalyzerStub(
        [
            _lighting_proposal(conf=0.9, room_id="living", weekday=0, scheduled_min=1200, fingerprint=fp1),
            _lighting_proposal(conf=0.95, room_id="bedroom", weekday=0, scheduled_min=1200, fingerprint=fp2),
        ]
    )
    engine2.register_analyzer(analyzer)
    await engine2.async_run()

    pending = engine2.pending_proposals()
    assert len(pending) == 2
    by_room = {p.suggested_reaction_config["room_id"]: p for p in pending}
    assert by_room["living"].confidence == 0.9
    assert by_room["bedroom"].confidence == 0.95


async def test_pending_proposals_sorted_by_confidence_then_updated_at(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    base = datetime(2026, 3, 26, tzinfo=UTC)
    older = _proposal(conf=0.7, weekday=0)
    older.proposal_id = "older"
    older.updated_at = (base).isoformat()
    newer = _proposal(conf=0.7, weekday=1)
    newer.proposal_id = "newer"
    newer.updated_at = (base + timedelta(minutes=5)).isoformat()
    strongest = _proposal(conf=0.9, weekday=2)
    strongest.proposal_id = "strongest"
    strongest.updated_at = (base - timedelta(minutes=5)).isoformat()
    engine._proposals = [older, strongest, newer]

    ordered = engine.pending_proposals()
    assert [p.proposal_id for p in ordered] == ["strongest", "newer", "older"]


async def test_proposal_engine_diagnostics_include_summary_and_explainability(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    proposal = _proposal(conf=0.85, weekday=0)
    proposal.suggested_reaction_config = {
        "reaction_class": "PresencePatternReaction",
        "weekday": 0,
        "steps": [],
        "learning_diagnostics": {
            "pattern_id": "presence_preheat",
            "observations_count": 6,
            "weeks_observed": 2,
            "iqr_min": 8,
        },
    }
    engine._proposals = [proposal]

    diagnostics = engine.diagnostics()
    item = diagnostics["proposals"][0]
    assert item["config_summary"]["reaction_class"] == "PresencePatternReaction"
    assert item["config_summary"]["weekday"] == 0
    assert item["config_summary"]["steps_count"] == 0
    assert item["explainability"]["pattern_id"] == "presence_preheat"
    assert item["explainability"]["observations_count"] == 6
