"""Tests for LightingPatternAnalyzer (learning system P9)."""

from __future__ import annotations

from custom_components.heima.runtime.analyzers.lighting import LightingPatternAnalyzer
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent

# Two distinct ISO weeks for the multi-week gate
_WEEK1_TS = "2026-03-02T08:00:00+00:00"  # ISO week 10
_WEEK2_TS = "2026-03-09T08:00:00+00:00"  # ISO week 11


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(self, *, event_type=None, since=None, limit=None):  # noqa: ARG002
        return [e for e in self._events if event_type is None or e.event_type == event_type]


def _ctx(weekday: int = 0, minute: int = 1200) -> EventContext:
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


def _lighting(
    *,
    room_id: str = "living",
    action: str = "on",
    weekday: int = 0,
    minute: int = 1200,
    source: str = "user",
    ts: str = _WEEK1_TS,
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=_ctx(weekday=weekday, minute=minute),
        source=source,
        data={"room_id": room_id, "action": action},
    )


def _multi_week_events(
    n_week1: int,
    n_week2: int,
    *,
    room_id: str = "living",
    action: str = "on",
    weekday: int = 0,
    minute: int = 1200,
    source: str = "user",
) -> list[HeimaEvent]:
    """Build events distributed across two ISO weeks."""
    evts = [
        _lighting(room_id=room_id, action=action, weekday=weekday, minute=minute, source=source, ts=_WEEK1_TS)
        for _ in range(n_week1)
    ]
    evts += [
        _lighting(room_id=room_id, action=action, weekday=weekday, minute=minute, source=source, ts=_WEEK2_TS)
        for _ in range(n_week2)
    ]
    return evts


async def test_lighting_analyzer_requires_min_occurrences():
    """Fewer than 5 events → no proposal."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(2, 2)  # 4 total, below _MIN_OCCURRENCES=5
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_requires_min_weeks():
    """5 events in a single ISO week → no proposal (week gate fails)."""
    analyzer = LightingPatternAnalyzer()
    events = [_lighting(ts=_WEEK1_TS) for _ in range(5)]
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_emits_proposal_when_both_gates_pass():
    """5 events across 2 weeks → 1 proposal."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2)
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) == 1
    p = proposals[0]
    assert p.reaction_type == "lighting_schedule"
    assert p.analyzer_id == "LightingPatternAnalyzer"


async def test_lighting_analyzer_proposal_config_fields():
    """suggested_reaction_config has all expected fields."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, room_id="kitchen", action="off", weekday=2, minute=1380)
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) == 1
    cfg = proposals[0].suggested_reaction_config
    assert cfg["reaction_class"] == "LightingScheduleReaction"
    assert cfg["room_id"] == "kitchen"
    assert cfg["action"] == "off"
    assert cfg["weekday"] == 2
    assert cfg["scheduled_min"] == 1380
    assert cfg["window_half_min"] == 10


async def test_lighting_analyzer_confidence_tight_schedule():
    """Tight IQR → high confidence."""
    analyzer = LightingPatternAnalyzer()
    tight = _multi_week_events(3, 2, minute=1200)
    proposals = await analyzer.analyze(_StoreStub(tight))  # type: ignore[arg-type]
    assert proposals[0].confidence > 0.9


async def test_lighting_analyzer_confidence_floor():
    """Very spread schedule → confidence floored at 0.3."""
    analyzer = LightingPatternAnalyzer()
    # Create 5 events spread widely: IQR > 120 → max(0.3, negative) = 0.3
    minutes = [600, 720, 840, 960, 1080]
    evts = []
    for i, m in enumerate(minutes):
        ts = _WEEK1_TS if i < 3 else _WEEK2_TS
        evts.append(_lighting(minute=m, ts=ts))
    proposals = await analyzer.analyze(_StoreStub(evts))  # type: ignore[arg-type]
    assert proposals[0].confidence == 0.3


async def test_lighting_analyzer_confidence_tight_vs_spread():
    """Tighter schedule → higher confidence than spread."""
    analyzer = LightingPatternAnalyzer()

    tight_evts = _multi_week_events(3, 2, minute=1200)
    tight_proposals = await analyzer.analyze(_StoreStub(tight_evts))  # type: ignore[arg-type]

    # Spread over 2+ hours between p25 and p75
    spread_minutes = [1080, 1140, 1200, 1260, 1320]  # IQR = 180 min → confidence 0.3
    spread_evts = []
    for i, m in enumerate(spread_minutes):
        ts = _WEEK1_TS if i < 3 else _WEEK2_TS
        spread_evts.append(_lighting(minute=m, ts=ts))
    spread_proposals = await analyzer.analyze(_StoreStub(spread_evts))  # type: ignore[arg-type]

    assert tight_proposals and spread_proposals
    assert tight_proposals[0].confidence > spread_proposals[0].confidence


async def test_lighting_analyzer_ignores_non_user_source():
    """Events not from 'user' source are excluded."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, source="heima")
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_ignores_invalid_action():
    """Events with action not in ('on', 'off') are skipped."""
    analyzer = LightingPatternAnalyzer()
    evts = []
    for i in range(5):
        ts = _WEEK1_TS if i < 3 else _WEEK2_TS
        evts.append(HeimaEvent(
            ts=ts,
            event_type="lighting",
            context=_ctx(),
            source="user",
            data={"room_id": "living", "action": "dim"},
        ))
    proposals = await analyzer.analyze(_StoreStub(evts))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_separate_proposals_per_key():
    """Different (room_id, action, weekday) keys generate separate proposals."""
    analyzer = LightingPatternAnalyzer()
    living_on = _multi_week_events(3, 2, room_id="living", action="on", weekday=0)
    kitchen_off = _multi_week_events(3, 2, room_id="kitchen", action="off", weekday=1)
    proposals = await analyzer.analyze(_StoreStub(living_on + kitchen_off))  # type: ignore[arg-type]
    assert len(proposals) == 2
    keys = {(p.suggested_reaction_config["room_id"], p.suggested_reaction_config["action"], p.suggested_reaction_config["weekday"]) for p in proposals}
    assert keys == {("living", "on", 0), ("kitchen", "off", 1)}


async def test_lighting_analyzer_empty_store():
    """Empty event store → no proposals."""
    analyzer = LightingPatternAnalyzer()
    proposals = await analyzer.analyze(_StoreStub([]))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_description_contains_room_and_action():
    """Proposal description mentions room and action."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, room_id="bedroom", action="off", weekday=6)
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert "bedroom" in proposals[0].description
    assert "off" in proposals[0].description
    assert "Sunday" in proposals[0].description
