"""End-to-end tests: EventStore → Analyzer → ProposalEngine → Reaction → ApplySteps → execute."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heima.runtime.analyzers.lighting import LightingPatternAnalyzer
from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.proposal_engine import ProposalEngine
from custom_components.heima.runtime.reactions.lighting_schedule import LightingScheduleReaction
from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent
from custom_components.heima.runtime.snapshot import DecisionSnapshot

# ---------------------------------------------------------------------------
# Fixtures / stubs
# ---------------------------------------------------------------------------

_WEEK1_TS = "2026-03-02T08:00:00+00:00"  # ISO week 10
_WEEK2_TS = "2026-03-09T08:00:00+00:00"  # ISO week 11


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


def _lighting_event(
    *,
    entity_id: str,
    room_id: str,
    action: str = "on",
    weekday: int = 0,
    minute: int = 1200,
    brightness: int | None = 128,
    color_temp_kelvin: int | None = 3000,
    ts: str = _WEEK1_TS,
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=_ctx(weekday=weekday, minute=minute),
        source="user",
        data={
            "entity_id": entity_id,
            "room_id": room_id,
            "action": action,
            "brightness": brightness,
            "color_temp_kelvin": color_temp_kelvin,
            "rgb_color": None,
        },
    )


def _seed_events(
    *,
    entity_id: str = "light.living_main",
    room_id: str = "living",
    action: str = "on",
    weekday: int = 0,
    minute: int = 1200,
    brightness: int | None = 128,
    color_temp_kelvin: int | None = 3000,
    n_week1: int = 3,
    n_week2: int = 2,
) -> list[HeimaEvent]:
    evts = [
        _lighting_event(entity_id=entity_id, room_id=room_id, action=action,
                        weekday=weekday, minute=minute, brightness=brightness,
                        color_temp_kelvin=color_temp_kelvin, ts=_WEEK1_TS)
        for _ in range(n_week1)
    ]
    evts += [
        _lighting_event(entity_id=entity_id, room_id=room_id, action=action,
                        weekday=weekday, minute=minute, brightness=brightness,
                        color_temp_kelvin=color_temp_kelvin, ts=_WEEK2_TS)
        for _ in range(n_week2)
    ]
    return evts


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(self, *, event_type=None, since=None, limit=None):
        return [e for e in self._events if event_type is None or e.event_type == event_type]


class _FakeHAStore:
    """Stub for homeassistant.helpers.storage.Store."""

    def __init__(self, hass, version, key):
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data


def _snapshot(house_state: str = "home") -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="snap1",
        ts="2026-03-17T20:00:00+00:00",
        house_state=house_state,
        anyone_home=True,
        people_count=1,
        occupied_rooms=["living"],
        lighting_intents={},
        security_state="disarmed",
    )


# ---------------------------------------------------------------------------
# 1. Store → Analyzer
# ---------------------------------------------------------------------------

async def test_e2e_analyzer_produces_proposal_with_entity_steps():
    """Seeding store with ≥5 events across ≥2 weeks → proposal with entity_steps."""
    store = _StoreStub(_seed_events())
    analyzer = LightingPatternAnalyzer()
    proposals = await analyzer.analyze(store)  # type: ignore[arg-type]
    assert len(proposals) == 1
    p = proposals[0]
    assert p.reaction_type == "lighting_scene_schedule"
    cfg = p.suggested_reaction_config
    assert cfg["reaction_class"] == "LightingScheduleReaction"
    assert len(cfg["entity_steps"]) == 1
    step = cfg["entity_steps"][0]
    assert step["entity_id"] == "light.living_main"
    assert step["action"] == "on"
    assert step["brightness"] == 128
    assert step["color_temp_kelvin"] == 3000


async def test_e2e_analyzer_scene_grouping():
    """Two entities in same room within 15 min → 1 proposal, 2 entity_steps."""
    main = _seed_events(entity_id="light.living_main", room_id="living", minute=1200)
    spot = _seed_events(entity_id="light.living_spot", room_id="living", minute=1205)
    store = _StoreStub(main + spot)
    analyzer = LightingPatternAnalyzer()
    proposals = await analyzer.analyze(store)  # type: ignore[arg-type]
    assert len(proposals) == 1
    assert len(proposals[0].suggested_reaction_config["entity_steps"]) == 2


# ---------------------------------------------------------------------------
# 2. Analyzer → ProposalEngine: run, dedup, confidence update
# ---------------------------------------------------------------------------

async def test_e2e_proposal_engine_run(monkeypatch):
    """ProposalEngine stores proposal and deduplicates on re-run."""
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeHAStore)
    store = _StoreStub(_seed_events())
    analyzer = LightingPatternAnalyzer()
    engine = ProposalEngine(object(), store, sensor_writer=None)  # type: ignore[arg-type]
    engine.register_analyzer(analyzer)
    await engine.async_initialize()

    await engine.async_run()
    pending = engine.pending_proposals()
    assert len(pending) == 1
    proposal_id = pending[0].proposal_id

    # Second run — same fingerprint → dedup, count stays at 1
    await engine.async_run()
    pending2 = engine.pending_proposals()
    assert len(pending2) == 1
    assert pending2[0].proposal_id == proposal_id


async def test_e2e_proposal_engine_accepted_not_overwritten(monkeypatch):
    """Accepted proposal is preserved even after re-run."""
    monkeypatch.setattr("custom_components.heima.runtime.proposal_engine.Store", _FakeHAStore)
    store = _StoreStub(_seed_events())
    analyzer = LightingPatternAnalyzer()
    engine = ProposalEngine(object(), store, sensor_writer=None)  # type: ignore[arg-type]
    engine.register_analyzer(analyzer)
    await engine.async_initialize()
    await engine.async_run()

    proposal_id = engine.pending_proposals()[0].proposal_id
    accepted = await engine.async_accept_proposal(proposal_id)
    assert accepted

    await engine.async_run()
    # Still accepted, not reset to pending
    all_proposals = engine._proposals
    match = next(p for p in all_proposals if p.proposal_id == proposal_id)
    assert match.status == "accepted"


# ---------------------------------------------------------------------------
# 3. Reaction instantiation from accepted proposal config
# ---------------------------------------------------------------------------

def _make_reaction(
    *,
    room_id: str = "living",
    weekday: int = 0,
    scheduled_min: int = 1200,
    entity_steps: list | None = None,
    reaction_id: str = "test-reaction",
) -> LightingScheduleReaction:
    if entity_steps is None:
        entity_steps = [
            {"entity_id": "light.living_main", "action": "on",
             "brightness": 128, "color_temp_kelvin": 3000, "rgb_color": None},
            {"entity_id": "light.living_spot", "action": "off",
             "brightness": None, "color_temp_kelvin": None, "rgb_color": None},
        ]
    return LightingScheduleReaction(
        room_id=room_id,
        weekday=weekday,
        scheduled_min=scheduled_min,
        window_half_min=10,
        entity_steps=entity_steps,
        reaction_id=reaction_id,
    )


def test_e2e_reaction_instantiation_from_config():
    """LightingScheduleReaction can be built from suggested_reaction_config."""
    cfg = {
        "reaction_class": "LightingScheduleReaction",
        "room_id": "living",
        "weekday": 1,
        "scheduled_min": 1320,
        "window_half_min": 10,
        "house_state_filter": None,
        "entity_steps": [
            {"entity_id": "light.kitchen_spot", "action": "on",
             "brightness": 200, "color_temp_kelvin": 2700, "rgb_color": None},
        ],
    }
    reaction = LightingScheduleReaction(
        room_id=cfg["room_id"],
        weekday=cfg["weekday"],
        scheduled_min=cfg["scheduled_min"],
        window_half_min=cfg["window_half_min"],
        house_state_filter=cfg["house_state_filter"],
        entity_steps=cfg["entity_steps"],
    )
    assert reaction.reaction_id  # non-empty default
    diag = reaction.diagnostics()
    assert diag["room_id"] == "living"
    assert diag["weekday"] == 1
    assert diag["scheduled_min"] == 1320
    assert diag["entity_steps"] == 1


# ---------------------------------------------------------------------------
# 4. evaluate() → ApplySteps + debounce
# ---------------------------------------------------------------------------

def _make_hass_mock_for_weekday(weekday: int, hour: int, minute: int):
    """Patch dt_util.now() to return a specific weekday/time."""
    from datetime import datetime, timezone
    from unittest.mock import patch
    dt = datetime(2026, 3, 2 + weekday, hour, minute, 0, tzinfo=timezone.utc)
    return patch("custom_components.heima.runtime.reactions.lighting_schedule.dt_util.now", return_value=dt)


def test_e2e_reaction_evaluate_returns_steps_in_window():
    """evaluate() at correct weekday+time returns ApplySteps for each entity_step."""
    reaction = _make_reaction(weekday=0, scheduled_min=1200)
    history = [_snapshot("home")]
    # weekday=0 (Monday), 20:00 → minute=1200, inside window [1190, 1210]
    with _make_hass_mock_for_weekday(weekday=0, hour=20, minute=0):
        steps = reaction.evaluate(history)
    assert len(steps) == 2
    turn_on = next(s for s in steps if s.action == "light.turn_on")
    assert turn_on.params["entity_id"] == "light.living_main"
    assert turn_on.params["brightness"] == 128
    assert turn_on.params["color_temp_kelvin"] == 3000
    turn_off = next(s for s in steps if s.action == "light.turn_off")
    assert turn_off.params["entity_id"] == "light.living_spot"


def test_e2e_reaction_evaluate_outside_window_returns_empty():
    """evaluate() outside the time window → no steps."""
    reaction = _make_reaction(weekday=0, scheduled_min=1200)
    history = [_snapshot("home")]
    # minute=1230 is outside [1190, 1210]
    with _make_hass_mock_for_weekday(weekday=0, hour=20, minute=30):
        steps = reaction.evaluate(history)
    assert steps == []


def test_e2e_reaction_evaluate_wrong_weekday_returns_empty():
    """evaluate() on wrong weekday → no steps."""
    reaction = _make_reaction(weekday=0, scheduled_min=1200)  # Monday
    history = [_snapshot("home")]
    # Tuesday = weekday 1
    with _make_hass_mock_for_weekday(weekday=1, hour=20, minute=0):
        steps = reaction.evaluate(history)
    assert steps == []


def test_e2e_reaction_evaluate_debounce_prevents_double_fire():
    """Second evaluate() on same day → no steps (debounce)."""
    reaction = _make_reaction(weekday=0, scheduled_min=1200)
    history = [_snapshot("home")]
    with _make_hass_mock_for_weekday(weekday=0, hour=20, minute=0):
        first = reaction.evaluate(history)
        second = reaction.evaluate(history)
    assert len(first) == 2
    assert second == []


def test_e2e_reaction_evaluate_house_state_filter_mismatch():
    """evaluate() with house_state_filter that doesn't match → no steps."""
    reaction = LightingScheduleReaction(
        room_id="living",
        weekday=0,
        scheduled_min=1200,
        window_half_min=10,
        house_state_filter="home",
        entity_steps=[
            {"entity_id": "light.living_main", "action": "on",
             "brightness": 128, "color_temp_kelvin": 3000, "rgb_color": None},
        ],
    )
    history = [_snapshot("away")]
    with _make_hass_mock_for_weekday(weekday=0, hour=20, minute=0):
        steps = reaction.evaluate(history)
    assert steps == []


