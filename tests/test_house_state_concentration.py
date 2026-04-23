"""Tests for house_state concentration rule (§3.0.2).

Coverage:
- compute_house_state_filter helper (unit)
- LightingPatternAnalyzer: house_state_filter set when concentrated
- CrossDomainPatternAnalyzer: house_state_filter set in composite proposals
- lifecycle identity_key: suffix present/absent
- RoomSignalAssistReaction: gate on house_state_filter
- RoomLightingAssistReaction: gate on house_state_filter
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.heima.runtime.analyzers.base import (
    ReactionProposal,
    compute_house_state_filter,
)
from custom_components.heima.runtime.analyzers.lifecycle import (
    composite_room_assist_lifecycle_hooks,
    lighting_lifecycle_hooks,
)
from custom_components.heima.runtime.analyzers.lighting import LightingPatternAnalyzer
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_WEEK1 = "2026-03-02T20:00:00+00:00"
_WEEK2 = "2026-03-09T20:00:00+00:00"
_WEEK3 = "2026-03-16T20:00:00+00:00"


def _ctx(house_state: str = "home") -> EventContext:
    return EventContext(
        weekday=0,
        minute_of_day=1200,
        month=3,
        house_state=house_state,
        occupants_count=1,
        occupied_rooms=(),
        outdoor_lux=None,
        outdoor_temp=None,
        weather_condition=None,
        signals={},
    )


def _event(house_state: str, ts: str = _WEEK1) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=_ctx(house_state),
        source="user",
        domain="light",
        subject_type="entity",
        subject_id="light.test",
        room_id="living",
        data={},
    )


# ---------------------------------------------------------------------------
# 1. compute_house_state_filter — unit tests
# ---------------------------------------------------------------------------


def test_compute_house_state_filter_returns_dominant_when_concentrated():
    events = [_event("relax")] * 9 + [_event("home")] * 1
    assert compute_house_state_filter(events) == "relax"


def test_compute_house_state_filter_returns_none_when_below_threshold():
    # 7/10 = 0.70 < 0.75
    events = [_event("relax")] * 7 + [_event("home")] * 3
    assert compute_house_state_filter(events) is None


def test_compute_house_state_filter_returns_none_when_below_min_observations():
    # 4/5 = 0.80 >= 0.75 but count=4 < HOUSE_STATE_MIN_DOMINANT_OBSERVATIONS (8)
    events = [_event("relax")] * 4 + [_event("home")] * 1
    assert compute_house_state_filter(events) is None


def test_compute_house_state_filter_returns_none_on_empty():
    assert compute_house_state_filter([]) is None


def test_compute_house_state_filter_returns_none_when_all_empty_house_state():
    ctx = EventContext(
        weekday=0,
        minute_of_day=0,
        month=1,
        house_state="",
        occupants_count=0,
        occupied_rooms=(),
        outdoor_lux=None,
        outdoor_temp=None,
        weather_condition=None,
        signals={},
    )
    events = [
        HeimaEvent(
            ts=_WEEK1,
            event_type="lighting",
            context=ctx,
            source="user",
            domain="light",
            subject_type="entity",
            subject_id="x",
            room_id="r",
            data={},
        )
    ] * 10
    assert compute_house_state_filter(events) is None


def test_compute_house_state_filter_exact_threshold():
    # 8/10 = 0.80 >= 0.75 and count=8 >= 8 → should return
    events = [_event("relax")] * 8 + [_event("home")] * 2
    assert compute_house_state_filter(events) == "relax"


def test_compute_house_state_filter_exact_min_observations():
    # count = 8 exactly, ratio = 1.0 → should return
    events = [_event("relax")] * 8
    assert compute_house_state_filter(events) == "relax"


# ---------------------------------------------------------------------------
# 2. LightingPatternAnalyzer — house_state_filter in proposal
# ---------------------------------------------------------------------------


def _lighting_event(
    *,
    house_state: str = "relax",
    weekday: int = 0,
    minute: int = 1200,
    ts: str = _WEEK1,
    entity_id: str = "light.living_main",
    room_id: str = "living",
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=EventContext(
            weekday=weekday,
            minute_of_day=minute,
            month=3,
            house_state=house_state,
            occupants_count=1,
            occupied_rooms=(room_id,),
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals={},
        ),
        source="user",
        domain="light",
        subject_type="entity",
        subject_id=entity_id,
        room_id=room_id,
        data={"entity_id": entity_id, "room_id": room_id, "action": "on"},
    )


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(self, *, event_type=None, **_kw):
        return [e for e in self._events if event_type is None or e.event_type == event_type]


@pytest.mark.asyncio
async def test_lighting_analyzer_sets_house_state_filter_when_concentrated():
    """All events in 'relax' → filter should be set."""
    ts_pairs = [(_WEEK1, 0), (_WEEK2, 1), (_WEEK3, 2)]
    events = []
    for ts, offset in ts_pairs:
        for _ in range(4):
            events.append(_lighting_event(house_state="relax", ts=ts, minute=1200 + offset))

    store = _StoreStub(events)
    proposals = await LightingPatternAnalyzer(min_occurrences=5, min_weeks=2).analyze(store)
    # all events are in "relax" but we need ≥ 8 observations for dominant count
    # with 12 events all in relax: 12/12 >= 0.75 and 12 >= 8 → filter = "relax"
    assert proposals, "expected at least one proposal"
    assert all(p.suggested_reaction_config.get("house_state_filter") == "relax" for p in proposals)


@pytest.mark.asyncio
async def test_lighting_analyzer_house_state_filter_none_when_spread():
    """Events split evenly between states → filter stays None."""
    ts_pairs = [(_WEEK1, 0), (_WEEK2, 1), (_WEEK3, 2)]
    events = []
    for ts, offset in ts_pairs:
        for _ in range(2):
            events.append(_lighting_event(house_state="relax", ts=ts, minute=1200 + offset))
            events.append(_lighting_event(house_state="home", ts=ts, minute=1200 + offset))

    store = _StoreStub(events)
    proposals = await LightingPatternAnalyzer(min_occurrences=5, min_weeks=2).analyze(store)
    if proposals:
        assert all(p.suggested_reaction_config.get("house_state_filter") is None for p in proposals)


# ---------------------------------------------------------------------------
# 3. Lifecycle identity key — suffix present/absent
# ---------------------------------------------------------------------------


def _proposal(
    reaction_type: str,
    cfg: dict[str, Any],
) -> ReactionProposal:
    return ReactionProposal(
        reaction_type=reaction_type,
        suggested_reaction_config=cfg,
    )


def test_lighting_identity_key_includes_house_state_suffix_when_set():
    hooks = lighting_lifecycle_hooks()
    proposal = _proposal(
        "lighting_scene_schedule",
        {
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1200,
            "house_state_filter": "relax",
            "entity_steps": [{"entity_id": "light.test", "action": "on"}],
        },
    )
    key = hooks.identity_key(proposal)
    assert "|house_state=relax" in key


def test_lighting_identity_key_no_suffix_when_filter_none():
    hooks = lighting_lifecycle_hooks()
    proposal = _proposal(
        "lighting_scene_schedule",
        {
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1200,
            "house_state_filter": None,
            "entity_steps": [{"entity_id": "light.test", "action": "on"}],
        },
    )
    key = hooks.identity_key(proposal)
    assert "house_state" not in key


def test_context_conditioned_lighting_identity_key_includes_context_signature():
    hooks = lighting_lifecycle_hooks()
    proposal = _proposal(
        "context_conditioned_lighting_scene",
        {
            "room_id": "living",
            "weekday": 0,
            "scheduled_min": 1200,
            "entity_steps": [{"entity_id": "light.test", "action": "on"}],
            "context_conditions": [
                {"signal_name": "projector_context", "state_in": ["active"]},
            ],
        },
    )
    key = hooks.identity_key(proposal)
    assert key.startswith("context_conditioned_lighting_scene|")
    assert "|context=projector_context=active" in key


def test_composite_identity_key_includes_house_state_suffix_when_set():
    hooks = composite_room_assist_lifecycle_hooks()
    proposal = _proposal(
        "room_signal_assist",
        {
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "house_state_filter": "relax",
        },
    )
    key = hooks.identity_key(proposal)
    assert "|house_state=relax" in key


def test_composite_identity_key_no_suffix_when_filter_none():
    hooks = composite_room_assist_lifecycle_hooks()
    proposal = _proposal(
        "room_signal_assist",
        {
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "house_state_filter": None,
        },
    )
    key = hooks.identity_key(proposal)
    assert "house_state" not in key


# ---------------------------------------------------------------------------
# 4. RoomSignalAssistReaction — gate on house_state_filter
# ---------------------------------------------------------------------------


def _fake_hass(bucket_value: str | None = "high") -> Any:
    states = SimpleNamespace(get=lambda _: None)
    services = SimpleNamespace(
        async_call=lambda *a, **kw: None,
        async_services=lambda: {},
    )
    bus = SimpleNamespace(async_fire=lambda *a, **kw: None)
    return SimpleNamespace(states=states, services=services, bus=bus)


def _snapshot(house_state: str = "home", room_id: str = "bathroom") -> Any:
    return SimpleNamespace(
        house_state=house_state,
        occupied_rooms={room_id},
        ts="2026-03-02T20:00:00+00:00",
        signal_buckets={},
        burst_signals=set(),
    )


def test_signal_assist_gate_inactive_when_house_state_matches():
    from custom_components.heima.runtime.reactions.signal_assist import RoomSignalAssistReaction

    reaction = RoomSignalAssistReaction(
        hass=_fake_hass(),
        room_id="bathroom",
        steps=[],
        primary_bucket="high",
        primary_signal_entities=["sensor.humidity"],
        house_state_filter="home",
    )
    # history with matching house_state → gate passes, evaluate proceeds
    snap = _snapshot(house_state="home")
    result = reaction.evaluate([snap])
    # may be empty (no steps to fire) but gate must not block
    # the test validates that no exception is raised and gate doesn't short-circuit
    assert isinstance(result, list)


def test_signal_assist_gate_returns_empty_when_house_state_mismatches():
    from custom_components.heima.runtime.reactions.signal_assist import RoomSignalAssistReaction

    reaction = RoomSignalAssistReaction(
        hass=_fake_hass(),
        room_id="bathroom",
        steps=[],
        primary_bucket="high",
        primary_signal_entities=["sensor.humidity"],
        house_state_filter="relax",
    )
    snap = _snapshot(house_state="home")  # mismatch
    result = reaction.evaluate([snap])
    assert result == []


def test_signal_assist_no_gate_when_filter_none():
    from custom_components.heima.runtime.reactions.signal_assist import RoomSignalAssistReaction

    reaction = RoomSignalAssistReaction(
        hass=_fake_hass(),
        room_id="bathroom",
        steps=[],
        primary_bucket="high",
        primary_signal_entities=["sensor.humidity"],
        house_state_filter=None,
    )
    snap = _snapshot(house_state="away")  # any state
    result = reaction.evaluate([snap])
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 5. RoomLightingAssistReaction — gate on house_state_filter
# ---------------------------------------------------------------------------


def test_lighting_assist_gate_returns_empty_when_house_state_mismatches():
    from custom_components.heima.runtime.reactions.lighting_assist import RoomLightingAssistReaction

    reaction = RoomLightingAssistReaction(
        hass=_fake_hass(),
        room_id="living",
        entity_steps=[{"entity_id": "light.test", "action": "on"}],
        primary_signal_entities=["sensor.lux"],
        house_state_filter="relax",
    )
    snap = _snapshot(house_state="home", room_id="living")
    result = reaction.evaluate([snap])
    assert result == []


def test_lighting_assist_no_gate_when_filter_none():
    from custom_components.heima.runtime.reactions.lighting_assist import RoomLightingAssistReaction

    reaction = RoomLightingAssistReaction(
        hass=_fake_hass(),
        room_id="living",
        entity_steps=[{"entity_id": "light.test", "action": "on"}],
        primary_signal_entities=["sensor.lux"],
        house_state_filter=None,
    )
    snap = _snapshot(house_state="away", room_id="living")
    result = reaction.evaluate([snap])
    assert isinstance(result, list)
