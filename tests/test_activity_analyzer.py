"""Tests for ActivityAnalyzer composite activity discovery."""

from __future__ import annotations

from datetime import timedelta, timezone

from custom_components.heima.runtime.analyzers import activity
from custom_components.heima.runtime.analyzers.activity import (
    BOOTSTRAP_MIN_COOCCURRENCES,
    BOOTSTRAP_MIN_DISTINCT_DAYS,
    MAX_PATTERN_SIZE,
    MIN_COOCCURRENCES,
    MIN_DISTINCT_DAYS,
    ActivityAnalyzer,
)
from custom_components.heima.runtime.inference import HouseSnapshot
from custom_components.heima.runtime.proposal_engine import ActivityProposal


class _SnapshotStoreStub:
    def __init__(self, snapshots: list[HouseSnapshot]) -> None:
        self._snapshots = snapshots

    def snapshots(self) -> list[HouseSnapshot]:
        return list(self._snapshots)


def _snapshot(
    *,
    day: int = 1,
    hour: int = 20,
    activities: tuple[str, ...] = ("tv", "relax"),
    rooms: dict[str, bool] | None = None,
) -> HouseSnapshot:
    return HouseSnapshot(
        ts=f"2026-05-{day:02d}T{hour:02d}:00:00+00:00",
        weekday=(day - 1) % 7,
        minute_of_day=hour * 60,
        anyone_home=True,
        named_present=("alice",),
        room_occupancy=rooms if rooms is not None else {"living_room": True},
        detected_activities=activities,
        house_state="relax",
        heating_setpoint=20.0,
        lighting_scenes={},
        security_state="disarmed",
    )


async def test_activity_analyzer_does_not_emit_below_min_cooccurrences() -> None:
    analyzer = ActivityAnalyzer(
        _SnapshotStoreStub([_snapshot(day=day) for day in (1, 2, 3, 1, 2, 3, 1, 2, 3)])
    )

    findings = await analyzer.analyze(event_store=object())

    assert findings == []


async def test_activity_analyzer_does_not_emit_below_min_distinct_days() -> None:
    analyzer = ActivityAnalyzer(_SnapshotStoreStub([_snapshot(day=1) for _ in range(10)]))

    findings = await analyzer.analyze(event_store=object())

    assert findings == []


async def test_activity_analyzer_emits_activity_proposal_above_thresholds() -> None:
    snapshots = [_snapshot(day=day) for day in (1, 2, 3, 1, 2, 3, 1, 2, 3, 1)]
    analyzer = ActivityAnalyzer(_SnapshotStoreStub(snapshots))

    findings = await analyzer.analyze(event_store=object())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "activity"
    assert finding.analyzer_id == "ActivityAnalyzer"
    assert isinstance(finding.payload, ActivityProposal)
    assert finding.payload.activity_name == "relax_tv"
    assert finding.payload.primitive_pattern == frozenset({"relax", "tv"})
    assert finding.payload.occurrence_count == 10
    assert finding.payload.bootstrap is False
    assert finding.payload.representative_ts == [snapshot.ts for snapshot in snapshots[:5]]


async def test_activity_analyzer_bootstrap_mode_uses_lower_thresholds() -> None:
    snapshots = [_snapshot(day=day) for day in (1, 2, 1, 2, 1)]
    analyzer = ActivityAnalyzer(_SnapshotStoreStub(snapshots), bootstrap_mode=True)

    findings = await analyzer.analyze(event_store=object())

    assert len(findings) == 1
    proposal = findings[0].payload
    assert isinstance(proposal, ActivityProposal)
    assert proposal.occurrence_count == BOOTSTRAP_MIN_COOCCURRENCES
    assert proposal.bootstrap is True


async def test_activity_analyzer_default_mode_ignores_bootstrap_sized_sample() -> None:
    snapshots = [_snapshot(day=day) for day in (1, 2, 1, 2, 1)]
    analyzer = ActivityAnalyzer(_SnapshotStoreStub(snapshots))

    findings = await analyzer.analyze(event_store=object())

    assert findings == []