def test_e2e_reaction_evaluate_empty_history():
    """evaluate() with empty history → no steps."""
    reaction = _make_reaction()
    with _make_hass_mock_for_weekday(weekday=0, hour=20, minute=0):
        steps = reaction.evaluate([])
    assert steps == []


# ---------------------------------------------------------------------------
# 5. scheduled_jobs()
# ---------------------------------------------------------------------------

def test_e2e_reaction_scheduled_jobs_due_in_future():
    """scheduled_jobs() returns one job with due_monotonic in the future."""
    reaction = _make_reaction(reaction_id="sched-test")
    jobs = reaction.scheduled_jobs("entry_abc")
    assert len(jobs) == 1
    job_id, job = next(iter(jobs.items()))
    assert "lighting_schedule:sched-test" == job_id
    assert job.due_monotonic > time.monotonic()
    assert job.owner == "LightingScheduleReaction"
    assert job.entry_id == "entry_abc"


# ---------------------------------------------------------------------------
# 6. execute_lighting_steps() → HA service calls
# ---------------------------------------------------------------------------

async def test_e2e_execute_lighting_steps_turn_on():
    """execute_lighting_steps() calls light.turn_on with entity_id + brightness + color_temp."""
    from custom_components.heima.runtime.domains.lighting import LightingDomain

    calls = []

    async def _fake_service_call(domain, service, params, blocking=False):
        calls.append((domain, service, dict(params)))

    hass = MagicMock()
    hass.services.async_call = _fake_service_call
    hass.states.get = MagicMock(return_value=MagicMock())

    normalizer = MagicMock()
    domain = LightingDomain(hass, normalizer)

    steps = [
        ApplyStep(
            domain="lighting",
            target="living",
            action="light.turn_on",
            params={"entity_id": "light.living_main", "brightness": 128, "color_temp_kelvin": 3000},
            reason="lighting_schedule:test",
        )
    ]
    await domain.execute_lighting_steps(steps)
    assert len(calls) == 1
    domain_called, service_called, params = calls[0]
    assert domain_called == "light"
    assert service_called == "turn_on"
    assert params["entity_id"] == "light.living_main"
    assert params["brightness"] == 128
    assert params["color_temp_kelvin"] == 3000


