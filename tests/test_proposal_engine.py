"""Tests for ProposalEngine (learning system P4)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.analyzers.heating import HeatingPatternAnalyzer
from custom_components.heima.runtime.analyzers.lifecycle import (
    ProposalLifecycleHooks,
    ProposalReviewGrouping,
)
from custom_components.heima.runtime.analyzers.presence import PresencePatternAnalyzer
from custom_components.heima.runtime.analyzers.registry import (
    LearningPatternPluginDescriptor,
    LearningPluginRegistry,
    create_builtin_learning_plugin_registry,
)
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent
from custom_components.heima.runtime.finding_router import FindingRouter
from custom_components.heima.runtime.inference.approval_store import HOUSE_STATE_PROPOSAL_TYPE
from custom_components.heima.runtime.plugin_contracts import (
    AnomalySignal,
    BehaviorFinding,
    IBehaviorAnalyzer,
)
from custom_components.heima.runtime.proposal_engine import (
    AcceptedRuleLifecyclePolicy,
    ActivityProposal,
    ProposalEngine,
)
from custom_components.heima.runtime.proposal_lifecycle_store import (
    ProposalLifecycleRecord,
    ProposalLifecycleStore,
)


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

    async def analyze(self, event_store, snapshot_store=None):  # noqa: ANN001, ARG002
        return [
            BehaviorFinding(
                kind="pattern",
                analyzer_id=self.analyzer_id,
                description=proposal.description,
                confidence=proposal.confidence,
                payload=proposal,
            )
            for proposal in self._proposals
        ]


class _AnalyzerErrorStub:
    @property
    def analyzer_id(self) -> str:
        return "broken"

    async def analyze(self, event_store, snapshot_store=None):  # noqa: ANN001, ARG002
        raise RuntimeError("boom")


class _AnalyzerInvalidOutputStub:
    @property
    def analyzer_id(self) -> str:
        return "invalid_output"

    async def analyze(self, event_store, snapshot_store=None):  # noqa: ANN001, ARG002
        proposal = _proposal(conf=0.8, weekday=3)
        return [
            "not-a-proposal",
            BehaviorFinding(
                kind="pattern",
                analyzer_id=self.analyzer_id,
                description=proposal.description,
                confidence=proposal.confidence,
                payload=proposal,
            ),
        ]


class _FindingAnalyzerStub:
    @property
    def analyzer_id(self) -> str:
        return "finding_stub"

    async def analyze(self, event_store, snapshot_store=None):  # noqa: ANN001, ARG002
        proposal = _proposal(conf=0.8, weekday=4)
        return [
            BehaviorFinding(
                kind="pattern",
                analyzer_id=self.analyzer_id,
                description=proposal.description,
                confidence=proposal.confidence,
                payload=proposal,
            )
        ]


class _ActivityFindingAnalyzerStub:
    @property
    def analyzer_id(self) -> str:
        return "activity_stub"

    async def analyze(self, event_store, snapshot_store=None):  # noqa: ANN001, ARG002
        proposal = _activity_proposal(conf=0.83)
        return [
            BehaviorFinding(
                kind="activity",
                analyzer_id=self.analyzer_id,
                description="activity",
                confidence=proposal.confidence,
                payload=proposal,
            )
        ]


class _EventStoreStub:
    pass


class _EventStoreWithEvents:
    def __init__(self, events: list[HeimaEvent]) -> None:
        self.events = events

    async def async_query(
        self,
        *,
        event_type=None,  # noqa: ANN001
        room_id=None,  # noqa: ANN001
        subject_id=None,  # noqa: ANN001
        since=None,  # noqa: ANN001
        limit=None,  # noqa: ANN001
    ) -> list[HeimaEvent]:
        results = list(self.events)
        if since:
            results = [event for event in results if event.ts >= since]
        if event_type:
            results = [event for event in results if event.event_type == event_type]
        if room_id is not None:
            results = [event for event in results if event.room_id == room_id]
        if subject_id is not None:
            results = [event for event in results if event.subject_id == subject_id]
        if limit is not None and limit >= 0:
            return results[-limit:]
        return results


class _FakeLifecycleStore:
    def __init__(self) -> None:
        self.loaded = False
        self.records_by_id: dict[str, ProposalLifecycleRecord] = {}
        self.upsert_calls = 0

    async def async_load(self) -> None:
        self.loaded = True

    async def async_upsert_missing(self, record: ProposalLifecycleRecord) -> bool:
        self.upsert_calls += 1
        if record.proposal_id in self.records_by_id:
            return False
        self.records_by_id[record.proposal_id] = record
        return True

    async def async_replace_record(self, record: ProposalLifecycleRecord) -> bool:
        if self.records_by_id.get(record.proposal_id) == record:
            return False
        self.records_by_id[record.proposal_id] = record
        return True

    def records(self) -> list[ProposalLifecycleRecord]:
        return list(self.records_by_id.values())

    def record_by_proposal_id(self, proposal_id: str) -> ProposalLifecycleRecord | None:
        return self.records_by_id.get(str(proposal_id or "").strip())

    def diagnostics(self) -> dict[str, object]:
        return {
            "storage_key": "fake",
            "loaded": self.loaded,
            "record_count": len(self.records_by_id),
            "records": [record.as_dict() for record in self.records_by_id.values()],
        }


def _proposal(*, conf: float, weekday: int = 0, status: str = "pending") -> ReactionProposal:
    return ReactionProposal(
        analyzer_id="PresencePatternAnalyzer",
        reaction_type="presence_preheat",
        confidence=conf,
        status=status,  # type: ignore[arg-type]
        description="proposal",
        suggested_reaction_config={"weekday": weekday},
    )


def _activity_proposal(
    *,
    conf: float = 0.8,
    activity_name: str = "movie_night",
    status: str = "pending",
    bootstrap: bool = False,
) -> ActivityProposal:
    return ActivityProposal(
        activity_name=activity_name,
        primitive_pattern=frozenset({"tv", "relax"}),
        context_conditions={"room_id": "living_room", "hour_range": [20, 24]},
        occurrence_count=12,
        confidence=conf,
        representative_ts=["2026-05-01T20:00:00+00:00"],
        bootstrap=bootstrap,
        status=status,
    )


def _house_state_lifecycle_proposal(*, context_key: str = "ctx-alpha") -> ReactionProposal:
    return ReactionProposal(
        analyzer_id="house_state_inference",
        reaction_type=HOUSE_STATE_PROPOSAL_TYPE,
        description="Learned house-state context predicts working.",
        confidence=1.0,
        identity_key=f"{HOUSE_STATE_PROPOSAL_TYPE}:{context_key}",
        suggested_reaction_config={
            "proposal_type": HOUSE_STATE_PROPOSAL_TYPE,
            "context_key": context_key,
            "context_snapshot": {
                "weekday": 1,
                "hour_bucket": 17,
                "anyone_home": True,
                "predicted_state": "working",
            },
            "predicted_state": "working",
            "support": 3,
            "total": 3,
        },
    )


def _configured_house_state_lifecycle_reaction(proposal: ReactionProposal) -> dict[str, object]:
    cfg = dict(proposal.suggested_reaction_config)
    cfg["reaction_type"] = proposal.reaction_type
    cfg["origin"] = proposal.origin
    cfg["author_kind"] = "heima"
    cfg["source_proposal_id"] = proposal.proposal_id
    cfg["source_proposal_identity_key"] = proposal.identity_key
    cfg["created_at"] = proposal.created_at
    cfg["source_request"] = "learned_pattern"
    return cfg


def _house_state_event(
    *,
    ts: str,
    weekday: int = 1,
    hour_bucket: int = 17,
    house_state: str = "working",
    anyone_home: bool = True,
    occupied_rooms: tuple[str, ...] = (),
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="house_state",
        context=EventContext(
            weekday=weekday,
            minute_of_day=hour_bucket * 60,
            month=6,
            house_state=house_state,
            occupants_count=1 if anyone_home else 0,
            occupied_rooms=occupied_rooms,
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals={},
        ),
        source=None,
        data={"to_state": house_state},
    )


def _house_state_events_for_days(
    states: list[str],
    *,
    anyone_home: bool = True,
) -> list[HeimaEvent]:
    return [
        _house_state_event(
            ts=f"2999-06-{index + 1:02d}T17:05:00+00:00",
            house_state=state,
            anyone_home=anyone_home,
        )
        for index, state in enumerate(states)
    ]


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
        reaction_type="context_conditioned_lighting_scene",
        confidence=conf,
        description=f"{room_id}:{scheduled_min}",
        suggested_reaction_config={
            "reaction_class": "ContextConditionedLightingReaction",
            "room_id": room_id,
            "weekday": weekday,
            "scheduled_min": scheduled_min,
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
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
        reaction_type="context_conditioned_lighting_scene",
        description="admin-authored lighting",
        confidence=1.0,
        origin="admin_authored",
        suggested_reaction_config={
            "reaction_class": "ContextConditionedLightingReaction",
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1200,
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
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
    assert sensor_updates[-1][1]["pending"] == 1
    proposal_attrs = sensor_updates[-1][1]["items"][pending[0].proposal_id]
    assert "updated_at" in proposal_attrs
    assert proposal_attrs["origin"] == "learned"
    assert proposal_attrs["type"] == "presence_preheat"


def test_reaction_proposal_from_dict_preserves_improvement_fields() -> None:
    proposal = ReactionProposal.from_dict(
        {
            "proposal_id": "improve-1",
            "analyzer_id": "CompositePatternCatalogAnalyzer",
            "reaction_type": "room_smart_lighting_assist",
            "description": "studio upgrade",
            "confidence": 0.81,
            "followup_kind": "improvement",
            "target_reaction_id": "darkness-1",
            "target_reaction_type": "room_smart_lighting_assist",
            "target_reaction_origin": "learned",
            "improves_reaction_type": "room_smart_lighting_assist",
            "improvement_reason": "time_window_variation",
            "suggested_reaction_config": {"room_id": "studio"},
        }
    )

    assert proposal.followup_kind == "improvement"
    assert proposal.target_reaction_id == "darkness-1"
    assert proposal.target_reaction_type == "room_smart_lighting_assist"
    assert proposal.improves_reaction_type == "room_smart_lighting_assist"
    assert proposal.improvement_reason == "time_window_variation"


def test_presence_and_heating_analyzers_satisfy_behavior_analyzer_protocol() -> None:
    assert isinstance(PresencePatternAnalyzer(), IBehaviorAnalyzer)
    assert isinstance(HeatingPatternAnalyzer(), IBehaviorAnalyzer)


def test_registered_learning_analyzers_satisfy_behavior_analyzer_protocol() -> None:
    registry = create_builtin_learning_plugin_registry()

    assert all(isinstance(analyzer, IBehaviorAnalyzer) for analyzer in registry.analyzers())


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


async def test_proposal_engine_accepts_behavior_findings(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine.register_analyzer(_FindingAnalyzerStub())  # type: ignore[arg-type]
    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].suggested_reaction_config["weekday"] == 4


async def test_proposal_engine_accepts_activity_findings(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine.register_analyzer(_ActivityFindingAnalyzerStub())  # type: ignore[arg-type]
    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert isinstance(pending[0], ActivityProposal)
    assert pending[0].activity_name == "movie_night"


async def test_finding_router_routes_pattern_and_activity_to_proposal_engine(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    await engine.async_initialize()
    router = FindingRouter(proposal_engine=engine)

    pattern_proposal = _proposal(conf=0.8, weekday=5)
    activity_proposal = _activity_proposal(conf=0.7)
    await router.async_route(
        [
            BehaviorFinding(
                kind="pattern",
                analyzer_id="pattern",
                description="pattern",
                confidence=0.8,
                payload=pattern_proposal,
            ),
            BehaviorFinding(
                kind="activity",
                analyzer_id="activity",
                description="activity",
                confidence=0.7,
                payload=activity_proposal,
            ),
        ]
    )

    pending = engine.pending_proposals()
    assert len(pending) == 2
    assert any(
        isinstance(item, ReactionProposal) and item.suggested_reaction_config["weekday"] == 5
        for item in pending
    )
    assert any(
        isinstance(item, ActivityProposal) and item.activity_name == "movie_night"
        for item in pending
    )


async def test_activity_finding_rejects_reaction_payload(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    await engine.async_initialize()
    router = FindingRouter(proposal_engine=engine)

    await router.async_route(
        [
            BehaviorFinding(
                kind="activity",
                analyzer_id="activity",
                description="activity",
                confidence=0.7,
                payload=_proposal(conf=0.7, weekday=6),
            )
        ]
    )

    assert engine.pending_proposals() == []


async def test_activity_proposal_round_trips_storage(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    await engine.async_initialize()
    proposal = _activity_proposal(conf=0.82, bootstrap=True)

    proposal_id = await engine.async_submit_proposal(proposal)

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].proposal_id == proposal_id
    assert isinstance(pending[0], ActivityProposal)
    assert pending[0].primitive_pattern == frozenset({"tv", "relax"})
    assert pending[0].bootstrap is True
    assert engine.diagnostics()["proposals"][0]["type"] == "activity_discovered"


async def test_activity_proposal_refreshes_pending_by_identity(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    await engine.async_initialize()

    first_id = await engine.async_submit_proposal(_activity_proposal(conf=0.62))
    second_id = await engine.async_submit_proposal(_activity_proposal(conf=0.91))

    pending = engine.pending_proposals()
    assert first_id == second_id
    assert len(pending) == 1
    assert pending[0].confidence == 0.91


async def test_finding_router_routes_anomaly_to_handler(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    await engine.async_initialize()
    handled = []
    router = FindingRouter(
        proposal_engine=engine, anomaly_handler=lambda signal: handled.append(signal)
    )
    signal = AnomalySignal(
        anomaly_type="arrival_outlier",
        severity="warning",
        description="Unusual arrival",
        confidence=0.75,
    )

    await router.async_route(
        [
            BehaviorFinding(
                kind="anomaly",
                analyzer_id="anomaly",
                description=signal.description,
                confidence=signal.confidence,
                payload=signal,
            )
        ]
    )

    assert handled == [signal]


async def test_proposal_engine_sensor_writer_exposes_improvement_metadata(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    sensor_updates = []
    proposal = ReactionProposal(
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_smart_lighting_assist",
        description="studio upgrade",
        confidence=0.84,
        followup_kind="improvement",
        target_reaction_id="darkness-1",
        target_reaction_type="room_smart_lighting_assist",
        target_reaction_origin="learned",
        improves_reaction_type="room_smart_lighting_assist",
        improvement_reason="house_state_variation",
        suggested_reaction_config={"room_id": "studio"},
    )
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        sensor_writer=lambda count, attrs: sensor_updates.append((count, attrs)),
    )
    engine.register_analyzer(_AnalyzerStub([proposal]))

    await engine.async_initialize()
    await engine.async_run()

    attrs = sensor_updates[-1][1]
    assert attrs["by_followup_kind"]["improvement"] == 1
    item = next(iter(attrs["items"].values()))
    assert item["followup_kind"] == "improvement"
    assert item["target_reaction_id"] == "darkness-1"
    assert item["target_reaction_type"] == "room_smart_lighting_assist"
    assert item["improves_reaction_type"] == "room_smart_lighting_assist"
    assert item["improvement_reason"] == "house_state_variation"
    assert "description" not in item


async def test_proposal_engine_dedup_pending_improvement_by_target_reaction(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    registry = create_builtin_learning_plugin_registry()
    analyzer = _AnalyzerStub(
        [
            ReactionProposal(
                analyzer_id="CompositePatternCatalogAnalyzer",
                reaction_type="room_smart_lighting_assist",
                description="studio upgrade",
                confidence=0.72,
                followup_kind="improvement",
                target_reaction_id="darkness-1",
                target_reaction_type="room_smart_lighting_assist",
                target_reaction_origin="learned",
                improves_reaction_type="room_smart_lighting_assist",
                improvement_reason="time_window_variation",
                suggested_reaction_config={
                    "room_id": "studio",
                    "primary_signal_name": "room_lux",
                },
            )
        ]
    )
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        learning_plugin_registry=registry,
    )
    engine.register_analyzer(analyzer)

    await engine.async_initialize()
    await engine.async_run()

    analyzer.set_proposals(
        [
            ReactionProposal(
                analyzer_id="CompositePatternCatalogAnalyzer",
                reaction_type="room_smart_lighting_assist",
                description="studio upgrade refined",
                confidence=0.88,
                followup_kind="improvement",
                target_reaction_id="darkness-1",
                target_reaction_type="room_smart_lighting_assist",
                target_reaction_origin="learned",
                improves_reaction_type="room_smart_lighting_assist",
                improvement_reason="house_state_variation",
                suggested_reaction_config={
                    "room_id": "studio",
                    "primary_signal_name": "room_lux",
                },
            )
        ]
    )
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].followup_kind == "improvement"
    assert pending[0].confidence == 0.88
    assert pending[0].description == "studio upgrade refined"


async def test_proposal_engine_normalizes_contextual_candidate_into_improvement(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    registry = create_builtin_learning_plugin_registry()
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        learning_plugin_registry=registry,
    )
    engine.register_analyzer(
        _AnalyzerStub(
            [
                ReactionProposal(
                    analyzer_id="CompositePatternCatalogAnalyzer",
                    reaction_type="room_smart_lighting_assist",
                    description="studio contextual candidate",
                    confidence=0.82,
                    suggested_reaction_config={
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "primary_bucket": "dim",
                    },
                )
            ]
        )
    )
    await engine.async_initialize()
    engine._proposals = [  # noqa: SLF001
        ReactionProposal(
            proposal_id="darkness-accepted",
            analyzer_id="CompositePatternCatalogAnalyzer",
            reaction_type="room_smart_lighting_assist",
            description="studio darkness",
            confidence=0.84,
            status="accepted",
            suggested_reaction_config={
                "room_id": "studio",
                "primary_signal_name": "room_lux",
                "admin_authored_template_id": "room.smart_lighting_assist.basic",
            },
        )
    ]

    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    proposal = pending[0]
    assert proposal.reaction_type == "room_smart_lighting_assist"
    assert proposal.followup_kind == "tuning_suggestion"
    assert proposal.target_reaction_id == ""
    assert proposal.target_reaction_type == "room_smart_lighting_assist"
    assert proposal.improves_reaction_type == ""
    assert proposal.improvement_reason == ""


async def test_proposal_engine_normalizes_contextual_candidate_into_improvement_from_configured_darkness(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    registry = create_builtin_learning_plugin_registry()
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        learning_plugin_registry=registry,
        configured_reactions_provider=lambda: {
            "darkness-configured": {
                "reaction_type": "room_smart_lighting_assist",
                "room_id": "studio",
                "primary_signal_name": "room_lux",
                "origin": "admin_authored",
                "source_template_id": "room.smart_lighting_assist.basic",
            }
        },
    )
    engine.register_analyzer(
        _AnalyzerStub(
            [
                ReactionProposal(
                    analyzer_id="CompositePatternCatalogAnalyzer",
                    reaction_type="room_smart_lighting_assist",
                    description="studio contextual candidate",
                    confidence=0.82,
                    suggested_reaction_config={
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "primary_bucket": "dim",
                    },
                )
            ]
        )
    )
    await engine.async_initialize()

    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    proposal = pending[0]
    assert proposal.reaction_type == "room_smart_lighting_assist"
    assert proposal.followup_kind == "discovery"
    assert proposal.target_reaction_id == ""
    assert proposal.target_reaction_type == ""
    assert proposal.target_reaction_origin == ""
    assert proposal.improves_reaction_type == ""
    assert proposal.improvement_reason == ""


async def test_proposal_engine_prefers_configured_darkness_over_accepted_history_for_improvement(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    registry = create_builtin_learning_plugin_registry()
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        learning_plugin_registry=registry,
        configured_reactions_provider=lambda: {
            "darkness-configured": {
                "reaction_type": "room_smart_lighting_assist",
                "room_id": "studio",
                "primary_signal_name": "room_lux",
                "origin": "admin_authored",
                "source_template_id": "room.smart_lighting_assist.basic",
            }
        },
    )
    engine.register_analyzer(
        _AnalyzerStub(
            [
                ReactionProposal(
                    analyzer_id="CompositePatternCatalogAnalyzer",
                    reaction_type="room_smart_lighting_assist",
                    description="studio contextual candidate",
                    confidence=0.82,
                    suggested_reaction_config={
                        "room_id": "studio",
                        "primary_signal_name": "room_lux",
                        "primary_bucket": "dim",
                    },
                )
            ]
        )
    )
    await engine.async_initialize()
    engine._proposals = [  # noqa: SLF001
        ReactionProposal(
            proposal_id="darkness-accepted",
            analyzer_id="CompositePatternCatalogAnalyzer",
            reaction_type="room_smart_lighting_assist",
            description="studio darkness",
            confidence=0.84,
            status="accepted",
            suggested_reaction_config={
                "room_id": "studio",
                "primary_signal_name": "room_lux",
                "admin_authored_template_id": "room.smart_lighting_assist.basic",
            },
        )
    ]

    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    proposal = pending[0]
    assert proposal.followup_kind == "tuning_suggestion"
    assert proposal.target_reaction_id == ""
    assert proposal.target_reaction_origin == "learned"


async def test_proposal_engine_normalizes_cooling_candidate_into_improvement_from_configured_signal(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    registry = create_builtin_learning_plugin_registry()
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        learning_plugin_registry=registry,
        configured_reactions_provider=lambda: {
            "signal-configured": {
                "reaction_type": "room_signal_assist",
                "room_id": "studio",
                "primary_signal_name": "room_temperature",
                "origin": "admin_authored",
                "source_template_id": "room.signal_assist.basic",
            }
        },
    )
    engine.register_analyzer(
        _AnalyzerStub(
            [
                ReactionProposal(
                    analyzer_id="RoomCoolingPatternAnalyzer",
                    reaction_type="room_cooling_assist",
                    description="studio cooling candidate",
                    confidence=0.82,
                    suggested_reaction_config={
                        "room_id": "studio",
                        "primary_signal_name": "room_temperature",
                        "primary_signal_entities": ["sensor.studio_temperature"],
                    },
                )
            ]
        )
    )
    await engine.async_initialize()

    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    proposal = pending[0]
    assert proposal.reaction_type == "room_cooling_assist"
    assert proposal.followup_kind == "improvement"
    assert proposal.target_reaction_id == "signal-configured"
    assert proposal.target_reaction_type == "room_signal_assist"
    assert proposal.target_reaction_origin == "admin_authored"
    assert proposal.target_template_id == "room.signal_assist.basic"
    assert proposal.improves_reaction_type == "room_signal_assist"
    assert proposal.improvement_reason == "cooling_specialization"


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


async def test_proposal_engine_boosts_accepted_target_reaction_confidence(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    sensor_updates = []
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        sensor_writer=lambda count, attrs: sensor_updates.append((count, attrs)),
    )
    await engine.async_initialize()
    proposal = ReactionProposal(
        analyzer_id="test",
        reaction_type="presence_preheat",
        confidence=0.7,
        status="accepted",
        target_reaction_id="rx1",
        suggested_reaction_config={"weekday": 1},
    )
    engine._proposals = [proposal]  # noqa: SLF001

    await engine.async_boost_confidence("rx1", 0.05)

    boosted = engine._proposals[0]  # noqa: SLF001
    assert isinstance(boosted, ReactionProposal)
    assert boosted.confidence == 0.75
    assert boosted.updated_at != proposal.updated_at
    assert sensor_updates[-1][0] == 0


async def test_proposal_engine_accept_sets_self_target_for_reaction_proposal(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    await engine.async_initialize()
    proposal = ReactionProposal(
        proposal_id="presence-1",
        analyzer_id="presence_pattern",
        reaction_type="presence_preheat",
        confidence=0.7,
    )
    engine._proposals = [proposal]  # noqa: SLF001

    assert await engine.async_accept_proposal("presence-1")

    accepted = engine.proposal_by_id("presence-1")
    assert isinstance(accepted, ReactionProposal)
    assert accepted.status == "accepted"
    assert accepted.target_reaction_id == "presence-1"
    assert accepted.target_reaction_type == "presence_preheat"


async def test_proposal_engine_boost_confidence_caps_at_one(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    await engine.async_initialize()
    engine._proposals = [  # noqa: SLF001
        ReactionProposal(
            analyzer_id="test",
            reaction_type="presence_preheat",
            confidence=0.98,
            status="accepted",
            target_reaction_id="rx1",
        )
    ]

    await engine.async_boost_confidence("rx1", 0.05)

    boosted = engine._proposals[0]  # noqa: SLF001
    assert isinstance(boosted, ReactionProposal)
    assert boosted.confidence == 1.0


async def test_proposal_engine_boost_confidence_noops_without_accepted_target(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    await engine.async_initialize()
    pending = ReactionProposal(
        analyzer_id="test",
        reaction_type="presence_preheat",
        confidence=0.7,
        status="pending",
        target_reaction_id="rx1",
    )
    other = ReactionProposal(
        analyzer_id="test",
        reaction_type="presence_preheat",
        confidence=0.6,
        status="accepted",
        target_reaction_id="rx2",
    )
    engine._proposals = [pending, other]  # noqa: SLF001

    await engine.async_boost_confidence("rx1", 0.05)
    await engine.async_boost_confidence("missing", 0.05)

    assert engine._proposals == [pending, other]  # noqa: SLF001


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
                    fingerprint="LightingPatternAnalyzer|context_conditioned_lighting_scene|living|0|1200",
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
    assert (
        pending[0].fingerprint
        == "LightingPatternAnalyzer|context_conditioned_lighting_scene|living|0|1200"
    )
    assert pending[0].origin == "learned"
    assert engine2.diagnostics()["load_errors"] == 0


async def test_proposal_lifecycle_store_loads_records_and_reports_malformed(
    monkeypatch,
):
    monkeypatch.setattr(
        "custom_components.heima.runtime.proposal_lifecycle_store.Store",
        _FakeStore,
    )
    store = ProposalLifecycleStore(object())  # type: ignore[arg-type]
    store._store._data = {  # noqa: SLF001
        "data": {
            "records": [
                ProposalLifecycleRecord(
                    proposal_id="proposal-1",
                    identity_key="house_state_learned_context:ctx",
                    plugin_family="house_state",
                    proposal_type=HOUSE_STATE_PROPOSAL_TYPE,
                    accepted_at="2026-06-18T10:00:00+00:00",
                    confirmed_count=2,
                ).as_dict(),
                {"proposal_id": ""},
                "bad",
            ]
        }
    }

    await store.async_load()

    diagnostics = store.diagnostics()
    assert diagnostics["record_count"] == 1
    assert diagnostics["load_errors"] == 2
    assert diagnostics["records"][0]["proposal_id"] == "proposal-1"
    assert diagnostics["records"][0]["confirmed_count"] == 2


async def test_proposal_engine_creates_lifecycle_record_for_accepted_house_state(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    lifecycle_store = _FakeLifecycleStore()
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),
        lifecycle_store=lifecycle_store,  # type: ignore[arg-type]
    )

    await engine.async_initialize()
    proposal_id = await engine.async_submit_proposal(_house_state_lifecycle_proposal())
    assert lifecycle_store.records_by_id == {}

    assert await engine.async_accept_proposal(proposal_id)

    record = lifecycle_store.records_by_id[proposal_id]
    diagnostics = engine.diagnostics()["lifecycle_monitoring"]
    assert record.proposal_id == proposal_id
    assert record.identity_key == "house_state_learned_context:ctx-alpha"
    assert record.plugin_family == "house_state"
    assert record.proposal_type == HOUSE_STATE_PROPOSAL_TYPE
    assert record.linked_reaction_id == proposal_id
    assert record.linked_reaction_type == HOUSE_STATE_PROPOSAL_TYPE
    assert record.reaction_link_state == "linked_clean"
    assert record.monitoring_window_start == record.accepted_at
    assert diagnostics["enabled"] is True
    assert diagnostics["record_count"] == 1


async def test_proposal_engine_loads_lifecycle_records_for_persisted_accepted_house_state(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    lifecycle_store = _FakeLifecycleStore()
    accepted = replace(
        _house_state_lifecycle_proposal(),
        status="accepted",
        target_reaction_id="reaction-1",
        target_reaction_type=HOUSE_STATE_PROPOSAL_TYPE,
    )
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),
        lifecycle_store=lifecycle_store,  # type: ignore[arg-type]
    )
    engine._store._data = {"data": {"proposals": [accepted.as_dict()]}}  # noqa: SLF001

    await engine.async_initialize()

    record = lifecycle_store.records_by_id[accepted.proposal_id]
    assert lifecycle_store.loaded is True
    assert record.linked_reaction_id == "reaction-1"
    assert record.identity_key == accepted.identity_key
    assert engine.pending_proposals() == []
    assert len(engine.accepted_proposals()) == 1


async def test_proposal_lifecycle_diagnostics_classify_clean_linked_reaction(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    lifecycle_store = _FakeLifecycleStore()
    configured: dict[str, dict[str, object]] = {}
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),
        configured_reactions_provider=lambda: configured,
        lifecycle_store=lifecycle_store,  # type: ignore[arg-type]
    )

    await engine.async_initialize()
    proposal = _house_state_lifecycle_proposal()
    proposal_id = await engine.async_submit_proposal(proposal)
    accepted = next(item for item in engine.pending_proposals() if item.proposal_id == proposal_id)
    assert isinstance(accepted, ReactionProposal)
    configured[proposal_id] = _configured_house_state_lifecycle_reaction(accepted)

    assert await engine.async_accept_proposal(proposal_id)

    record = engine.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert record["reaction_link_state"] == "linked_clean"
    assert record["reaction_link_state_reason"] == "matches_accepted_baseline"
    assert record["resolved_reaction_id"] == proposal_id


async def test_proposal_lifecycle_diagnostics_classify_interpretable_user_baseline(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    lifecycle_store = _FakeLifecycleStore()
    configured: dict[str, dict[str, object]] = {}
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),
        configured_reactions_provider=lambda: configured,
        lifecycle_store=lifecycle_store,  # type: ignore[arg-type]
    )

    await engine.async_initialize()
    proposal_id = await engine.async_submit_proposal(_house_state_lifecycle_proposal())
    accepted = next(item for item in engine.pending_proposals() if item.proposal_id == proposal_id)
    assert isinstance(accepted, ReactionProposal)
    configured[proposal_id] = _configured_house_state_lifecycle_reaction(accepted)
    configured[proposal_id]["note"] = "admin edited but still interpretable"

    assert await engine.async_accept_proposal(proposal_id)

    record = engine.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert record["reaction_link_state"] == "linked_user_baseline"
    assert record["reaction_link_state_reason"] == "interpretable_user_modified_baseline"


async def test_proposal_lifecycle_diagnostics_classify_uninterpretable_reaction(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    lifecycle_store = _FakeLifecycleStore()
    configured: dict[str, dict[str, object]] = {}
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),
        configured_reactions_provider=lambda: configured,
        lifecycle_store=lifecycle_store,  # type: ignore[arg-type]
    )

    await engine.async_initialize()
    proposal_id = await engine.async_submit_proposal(_house_state_lifecycle_proposal())
    accepted = next(item for item in engine.pending_proposals() if item.proposal_id == proposal_id)
    assert isinstance(accepted, ReactionProposal)
    configured[proposal_id] = _configured_house_state_lifecycle_reaction(accepted)
    configured[proposal_id]["reaction_type"] = "room_smart_lighting_assist"

    assert await engine.async_accept_proposal(proposal_id)

    record = engine.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert record["reaction_link_state"] == "linked_uninterpretable"
    assert record["reaction_link_state_reason"] == "reaction_type_mismatch"


async def test_proposal_lifecycle_diagnostics_classify_malformed_reaction_payload(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    lifecycle_store = _FakeLifecycleStore()
    configured: dict[str, object] = {}
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),
        configured_reactions_provider=lambda: configured,
        lifecycle_store=lifecycle_store,  # type: ignore[arg-type]
    )

    await engine.async_initialize()
    proposal_id = await engine.async_submit_proposal(_house_state_lifecycle_proposal())
    configured[proposal_id] = "not-a-dict"

    assert await engine.async_accept_proposal(proposal_id)

    record = engine.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert record["reaction_link_state"] == "linked_uninterpretable"
    assert record["reaction_link_state_reason"] == "configured_reaction_payload_malformed"


async def test_proposal_lifecycle_diagnostics_classify_missing_reaction(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    lifecycle_store = _FakeLifecycleStore()
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),
        configured_reactions_provider=dict,
        lifecycle_store=lifecycle_store,  # type: ignore[arg-type]
    )

    await engine.async_initialize()
    proposal_id = await engine.async_submit_proposal(_house_state_lifecycle_proposal())
    assert await engine.async_accept_proposal(proposal_id)

    record = engine.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert record["reaction_link_state"] == "reaction_missing"
    assert record["reaction_link_state_reason"] == "configured_reaction_not_found"


async def _accepted_house_state_lifecycle_engine(
    monkeypatch,
    events: list[HeimaEvent],
    *,
    configure_reaction: bool = True,
    lifecycle_policy: AcceptedRuleLifecyclePolicy | None = None,
) -> tuple[ProposalEngine, _FakeLifecycleStore, str, dict[str, object]]:
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    lifecycle_store = _FakeLifecycleStore()
    configured: dict[str, object] = {}
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreWithEvents(events),  # type: ignore[arg-type]
        configured_reactions_provider=lambda: configured,
        lifecycle_store=lifecycle_store,  # type: ignore[arg-type]
        lifecycle_policy=lifecycle_policy,
    )
    await engine.async_initialize()
    proposal_id = await engine.async_submit_proposal(_house_state_lifecycle_proposal())
    accepted = next(item for item in engine.pending_proposals() if item.proposal_id == proposal_id)
    assert isinstance(accepted, ReactionProposal)
    if configure_reaction:
        configured[proposal_id] = _configured_house_state_lifecycle_reaction(accepted)
    assert await engine.async_accept_proposal(proposal_id)
    return engine, lifecycle_store, proposal_id, configured


async def _restart_house_state_lifecycle_engine(
    source: ProposalEngine,
    source_lifecycle_store: _FakeLifecycleStore,
    events: list[HeimaEvent],
    configured: dict[str, object],
    *,
    lifecycle_policy: AcceptedRuleLifecyclePolicy | None = None,
) -> tuple[ProposalEngine, _FakeLifecycleStore]:
    lifecycle_store = _FakeLifecycleStore()
    lifecycle_store.records_by_id = dict(source_lifecycle_store.records_by_id)
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreWithEvents(events),  # type: ignore[arg-type]
        configured_reactions_provider=lambda: configured,
        lifecycle_store=lifecycle_store,  # type: ignore[arg-type]
        lifecycle_policy=lifecycle_policy,
    )
    engine._store._data = deepcopy(source._store._data)  # noqa: SLF001
    await engine.async_initialize()
    return engine, lifecycle_store


async def test_house_state_lifecycle_evaluation_counts_confirmed_opportunities(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        [
            _house_state_event(ts="2999-06-16T17:05:00+00:00", house_state="working"),
            _house_state_event(ts="2999-06-16T17:25:00+00:00", house_state="working"),
        ],
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()
    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    assert record.confirmed_count == 1
    assert record.outcome_contradiction_count == 0
    assert record.context_miss_count == 0
    assert record.unknown_transient_count == 0
    assert record.dependency_unavailable_count == 0
    assert record.last_confirmed_at == "2999-06-16T17:25:00+00:00"


async def test_house_state_lifecycle_evaluation_counts_contradicted_opportunities(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        [_house_state_event(ts="2999-06-16T17:05:00+00:00", house_state="home")],
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    assert record.confirmed_count == 0
    assert record.outcome_contradiction_count == 1
    assert record.context_miss_count == 0


async def test_house_state_lifecycle_evaluation_counts_context_missed_opportunities(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        [
            _house_state_event(
                ts="2999-06-16T17:05:00+00:00",
                house_state="working",
                anyone_home=False,
            )
        ],
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    assert record.confirmed_count == 0
    assert record.outcome_contradiction_count == 0
    assert record.context_miss_count == 1


async def test_house_state_lifecycle_evaluation_counts_unknown_transient(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        [_house_state_event(ts="2999-06-16T17:05:00+00:00", house_state="unknown")],
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    assert record.confirmed_count == 0
    assert record.outcome_contradiction_count == 0
    assert record.context_miss_count == 0
    assert record.unknown_transient_count == 1


async def test_house_state_lifecycle_evaluation_counts_dependency_unavailable(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        [_house_state_event(ts="2999-06-16T17:05:00+00:00", house_state="working")],
        configure_reaction=False,
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    assert record.confirmed_count == 0
    assert record.outcome_contradiction_count == 0
    assert record.context_miss_count == 0
    assert record.dependency_unavailable_count == 1


async def test_house_state_lifecycle_policy_uses_rolling_window_without_resetting_drift(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "home", "working"]),
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=2,
            retirement_multiplier=2,
            maintenance_threshold=2,
            rolling_window_limit=3,
        ),
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    diagnostic = engine.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert record.confirmed_count == 1
    assert record.outcome_contradiction_count == 2
    assert record.replacement_candidate_state == "home"
    assert record.replacement_candidate_count == 2
    assert record.lifecycle_review_kind == "replacement_suggestion"
    assert diagnostic["policy"]["rolling_window_limit"] == 3
    assert diagnostic["policy"]["replacement_threshold"] == 2


async def test_house_state_lifecycle_policy_naturally_evicts_old_drift(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "home", "working"]),
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=2,
            retirement_multiplier=2,
            maintenance_threshold=2,
            rolling_window_limit=1,
        ),
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    assert record.evaluated_window_count == 1
    assert record.confirmed_count == 1
    assert record.outcome_contradiction_count == 0
    assert record.lifecycle_review_kind == ""


async def test_house_state_lifecycle_policy_prefers_replacement_over_retirement(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "home"]),
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=2,
            retirement_multiplier=1,
            maintenance_threshold=2,
            rolling_window_limit=4,
        ),
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    assert record.outcome_contradiction_count == 2
    assert record.replacement_candidate_count == 2
    assert record.lifecycle_review_kind == "replacement_suggestion"


async def test_house_state_lifecycle_policy_uses_retirement_without_stable_replacement(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "relax"]),
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=2,
            retirement_multiplier=1,
            maintenance_threshold=2,
            rolling_window_limit=4,
        ),
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    assert record.outcome_contradiction_count == 2
    assert record.replacement_candidate_count == 0
    assert record.lifecycle_review_kind == "retirement_suggestion"


async def test_house_state_lifecycle_policy_keeps_maintenance_separate(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "home"]),
        configure_reaction=False,
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=1,
            retirement_multiplier=1,
            maintenance_threshold=1,
            rolling_window_limit=4,
        ),
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    record = lifecycle_store.records_by_id[proposal_id]
    assert record.dependency_unavailable_count == 1
    assert record.outcome_contradiction_count == 0
    assert record.lifecycle_review_kind == "maintenance_suggestion"
    diagnostic = engine.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert diagnostic["lifecycle_review_kind"] == "maintenance_suggestion"


async def test_house_state_lifecycle_generates_replacement_suggestion(
    monkeypatch,
):
    (
        engine,
        _lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "home"]),
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=2,
            retirement_multiplier=2,
            maintenance_threshold=2,
            rolling_window_limit=4,
        ),
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    pending = engine.pending_proposals()
    suggestion = next(
        proposal
        for proposal in pending
        if isinstance(proposal, ReactionProposal)
        and proposal.followup_kind == "replacement_suggestion"
    )
    cfg = suggestion.suggested_reaction_config
    assert suggestion.reaction_type == "proposal_lifecycle_suggestion"
    assert suggestion.target_reaction_id == proposal_id
    assert cfg["lifecycle_suggestion_type"] == "replacement_suggestion"
    assert cfg["target_proposal_id"] == proposal_id
    assert cfg["accepted_predicted_state"] == "working"
    assert cfg["proposed_predicted_state"] == "home"
    assert cfg["rejection_key"]


async def test_house_state_lifecycle_rejected_suggestion_is_not_recreated(
    monkeypatch,
):
    (
        engine,
        _lifecycle_store,
        _proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "home"]),
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=2,
            retirement_multiplier=2,
            maintenance_threshold=2,
            rolling_window_limit=4,
        ),
    )

    await engine.async_evaluate_house_state_lifecycle_opportunities()
    suggestion = next(
        proposal
        for proposal in engine.pending_proposals()
        if isinstance(proposal, ReactionProposal)
        and proposal.followup_kind == "replacement_suggestion"
    )
    assert await engine.async_reject_proposal(suggestion.proposal_id)

    await engine.async_evaluate_house_state_lifecycle_opportunities()

    assert all(
        not (
            isinstance(proposal, ReactionProposal)
            and proposal.followup_kind == "replacement_suggestion"
        )
        for proposal in engine.pending_proposals()
    )
    rejected = [
        proposal
        for proposal in engine.diagnostics()["proposals"]
        if proposal["status"] == "rejected"
        and proposal["followup_kind"] == "replacement_suggestion"
    ]
    assert len(rejected) == 1


async def test_apply_lifecycle_replacement_marks_source_record_idempotently(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "home"]),
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=2,
            retirement_multiplier=2,
            maintenance_threshold=2,
            rolling_window_limit=4,
        ),
    )
    await engine.async_evaluate_house_state_lifecycle_opportunities()
    suggestion = next(
        proposal
        for proposal in engine.pending_proposals()
        if isinstance(proposal, ReactionProposal)
        and proposal.followup_kind == "replacement_suggestion"
    )

    assert await engine.async_apply_lifecycle_suggestion(suggestion.proposal_id)
    first = lifecycle_store.records_by_id[proposal_id]
    assert first.replaced_by == suggestion.proposal_id
    assert first.retired_at == ""
    accepted = engine.proposal_by_id(proposal_id)
    assert isinstance(accepted, ReactionProposal)
    assert accepted.suggested_reaction_config["predicted_state"] == "home"
    assert accepted.suggested_reaction_config["context_snapshot"]["predicted_state"] == "home"
    assert accepted.suggested_reaction_config["context_key"].endswith(":state:home")
    assert accepted.identity_key.endswith(":state:home")

    assert await engine.async_apply_lifecycle_suggestion(suggestion.proposal_id)
    second = lifecycle_store.records_by_id[proposal_id]
    assert second.replaced_by == suggestion.proposal_id
    assert second.last_lifecycle_review_at == first.last_lifecycle_review_at
    accepted_again = engine.proposal_by_id(proposal_id)
    assert isinstance(accepted_again, ReactionProposal)
    assert (
        accepted_again.suggested_reaction_config["context_key"]
        == accepted.suggested_reaction_config["context_key"]
    )


async def test_apply_lifecycle_retirement_marks_source_record_idempotently(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "relax"]),
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=2,
            retirement_multiplier=1,
            maintenance_threshold=2,
            rolling_window_limit=4,
        ),
    )
    await engine.async_evaluate_house_state_lifecycle_opportunities()
    suggestion = next(
        proposal
        for proposal in engine.pending_proposals()
        if isinstance(proposal, ReactionProposal)
        and proposal.followup_kind == "retirement_suggestion"
    )

    assert await engine.async_apply_lifecycle_suggestion(suggestion.proposal_id)
    first = lifecycle_store.records_by_id[proposal_id]
    assert first.retired_at
    assert first.replaced_by == ""

    assert await engine.async_apply_lifecycle_suggestion(suggestion.proposal_id)
    second = lifecycle_store.records_by_id[proposal_id]
    assert second.retired_at == first.retired_at


async def test_apply_lifecycle_maintenance_marks_review_without_behavior_drift(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        _configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "home"]),
        configure_reaction=False,
        lifecycle_policy=AcceptedRuleLifecyclePolicy(
            required_observations=1,
            retirement_multiplier=1,
            maintenance_threshold=1,
            rolling_window_limit=4,
        ),
    )
    await engine.async_evaluate_house_state_lifecycle_opportunities()
    suggestion = next(
        proposal
        for proposal in engine.pending_proposals()
        if isinstance(proposal, ReactionProposal)
        and proposal.followup_kind == "maintenance_suggestion"
    )

    assert await engine.async_apply_lifecycle_suggestion(suggestion.proposal_id)
    record = lifecycle_store.records_by_id[proposal_id]
    assert record.last_lifecycle_review_at
    assert record.replaced_by == ""
    assert record.retired_at == ""


async def test_lifecycle_recovery_restores_accepted_rule_record(monkeypatch):
    (
        engine,
        lifecycle_store,
        proposal_id,
        configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["working"]),
    )

    restarted, restarted_lifecycle_store = await _restart_house_state_lifecycle_engine(
        engine,
        lifecycle_store,
        _house_state_events_for_days(["working"]),
        configured,
    )

    assert restarted.pending_proposals() == []
    record = restarted_lifecycle_store.records_by_id[proposal_id]
    assert record.proposal_id == proposal_id
    assert record.linked_reaction_id == proposal_id
    assert record.replaced_by == ""
    assert record.retired_at == ""
    diagnostic = restarted.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert diagnostic["reaction_link_state"] == "linked_clean"


async def test_lifecycle_recovery_keeps_replacement_pending_after_restart(monkeypatch):
    policy = AcceptedRuleLifecyclePolicy(
        required_observations=2,
        retirement_multiplier=2,
        maintenance_threshold=2,
        rolling_window_limit=4,
    )
    (
        engine,
        lifecycle_store,
        _proposal_id,
        configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "home"]),
        lifecycle_policy=policy,
    )
    await engine.async_evaluate_house_state_lifecycle_opportunities()
    suggestion = next(
        proposal
        for proposal in engine.pending_proposals()
        if isinstance(proposal, ReactionProposal)
        and proposal.followup_kind == "replacement_suggestion"
    )
    configured_before_restart = deepcopy(configured)

    restarted, _restarted_lifecycle_store = await _restart_house_state_lifecycle_engine(
        engine,
        lifecycle_store,
        _house_state_events_for_days(["home", "home"]),
        configured,
        lifecycle_policy=policy,
    )

    pending = restarted.pending_proposals()
    assert [proposal.proposal_id for proposal in pending] == [suggestion.proposal_id]
    assert isinstance(pending[0], ReactionProposal)
    assert pending[0].followup_kind == "replacement_suggestion"
    assert configured == configured_before_restart


async def test_lifecycle_recovery_restores_accepted_retirement(monkeypatch):
    policy = AcceptedRuleLifecyclePolicy(
        required_observations=2,
        retirement_multiplier=1,
        maintenance_threshold=2,
        rolling_window_limit=4,
    )
    (
        engine,
        lifecycle_store,
        proposal_id,
        configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["home", "relax"]),
        lifecycle_policy=policy,
    )
    await engine.async_evaluate_house_state_lifecycle_opportunities()
    suggestion = next(
        proposal
        for proposal in engine.pending_proposals()
        if isinstance(proposal, ReactionProposal)
        and proposal.followup_kind == "retirement_suggestion"
    )
    assert await engine.async_apply_lifecycle_suggestion(suggestion.proposal_id)

    restarted, restarted_lifecycle_store = await _restart_house_state_lifecycle_engine(
        engine,
        lifecycle_store,
        _house_state_events_for_days(["home", "relax"]),
        configured,
        lifecycle_policy=policy,
    )

    record = restarted_lifecycle_store.records_by_id[proposal_id]
    assert record.retired_at == lifecycle_store.records_by_id[proposal_id].retired_at
    assert all(
        not (
            isinstance(proposal, ReactionProposal)
            and proposal.followup_kind == "retirement_suggestion"
        )
        for proposal in restarted.pending_proposals()
    )


async def test_lifecycle_recovery_preserves_rejected_maintenance_suppression(monkeypatch):
    policy = AcceptedRuleLifecyclePolicy(
        required_observations=1,
        retirement_multiplier=1,
        maintenance_threshold=1,
        rolling_window_limit=4,
    )
    (
        engine,
        lifecycle_store,
        _proposal_id,
        configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["working"]),
        configure_reaction=False,
        lifecycle_policy=policy,
    )
    await engine.async_evaluate_house_state_lifecycle_opportunities()
    suggestion = next(
        proposal
        for proposal in engine.pending_proposals()
        if isinstance(proposal, ReactionProposal)
        and proposal.followup_kind == "maintenance_suggestion"
    )
    assert await engine.async_reject_proposal(suggestion.proposal_id)

    restarted, _restarted_lifecycle_store = await _restart_house_state_lifecycle_engine(
        engine,
        lifecycle_store,
        _house_state_events_for_days(["working"]),
        configured,
        lifecycle_policy=policy,
    )
    await restarted.async_evaluate_house_state_lifecycle_opportunities()

    assert all(
        not (
            isinstance(proposal, ReactionProposal)
            and proposal.followup_kind == "maintenance_suggestion"
        )
        for proposal in restarted.pending_proposals()
    )
    rejected = [
        proposal
        for proposal in restarted.diagnostics()["proposals"]
        if proposal["status"] == "rejected"
        and proposal["followup_kind"] == "maintenance_suggestion"
    ]
    assert len(rejected) == 1


async def test_lifecycle_recovery_does_not_turn_disabled_gap_into_negative_evidence(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["working"]),
    )

    restarted, restarted_lifecycle_store = await _restart_house_state_lifecycle_engine(
        engine,
        lifecycle_store,
        [],
        configured,
    )
    await restarted.async_evaluate_house_state_lifecycle_opportunities()

    record = restarted_lifecycle_store.records_by_id[proposal_id]
    assert record.outcome_contradiction_count == 0
    assert record.context_miss_count == 0


async def test_lifecycle_recovery_reports_missing_reaction_without_recreating_it(
    monkeypatch,
):
    (
        engine,
        lifecycle_store,
        proposal_id,
        configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["working"]),
    )
    configured.clear()

    restarted, _restarted_lifecycle_store = await _restart_house_state_lifecycle_engine(
        engine,
        lifecycle_store,
        _house_state_events_for_days(["working"]),
        configured,
    )

    diagnostic = restarted.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert diagnostic["proposal_id"] == proposal_id
    assert diagnostic["reaction_link_state"] == "reaction_missing"
    assert configured == {}


async def test_lifecycle_recovery_preserves_linked_user_baseline(monkeypatch):
    (
        engine,
        lifecycle_store,
        proposal_id,
        configured,
    ) = await _accepted_house_state_lifecycle_engine(
        monkeypatch,
        _house_state_events_for_days(["working"]),
    )
    assert isinstance(configured[proposal_id], dict)
    configured[proposal_id]["note"] = "admin edited but still interpretable"

    restarted, _restarted_lifecycle_store = await _restart_house_state_lifecycle_engine(
        engine,
        lifecycle_store,
        _house_state_events_for_days(["working"]),
        configured,
    )

    diagnostic = restarted.diagnostics()["lifecycle_monitoring"]["records"][0]
    assert diagnostic["reaction_link_state"] == "linked_user_baseline"
    assert diagnostic["reaction_link_state_reason"] == "interpretable_user_modified_baseline"


def test_reaction_proposal_preserves_lifecycle_followup_kind() -> None:
    proposal = ReactionProposal.from_dict(
        {
            "analyzer_id": "proposal_lifecycle",
            "reaction_type": "proposal_lifecycle_suggestion",
            "followup_kind": "retirement_suggestion",
            "suggested_reaction_config": {"proposal_type": "proposal_lifecycle_suggestion"},
        }
    )

    assert proposal.followup_kind == "retirement_suggestion"


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
        reaction_type="context_conditioned_lighting_scene",
        confidence=0.8,
        description="living:1205",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1205,
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
            "entity_steps": [{"entity_id": "light.living_main", "action": "on"}],
        },
    )
    second = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="context_conditioned_lighting_scene",
        confidence=0.9,
        description="living:1225",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1225,
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
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
        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200|scene="
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
                fingerprint="LightingPatternAnalyzer|context_conditioned_lighting_scene|living|0|1350",
            )
        ]
    )
    engine.register_analyzer(analyzer)

    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert (
        pending[0].fingerprint
        == "LightingPatternAnalyzer|context_conditioned_lighting_scene|living|0|1350"
    )
    assert pending[0].identity_key.startswith(
        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1350|scene="
    )


async def test_proposal_engine_lighting_identity_tolerates_minor_scene_drift(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    first = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="context_conditioned_lighting_scene",
        confidence=0.8,
        description="living:1205",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1205,
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
            "entity_steps": [{"entity_id": "light.living_main", "action": "on", "brightness": 120}],
        },
    )
    second = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="context_conditioned_lighting_scene",
        confidence=0.9,
        description="living:1225",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1225,
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
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
        reaction_type="context_conditioned_lighting_scene",
        confidence=0.8,
        description="living:1205",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1205,
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
            "entity_steps": [{"entity_id": "light.living_main", "action": "on", "brightness": 96}],
        },
    )
    second = ReactionProposal(
        analyzer_id="LightingPatternAnalyzer",
        reaction_type="context_conditioned_lighting_scene",
        confidence=0.9,
        description="living:1225",
        suggested_reaction_config={
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1225,
            "context_conditions": [{"signal_name": "projector_context", "state_in": ["active"]}],
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
    fp1 = "LightingPatternAnalyzer|context_conditioned_lighting_scene|living|0|1200"
    fp2 = "LightingPatternAnalyzer|context_conditioned_lighting_scene|bedroom|0|1200"

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


async def test_proposal_engine_explainability_includes_context_condition_metrics(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    proposal = _proposal(conf=0.94, weekday=3)
    proposal.reaction_type = "context_conditioned_lighting_scene"
    proposal.description = "studio: Thursday ~10:05 — test_heima_studio_desk on (160bri, 3300K)"
    proposal.suggested_reaction_config = {
        "reaction_type": "context_conditioned_lighting_scene",
        "room_id": "studio",
        "weekday": 3,
        "scheduled_min": 605,
        "entity_steps": [{"entity_id": "light.test_heima_studio_desk", "action": "on"}],
        "context_conditions": [
            {"signal_name": "test_heima_studio_fan_context", "state_in": ["active"]}
        ],
        "learning_diagnostics": {
            "pattern_id": "context_conditioned_lighting_scene",
            "analyzer_id": "LightingPatternAnalyzer",
            "reaction_type": "context_conditioned_lighting_scene",
            "plugin_family": "lighting",
            "room_id": "studio",
            "weekday": 3,
            "scheduled_min": 605,
            "observations_count": 5,
            "weeks_observed": 3,
            "iqr_min": 0,
            "entity_steps_count": 1,
            "positive_episode_count": 5,
            "selected_context_condition": {
                "signal_name": "test_heima_studio_fan_context",
                "state_in": ["active"],
            },
            "concentration": 1.0,
            "lift": float("inf"),
            "negative_episode_count": 4,
            "contrast_status": "verified",
        },
    }
    engine._store._data = {"data": {"proposals": [proposal.as_dict()]}}

    await engine.async_initialize()

    item = engine.diagnostics()["proposals"][0]
    explainability = item["explainability"]
    assert explainability["selected_context_condition"] == {
        "signal_name": "test_heima_studio_fan_context",
        "state_in": ["active"],
    }
    assert explainability["concentration"] == 1.0
    assert explainability["negative_episode_count"] == 4
    assert explainability["contrast_status"] == "verified"
    assert explainability["lift"] == float("inf")


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
                    "reaction_type": "context_conditioned_lighting_scene",
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
    assert sensor_updates[-1][1]["items"]["legacy"]["origin"] == "learned"
    assert sensor_updates[-1][1]["items"]["legacy"]["type"] == "presence_preheat"


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
    assert sensor_updates[-1][1]["items"][proposal_id]["origin"] == "admin_authored"


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
    assert attrs["total"] == 5
    assert attrs["pending_items_total"] == 5
    assert attrs["pending_items_included"] == 5
    assert attrs["pending_items_truncated"] is False
    assert len(attrs["items"]) == 5
    assert attrs["items"][proposal_ids[0]]["origin"] == "admin_authored"


async def test_proposal_engine_sensor_writer_limits_items_payload(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    sensor_updates = []
    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        sensor_writer=lambda count, attrs: sensor_updates.append((count, attrs)),
    )
    await engine.async_initialize()
    proposal_ids = []
    for index in range(ProposalEngine.SENSOR_ITEMS_LIMIT + 5):
        proposal = _admin_authored_proposal()
        proposal.suggested_reaction_config["scheduled_min"] = 1200 + (index * 30)
        proposal_ids.append(await engine.async_submit_proposal(proposal))

    count, attrs = sensor_updates[-1]
    assert count == ProposalEngine.SENSOR_ITEMS_LIMIT + 5
    assert attrs["pending_items_total"] == ProposalEngine.SENSOR_ITEMS_LIMIT + 5
    assert attrs["pending_items_included"] == ProposalEngine.SENSOR_ITEMS_LIMIT
    assert attrs["pending_items_truncated"] is True
    assert len(attrs["items"]) == ProposalEngine.SENSOR_ITEMS_LIMIT
    assert set(attrs["items"]).issubset(set(proposal_ids))


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


async def test_proposal_engine_accepted_proposals_and_config_suggestion_counts(monkeypatch):
    sensor_payloads: list[tuple[int, dict]] = []
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(
        object(),
        _EventStoreStub(),  # type: ignore[arg-type]
        sensor_writer=lambda count, attrs: sensor_payloads.append((count, attrs)),
    )

    await engine.async_initialize()
    proposal = _admin_authored_proposal()
    proposal.followup_kind = "config_suggestion"
    proposal_id = await engine.async_submit_proposal(proposal)
    assert await engine.async_accept_proposal(proposal_id)

    accepted = engine.accepted_proposals()
    assert len(accepted) == 1
    assert accepted[0].proposal_id == proposal_id
    assert accepted[0].followup_kind == "config_suggestion"
    assert sensor_payloads[-1][1]["by_followup_kind"]["config_suggestion"] == 1


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


async def test_proposal_engine_async_submit_proposal_preserves_existing_accepted_identity(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()
    first = _admin_authored_proposal()
    proposal_id = await engine.async_submit_proposal(first)
    assert await engine.async_accept_proposal(proposal_id)

    second = _admin_authored_proposal()
    second.description = "Ignored draft"
    submitted_id = await engine.async_submit_proposal(second)

    pending = engine.pending_proposals()
    accepted = engine.accepted_proposals()
    assert submitted_id == proposal_id
    assert pending == []
    assert len(accepted) == 1
    assert accepted[0].proposal_id == proposal_id
    assert accepted[0].status == "accepted"
    assert accepted[0].description == first.description


async def test_proposal_engine_async_submit_proposal_preserves_existing_rejected_identity(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()
    first = _admin_authored_proposal()
    proposal_id = await engine.async_submit_proposal(first)
    assert await engine.async_reject_proposal(proposal_id)

    second = _admin_authored_proposal()
    second.description = "Ignored draft"
    submitted_id = await engine.async_submit_proposal(second)

    proposal = engine.proposal_by_id(proposal_id)
    assert submitted_id == proposal_id
    assert engine.pending_proposals() == []
    assert isinstance(proposal, ReactionProposal)
    assert proposal.status == "rejected"
    assert proposal.description == first.description


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


async def test_proposal_engine_async_withdraw_removes_pending_identity(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()
    proposal = _admin_authored_proposal()
    proposal.identity_key = "semantic.rule"
    await engine.async_submit_proposal(proposal)

    assert await engine.async_withdraw("semantic.rule") is True
    assert engine.pending_proposals() == []


async def test_proposal_engine_async_withdraw_preserves_accepted_identity(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()
    proposal = _admin_authored_proposal()
    proposal.identity_key = "semantic.rule"
    proposal_id = await engine.async_submit_proposal(proposal)
    assert await engine.async_accept_proposal(proposal_id)

    assert await engine.async_withdraw("semantic.rule") is False
    assert engine.proposal_by_identity_key("semantic.rule") is not None


async def test_proposal_engine_async_withdraw_preserves_rejected_identity(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()
    proposal = _admin_authored_proposal()
    proposal.identity_key = "semantic.rule"
    proposal_id = await engine.async_submit_proposal(proposal)
    assert await engine.async_reject_proposal(proposal_id)

    assert await engine.async_withdraw("semantic.rule") is False
    assert engine.proposal_by_identity_key("semantic.rule") is not None


async def test_proposal_engine_async_withdraw_returns_false_for_missing_identity(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    await engine.async_initialize()

    assert await engine.async_withdraw("missing.rule") is False


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
        fingerprint="LightingPatternAnalyzer|context_conditioned_lighting_scene|living|0|1200",
        brightness=192,
        color_temp_kelvin=2750,
    )
    candidate = _lighting_proposal(
        conf=0.92,
        room_id="living",
        weekday=0,
        scheduled_min=1204,
        fingerprint="LightingPatternAnalyzer|context_conditioned_lighting_scene|living|0|1200",
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
        fingerprint="LightingPatternAnalyzer|context_conditioned_lighting_scene|living|0|1200",
        brightness=192,
        color_temp_kelvin=2750,
    )
    candidate = _lighting_proposal(
        conf=0.92,
        room_id="living",
        weekday=0,
        scheduled_min=1218,
        fingerprint="LightingPatternAnalyzer|context_conditioned_lighting_scene|living|0|1200",
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


async def test_proposal_engine_review_grouping_exposes_only_best_pending_representative(
    monkeypatch,
):
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
                    f"custom|id={proposal.suggested_reaction_config.get('id')}"
                ),
                review_grouping=lambda proposal: ProposalReviewGrouping(
                    group_key=str(proposal.suggested_reaction_config.get("group") or ""),
                    specificity_rank=int(
                        proposal.suggested_reaction_config.get("specificity") or 0
                    ),
                    quality_rank=(float(proposal.suggested_reaction_config.get("quality") or 0),),
                ),
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
    weak = _proposal(conf=0.8)
    weak = replace(
        weak,
        suggested_reaction_config={
            "id": "weak",
            "group": "morning",
            "specificity": 1,
            "quality": 1,
        },
    )
    strong = _proposal(conf=0.7)
    strong = replace(
        strong,
        suggested_reaction_config={
            "id": "strong",
            "group": "morning",
            "specificity": 2,
            "quality": 0,
        },
    )
    other = _proposal(conf=0.6)
    other = replace(
        other,
        suggested_reaction_config={"id": "other", "group": "evening", "specificity": 1},
    )

    await engine.async_submit_proposal(weak)
    strong_id = await engine.async_submit_proposal(strong)
    other_id = await engine.async_submit_proposal(other)

    pending = engine.pending_proposals()
    assert {proposal.proposal_id for proposal in pending} == {strong_id, other_id}

    diagnostics = engine.diagnostics()
    assert diagnostics["pending"] == 2
    assert diagnostics["suppressed_in_review_count"] == 1
    suppressed = [
        proposal
        for proposal in diagnostics["proposals"]
        if proposal["identity_key"] == "custom|id=weak"
    ][0]
    assert suppressed["review_group_key"] == "presence_preheat:morning"
    assert suppressed["review_group_role"] == "suppressed"
    assert suppressed["suppressed_by_review_group"] is True


async def test_proposal_engine_review_grouping_suppresses_pending_at_or_below_accepted_rank(
    monkeypatch,
):
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
                    f"custom|id={proposal.suggested_reaction_config.get('id')}"
                ),
                review_grouping=lambda proposal: ProposalReviewGrouping(
                    group_key=str(proposal.suggested_reaction_config.get("group") or ""),
                    specificity_rank=int(
                        proposal.suggested_reaction_config.get("specificity") or 0
                    ),
                    quality_rank=(float(proposal.suggested_reaction_config.get("quality") or 0),),
                ),
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
    accepted = replace(
        _proposal(conf=0.9, status="accepted"),
        suggested_reaction_config={"id": "accepted", "group": "morning", "specificity": 2},
    )
    lower = replace(
        _proposal(conf=0.8),
        suggested_reaction_config={"id": "lower", "group": "morning", "specificity": 1},
    )
    higher = replace(
        _proposal(conf=0.7),
        suggested_reaction_config={"id": "higher", "group": "morning", "specificity": 3},
    )

    await engine.async_submit_proposal(accepted)
    await engine.async_submit_proposal(lower)
    higher_id = await engine.async_submit_proposal(higher)

    pending = engine.pending_proposals()
    assert [proposal.proposal_id for proposal in pending] == [higher_id]


async def test_proposal_engine_review_grouping_recomputes_representative_after_rejection(
    monkeypatch,
):
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
                    f"custom|id={proposal.suggested_reaction_config.get('id')}"
                ),
                review_grouping=lambda proposal: ProposalReviewGrouping(
                    group_key=str(proposal.suggested_reaction_config.get("group") or ""),
                    specificity_rank=int(
                        proposal.suggested_reaction_config.get("specificity") or 0
                    ),
                    quality_rank=(float(proposal.suggested_reaction_config.get("quality") or 0),),
                ),
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
    first = replace(
        _proposal(conf=0.9),
        suggested_reaction_config={"id": "first", "group": "morning", "specificity": 2},
    )
    second = replace(
        _proposal(conf=0.8),
        suggested_reaction_config={"id": "second", "group": "morning", "specificity": 1},
    )

    first_id = await engine.async_submit_proposal(first)
    second_id = await engine.async_submit_proposal(second)
    assert [proposal.proposal_id for proposal in engine.pending_proposals()] == [first_id]

    assert await engine.async_reject_proposal(first_id)

    pending = engine.pending_proposals()
    assert [proposal.proposal_id for proposal in pending] == [second_id]
    assert engine.proposal_by_id(second_id).status == "pending"  # type: ignore[union-attr]


async def test_proposal_engine_groups_house_state_learned_context_by_review_context(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]

    def _house_state_proposal(
        *,
        context_key: str,
        rooms: list[str],
        learning_context: dict[str, object],
        support: int,
    ) -> ReactionProposal:
        return ReactionProposal(
            analyzer_id="house_state_inference",
            reaction_type=HOUSE_STATE_PROPOSAL_TYPE,
            description="Learned house-state context predicts working.",
            confidence=1.0,
            identity_key=f"{HOUSE_STATE_PROPOSAL_TYPE}:{context_key}",
            suggested_reaction_config={
                "proposal_type": HOUSE_STATE_PROPOSAL_TYPE,
                "context_key": context_key,
                "context_snapshot": {
                    "weekday": 1,
                    "hour_bucket": 17,
                    "rooms": rooms,
                    "anyone_home": True,
                    "predicted_state": "working",
                    "learning_context": learning_context,
                },
                "predicted_state": "working",
                "support": support,
                "total": support,
            },
        )

    await engine.async_initialize()
    minimal = _house_state_proposal(
        context_key="minimal-key",
        rooms=[],
        learning_context={"module": "house_state_inference_minimal"},
        support=10,
    )
    coarse = _house_state_proposal(
        context_key="coarse-key",
        rooms=["studio"],
        learning_context={},
        support=3,
    )
    rich = _house_state_proposal(
        context_key="rich-key",
        rooms=["studio"],
        learning_context={
            "module": "house_state_inference_rich",
            "room_context_pattern": [
                {"room_id": "studio", "media_on": False, "work_activity": True}
            ],
        },
        support=3,
    )

    await engine.async_submit_proposal(minimal)
    await engine.async_submit_proposal(coarse)
    rich_id = await engine.async_submit_proposal(rich)

    pending = engine.pending_proposals()
    assert [proposal.proposal_id for proposal in pending] == [rich_id]

    diagnostics = engine.diagnostics()
    assert diagnostics["pending"] == 1
    assert diagnostics["suppressed_in_review_count"] == 2
    group_keys = {
        proposal["review_group_key"]
        for proposal in diagnostics["proposals"]
        if proposal["type"] == HOUSE_STATE_PROPOSAL_TYPE
    }
    assert group_keys == {
        (
            "house_state_learned_context:house_state_ctx_group:"
            "weekday:1:hour_bucket:17:anyone_home:1:state:working"
        )
    }


async def test_proposal_engine_composite_identity_uses_room_and_primary_signal(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    analyzer = _AnalyzerStub(
        [
            _composite_proposal(
                reaction_type="room_signal_assist",
                room_id="bathroom",
                primary_signal_name="room_humidity",
            )
        ]
    )
    engine.register_analyzer(analyzer)

    await engine.async_initialize()
    await engine.async_run()

    pending = engine.pending_proposals()
    assert len(pending) == 1
    assert pending[0].identity_key == "room_signal_assist|room=bathroom|primary=room_humidity"


async def test_proposal_engine_composite_config_summary_exposes_signal_fields(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    proposal = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="room_humidity",
    )
    proposal.suggested_reaction_config.update(
        {
            "primary_bucket": "high",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [],
        }
    )
    engine._store._data = {"data": {"proposals": [proposal.as_dict()]}}

    await engine.async_initialize()

    diagnostics = engine.diagnostics()

    summary = diagnostics["proposals"][0]["config_summary"]
    assert summary["primary_signal_name"] == "room_humidity"
    assert summary["primary_bucket"] == "high"
    assert summary["primary_signal_entities_count"] == 1
    assert summary["corroboration_signal_name"] == "room_temperature"
    assert summary["corroboration_bucket"] == "warm"
    assert summary["corroboration_signal_entities_count"] == 1


async def test_proposal_engine_creates_composite_tuning_followup_for_accepted_slot(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="room_humidity",
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
        primary_signal_name="room_humidity",
    )
    candidate.suggested_reaction_config.update(
        {
            "primary_bucket": "high",
            "primary_signal_entities": [
                "sensor.bathroom_humidity",
                "sensor.bathroom_humidity_aux",
            ],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "hot",
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
    assert pending["identity_key"] == "room_signal_assist|room=bathroom|primary=room_humidity"


async def test_proposal_engine_suppresses_minor_room_signal_assist_tuning_drift(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="room_humidity",
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
            "primary_bucket": "high",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [],
        }
    )
    candidate = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="room_humidity",
    )
    candidate.suggested_reaction_config.update(
        {
            "primary_bucket": "high",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
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


async def test_proposal_engine_suppresses_canonical_room_signal_followup_despite_legacy_primary_threshold_fields(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="room_humidity",
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
            "primary_bucket": "high",
            "primary_threshold": 8.0,
            "primary_threshold_mode": "rise",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
            "corroboration_signal_entities": ["sensor.bathroom_temperature"],
            "steps": [],
        }
    )
    candidate = _composite_proposal(
        reaction_type="room_signal_assist",
        room_id="bathroom",
        primary_signal_name="room_humidity",
    )
    candidate.suggested_reaction_config.update(
        {
            "primary_bucket": "high",
            "primary_threshold": 99.0,
            "primary_threshold_mode": "above",
            "primary_signal_entities": ["sensor.bathroom_humidity"],
            "corroboration_signal_name": "room_temperature",
            "corroboration_bucket": "warm",
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
        reaction_type="room_smart_lighting_assist",
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
            "reaction_class": "RoomSmartLightingAssistReaction",
            "primary_bucket": "ok",
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
        reaction_type="room_smart_lighting_assist",
        room_id="living",
        primary_signal_name="room_lux",
    )
    candidate.suggested_reaction_config.update(
        {
            "reaction_class": "RoomSmartLightingAssistReaction",
            "primary_bucket": "dim",
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
    assert pending["identity_key"] == "room_smart_lighting_assist|room=living|primary=room_lux"


async def test_proposal_engine_suppresses_minor_room_darkness_lighting_tuning_drift(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    base = _composite_proposal(
        reaction_type="room_smart_lighting_assist",
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
            "reaction_class": "RoomSmartLightingAssistReaction",
            "primary_bucket": "ok",
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
        reaction_type="room_smart_lighting_assist",
        room_id="living",
        primary_signal_name="room_lux",
    )
    candidate.suggested_reaction_config.update(
        {
            "reaction_class": "RoomSmartLightingAssistReaction",
            "primary_bucket": "ok",
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


async def test_proposal_engine_suppresses_against_any_matching_accepted_followup(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    old_base = _composite_proposal(
        reaction_type="room_vacancy_lighting_off",
        room_id="studio",
        primary_signal_name="",
    )
    old_base = ReactionProposal.from_dict(
        {
            **old_base.as_dict(),
            "proposal_id": "old-base",
            "status": "accepted",
            "origin": "admin_authored",
            "updated_at": "2026-04-09T00:00:00+00:00",
        }
    )
    old_base.suggested_reaction_config.update(
        {
            "reaction_type": "room_vacancy_lighting_off",
            "vacancy_delay_s": 300,
            "entity_steps": [
                {"entity_id": "light.studio_window", "action": "off"},
                {"entity_id": "light.studio_door", "action": "off"},
            ],
        }
    )
    newer_base = _composite_proposal(
        reaction_type="room_vacancy_lighting_off",
        room_id="studio",
        primary_signal_name="",
    )
    newer_base = ReactionProposal.from_dict(
        {
            **newer_base.as_dict(),
            "proposal_id": "newer-base",
            "status": "accepted",
            "origin": "learned",
            "updated_at": "2026-04-28T00:00:00+00:00",
        }
    )
    newer_base.suggested_reaction_config.update(
        {
            "reaction_type": "room_vacancy_lighting_off",
            "vacancy_delay_s": 300,
            "entity_steps": [
                {"entity_id": "light.studio_window", "action": "off"},
                {"entity_id": "light.studio_door", "action": "off"},
                {"entity_id": "light.studio_led", "action": "off"},
            ],
        }
    )
    stale_pending = ReactionProposal.from_dict(
        {
            **newer_base.as_dict(),
            "proposal_id": "stale-pending",
            "status": "pending",
            "origin": "learned",
            "updated_at": "2026-04-29T00:00:00+00:00",
        }
    )
    candidate = _composite_proposal(
        reaction_type="room_vacancy_lighting_off",
        room_id="studio",
        primary_signal_name="",
    )
    candidate.suggested_reaction_config.update(
        {
            "reaction_type": "room_vacancy_lighting_off",
            "vacancy_delay_s": 300,
            "entity_steps": [
                {"entity_id": "light.studio_window", "action": "off"},
                {"entity_id": "light.studio_door", "action": "off"},
                {"entity_id": "light.studio_led", "action": "off"},
            ],
        }
    )

    engine = ProposalEngine(object(), _EventStoreStub())  # type: ignore[arg-type]
    engine._store._data = {
        "data": {
            "proposals": [
                old_base.as_dict(),
                newer_base.as_dict(),
                stale_pending.as_dict(),
            ]
        }
    }
    engine.register_analyzer(_AnalyzerStub([candidate]))

    await engine.async_initialize()
    await engine.async_run()

    diagnostics = engine.diagnostics()
    assert diagnostics["pending"] == 0
    assert {item["id"] for item in diagnostics["proposals"]} == {"old-base", "newer-base"}


async def test_proposal_engine_suppresses_followup_covered_by_configured_reaction(monkeypatch):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    candidate = _composite_proposal(
        reaction_type="room_vacancy_lighting_off",
        room_id="studio",
        primary_signal_name="",
    )
    candidate.suggested_reaction_config.update(
        {
            "reaction_type": "room_vacancy_lighting_off",
            "vacancy_delay_s": 300,
            "entity_steps": [
                {"entity_id": "light.studio_window", "action": "off"},
                {"entity_id": "light.studio_door", "action": "off"},
            ],
        }
    )
    stale_pending = ReactionProposal.from_dict(
        {
            **candidate.as_dict(),
            "proposal_id": "stale-pending",
            "status": "pending",
        }
    )

    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        configured_reactions_provider=lambda: {
            "configured-vacancy": {
                "reaction_type": "room_vacancy_lighting_off",
                "room_id": "studio",
                "vacancy_delay_s": 330,
                "entity_steps": [
                    {"entity_id": "light.studio_door", "action": "off"},
                    {"entity_id": "light.studio_window", "action": "off"},
                ],
            }
        },
    )
    engine._store._data = {"data": {"proposals": [stale_pending.as_dict()]}}
    engine.register_analyzer(_AnalyzerStub([candidate]))

    await engine.async_initialize()
    await engine.async_run()

    assert len(engine.pending_proposals()) == 0


async def test_proposal_engine_suppresses_darkness_when_configured_contextual_covers_room(
    monkeypatch,
):
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeStore)
    candidate = _composite_proposal(
        reaction_type="room_smart_lighting_assist",
        room_id="studio",
        primary_signal_name="room_lux",
    )
    candidate.suggested_reaction_config.update(
        {
            "reaction_type": "room_smart_lighting_assist",
            "primary_bucket": "ok",
            "primary_bucket_match_mode": "lte",
            "primary_signal_entities": ["sensor.studio_lux"],
            "entity_steps": [
                {
                    "entity_id": "light.studio_window",
                    "action": "on",
                    "brightness": 160,
                }
            ],
        }
    )
    stale_pending = ReactionProposal.from_dict(
        {
            **candidate.as_dict(),
            "proposal_id": "stale-darkness",
            "status": "pending",
        }
    )

    engine = ProposalEngine(
        object(),  # type: ignore[arg-type]
        _EventStoreStub(),  # type: ignore[arg-type]
        configured_reactions_provider=lambda: {
            "configured-contextual": {
                "reaction_type": "room_smart_lighting_assist",
                "room_id": "studio",
                "primary_signal_name": "room_lux",
                "primary_bucket": "ok",
                "primary_bucket_match_mode": "lte",
                "primary_signal_entities": ["sensor.studio_lux"],
                "entity_steps": [
                    {
                        "entity_id": "light.studio_window",
                        "action": "on",
                        "brightness": 160,
                    }
                ],
            }
        },
    )
    engine._store._data = {"data": {"proposals": [stale_pending.as_dict()]}}
    engine.register_analyzer(_AnalyzerStub([candidate]))

    await engine.async_initialize()
    await engine.async_run()

    assert len(engine.pending_proposals()) == 0