async def test_activity_analyzer_sorts_and_dedupes_primitive_pattern() -> None:
    snapshots = [
        _snapshot(day=day, activities=("TV", "relax", "tv"))
        for day in (1, 2, 3, 1, 2, 3, 1, 2, 3, 1)
    ]
    analyzer = ActivityAnalyzer(_SnapshotStoreStub(snapshots))

    findings = await analyzer.analyze(event_store=object())

    proposal = findings[0].payload
    assert isinstance(proposal, ActivityProposal)
    assert proposal.activity_name == "relax_tv"
    assert proposal.primitive_pattern == frozenset({"relax", "tv"})


async def test_activity_analyzer_context_conditions_include_dominant_room_and_hour() -> None:
    analyzer = ActivityAnalyzer(
        _SnapshotStoreStub(
            [_snapshot(day=day, hour=20, rooms={"living_room": True}) for day in (1, 2, 3)] * 4
        )
    )

    findings = await analyzer.analyze(event_store=object())

    proposal = findings[0].payload
    assert isinstance(proposal, ActivityProposal)
    assert proposal.context_conditions == {"room_id": "living_room", "hour_range": [20, 21]}


async def test_activity_analyzer_omits_context_when_no_dominant_room_or_hour() -> None:
    snapshots = [
        _snapshot(day=1, hour=18, rooms={"living_room": True}),
        _snapshot(day=2, hour=19, rooms={"kitchen": True}),
        _snapshot(day=3, hour=20, rooms={"studio": True}),
        _snapshot(day=1, hour=21, rooms={"bedroom": True}),
        _snapshot(day=2, hour=22, rooms={"living_room": True}),
        _snapshot(day=3, hour=23, rooms={"kitchen": True}),
        _snapshot(day=1, hour=0, rooms={"studio": True}),
        _snapshot(day=2, hour=1, rooms={"bedroom": True}),
        _snapshot(day=3, hour=2, rooms={"garage": True}),
        _snapshot(day=1, hour=3, rooms={"office": True}),
    ]
    analyzer = ActivityAnalyzer(_SnapshotStoreStub(snapshots))

    findings = await analyzer.analyze(event_store=object())

    proposal = findings[0].payload
    assert isinstance(proposal, ActivityProposal)
    assert proposal.context_conditions == {}


async def test_activity_analyzer_uses_injected_snapshot_store() -> None:
    class BrokenEventStore:
        def snapshots(self) -> list[HouseSnapshot]:
            raise AssertionError("event_store should not be used")

    analyzer = ActivityAnalyzer(
        _SnapshotStoreStub([_snapshot(day=day) for day in (1, 2, 3, 1, 2, 3, 1, 2, 3, 1)])
    )

    findings = await analyzer.analyze(event_store=BrokenEventStore())

    assert len(findings) == 1


async def test_activity_analyzer_only_generates_pairs_for_i4() -> None:
    analyzer = ActivityAnalyzer(
        _SnapshotStoreStub(
            [
                _snapshot(day=day, activities=("tv", "relax", "pc"))
                for day in (1, 2, 3, 1, 2, 3, 1, 2, 3, 1)
            ]
        )
    )

    findings = await analyzer.analyze(event_store=object())

    assert findings
    assert all(isinstance(finding.payload, ActivityProposal) for finding in findings)
    assert all(len(finding.payload.primitive_pattern) == 2 for finding in findings)


def test_activity_analyzer_threshold_constants_are_nominal() -> None:
    assert MIN_COOCCURRENCES == 10
    assert MIN_DISTINCT_DAYS == 3
    assert BOOTSTRAP_MIN_COOCCURRENCES == 5
    assert BOOTSTRAP_MIN_DISTINCT_DAYS == 2
    assert MAX_PATTERN_SIZE == 2


def test_activity_day_key_uses_home_assistant_local_date(monkeypatch) -> None:
    monkeypatch.setattr(
        activity.dt_util,
        "as_local",
        lambda value: value.astimezone(timezone(timedelta(hours=2))),
    )

    assert activity._day_key("2026-05-01T22:30:00+00:00") == "2026-05-02"
