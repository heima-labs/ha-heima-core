"""Tests for PresencePatternAnalyzer (learning system P2)."""

from __future__ import annotations

from custom_components.heima.runtime.analyzers.presence import PresencePatternAnalyzer
from custom_components.heima.runtime.event_store import PresenceEvent


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(self, *, event_type=None, since=None, limit=None):  # noqa: ARG002
        return [e for e in self._events if event_type is None or e.event_type == event_type]


def _arrive(minute_of_day: int, weekday: int = 0) -> PresenceEvent:
    return PresenceEvent(
        ts="2026-03-10T08:00:00+00:00",
        event_type="presence",
        transition="arrive",
        weekday=weekday,
        minute_of_day=minute_of_day,
    )


async def test_presence_analyzer_requires_min_arrivals():
    analyzer = PresencePatternAnalyzer(min_arrivals=5)
    proposals = await analyzer.analyze(_StoreStub([_arrive(480), _arrive(490), _arrive(500), _arrive(510)]))  # type: ignore[arg-type]
    assert proposals == []


async def test_presence_analyzer_emits_proposal():
    analyzer = PresencePatternAnalyzer(min_arrivals=5)
    samples = [_arrive(470), _arrive(475), _arrive(480), _arrive(485), _arrive(490)]
    proposals = await analyzer.analyze(_StoreStub(samples))  # type: ignore[arg-type]
    assert len(proposals) == 1
    p = proposals[0]
    assert p.reaction_type == "presence_preheat"
    assert p.suggested_reaction_config["weekday"] == 0
    assert p.suggested_reaction_config["median_arrival_min"] == 480


async def test_presence_analyzer_confidence_tight_vs_spread():
    analyzer = PresencePatternAnalyzer(min_arrivals=5)
    tight = await analyzer.analyze(_StoreStub([_arrive(480), _arrive(481), _arrive(482), _arrive(483), _arrive(484)]))  # type: ignore[arg-type]
    spread = await analyzer.analyze(_StoreStub([_arrive(360), _arrive(420), _arrive(480), _arrive(540), _arrive(600)]))  # type: ignore[arg-type]
    assert tight and spread
    assert tight[0].confidence > spread[0].confidence


async def test_presence_analyzer_per_weekday():
    analyzer = PresencePatternAnalyzer(min_arrivals=5)
    monday = [_arrive(480, weekday=0), _arrive(482, weekday=0), _arrive(484, weekday=0), _arrive(486, weekday=0), _arrive(488, weekday=0)]
    tuesday = [_arrive(500, weekday=1), _arrive(502, weekday=1)]
    proposals = await analyzer.analyze(_StoreStub(monday + tuesday))  # type: ignore[arg-type]
    assert len(proposals) == 1
    assert proposals[0].suggested_reaction_config["weekday"] == 0

