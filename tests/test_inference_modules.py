"""Tests for WeekdayStateModule and HeatingPreferenceModule."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from custom_components.heima.runtime.inference import (
    ActivityInferenceModule,
    HeatingPreferenceModule,
    HouseSnapshot,
    HouseStateInferenceModule,
    Importance,
    InferenceContext,
    RoomContextModule,
    WeekdayStateModule,
)
from custom_components.heima.runtime.inference.approval_store import (
    HOUSE_STATE_PROPOSAL_TYPE,
    house_state_context_key,
)
from custom_components.heima.runtime.proposal_engine import ActivityProposal
from custom_components.heima.runtime.room_context import RoomDeviceContext


def _context(
    *,
    weekday: int = 0,
    minute_of_day: int = 600,
    previous_house_state: str = "home",
    previous_heating_setpoint: float | None = 20.0,
    anyone_home: bool = True,
    room_occupancy: dict[str, bool] | None = None,
    previous_activity_names: tuple[str, ...] = (),
    room_device_context: dict[str, RoomDeviceContext] | None = None,
) -> InferenceContext:
    return InferenceContext(
        now_local=datetime(2026, 4, 30, 10, 0, tzinfo=UTC),
        weekday=weekday,
        minute_of_day=minute_of_day,
        anyone_home=anyone_home,
        named_present=("alice",),
        room_occupancy=room_occupancy or {"kitchen": True},
        previous_house_state=previous_house_state,
        previous_heating_setpoint=previous_heating_setpoint,
        previous_lighting_scenes={},
        previous_activity_names=previous_activity_names,
        room_device_context=room_device_context or {},
    )


def _snapshot(
    *,
    weekday: int = 0,
    minute_of_day: int = 600,
    house_state: str = "home",
    heating_setpoint: float | None = 20.5,
    anyone_home: bool = True,
    room_occupancy: dict[str, bool] | None = None,
    detected_activities: tuple[str, ...] = (),
    room_device_context: dict[str, dict] | None = None,
) -> HouseSnapshot:
    return HouseSnapshot(
        ts="2026-04-30T10:00:00+00:00",
        weekday=weekday,
        minute_of_day=minute_of_day,
        anyone_home=anyone_home,
        named_present=("alice",),
        room_occupancy=room_occupancy or {},
        detected_activities=detected_activities,
        house_state=house_state,
        heating_setpoint=heating_setpoint,
        lighting_scenes={},
        room_device_context=room_device_context or {},
        security_state="disarmed",
    )


class _FakeStore:
    def __init__(self, snapshots: list[HouseSnapshot]) -> None:
        self._snapshots = snapshots

    def snapshots(self) -> list[HouseSnapshot]:
        return self._snapshots


# ─── ActivityInferenceModule ──────────────────────────────────────────────────


def _activity_proposal(
    *,
    activity_name: str = "Movie Night",
    primitive_pattern: frozenset[str] = frozenset({"tv", "relax"}),
    context_conditions: dict | None = None,
    confidence: float = 0.9,
    bootstrap: bool = False,
) -> ActivityProposal:
    return ActivityProposal(
        activity_name=activity_name,
        primitive_pattern=primitive_pattern,
        context_conditions=context_conditions
        if context_conditions is not None
        else {"room_id": "living_room", "hour_range": [20, 24]},
        occurrence_count=12,
        confidence=confidence,
        representative_ts=["2026-04-30T20:00:00+00:00"],
        bootstrap=bootstrap,
    )


def test_activity_inference_returns_empty_before_analyze() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals([_activity_proposal()])

    assert (
        module.infer(
            _context(
                minute_of_day=20 * 60,
                room_occupancy={"living_room": True},
                previous_activity_names=("tv", "relax"),
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_activity_inference_returns_empty_without_approved_proposals() -> None:
    module = ActivityInferenceModule()
    snapshots = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 10

    await module.analyze(_FakeStore(snapshots))

    assert (
        module.infer(
            _context(
                minute_of_day=20 * 60,
                room_occupancy={"living_room": True},
                previous_activity_names=("tv", "relax"),
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_activity_inference_emits_for_approved_pattern() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals([_activity_proposal()])
    snapshots = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 10

    await module.analyze(_FakeStore(snapshots))
    signals = module.infer(
        _context(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            previous_activity_names=("tv", "relax"),
        )
    )

    assert len(signals) == 1
    assert signals[0].source_id == "activity_inference"
    assert signals[0].activity_name == "movie_night"
    assert signals[0].room_id == "living_room"
    assert signals[0].confidence == 1.0
    assert signals[0].importance == Importance.ASSERT
    assert signals[0].context["primitive_pattern"] == ["relax", "tv"]


# ─── RoomContextModule ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_room_context_module_ignores_legacy_snapshots_without_context() -> None:
    module = RoomContextModule(min_support=1, confidence_threshold=0.5)

    await module.analyze(
        _FakeStore(
            [
                _snapshot(
                    weekday=3,
                    minute_of_day=8 * 60,
                    house_state="relax",
                    room_occupancy={"living_room": True},
                )
            ]
        )
    )

    assert module.generate_candidates() == []
    assert module.diagnostics()["analyzed_snapshots"] == 0


@pytest.mark.asyncio
async def test_room_context_module_generates_candidate_after_support() -> None:
    module = RoomContextModule(min_support=2, confidence_threshold=0.65)
    snapshots = [
        _snapshot(
            weekday=3,
            minute_of_day=8 * 60,
            house_state="relax",
            room_occupancy={"living_room": True},
            room_device_context={
                "living_room": {
                    "room_id": "living_room",
                    "media_on": True,
                    "work_activity": False,
                }
            },
        )
    ] * 2

    await module.analyze(_FakeStore(snapshots))

    candidates = module.generate_candidates()
    assert len(candidates) == 1
    assert candidates[0].proposal_type == HOUSE_STATE_PROPOSAL_TYPE
    assert candidates[0].predicted_state == "relax"
    assert candidates[0].support == 2
    assert candidates[0].confidence == 1.0
    assert candidates[0].context_snapshot["learning_context"]["module"] == "room_context"


@pytest.mark.asyncio
async def test_room_context_module_does_not_emit_without_approval() -> None:
    module = RoomContextModule(min_support=1, confidence_threshold=0.65)
    await module.analyze(
        _FakeStore(
            [
                _snapshot(
                    weekday=3,
                    minute_of_day=8 * 60,
                    house_state="relax",
                    room_occupancy={"living_room": True},
                    room_device_context={
                        "living_room": {
                            "room_id": "living_room",
                            "media_on": True,
                            "work_activity": False,
                        }
                    },
                )
            ]
        )
    )

    assert (
        module.infer(
            _context(
                weekday=3,
                minute_of_day=8 * 60,
                room_occupancy={"living_room": True},
                room_device_context={
                    "living_room": RoomDeviceContext("living_room", media_on=True)
                },
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_room_context_module_emits_after_approval() -> None:
    module = RoomContextModule(min_support=1, confidence_threshold=0.65)
    snapshot = _snapshot(
        weekday=3,
        minute_of_day=8 * 60,
        house_state="relax",
        room_occupancy={"living_room": True},
        room_device_context={
            "living_room": {
                "room_id": "living_room",
                "media_on": True,
                "work_activity": False,
            }
        },
    )
    await module.analyze(_FakeStore([snapshot]))
    candidate = module.generate_candidates()[0]
    module.sync_approval_state({candidate.context_key}, set())

    signals = module.infer(
        _context(
            weekday=3,
            minute_of_day=8 * 60,
            room_occupancy={"living_room": True},
            room_device_context={"living_room": RoomDeviceContext("living_room", media_on=True)},
        )
    )

    assert len(signals) == 1
    assert signals[0].source_id == "room_context"
    assert signals[0].predicted_state == "relax"
    assert signals[0].importance == Importance.SUGGEST


@pytest.mark.asyncio
async def test_room_context_module_respects_min_support() -> None:
    module = RoomContextModule(min_support=2, confidence_threshold=0.65)
    await module.analyze(
        _FakeStore(
            [
                _snapshot(
                    weekday=3,
                    minute_of_day=8 * 60,
                    house_state="relax",
                    room_occupancy={"living_room": True},
                    room_device_context={
                        "living_room": {"room_id": "living_room", "media_on": True}
                    },
                )
            ]
        )
    )

    assert module.generate_candidates() == []


@pytest.mark.asyncio
async def test_room_context_module_pattern_excludes_lights_and_pc() -> None:
    module = RoomContextModule(min_support=1, confidence_threshold=0.65)
    await module.analyze(
        _FakeStore(
            [
                _snapshot(
                    weekday=3,
                    minute_of_day=8 * 60,
                    house_state="working",
                    room_occupancy={"studio": True},
                    room_device_context={
                        "studio": {
                            "room_id": "studio",
                            "media_on": True,
                            "work_activity": True,
                            "lights_on": False,
                            "pc_active": False,
                        }
                    },
                )
            ]
        )
    )
    candidate = module.generate_candidates()[0]
    module.sync_approval_state({candidate.context_key}, set())

    signals = module.infer(
        _context(
            weekday=3,
            minute_of_day=8 * 60,
            room_occupancy={"studio": True},
            room_device_context={
                "studio": RoomDeviceContext(
                    "studio",
                    media_on=True,
                    work_activity=True,
                    lights_on=True,
                    pc_active=True,
                )
            },
        )
    )

    assert len(signals) == 1
    assert signals[0].predicted_state == "working"


@pytest.mark.asyncio
async def test_activity_inference_no_signal_below_min_support() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals([_activity_proposal()])
    snapshots = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 9

    await module.analyze(_FakeStore(snapshots))

    assert (
        module.infer(
            _context(
                minute_of_day=20 * 60,
                room_occupancy={"living_room": True},
                previous_activity_names=("tv", "relax"),
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_activity_inference_uses_bootstrap_min_support_for_bootstrap_pattern() -> None:
    module = ActivityInferenceModule(bootstrap_mode=True)
    module.sync_approved_proposals([_activity_proposal(bootstrap=True)])
    snapshots = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 5

    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(
        _context(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            previous_activity_names=("tv", "relax"),
        )
    )

    assert len(signals) == 1
    assert signals[0].context["bootstrap"] is True
    assert signals[0].context["required_support"] == 5
    assert module.diagnostics()["bootstrap_patterns"] == 1
    assert module.diagnostics()["bootstrap_mode"] is True


@pytest.mark.asyncio
async def test_activity_inference_explicit_min_support_overrides_bootstrap_support() -> None:
    module = ActivityInferenceModule(
        min_support=8,
        explicit_min_support=True,
        bootstrap_mode=True,
    )
    module.sync_approved_proposals([_activity_proposal(bootstrap=True)])
    snapshots = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 5

    await module.analyze(_FakeStore(snapshots))

    assert (
        module.infer(
            _context(
                minute_of_day=20 * 60,
                room_occupancy={"living_room": True},
                previous_activity_names=("tv", "relax"),
            )
        )
        == []
    )
    assert module.diagnostics()["explicit_min_support"] is True


@pytest.mark.asyncio
async def test_activity_inference_no_signal_below_confidence_threshold() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals([_activity_proposal()])
    matching = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 10
    non_matching_context = [
        _snapshot(
            minute_of_day=18 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 10

    await module.analyze(_FakeStore(matching + non_matching_context))

    assert (
        module.infer(
            _context(
                minute_of_day=20 * 60,
                room_occupancy={"living_room": True},
                previous_activity_names=("tv", "relax"),
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_activity_inference_no_signal_when_current_pattern_missing() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals([_activity_proposal()])
    snapshots = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 10

    await module.analyze(_FakeStore(snapshots))

    assert (
        module.infer(
            _context(
                minute_of_day=20 * 60,
                room_occupancy={"living_room": True},
                previous_activity_names=("tv",),
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_activity_inference_no_signal_when_context_does_not_match_now() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals([_activity_proposal()])
    snapshots = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 10

    await module.analyze(_FakeStore(snapshots))

    assert (
        module.infer(
            _context(
                minute_of_day=18 * 60,
                room_occupancy={"living_room": True},
                previous_activity_names=("tv", "relax"),
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_activity_inference_matches_weekday_filter() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals(
        [_activity_proposal(context_conditions={"weekday_filter": {"days": ["thursday"]}})]
    )
    snapshots = [
        _snapshot(
            weekday=3,
            minute_of_day=20 * 60,
            detected_activities=("tv", "relax"),
        )
    ] * 10

    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(
        _context(
            weekday=3,
            minute_of_day=20 * 60,
            previous_activity_names=("tv", "relax"),
        )
    )
    assert len(signals) == 1


@pytest.mark.asyncio
async def test_activity_inference_sync_approved_proposals_replaces_previous_state() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals([_activity_proposal(activity_name="Movie Night")])
    snapshots = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 10
    await module.analyze(_FakeStore(snapshots))
    assert module.diagnostics()["approved_patterns"] == 1

    module.sync_approved_proposals([])

    assert module.diagnostics()["approved_patterns"] == 0
    assert (
        module.infer(
            _context(
                minute_of_day=20 * 60,
                room_occupancy={"living_room": True},
                previous_activity_names=("tv", "relax"),
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_activity_inference_infer_completes_under_1ms() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals([_activity_proposal()])
    snapshots = [
        _snapshot(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            detected_activities=("tv", "relax"),
        )
    ] * 10
    await module.analyze(_FakeStore(snapshots))

    start = time.perf_counter()
    module.infer(
        _context(
            minute_of_day=20 * 60,
            room_occupancy={"living_room": True},
            previous_activity_names=("tv", "relax"),
        )
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 1.0


@pytest.mark.asyncio
async def test_activity_inference_diagnostics() -> None:
    module = ActivityInferenceModule()
    module.sync_approved_proposals([_activity_proposal()])
    await module.analyze(
        _FakeStore(
            [
                _snapshot(
                    minute_of_day=20 * 60,
                    room_occupancy={"living_room": True},
                    detected_activities=("tv", "relax"),
                )
            ]
            * 10
        )
    )

    diag = module.diagnostics()

    assert diag["module_id"] == "activity_inference"
    assert diag["ready"] is True
    assert diag["approved_patterns"] == 1
    assert diag["model_entries"] == 1
    assert diag["analyzed_snapshots"] == 10


# ─── WeekdayStateModule ───────────────────────────────────────────────────────


def test_weekday_state_returns_empty_before_analyze() -> None:
    module = WeekdayStateModule()
    assert module.infer(_context()) == []


@pytest.mark.asyncio
async def test_weekday_state_emits_signal_with_enough_support() -> None:
    module = WeekdayStateModule()
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))

    assert len(signals) == 1
    assert signals[0].predicted_state == "home"
    assert signals[0].source_id == "weekday_state"
    assert signals[0].confidence > 0.0


@pytest.mark.asyncio
async def test_weekday_state_no_signal_below_min_support() -> None:
    module = WeekdayStateModule()
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 5
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))
    assert signals == []


@pytest.mark.asyncio
async def test_weekday_state_uses_constructor_thresholds() -> None:
    module = WeekdayStateModule(min_support=5, confidence_threshold=0.80)
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 3
    snapshots.extend(_snapshot(weekday=0, minute_of_day=600, house_state="away") for _ in range(2))
    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context(weekday=0, minute_of_day=600)) == []

    permissive = WeekdayStateModule(min_support=5, confidence_threshold=0.60)
    await permissive.analyze(_FakeStore(snapshots))
    signals = permissive.infer(_context(weekday=0, minute_of_day=600))
    assert len(signals) == 1
    assert signals[0].confidence == 0.6


@pytest.mark.asyncio
async def test_weekday_state_no_signal_for_unknown_slot() -> None:
    module = WeekdayStateModule()
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=1, minute_of_day=600))
    assert signals == []


@pytest.mark.asyncio
async def test_weekday_state_importance_observe_range() -> None:
    module = WeekdayStateModule()
    # 10 snapshots split 5 home / 5 away → probability=0.5, confidence = 0.5 * 1.0 = 0.50 → OBSERVE
    snapshots = [
        _snapshot(weekday=0, minute_of_day=600, house_state="home"),
        _snapshot(weekday=0, minute_of_day=600, house_state="away"),
    ] * 5
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))
    # majority (home or away, both 5 each — max picks first alphabetically or by dict iteration)
    # Either way: probability=0.5, confidence=0.5, importance=OBSERVE
    assert len(signals) == 1
    assert signals[0].importance == Importance.OBSERVE


@pytest.mark.asyncio
async def test_weekday_state_high_confidence_remains_observe() -> None:
    module = WeekdayStateModule()
    # WeekdayStateModule is legacy observational context; confidence no longer escalates
    # its domain authority.
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 7 + [
        _snapshot(weekday=0, minute_of_day=600, house_state="away")
    ] * 3
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))
    assert len(signals) == 1
    assert signals[0].importance == Importance.OBSERVE
    assert signals[0].predicted_state == "home"


@pytest.mark.asyncio
async def test_weekday_state_very_high_confidence_remains_observe() -> None:
    module = WeekdayStateModule()
    # Even very high-confidence weekday-only predictions remain observational.
    snapshots = [_snapshot(weekday=0, minute_of_day=600, house_state="home")] * 9 + [
        _snapshot(weekday=0, minute_of_day=600, house_state="away")
    ] * 1
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(weekday=0, minute_of_day=600))
    assert len(signals) == 1
    assert signals[0].importance == Importance.OBSERVE


@pytest.mark.asyncio
async def test_weekday_state_infer_completes_under_1ms() -> None:
    module = WeekdayStateModule()
    snapshots = [
        _snapshot(weekday=wd, minute_of_day=h * 60, house_state="home")
        for wd in range(7)
        for h in range(24)
        for _ in range(10)
    ]
    await module.analyze(_FakeStore(snapshots))

    start = time.perf_counter()
    module.infer(_context(weekday=3, minute_of_day=660))
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 1.0


@pytest.mark.asyncio
async def test_weekday_state_diagnostics() -> None:
    module = WeekdayStateModule()
    await module.analyze(_FakeStore([_snapshot()] * 10))
    diag = module.diagnostics()
    assert diag["module_id"] == "weekday_state"
    assert diag["ready"] is True
    assert diag["slot_count"] >= 1
    assert diag["min_support"] == 10
    assert diag["confidence_threshold"] == 0.4


# ─── HeatingPreferenceModule ──────────────────────────────────────────────────


def test_heating_preference_returns_empty_before_analyze() -> None:
    module = HeatingPreferenceModule()
    assert module.infer(_context()) == []


@pytest.mark.asyncio
async def test_heating_preference_emits_signal_with_enough_support() -> None:
    module = HeatingPreferenceModule()
    snapshots = [_snapshot(house_state="home", heating_setpoint=20.5)] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="home"))
    assert len(signals) == 1
    assert abs(signals[0].predicted_setpoint - 20.5) < 0.01
    assert signals[0].house_state_context == "home"
    assert signals[0].source_id == "heating_preference"


@pytest.mark.asyncio
async def test_heating_preference_no_signal_below_min_support() -> None:
    module = HeatingPreferenceModule()
    snapshots = [_snapshot(house_state="home", heating_setpoint=20.5)] * 5
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="home"))
    assert signals == []


@pytest.mark.asyncio
async def test_heating_preference_uses_constructor_thresholds() -> None:
    module = HeatingPreferenceModule(min_support=20, confidence_threshold=0.40)
    snapshots = [_snapshot(house_state="home", heating_setpoint=20.5)] * 10
    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context(previous_house_state="home")) == []

    permissive = HeatingPreferenceModule(min_support=10, confidence_threshold=0.40)
    await permissive.analyze(_FakeStore(snapshots))
    assert len(permissive.infer(_context(previous_house_state="home"))) == 1


@pytest.mark.asyncio
async def test_heating_preference_no_signal_for_unknown_state() -> None:
    module = HeatingPreferenceModule()
    snapshots = [_snapshot(house_state="home", heating_setpoint=20.5)] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="away"))
    assert signals == []


@pytest.mark.asyncio
async def test_heating_preference_skips_snapshots_without_setpoint() -> None:
    module = HeatingPreferenceModule()
    snapshots = [_snapshot(house_state="home", heating_setpoint=None)] * 5 + [
        _snapshot(house_state="home", heating_setpoint=21.0)
    ] * 10
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="home"))
    assert len(signals) == 1
    assert abs(signals[0].predicted_setpoint - 21.0) < 0.01


@pytest.mark.asyncio
async def test_heating_preference_mean_setpoint() -> None:
    module = HeatingPreferenceModule()
    setpoints = [19.0, 20.0, 21.0, 22.0, 19.5, 20.5, 21.5, 19.0, 20.0, 21.0]
    snapshots = [_snapshot(house_state="home", heating_setpoint=sp) for sp in setpoints]
    await module.analyze(_FakeStore(snapshots))

    signals = module.infer(_context(previous_house_state="home"))
    assert len(signals) == 1
    assert abs(signals[0].predicted_setpoint - (sum(setpoints) / len(setpoints))) < 0.001


@pytest.mark.asyncio
async def test_heating_preference_infer_completes_under_1ms() -> None:
    module = HeatingPreferenceModule()
    snapshots = [
        _snapshot(house_state=state, heating_setpoint=sp)
        for state, sp in [("home", 20.5), ("away", 16.0), ("night", 18.0), ("vacation", 14.0)]
        for _ in range(10)
    ]
    await module.analyze(_FakeStore(snapshots))

    start = time.perf_counter()
    module.infer(_context(previous_house_state="home"))
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 1.0


@pytest.mark.asyncio
async def test_heating_preference_diagnostics() -> None:
    module = HeatingPreferenceModule()
    await module.analyze(_FakeStore([_snapshot(house_state="home")] * 10))
    diag = module.diagnostics()
    assert diag["module_id"] == "heating_preference"
    assert diag["ready"] is True
    assert diag["state_count"] >= 1
    assert diag["min_support"] == 10
    assert diag["confidence_threshold"] == 0.4


# ─── HouseStateInferenceModule ────────────────────────────────────────────────


def _house_state_key(
    *,
    weekday: int = 0,
    minute_of_day: int = 600,
    rooms: tuple[str, ...] = ("kitchen",),
    anyone_home: bool = True,
    predicted_state: str = "working",
) -> str:
    return house_state_context_key(
        weekday=weekday,
        hour_bucket=minute_of_day // 60,
        rooms=rooms,
        anyone_home=anyone_home,
        predicted_state=predicted_state,
        learning_context={},
    )


def _house_state_candidate_by_tier(candidates, tier: str):
    for candidate in candidates:
        learning_context = candidate.context_snapshot.get("learning_context", {})
        module = learning_context.get("module")
        if tier == "coarse" and learning_context == {}:
            return candidate
        if tier == "rich" and module == "house_state_inference_rich":
            return candidate
        if tier == "minimal" and module == "house_state_inference_minimal":
            return candidate
    raise AssertionError(f"Missing {tier} candidate")


def test_house_state_inference_returns_empty_before_analyze() -> None:
    module = HouseStateInferenceModule()

    assert module.infer(_context()) == []


@pytest.mark.asyncio
async def test_house_state_inference_analyzes_without_approval() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 3

    await module.analyze(_FakeStore(snapshots))

    assert module.diagnostics()["ready"] is True
    assert module.diagnostics()["slot_count"] == 1
    assert module.infer(_context(room_occupancy={"kitchen": True})) == []


@pytest.mark.asyncio
async def test_house_state_inference_generates_candidate_for_unknown_context() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"bedroom": True, "kitchen": True},
        )
    ] * 3

    await module.analyze(_FakeStore(snapshots))

    candidates = module.generate_candidates()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.proposal_type == HOUSE_STATE_PROPOSAL_TYPE
    assert candidate.predicted_state == "working"
    assert candidate.support == 3
    assert candidate.total == 3
    assert candidate.confidence == 1.0
    assert candidate.context_key == _house_state_key(
        rooms=("bedroom", "kitchen"),
        predicted_state="working",
    )
    assert candidate.context_snapshot == {
        "weekday": 0,
        "hour_bucket": 10,
        "rooms": ["bedroom", "kitchen"],
        "anyone_home": True,
        "predicted_state": "working",
        "learning_context": {},
    }
    assert module.infer(_context(room_occupancy={"bedroom": True, "kitchen": True})) == []


@pytest.mark.asyncio
async def test_house_state_inference_does_not_generate_candidate_for_hard_state() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="guest",
            room_occupancy={"bathroom": True},
        )
    ] * 3

    await module.analyze(_FakeStore(snapshots))

    assert module.generate_candidates() == []


@pytest.mark.asyncio
async def test_house_state_inference_does_not_generate_candidate_for_approved_context() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 3
    approved_key = _house_state_key(rooms=("kitchen",), predicted_state="working")

    await module.analyze(_FakeStore(snapshots))
    module.sync_approval_state({approved_key}, set())

    assert module.generate_candidates() == []


@pytest.mark.asyncio
async def test_house_state_inference_rejected_context_has_no_candidate_or_signal() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 3
    rejected_key = _house_state_key(rooms=("kitchen",), predicted_state="working")

    await module.analyze(_FakeStore(snapshots))
    module.sync_approval_state(set(), {rejected_key})

    assert module.generate_candidates() == []
    assert module.infer(_context(room_occupancy={"kitchen": True})) == []


@pytest.mark.asyncio
async def test_house_state_inference_no_candidate_below_min_support() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 2

    await module.analyze(_FakeStore(snapshots))

    assert module.generate_candidates() == []


@pytest.mark.asyncio
async def test_house_state_inference_no_candidate_below_confidence_threshold() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(house_state="working", room_occupancy={"kitchen": True}),
        _snapshot(house_state="home", room_occupancy={"kitchen": True}),
        _snapshot(house_state="home", room_occupancy={"kitchen": True}),
        _snapshot(house_state="relax", room_occupancy={"kitchen": True}),
    ]

    await module.analyze(_FakeStore(snapshots))

    assert module.generate_candidates() == []


@pytest.mark.asyncio
async def test_house_state_inference_sync_approval_state_replaces_previous_state() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 3
    context_key = _house_state_key(rooms=("kitchen",), predicted_state="working")

    await module.analyze(_FakeStore(snapshots))
    module.sync_approval_state({context_key}, set())
    assert module.generate_candidates() == []

    module.sync_approval_state(set(), set())

    candidates = module.generate_candidates()
    assert len(candidates) == 1
    assert candidates[0].context_key == context_key


@pytest.mark.asyncio
async def test_house_state_inference_emits_only_after_context_key_approval() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 3
    await module.analyze(_FakeStore(snapshots))
    module.sync_approval_state(
        {_house_state_key(rooms=("kitchen",), predicted_state="working")},
        set(),
    )

    signals = module.infer(_context(room_occupancy={"kitchen": True}))

    assert len(signals) == 1
    assert signals[0].source_id == "house_state_inference"
    assert signals[0].predicted_state == "working"
    assert signals[0].importance == Importance.ASSERT


@pytest.mark.asyncio
async def test_house_state_inference_approval_for_different_state_does_not_emit() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 3
    await module.analyze(_FakeStore(snapshots))
    module.sync_approval_state(
        {_house_state_key(rooms=("kitchen",), predicted_state="relaxing")},
        set(),
    )

    assert module.infer(_context(room_occupancy={"kitchen": True})) == []


@pytest.mark.asyncio
async def test_house_state_inference_no_signal_below_min_support_even_if_approved() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 2
    await module.analyze(_FakeStore(snapshots))
    module.sync_approval_state(
        {_house_state_key(rooms=("kitchen",), predicted_state="working")},
        set(),
    )

    assert module.infer(_context(room_occupancy={"kitchen": True})) == []


@pytest.mark.asyncio
async def test_house_state_inference_no_signal_below_confidence_threshold() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(house_state="working", room_occupancy={"kitchen": True}),
        _snapshot(house_state="home", room_occupancy={"kitchen": True}),
        _snapshot(house_state="home", room_occupancy={"kitchen": True}),
        _snapshot(house_state="relax", room_occupancy={"kitchen": True}),
    ]
    await module.analyze(_FakeStore(snapshots))
    module.sync_approval_state(
        {_house_state_key(rooms=("kitchen",), predicted_state="home")},
        set(),
    )

    assert module.infer(_context(room_occupancy={"kitchen": True})) == []


@pytest.mark.asyncio
async def test_house_state_inference_uses_current_context_slot() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            weekday=0,
            minute_of_day=600,
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 3 + [
        _snapshot(
            weekday=1,
            minute_of_day=600,
            house_state="relax",
            room_occupancy={"kitchen": True},
        )
    ] * 3
    await module.analyze(_FakeStore(snapshots))
    module.sync_approval_state(
        {
            _house_state_key(
                weekday=1,
                minute_of_day=600,
                rooms=("kitchen",),
                predicted_state="relax",
            )
        },
        set(),
    )

    signals = module.infer(_context(weekday=1, minute_of_day=600))

    assert len(signals) == 1
    assert signals[0].predicted_state == "relax"


@pytest.mark.asyncio
async def test_house_state_inference_infer_completes_under_1ms() -> None:
    module = HouseStateInferenceModule()
    snapshots = [
        _snapshot(
            weekday=wd,
            minute_of_day=h * 60,
            house_state="working",
            room_occupancy={"kitchen": True},
        )
        for wd in range(7)
        for h in range(24)
        for _ in range(3)
    ]
    await module.analyze(_FakeStore(snapshots))
    module.sync_approval_state(
        {
            _house_state_key(
                weekday=3,
                minute_of_day=660,
                rooms=("kitchen",),
                predicted_state="working",
            )
        },
        set(),
    )

    start = time.perf_counter()
    module.infer(_context(weekday=3, minute_of_day=660, room_occupancy={"kitchen": True}))
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 1.0


@pytest.mark.asyncio
async def test_house_state_inference_diagnostics() -> None:
    module = HouseStateInferenceModule()
    await module.analyze(
        _FakeStore([_snapshot(house_state="working", room_occupancy={"kitchen": True})] * 3)
    )
    module.sync_approval_state({"key-1", "key-2"}, {"key-3"})

    diag = module.diagnostics()

    assert diag["module_id"] == "house_state_inference"
    assert diag["ready"] is True
    assert diag["slot_count"] == 1
    assert diag["approved_context_keys"] == 2
    assert diag["rejected_context_keys"] == 1
    assert diag["analyzed_snapshots"] == 3


@pytest.mark.asyncio
async def test_house_state_inference_uses_rich_tier_before_coarse() -> None:
    module = HouseStateInferenceModule(
        min_support=3,
        rich_min_support=2,
        minimal_min_support=5,
    )
    rich_relax = [
        _snapshot(
            weekday=2,
            minute_of_day=8 * 60,
            house_state="relax",
            room_occupancy={"living_room": True},
            room_device_context={
                "living_room": {
                    "room_id": "living_room",
                    "media_on": True,
                    "work_activity": False,
                }
            },
        )
    ] * 2
    coarse_work = [
        _snapshot(
            weekday=2,
            minute_of_day=8 * 60,
            house_state="working",
            room_occupancy={"living_room": True},
        )
    ] * 3

    await module.analyze(_FakeStore([*rich_relax, *coarse_work]))
    candidates = module.generate_candidates()
    rich = _house_state_candidate_by_tier(candidates, "rich")
    coarse = _house_state_candidate_by_tier(candidates, "coarse")
    module.sync_approval_state({rich.context_key, coarse.context_key}, set())

    signals = module.infer(
        _context(
            weekday=2,
            minute_of_day=8 * 60,
            room_occupancy={"living_room": True},
            room_device_context={"living_room": RoomDeviceContext("living_room", media_on=True)},
        )
    )

    assert len(signals) == 1
    assert signals[0].predicted_state == "relax"
    assert signals[0].context["tier"] == "rich"


@pytest.mark.asyncio
async def test_house_state_inference_falls_back_to_coarse_when_rich_support_insufficient() -> None:
    module = HouseStateInferenceModule(
        min_support=3,
        rich_min_support=2,
        minimal_min_support=5,
    )
    snapshots = [
        _snapshot(
            weekday=2,
            minute_of_day=8 * 60,
            house_state="working",
            room_occupancy={"studio": True},
            room_device_context={
                "studio": {
                    "room_id": "studio",
                    "media_on": True,
                    "work_activity": True,
                }
            },
        ),
        *[
            _snapshot(
                weekday=2,
                minute_of_day=8 * 60,
                house_state="working",
                room_occupancy={"studio": True},
            )
            for _ in range(2)
        ],
    ]

    await module.analyze(_FakeStore(snapshots))
    coarse = _house_state_candidate_by_tier(module.generate_candidates(), "coarse")
    module.sync_approval_state({coarse.context_key}, set())

    signals = module.infer(
        _context(
            weekday=2,
            minute_of_day=8 * 60,
            room_occupancy={"studio": True},
            room_device_context={
                "studio": RoomDeviceContext(
                    "studio",
                    media_on=True,
                    work_activity=True,
                )
            },
        )
    )

    assert len(signals) == 1
    assert signals[0].predicted_state == "working"
    assert signals[0].context["tier"] == "coarse"


@pytest.mark.asyncio
async def test_house_state_inference_falls_back_to_minimal_when_coarse_insufficient() -> None:
    module = HouseStateInferenceModule(
        min_support=3,
        rich_min_support=2,
        minimal_min_support=5,
    )
    snapshots = [
        _snapshot(
            weekday=4,
            minute_of_day=21 * 60,
            house_state="relax",
            room_occupancy={f"room_{idx}": True},
        )
        for idx in range(5)
    ]

    await module.analyze(_FakeStore(snapshots))
    minimal = _house_state_candidate_by_tier(module.generate_candidates(), "minimal")
    module.sync_approval_state({minimal.context_key}, set())

    signals = module.infer(
        _context(
            weekday=4,
            minute_of_day=21 * 60,
            room_occupancy={"new_room": True},
        )
    )

    assert len(signals) == 1
    assert signals[0].predicted_state == "relax"
    assert signals[0].context["tier"] == "minimal"


@pytest.mark.asyncio
async def test_house_state_inference_no_signal_when_all_tiers_below_support() -> None:
    module = HouseStateInferenceModule(
        min_support=3,
        rich_min_support=2,
        minimal_min_support=5,
    )
    snapshots = [
        _snapshot(
            weekday=4,
            minute_of_day=21 * 60,
            house_state="relax",
            room_occupancy={"living_room": True},
            room_device_context={
                "living_room": {
                    "room_id": "living_room",
                    "media_on": True,
                    "work_activity": False,
                }
            },
        )
    ]

    await module.analyze(_FakeStore(snapshots))

    assert module.generate_candidates() == []
    assert (
        module.infer(
            _context(
                weekday=4,
                minute_of_day=21 * 60,
                room_occupancy={"living_room": True},
                room_device_context={
                    "living_room": RoomDeviceContext("living_room", media_on=True)
                },
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_house_state_inference_legacy_snapshots_populate_coarse_and_minimal_only() -> None:
    module = HouseStateInferenceModule(
        min_support=3,
        rich_min_support=2,
        minimal_min_support=3,
    )
    snapshots = [
        _snapshot(
            weekday=1,
            minute_of_day=9 * 60,
            house_state="working",
            room_occupancy={"office": True},
        )
    ] * 3

    await module.analyze(_FakeStore(snapshots))
    diag = module.diagnostics()

    assert diag["tiers"]["rich"]["slot_count"] == 0
    assert diag["tiers"]["coarse"]["slot_count"] == 1
    assert diag["tiers"]["minimal"]["slot_count"] == 1


@pytest.mark.asyncio
async def test_house_state_inference_diagnostics_tracks_tier_hits() -> None:
    module = HouseStateInferenceModule(
        min_support=3,
        rich_min_support=2,
        minimal_min_support=5,
    )
    snapshots = [
        _snapshot(
            weekday=0,
            minute_of_day=10 * 60,
            house_state="working",
            room_occupancy={"kitchen": True},
        )
    ] * 3
    await module.analyze(_FakeStore(snapshots))
    coarse = _house_state_candidate_by_tier(module.generate_candidates(), "coarse")
    module.sync_approval_state({coarse.context_key}, set())

    module.infer(_context(weekday=0, minute_of_day=10 * 60, room_occupancy={"kitchen": True}))
    diag = module.diagnostics()

    assert diag["tiers"]["coarse"]["infer_attempts"] == 1
    assert diag["tiers"]["coarse"]["infer_hits"] == 1
    assert diag["tiers"]["coarse"]["hit_rate"] == 1.0