async def test_e2e_execute_lighting_steps_turn_off_entity():
    """execute_lighting_steps() calls light.turn_off with entity_id (not area_id)."""
    from custom_components.heima.runtime.domains.lighting import LightingDomain

    calls = []

    async def _fake_service_call(domain, service, params, blocking=False):
        calls.append((domain, service, dict(params)))

    hass = MagicMock()
    hass.services.async_call = _fake_service_call
    hass.states.get = MagicMock(return_value=MagicMock())

    normalizer = MagicMock()
    domain = LightingDomain(hass, normalizer)

    steps = [
        ApplyStep(
            domain="lighting",
            target="living",
            action="light.turn_off",
            params={"entity_id": "light.living_spot"},
            reason="lighting_schedule:test",
        )
    ]
    await domain.execute_lighting_steps(steps)
    assert len(calls) == 1
    domain_called, service_called, params = calls[0]
    assert domain_called == "light"
    assert service_called == "turn_off"
    assert params["entity_id"] == "light.living_spot"
    assert "area_id" not in params


async def test_e2e_execute_lighting_steps_mixed_scene():
    """execute_lighting_steps() handles mixed on+off steps from one reaction."""
    from custom_components.heima.runtime.domains.lighting import LightingDomain

    calls = []

    async def _fake_service_call(domain, service, params, blocking=False):
        calls.append((domain, service, dict(params)))

    hass = MagicMock()
    hass.services.async_call = _fake_service_call
    hass.states.get = MagicMock(return_value=MagicMock())

    normalizer = MagicMock()
    domain = LightingDomain(hass, normalizer)

    reaction = _make_reaction()
    history = [_snapshot("home")]
    with _make_hass_mock_for_weekday(weekday=0, hour=20, minute=0):
        steps = reaction.evaluate(history)
    assert len(steps) == 2

    await domain.execute_lighting_steps(steps)
    assert len(calls) == 2
    services = {c[1] for c in calls}
    assert services == {"turn_on", "turn_off"}
