"""Tests for HeatingPatternAnalyzer (learning system P3)."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC

from custom_components.heima.runtime.analyzers.heating import HeatingPatternAnalyzer
from custom_components.heima.runtime.event_store import HeatingEvent


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(self, *, event_type=None, since=None, limit=None):  # noqa: ARG002
        return [e for e in self._events if event_type is None or e.event_type == event_type]


def _heating_event(
    *,
    house_state: str = "home",
    temperature_set: float = 21.5,
    source: str = "heima",
    ts: str = "2026-03-10T08:00:00+00:00",
    env: dict | None = None,
) -> HeatingEvent:
    return HeatingEvent(
        ts=ts,
        event_type="heating",
        house_state=house_state,
        temperature_set=temperature_set,
        source=source,  # type: ignore[arg-type]
        env=env or {},
    )


async def test_heating_analyzer_requires_min_events():
    analyzer = HeatingPatternAnalyzer()
    # 9 events for "home" — below the minimum of 10
    events = [_heating_event() for _ in range(9)]
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_heating_analyzer_pattern_b_emits():
    analyzer = HeatingPatternAnalyzer()
    events = [_heating_event(temperature_set=21.5) for _ in range(10)]
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) >= 1
    assert any(p.reaction_type == "heating_preference" for p in proposals)


async def test_heating_analyzer_confidence_consistent():
    analyzer = HeatingPatternAnalyzer()
    events = [_heating_event(temperature_set=21.5) for _ in range(10)]
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    pref_proposals = [p for p in proposals if p.reaction_type == "heating_preference"]
    assert pref_proposals
    assert pref_proposals[0].confidence > 0.9


async def test_heating_analyzer_confidence_spread():
    analyzer = HeatingPatternAnalyzer()
    # Spread of 6°C (18 to 24) → confidence should be low
    temps = [18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 20.5, 21.5, 22.5]
    events = [_heating_event(temperature_set=t) for t in temps]
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    pref_proposals = [p for p in proposals if p.reaction_type == "heating_preference"]
    assert pref_proposals
    assert pref_proposals[0].confidence < 0.5


async def test_heating_analyzer_per_house_state():
    analyzer = HeatingPatternAnalyzer()
    # 10 "home" events (qualifies) + 4 "away" events (below minimum)
    home_events = [_heating_event(house_state="home", temperature_set=21.5) for _ in range(10)]
    away_events = [_heating_event(house_state="away", temperature_set=18.0) for _ in range(4)]
    proposals = await analyzer.analyze(_StoreStub(home_events + away_events))  # type: ignore[arg-type]
    pref_proposals = [p for p in proposals if p.reaction_type == "heating_preference"]
    assert len(pref_proposals) == 1
    assert pref_proposals[0].suggested_reaction_config["house_state"] == "home"


async def test_heating_analyzer_empty_store():
    analyzer = HeatingPatternAnalyzer()
    proposals = await analyzer.analyze(_StoreStub([]))  # type: ignore[arg-type]
    assert proposals == []


async def test_heating_analyzer_eco_pattern():
    analyzer = HeatingPatternAnalyzer()
    # Build 3 eco sessions: away → home (user) with >120 min gap
    base = datetime(2026, 3, 1, 8, 0, 0, tzinfo=UTC)
    events = []
    for i in range(3):
        # away event
        away_ts = (base + timedelta(days=i * 2)).isoformat()
        # return home event 3 hours later — qualifies as eco session
        home_ts = (base + timedelta(days=i * 2, hours=3)).isoformat()
        events.append(_heating_event(house_state="away", temperature_set=16.0, ts=away_ts, source="heima"))
        events.append(_heating_event(house_state="home", temperature_set=21.0, ts=home_ts, source="user"))

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    eco_proposals = [p for p in proposals if p.reaction_type == "heating_eco"]
    assert eco_proposals
    assert eco_proposals[0].suggested_reaction_config["eco_sessions_observed"] >= 3


async def test_heating_analyzer_env_correlation():
    analyzer = HeatingPatternAnalyzer()
    # 10 events with low outdoor temp → higher setpoint
    # 10 events with high outdoor temp → lower setpoint
    events = []
    for _ in range(10):
        events.append(_heating_event(
            house_state="home",
            temperature_set=22.0,
            env={"sensor.outdoor_temp": "5"},
        ))
    for _ in range(10):
        events.append(_heating_event(
            house_state="home",
            temperature_set=19.0,
            env={"sensor.outdoor_temp": "20"},
        ))

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    pref_proposals = [p for p in proposals if p.reaction_type == "heating_preference"]
    assert pref_proposals
    env_corr = pref_proposals[0].suggested_reaction_config.get("env_correlations", {})
    assert "sensor.outdoor_temp" in env_corr
    corr = env_corr["sensor.outdoor_temp"]
    assert corr["delta"] > 0
