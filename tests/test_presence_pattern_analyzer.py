"""Tests for PresencePatternAnalyzer (learning system P2)."""

from __future__ import annotations

from custom_components.heima.runtime.analyzers.presence import PresencePatternAnalyzer
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(self, *, event_type=None, since=None, limit=None):  # noqa: ARG002
        return [e for e in self._events if event_type is None or e.event_type == event_type]


async def _analyze_proposals(analyzer, store):  # noqa: ANN001
    findings = await analyzer.analyze(store)  # type: ignore[arg-type]
    return [finding.payload for finding in findings]


def _ctx(weekday: int = 0, minute: int = 480) -> EventContext:
    return EventContext(
        weekday=weekday,
        minute_of_day=minute,
        month=3,
        house_state="home",
        occupants_count=1,
        occupied_rooms=(),
        outdoor_lux=None,
        outdoor_temp=None,
        weather_condition=None,
        signals={},
    )


# ISO weeks for multi-week test data: week 11 (2026-03-10) and week 12 (2026-03-17)
_WEEK_TIMESTAMPS = [
    "2026-03-10T08:00:00+00:00",  # week 11
    "2026-03-17T08:00:00+00:00",  # week 12
    "2026-03-24T08:00:00+00:00",  # week 13
]


def _arrive(minute_of_day: int, weekday: int = 0, ts_index: int = 0) -> HeimaEvent:
    return HeimaEvent(
        ts=_WEEK_TIMESTAMPS[ts_index % len(_WEEK_TIMESTAMPS)],
        event_type="presence",
        context=_ctx(weekday=weekday, minute=minute_of_day),
        source=None,
        data={"transition": "arrive"},
    )


def _arrive_multi_week(minutes: list[int], weekday: int = 0) -> list[HeimaEvent]:
    """Create events spread across multiple weeks (one per week, cycling)."""
    return [_arrive(m, weekday=weekday, ts_index=i) for i, m in enumerate(minutes)]


async def test_presence_analyzer_requires_min_arrivals():
    analyzer = PresencePatternAnalyzer(min_arrivals=5)
    proposals = await _analyze_proposals(
        analyzer, _StoreStub([_arrive(480), _arrive(490), _arrive(500), _arrive(510)])
    )  # type: ignore[arg-type]
    assert proposals == []


async def test_presence_analyzer_requires_min_weeks():
    """All arrivals in same week: filtered out by min_weeks check."""
    analyzer = PresencePatternAnalyzer(min_arrivals=5)
    samples = [_arrive(470 + i, ts_index=0) for i in range(5)]  # all same week
    proposals = await _analyze_proposals(analyzer, _StoreStub(samples))  # type: ignore[arg-type]
    assert proposals == []


async def test_presence_analyzer_emits_proposal():
    analyzer = PresencePatternAnalyzer(min_arrivals=5)
    samples = _arrive_multi_week([470, 475, 480, 485, 490])
    proposals = await _analyze_proposals(analyzer, _StoreStub(samples))  # type: ignore[arg-type]
    assert len(proposals) == 1
    p = proposals[0]
    assert p.reaction_type == "presence_preheat"
    assert p.suggested_reaction_config["weekday"] == 0
    assert p.suggested_reaction_config["median_arrival_min"] == 480
    diagnostics = p.suggested_reaction_config["learning_diagnostics"]
    assert diagnostics["pattern_id"] == "presence_preheat"
    assert diagnostics["analyzer_id"] == "PresencePatternAnalyzer"
    assert diagnostics["reaction_type"] == "presence_preheat"
    assert diagnostics["plugin_family"] == "presence"
    assert diagnostics["observations_count"] == 5
    assert diagnostics["median_arrival_min"] == 480
    assert diagnostics["iqr_min"] >= 0


async def test_presence_analyzer_confidence_tight_vs_spread():
    analyzer = PresencePatternAnalyzer(min_arrivals=5)
    tight = await _analyze_proposals(
        analyzer, _StoreStub(_arrive_multi_week([480, 481, 482, 483, 484]))
    )  # type: ignore[arg-type]
    spread = await _analyze_proposals(
        analyzer, _StoreStub(_arrive_multi_week([360, 420, 480, 540, 600]))
    )  # type: ignore[arg-type]
    assert tight and spread
    assert tight[0].confidence > spread[0].confidence


async def test_presence_analyzer_per_weekday():
    analyzer = PresencePatternAnalyzer(min_arrivals=5)
    monday = _arrive_multi_week([480, 482, 484, 486, 488], weekday=0)
    tuesday = [_arrive(500, weekday=1), _arrive(502, weekday=1)]
    proposals = await _analyze_proposals(analyzer, _StoreStub(monday + tuesday))  # type: ignore[arg-type]
    assert len(proposals) == 1
    assert proposals[0].suggested_reaction_config["weekday"] == 0
