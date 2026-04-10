"""Tests for ProposalEngine (learning system P4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.analyzers.lifecycle import ProposalLifecycleHooks
from custom_components.heima.runtime.analyzers.registry import (
    LearningPatternPluginDescriptor,
    LearningPluginRegistry,
)
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

    def set_proposals(self, proposals) -> None:
        self._proposals = list(proposals)

    async def analyze(self, event_store):  # noqa: ANN001, ARG002
        return list(self._proposals)


class _AnalyzerErrorStub:
    @property
    def analyzer_id(self) -> str:
        return "broken"

    async def analyze(self, event_store):  # noqa: ANN001, ARG002
        raise RuntimeError("boom")


class _AnalyzerInvalidOutputStub:
    @property
    def analyzer_id(self) -> str:
        return "invalid_output"

    async def analyze(self, event_store):  # noqa: ANN001, ARG002
        return ["not-a-proposal", _proposal(conf=0.8, weekday=3)]


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


def _lighting_proposal(
    *,
    conf: float,
    room_id: str,
    weekday: int,
    scheduled_min: int,
    fingerprint: str,
    entity_id: str | None = None,
    brightness: int | None = None,
    color_temp_kelvin: int | None = None,
) -> ReactionProposal:
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
            "entity_steps": [
                {
                    "entity_id": entity_id or f"light.{room_id}_main",
                    "action": "on",
                    "brightness": brightness,
                    "color_temp_kelvin": color_temp_kelvin,
                }
            ],
        },
        fingerprint=fingerprint,
    )


def _admin_authored_proposal() -> ReactionProposal:
    return ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="lighting_scene_schedule",
        description="admin-authored lighting",
        confidence=1.0,
        origin="admin_authored",
        suggested_reaction_config={
            "reaction_class": "LightingScheduleReaction",
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1200,
        },
    )


def _composite_proposal(
    *, reaction_type: str, room_id: str, primary_signal_name: str
) -> ReactionProposal:
    return ReactionProposal(
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type=reaction_type,
        confidence=0.8,
        description=f"{room_id}:{primary_signal_name}",
        suggested_reaction_config={
            "reaction_class": "RoomSignalAssistReaction",
            "room_id": room_id,
            "primary_signal_name": primary_signal_name,
        },
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
    assert "last_observed_at" in proposal_attrs
    assert proposal_attrs["origin"] == "learned"
    assert "identity_key" in proposal_attrs
    assert "config_summary" in proposal_attrs
    assert "explainability" in proposal_attrs


async def test_proposal_engine_dedup_pending_updates_confidence(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    analyzer = _AnalyzerStub([_proposal(conf=0.6)])
    engine.register_analyzer(analyzer)
    await engine.async_initialize()
    await engine.async_run()

    analyzer.set_proposals([_proposal(conf=0.85)])
    await engine.async_run()
    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].confidence == 0.85


async def test_proposal_engine_accepted_history_generates_followup_pending(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    analyzer = _AnalyzerStub([_proposal(conf=0.9)])
    engine.register_analyzer(analyzer)
    await engine.async_initialize()
    await engine.async_run()
    pid = engine.pending_proposals()[0].proposal_id
    assert await engine.async_accept_proposal(pid)

    analyzer.set_proposals([_proposal(conf=0.4)])
    await engine.async_run()
    all_pending = engine.pending_proposals()
    assert len(all_pending) == 1
    assert all_pending[0].followup_kind == "tuning_suggestion"


async def test_proposal_engine_still_skips_rejected_history(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    analyzer = _AnalyzerStub([_proposal(conf=0.9, weekday=1)])
    engine.register_analyzer(analyzer)
    await engine.async_initialize()
    await engine.async_run()
    pid = engine.pending_proposals()[0].proposal_id
    assert await engine.async_reject_proposal(pid)

    analyzer.set_proposals([_proposal(conf=0.95, weekday=1)])
    await engine.async_run()

    assert engine.pending_proposals() == []


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

    pending = engine2.pending_proposals()
    assert len(pending) == 1
    assert pending[0].fingerprint == "LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200"
    assert pending[0].origin == "learned"
    assert engine2.diagnostics()["load_errors"] == 0


async def test_proposal_engine_assigns_identity_key_and_last_observed_at(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine.register_analyzer(_AnalyzerStub([_proposal(conf=0.9, weekday=2)]))
    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].identity_key == "presence_preheat|weekday=2"
    assert pending[0].last_observed_at


async def test_proposal_engine_lighting_identity_uses_30_minute_bucket(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    first = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="lighting_scene_schedule",
        confidence=0.8,
        description="living:1205",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1205,
            "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
        },
    )
    second = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="lighting_scene_schedule",
        confidence=0.9,
        description="living:1225",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1225,
            "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
        },
    )
    analyzer = _AnalyzerStub([first])
    engine.register_analyzer(analyzer)
    await engine.async_initialize()
    await engine.async_run()

    analyzer.set_proposals([second])
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].identity_key.startswith(
        "lighting_scene_schedule|room=living|weekday=0|bucket=1200|scene="
    )
    assert pending[0].confidence == 0.9


async def test_proposal_engine_lighting_identity_prefers_semantic_slot_over_fingerprint(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    analyzer = _AnalyzerStub(
        [
            _lighting_proposal(
                conf=0.9,
                room_id="living",
                weekday=0,
                scheduled_min=1360,
                fingerprint="LightingPatternAnalyzer|lighting_scene_schedule|living|0|1350",
            )
        ]
    )
    engine.register_analyzer(analyzer)

    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].fingerprint == "LightingPatternAnalyzer|lighting_scene_schedule|living|0|1350"
    assert pending[0].identity_key.startswith(
        "lighting_scene_schedule|room=living|weekday=0|bucket=1350|scene="
    )


async def test_proposal_engine_lighting_identity_tolerates_minor_scene_drift(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    first = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="lighting_scene_schedule",
        confidence=0.8,
        description="living:1205",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1205,
            "entity_steps": [{"entity_id": "light.living_main", "action": "on", "brightness": 120}],
        },
    )
    second = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="lighting_scene_schedule",
        confidence=0.9,
        description="living:1225",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1225,
            "entity_steps": [{"entity_id": "light.living_main", "action": "on", "brightness": 135}],
        },
    )
    analyzer = _AnalyzerStub([first])
    engine.register_analyzer(analyzer)
    await engine.async_initialize()
    await engine.async_run()

    analyzer.set_proposals([second])
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].confidence == 0.9


async def test_proposal_engine_lighting_identity_separates_materially_different_scenes(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    first = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="lighting_scene_schedule",
        confidence=0.8,
        description="living:1205",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1205,
            "entity_steps": [{"entity_id": "light.living_main", "action": "on", "brightness": 96}],
        },
    )
    second = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="lighting_scene_schedule",
        confidence=0.9,
        description="living:1225",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1225,
            "entity_steps": [
                {"entity_id": "light.living_main", "action": "on", "brightness": 224},
                {"entity_id": "light.living_spot", "action": "off"},
            ],
        },
    )
    analyzer = _AnalyzerStub([first, second])
    engine.register_analyzer(analyzer)
    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 2
    assert pending[0].identity_key != pending[1].identity_key


async def test_proposal_engine_restart_dedup_uses_persisted_fingerprint(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    fp1 = "LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200"
    fp2 = "LightingPatternAnalyzer|lighting_scene_schedule|bedroom|0|1200"

    engine1 = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine1.register_analyzer(
        _AnalyzerStub(
            [
                _lighting_proposal(
                    conf=0.7, room_id="living", weekday=0, scheduled_min=1200, fingerprint=fp1
                ),
                _lighting_proposal(
                    conf=0.8, room_id="bedroom", weekday=0, scheduled_min=1200, fingerprint=fp2
                ),
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
            _lighting_proposal(
                conf=0.9, room_id="living", weekday=0, scheduled_min=1200, fingerprint=fp1
            ),
            _lighting_proposal(
                conf=0.95, room_id="bedroom", weekday=0, scheduled_min=1200, fingerprint=fp2
            ),
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
    engine._store._data = {
        "data": {"proposals": [older.as_dict(), strongest.as_dict(), newer.as_dict()]}
    }

    await engine.async_initialize()

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
    engine._store._data = {"data": {"proposals": [proposal.as_dict()]}}

    await engine.async_initialize()

    diagnostics = engine.diagnostics()
    assert diagnostics["pending_stale"] == 0
    assert diagnostics["stale_after_s"] == 14 * 24 * 60 * 60
    assert diagnostics["prune_pending_stale_after_s"] == 45 * 24 * 60 * 60
    item = diagnostics["proposals"][0]
    assert item["identity_key"] == "presence_preheat|weekday=0"
    assert item["last_observed_at"]
    assert item["is_stale"] is False
    assert item["stale_reason"] is None
    assert item["config_summary"]["reaction_type"] == "presence_preheat"
    assert item["config_summary"]["weekday"] == 0
    assert item["config_summary"]["steps_count"] == 0
    assert item["explainability"]["pattern_id"] == "presence_preheat"
    assert item["explainability"]["observations_count"] == 6


async def test_proposal_engine_marks_old_pending_proposal_as_stale(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub(), stale_after=timedelta(days=7))  # type: ignore[arg-type]
    proposal = _proposal(conf=0.75, weekday=1)
    old_ts = datetime(2026, 3, 1, tzinfo=UTC).isoformat()
    proposal.created_at = old_ts
    proposal.updated_at = old_ts
    proposal.last_observed_at = old_ts
    engine._store._data = {"data": {"proposals": [proposal.as_dict()]}}

    await engine.async_initialize()

    diagnostics = engine.diagnostics()

    assert diagnostics["pending_stale"] == 1
    item = diagnostics["proposals"][0]
    assert item["is_stale"] is True
    assert item["stale_reason"].startswith("not_observed_recently:")


async def test_proposal_engine_never_marks_accepted_proposal_as_stale(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub(), stale_after=timedelta(days=1))  # type: ignore[arg-type]
    proposal = _proposal(conf=0.75, weekday=1, status="accepted")
    proposal.last_observed_at = datetime(2026, 3, 1, tzinfo=UTC).isoformat()
    engine._store._data = {"data": {"proposals": [proposal.as_dict()]}}

    await engine.async_initialize()

    diagnostics = engine.diagnostics()

    assert diagnostics["pending_stale"] == 0
    item = diagnostics["proposals"][0]
    assert item["is_stale"] is False
    assert item["stale_reason"] is None


async def test_proposal_engine_prunes_very_old_stale_pending_proposals(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(
        object(),
        _EventStoreStub(),
        stale_after=timedelta(days=7),
        prune_pending_stale_after=timedelta(days=30),
    )  # type: ignore[arg-type]
    old_pending = _proposal(conf=0.7, weekday=0)
    old_pending.last_observed_at = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    recent_pending = _proposal(conf=0.8, weekday=1)
    recent_pending.last_observed_at = datetime.now(UTC).isoformat()
    accepted = _proposal(conf=0.9, weekday=2, status="accepted")
    accepted.last_observed_at = datetime(2026, 1, 1, tzinfo=UTC).isoformat()

    analyzer = _AnalyzerStub([recent_pending])
    engine.register_analyzer(analyzer)
    engine._store._data = {
        "data": {
            "proposals": [
                old_pending.as_dict(),
                recent_pending.as_dict(),
                accepted.as_dict(),
            ]
        }
    }
    await engine.async_initialize()

    await engine.async_run()

    diagnostics = engine.diagnostics()
    assert diagnostics["total"] == 2
    assert all(
        not (
            proposal["status"] == "pending"
            and proposal["last_observed_at"] == datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        )
        for proposal in diagnostics["proposals"]
    )
    assert any(proposal["status"] == "accepted" for proposal in diagnostics["proposals"])


async def test_proposal_engine_initialize_skips_malformed_storage_records(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {
        "data": {
            "proposals": [
                {
                    "proposal_id": "ok",
                    "analyzer_id": "PresencePatternAnalyzer",
                    "reaction_type": "presence_preheat",
                    "description": "ok",
                    "confidence": "0.7",
                    "status": "pending",
                    "suggested_reaction_config": {"weekday": 0},
                },
                {
                    "proposal_id": "missing_type",
                    "analyzer_id": "PresencePatternAnalyzer",
                    "description": "bad",
                    "confidence": "0.5",
                    "status": "pending",
                },
                "not-a-dict",
            ]
        }
    }

    await engine.async_initialize()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    diagnostics = engine.diagnostics()
    assert diagnostics["loaded_proposals"] == 1
    assert diagnostics["load_errors"] == 2


async def test_reaction_proposal_from_dict_sanitizes_invalid_status_and_confidence(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {
        "data": {
            "proposals": [
                {
                    "proposal_id": "weird",
                    "analyzer_id": "PresencePatternAnalyzer",
                    "reaction_type": "presence_preheat",
                    "description": "weird",
                    "confidence": "not-a-number",
                    "status": "stale",
                    "suggested_reaction_config": {"weekday": 2},
                }
            ]
        }
    }

    await engine.async_initialize()

    proposal = engine.pending_proposals()[0]
    assert proposal.confidence == 0.0
    assert proposal.origin == "learned"
    assert proposal.status == "pending"


async def test_reaction_proposal_from_dict_preserves_admin_authored_origin(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {
        "data": {
            "proposals": [
                {
                    "proposal_id": "admin-1",
                    "analyzer_id": "LightingPatternAnalyzer",
                    "reaction_type": "lighting_scene_schedule",
                    "description": "admin",
                    "confidence": 1.0,
                    "origin": "admin_authored",
                    "status": "pending",
                    "suggested_reaction_config": {
                        "room_id": "living",
                        "weekday": 0,
                        "scheduled_min": 1200,
                    },
                }
            ]
        }
    }

    await engine.async_initialize()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].origin == "admin_authored"


async def test_reaction_proposal_from_dict_sanitizes_non_dict_config(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {
        "data": {
            "proposals": [
                {
                    "proposal_id": "odd",
                    "analyzer_id": "PresencePatternAnalyzer",
                    "reaction_type": "presence_preheat",
                    "description": "odd",
                    "confidence": 0.5,
                    "status": "pending",
                    "suggested_reaction_config": ["not", "a", "dict"],
                }
            ]
        }
    }

    await engine.async_initialize()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].suggested_reaction_config == {}


async def test_proposal_engine_run_survives_analyzer_exception(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine.register_analyzer(_AnalyzerErrorStub())
    engine.register_analyzer(_AnalyzerStub([_proposal(conf=0.8, weekday=1)]))

    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    diagnostics = engine.diagnostics()
    assert diagnostics["analyzer_failures"] == 1
    assert diagnostics["analyzer_output_errors"] == 0


async def test_proposal_engine_run_skips_invalid_analyzer_outputs(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine.register_analyzer(_AnalyzerInvalidOutputStub())

    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    diagnostics = engine.diagnostics()
    assert diagnostics["analyzer_failures"] == 0
    assert diagnostics["analyzer_output_errors"] == 1


async def test_proposal_engine_restart_dedup_uses_computed_identity_for_legacy_records(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {
        "data": {
            "proposals": [
                {
                    "proposal_id": "legacy-presence",
                    "analyzer_id": "PresencePatternAnalyzer",
                    "reaction_type": "presence_preheat",
                    "description": "legacy",
                    "confidence": 0.6,
                    "status": "pending",
                    "fingerprint": "",
                    "identity_key": "",
                    "suggested_reaction_config": {"weekday": 0},
                }
            ]
        }
    }
    engine.register_analyzer(_AnalyzerStub([_proposal(conf=0.9, weekday=0)]))

    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].confidence == 0.9
    assert pending[0].identity_key == "presence_preheat|weekday=0"


async def test_proposal_engine_diagnostics_tolerate_non_dict_config(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    sensor_updates = []
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        sensor_writer=lambda count, attrs: sensor_updates.append((count, attrs)),
    )
    engine._store._data = {
        "data": {
            "proposals": [
                {
                    "proposal_id": "legacy",
                    "analyzer_id": "PresencePatternAnalyzer",
                    "reaction_type": "presence_preheat",
                    "description": "legacy",
                    "confidence": 0.5,
                    "status": "pending",
                    "suggested_reaction_config": ["bad"],
                }
            ]
        }
    }

    await engine.async_initialize()

    diagnostics = engine.diagnostics()
    engine._write_sensor()

    item = diagnostics["proposals"][0]
    assert item["origin"] == "learned"
    assert item["config_summary"] == {"reaction_type": "presence_preheat"}
    assert item["explainability"] == {}
    assert sensor_updates[-1][1]["legacy"]["origin"] == "learned"
    assert sensor_updates[-1][1]["legacy"]["config_summary"] == {
        "reaction_type": "presence_preheat"
    }
    assert sensor_updates[-1][1]["legacy"]["explainability"] == {}


async def test_proposal_engine_run_sanitizes_non_dict_config_on_pending_update(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    analyzer = _AnalyzerStub([_proposal(conf=0.6, weekday=0)])
    engine.register_analyzer(analyzer)

    await engine.async_initialize()
    await engine.async_run()

    analyzer.set_proposals(
        [
            ReactionProposal(
                analyzer_id="PresencePatternAnalyzer",
                reaction_type="presence_preheat",
                confidence=0.85,
                description="bad-update",
                identity_key="presence_preheat|weekday=0",
                suggested_reaction_config=["bad"],  # type: ignore[arg-type]
            )
        ]
    )
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].confidence == 0.85
    assert pending[0].suggested_reaction_config == {}


async def test_proposal_engine_diagnostics_expose_admin_authored_origin(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    sensor_updates = []
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        sensor_writer=lambda count, attrs: sensor_updates.append((count, attrs)),
    )
    await engine.async_initialize()
    proposal = _admin_authored_proposal()
    proposal_id = await engine.async_submit_proposal(proposal)

    diagnostics = engine.diagnostics()

    item = diagnostics["proposals"][0]
    assert item["origin"] == "admin_authored"
    assert sensor_updates[-1][1][proposal_id]["origin"] == "admin_authored"


async def test_proposal_engine_sensor_writer_keeps_count_in_state_and_payload_in_attrs(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    sensor_updates = []
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        sensor_writer=lambda count, attrs: sensor_updates.append((count, attrs)),
    )
    await engine.async_initialize()
    proposal_ids = []
    for index in range(5):
        proposal = _admin_authored_proposal()
        proposal.suggested_reaction_config["scheduled_min"] = 1200 + (index * 30)
        proposal_ids.append(await engine.async_submit_proposal(proposal))

    count, attrs = sensor_updates[-1]
    assert count == 5
    assert isinstance(count, int)
    assert len(str(count)) < 255
    assert len(attrs) == 5
    assert attrs[proposal_ids[0]]["origin"] == "admin_authored"


async def test_proposal_engine_async_submit_proposal_creates_pending_admin_authored(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()
    proposal = _admin_authored_proposal()
    proposal_id = await engine.async_submit_proposal(proposal)

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].proposal_id == proposal_id
    assert pending[0].origin == "admin_authored"


async def test_proposal_engine_async_submit_proposal_updates_existing_pending_identity(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()
    first = _admin_authored_proposal()
    proposal_id = await engine.async_submit_proposal(first)

    second = _admin_authored_proposal()
    second.description = "Updated draft"
    updated_id = await engine.async_submit_proposal(second)

    pending = engine.pending_proposals()
    assert updated_id == proposal_id
    assert len(pending) == 1
    assert pending[0].description == "Updated draft"


async def test_proposal_engine_async_submit_proposal_reopens_existing_accepted_identity(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()
    first = _admin_authored_proposal()
    proposal_id = await engine.async_submit_proposal(first)
    assert await engine.async_accept_proposal(proposal_id)

    second = _admin_authored_proposal()
    second.description = "Reopened draft"
    reopened_id = await engine.async_submit_proposal(second)

    pending = engine.pending_proposals()
    assert reopened_id == proposal_id
    assert len(pending) == 1
    assert pending[0].proposal_id == proposal_id
    assert pending[0].status == "pending"
    assert pending[0].description == "Reopened draft"


async def test_proposal_engine_async_submit_proposal_sanitizes_non_dict_config(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()
    proposal = _admin_authored_proposal()
    proposal.suggested_reaction_config = ["bad"]  # type: ignore[assignment]
    proposal_id = await engine.async_submit_proposal(proposal)

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].proposal_id == proposal_id
    assert pending[0].suggested_reaction_config == {}


async def test_proposal_engine_shutdown_persists_latest_accepted_status(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine.register_analyzer(_AnalyzerStub([_proposal(conf=0.9, weekday=0)]))

    await engine.async_initialize()
    await engine.async_run()
    proposal_id = engine.pending_proposals()[0].proposal_id
    assert await engine.async_accept_proposal(proposal_id)

    await engine.async_shutdown()

    stored = engine._store._data
    assert isinstance(stored, dict)
    proposals = ((stored.get("data") or {}).get("proposals")) or []
    assert len(proposals) == 1
    assert proposals[0]["proposal_id"] == proposal_id
    assert proposals[0]["status"] == "accepted"


async def test_proposal_engine_shutdown_persisted_state_reloads_with_single_followup_pending(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine1 = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine1.register_analyzer(_AnalyzerStub([_proposal(conf=0.7, weekday=2)]))

    await engine1.async_initialize()
    await engine1.async_run()
    proposal_id = engine1.pending_proposals()[0].proposal_id
    assert await engine1.async_accept_proposal(proposal_id)
    await engine1.async_shutdown()

    engine2 = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine2._store._data = engine1._store._data
    engine2.register_analyzer(_AnalyzerStub([_proposal(conf=0.95, weekday=2)]))

    await engine2.async_initialize()
    await engine2.async_run()

    diagnostics = engine2.diagnostics()
    assert diagnostics["total"] == 2
    accepted = next(
        proposal for proposal in diagnostics["proposals"] if proposal["status"] == "accepted"
    )
    pending = next(
        proposal for proposal in diagnostics["proposals"] if proposal["status"] == "pending"
    )
    assert accepted["id"] == proposal_id
    assert accepted["confidence"] == 0.7
    assert pending["followup_kind"] == "tuning_suggestion"
    assert pending["confidence"] == 0.95


async def test_lighting_followup_minor_drift_is_suppressed(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _lighting_proposal(
        conf=0.9,
        room_id="living",
        weekday=0,
        scheduled_min=1200,
        fingerprint="LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200",
        brightness=192,
        color_temp_kelvin=2750,
    )
    candidate = _lighting_proposal(
        conf=0.92,
        room_id="living",
        weekday=0,
        scheduled_min=1204,
        fingerprint="LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200",
        brightness=176,
        color_temp_kelvin=2850,
    )

    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {"data": {"proposals": [{**base.as_dict(), "status": "accepted"}]}}
    engine.register_analyzer(_AnalyzerStub([candidate]))

    await engine.async_initialize()
    await engine.async_run()

    diagnostics = engine.diagnostics()
    assert diagnostics["total"] == 1
    assert diagnostics["proposals"][0]["status"] == "accepted"


async def test_lighting_followup_material_drift_still_creates_tuning(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _lighting_proposal(
        conf=0.9,
        room_id="living",
        weekday=0,
        scheduled_min=1200,
        fingerprint="LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200",
        brightness=192,
        color_temp_kelvin=2750,
    )
    candidate = _lighting_proposal(
        conf=0.92,
        room_id="living",
        weekday=0,
        scheduled_min=1218,
        fingerprint="LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200",
        brightness=96,
        color_temp_kelvin=3250,
    )

    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {"data": {"proposals": [{**base.as_dict(), "status": "accepted"}]}}
    engine.register_analyzer(_AnalyzerStub([candidate]))

    await engine.async_initialize()
    await engine.async_run()

    diagnostics = engine.diagnostics()
    assert diagnostics["total"] == 2
    pending = next(item for item in diagnostics["proposals"] if item["status"] == "pending")
    assert pending["followup_kind"] == "tuning_suggestion"


async def test_proposal_engine_uses_plugin_lifecycle_hooks_for_identity(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    registry = LearningPluginRegistry()
    registry.register(
        descriptor=LearningPatternPluginDescriptor(
            plugin_id="test.presence",
            analyzer_id="PresencePatternAnalyzer",
            plugin_family="presence",
            proposal_types=("presence_preheat",),
            reaction_targets=("PresencePatternReaction",),
            lifecycle_hooks=ProposalLifecycleHooks(
                identity_key=lambda proposal: (
                    f"custom|weekday={proposal.suggested_reaction_config.get('weekday')}"
                )
            ),
        ),
        analyzer=_AnalyzerStub([]),
    )
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        learning_plugin_registry=registry,
    )

    await engine.async_initialize()
    proposal_id = await engine.async_submit_proposal(_proposal(conf=0.8, weekday=4))

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].proposal_id == proposal_id
    assert pending[0].identity_key == "custom|weekday=4"


async def test_proposal_engine_composite_identity_uses_room_and_primary_signal(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    analyzer = _AnalyzerStub(
        [
            _composite_proposal(
                reaction_type="room_signal_assist",
                room_id="bathroom",
                primary_signal_name="humidity",
            )
        ]
    )
    engine.register_analyzer(analyzer)

    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].identity_key == "room_signal_assist|room=bathroom|primary=humidity"


async def test_proposal_engine_composite_config_summary_exposes_signal_fields(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    proposal = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="humidity",
    )
    proposal.suggested_reaction_config.update(
        {
            "primary_threshold_mode": "rise",
            "primary_threshold": 8.0,
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "temperature",
            "corroboration_threshold_mode": "rise",
            "corroboration_threshold": 0.8,
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [],
        }
    )
    engine._store._data = {"data": {"proposals": [proposal.as_dict()]}}

    await engine.async_initialize()

    diagnostics = engine.diagnostics()

    summary = diagnostics["proposals"][0]["config_summary"]
    assert summary["primary_signal_name"] == "humidity"
    assert summary["primary_threshold_mode"] == "rise"
    assert summary["primary_threshold"] == 8.0
    assert summary["primary_signal_entities_count"] == 1
    assert summary["corroboration_signal_name"] == "temperature"
    assert summary["corroboration_threshold_mode"] == "rise"
    assert summary["corroboration_threshold"] == 0.8
    assert summary["corroboration_signal_entities_count"] == 1


async def test_proposal_engine_creates_composite_tuning_followup_for_accepted_slot(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="humidity",
    )
    base = ReactionProposal.from_dict(
        {
            **base.as_dict(),
            "status": "accepted",
            "origin": "admin_authored",
        }
    )
    candidate = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="humidity",
    )
    candidate.suggested_reaction_config.update(
        {
            "primary_threshold": 9.5,
            "primary_threshold_mode": "above",
            "primary_signal_entities": [
                "sensor.bathroom_humidity",
                "sensor.bathroom_humidity_aux",
            ],
            "corroboration_threshold": 1.2,
            "corroboration_threshold_mode": "above",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [
                {
                    "domain": "fan",
                    "target": "fan.bathroom",
                    "action": "fan.turn_on",
                    "params": {"entity_id": "fan.bathroom"},
                }
            ],
        }
    )

    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {"data": {"proposals": [base.as_dict()]}}
    engine.register_analyzer(_AnalyzerStub([candidate]))

    await engine.async_initialize()
    await engine.async_run()

    diagnostics = engine.diagnostics()
    assert diagnostics["total"] == 2
    pending = next(item for item in diagnostics["proposals"] if item["status"] == "pending")
    assert pending["followup_kind"] == "tuning_suggestion"
    assert pending["identity_key"] == "room_signal_assist|room=bathroom|primary=humidity"


async def test_proposal_engine_suppresses_minor_room_signal_assist_tuning_drift(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="humidity",
    )
    base = ReactionProposal.from_dict(
        {
            **base.as_dict(),
            "status": "accepted",
            "origin": "admin_authored",
        }
    )
    base.suggested_reaction_config.update(
        {
            "primary_threshold_mode": "rise",
            "primary_threshold": 8.0,
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_threshold_mode": "rise",
            "corroboration_threshold": 0.8,
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [],
        }
    )
    candidate = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="humidity",
    )
    candidate.suggested_reaction_config.update(
        {
            "primary_threshold_mode": "rise",
            "primary_threshold": 8.5,
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_threshold_mode": "rise",
            "corroboration_threshold": 0.8,
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [],
        }
    )

    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {"data": {"proposals": [base.as_dict()]}}
    engine.register_analyzer(_AnalyzerStub([candidate]))

    await engine.async_initialize()
    await engine.async_run()

    assert len(engine.pending_proposals()) == 0


async def test_proposal_engine_creates_room_darkness_lighting_tuning_followup(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _composite_proposal(
        reaction_type="room_darkness_lighting_assist",
        room_id="living",
        primary_signal_name="room_lux",
    )
    base = ReactionProposal.from_dict(
        {
            **base.as_dict(),
            "status": "accepted",
            "origin": "admin_authored",
        }
    )
    base.suggested_reaction_config.update(
        {
            "reaction_class": "RoomLightingAssistReaction",
            "primary_threshold_mode": "below",
            "primary_threshold": 100.0,
            "primary_signal_entities": ["sensor.living_room_lux"],
            "entity_steps": [
                {
                    "entity_id": "light.living_main",
                    "action": "on",
                    "brightness": 190,
                    "color_temp_kelvin": 2850,
                    "rgb_color": None,
                }
            ],
        }
    )
    candidate = _composite_proposal(
        reaction_type="room_darkness_lighting_assist",
        room_id="living",
        primary_signal_name="room_lux",
    )
    candidate.suggested_reaction_config.update(
        {
            "reaction_class": "RoomLightingAssistReaction",
            "primary_threshold_mode": "below",
            "primary_threshold": 120.0,
            "primary_signal_entities": [
                "sensor.living_room_lux",
                "sensor.living_room_lux_aux",
            ],
            "entity_steps": [
                {
                    "entity_id": "light.living_main",
                    "action": "on",
                    "brightness": 144,
                    "color_temp_kelvin": 2900,
                    "rgb_color": None,
                }
            ],
        }
    )

    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {"data": {"proposals": [base.as_dict()]}}
    engine.register_analyzer(_AnalyzerStub([candidate]))

    await engine.async_initialize()
    await engine.async_run()

    diagnostics = engine.diagnostics()
    assert diagnostics["total"] == 2
    pending = next(item for item in diagnostics["proposals"] if item["status"] == "pending")
    assert pending["followup_kind"] == "tuning_suggestion"
    assert pending["identity_key"] == "room_darkness_lighting_assist|room=living|primary=room_lux"


async def test_proposal_engine_suppresses_minor_room_darkness_lighting_tuning_drift(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _composite_proposal(
        reaction_type="room_darkness_lighting_assist",
        room_id="living",
        primary_signal_name="room_lux",
    )
    base = ReactionProposal.from_dict(
        {
            **base.as_dict(),
            "status": "accepted",
            "origin": "admin_authored",
        }
    )
    base.suggested_reaction_config.update(
        {
            "reaction_class": "RoomLightingAssistReaction",
            "primary_threshold_mode": "below",
            "primary_threshold": 120.0,
            "primary_signal_entities": ["sensor.living_room_lux"],
            "entity_steps": [
                {
                    "entity_id": "light.living_main",
                    "action": "on",
                    "brightness": 160,
                    "color_temp_kelvin": 2800,
                    "rgb_color": None,
                }
            ],
        }
    )
    candidate = _composite_proposal(
        reaction_type="room_darkness_lighting_assist",
        room_id="living",
        primary_signal_name="room_lux",
    )
    candidate.suggested_reaction_config.update(
        {
            "reaction_class": "RoomLightingAssistReaction",
            "primary_threshold_mode": "below",
            "primary_threshold": 125.0,
            "primary_signal_entities": ["sensor.living_room_lux"],
            "entity_steps": [
                {
                    "entity_id": "light.living_main",
                    "action": "on",
                    "brightness": 168,
                    "color_temp_kelvin": 2900,
                    "rgb_color": None,
                }
            ],
        }
    )

    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {"data": {"proposals": [base.as_dict()]}}
    engine.register_analyzer(_AnalyzerStub([candidate]))

    await engine.async_initialize()
    await engine.async_run()

    assert len(engine.pending_proposals()) == 0
