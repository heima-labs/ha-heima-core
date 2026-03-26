"""Tests for LightingPatternAnalyzer (learning system P9) — entity-level + scene grouping."""

from __future__ import annotations

from custom_components.heima.runtime.analyzers.lighting import LightingPatternAnalyzer
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent

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
    entity_id: str = "light.living_main",
    room_id: str = "living",
    action: str = "on",
    weekday: int = 0,
    minute: int = 1200,
    source: str = "user",
    ts: str = _WEEK1_TS,
    brightness: int | None = None,
    color_temp_kelvin: int | None = None,
    rgb_color: list | None = None,
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=_ctx(weekday=weekday, minute=minute),
        source=source,
        data={
            "entity_id": entity_id,
            "room_id": room_id,
            "action": action,
            "brightness": brightness,
            "color_temp_kelvin": color_temp_kelvin,
            "rgb_color": rgb_color,
        },
    )


def _multi_week_events(
    n_week1: int,
    n_week2: int,
    *,
    entity_id: str = "light.living_main",
    room_id: str = "living",
    action: str = "on",
    weekday: int = 0,
    minute: int = 1200,
    source: str = "user",
    brightness: int | None = None,
    color_temp_kelvin: int | None = None,
) -> list[HeimaEvent]:
    evts = [
        _lighting(entity_id=entity_id, room_id=room_id, action=action, weekday=weekday,
                  minute=minute, source=source, ts=_WEEK1_TS,
                  brightness=brightness, color_temp_kelvin=color_temp_kelvin)
        for _ in range(n_week1)
    ]
    evts += [
        _lighting(entity_id=entity_id, room_id=room_id, action=action, weekday=weekday,
                  minute=minute, source=source, ts=_WEEK2_TS,
                  brightness=brightness, color_temp_kelvin=color_temp_kelvin)
        for _ in range(n_week2)
    ]
    return evts


# ---------------------------------------------------------------------------
# Gate tests
# ---------------------------------------------------------------------------

async def test_lighting_analyzer_requires_min_occurrences():
    """Fewer than 5 events per entity → no proposal."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(2, 2)  # 4 total
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_requires_min_weeks():
    """5 events in a single ISO week → no proposal."""
    analyzer = LightingPatternAnalyzer()
    events = [_lighting(ts=_WEEK1_TS) for _ in range(5)]
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_emits_proposal_when_both_gates_pass():
    """5 events across 2 weeks → 1 proposal with lighting_scene_schedule type."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2)
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) == 1
    p = proposals[0]
    assert p.reaction_type == "lighting_scene_schedule"
    assert p.analyzer_id == "LightingPatternAnalyzer"


# ---------------------------------------------------------------------------
# Proposal structure
# ---------------------------------------------------------------------------

async def test_lighting_analyzer_proposal_config_fields():
    """suggested_reaction_config has room_id, weekday, scheduled_min, entity_steps."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(
        3, 2,
        entity_id="light.kitchen_spot",
        room_id="kitchen",
        action="off",
        weekday=2,
        minute=1380,
    )
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) == 1
    cfg = proposals[0].suggested_reaction_config
    assert cfg["reaction_class"] == "LightingScheduleReaction"
    assert cfg["room_id"] == "kitchen"
    assert cfg["weekday"] == 2
    assert cfg["scheduled_min"] == 1380
    assert cfg["window_half_min"] == 10
    assert len(cfg["entity_steps"]) == 1
    step = cfg["entity_steps"][0]
    assert step["entity_id"] == "light.kitchen_spot"
    assert step["action"] == "off"
    diagnostics = cfg["learning_diagnostics"]
    assert diagnostics["pattern_id"] == "lighting_scene_schedule"
    assert diagnostics["room_id"] == "kitchen"
    assert diagnostics["weekday"] == 2
    assert diagnostics["observations_count"] == 5
    assert diagnostics["weeks_observed"] >= 2
    assert diagnostics["entity_steps_count"] == 1


async def test_lighting_analyzer_entity_steps_contain_attributes():
    """On-entity step aggregates brightness and color_temp from events."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(
        3, 2,
        entity_id="light.living_main",
        room_id="living",
        action="on",
        brightness=128,
        color_temp_kelvin=3000,
    )
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    step = proposals[0].suggested_reaction_config["entity_steps"][0]
    assert step["brightness"] == 128
    assert step["color_temp_kelvin"] == 3000


async def test_lighting_analyzer_off_step_has_no_attributes():
    """Off-entity step has all attributes None."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, action="off")
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    step = proposals[0].suggested_reaction_config["entity_steps"][0]
    assert step["brightness"] is None
    assert step["color_temp_kelvin"] is None
    assert step["rgb_color"] is None


async def test_lighting_analyzer_fingerprint_set():
    """Fingerprint encodes room, weekday and rounded scheduled_min."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, room_id="living", weekday=0, minute=1200)
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    fp = proposals[0].fingerprint
    assert "LightingPatternAnalyzer" in fp
    assert "lighting_scene_schedule" in fp
    assert "living" in fp
    assert "0" in fp  # weekday


# ---------------------------------------------------------------------------
# Scene grouping
# ---------------------------------------------------------------------------

async def test_lighting_analyzer_groups_same_room_into_one_proposal():
    """Two entities in the same room at the same time → 1 proposal, 2 entity_steps."""
    analyzer = LightingPatternAnalyzer()
    main = _multi_week_events(3, 2, entity_id="light.living_main", room_id="living", minute=1200)
    spot = _multi_week_events(3, 2, entity_id="light.living_spot", room_id="living", minute=1205)
    proposals = await analyzer.analyze(_StoreStub(main + spot))  # type: ignore[arg-type]
    assert len(proposals) == 1
    assert len(proposals[0].suggested_reaction_config["entity_steps"]) == 2


async def test_lighting_analyzer_splits_distant_times_into_separate_proposals():
    """Two entities in the same room but 20+ min apart → 2 separate proposals."""
    analyzer = LightingPatternAnalyzer()
    early = _multi_week_events(3, 2, entity_id="light.living_main", room_id="living", minute=1200)
    late = _multi_week_events(3, 2, entity_id="light.living_spot", room_id="living", minute=1230)
    proposals = await analyzer.analyze(_StoreStub(early + late))  # type: ignore[arg-type]
    assert len(proposals) == 2


async def test_lighting_analyzer_different_rooms_separate_proposals():
    """Entities in different rooms → separate proposals."""
    analyzer = LightingPatternAnalyzer()
    living = _multi_week_events(3, 2, entity_id="light.living_main", room_id="living", weekday=0)
    kitchen = _multi_week_events(3, 2, entity_id="light.kitchen_main", room_id="kitchen", weekday=0)
    proposals = await analyzer.analyze(_StoreStub(living + kitchen))  # type: ignore[arg-type]
    assert len(proposals) == 2
    rooms = {p.suggested_reaction_config["room_id"] for p in proposals}
    assert rooms == {"living", "kitchen"}


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

async def test_lighting_analyzer_confidence_tight_schedule():
    """Tight IQR → high confidence."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, minute=1200)
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert proposals[0].confidence > 0.9


async def test_lighting_analyzer_confidence_floor():
    """Very spread schedule → confidence floored at 0.3."""
    analyzer = LightingPatternAnalyzer()
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
    tight = _multi_week_events(3, 2, minute=1200)
    tight_p = await analyzer.analyze(_StoreStub(tight))  # type: ignore[arg-type]

    spread_minutes = [1080, 1140, 1200, 1260, 1320]
    spread = []
    for i, m in enumerate(spread_minutes):
        ts = _WEEK1_TS if i < 3 else _WEEK2_TS
        spread.append(_lighting(minute=m, ts=ts))
    spread_p = await analyzer.analyze(_StoreStub(spread))  # type: ignore[arg-type]

    assert tight_p and spread_p
    assert tight_p[0].confidence > spread_p[0].confidence


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

async def test_lighting_analyzer_ignores_non_user_source():
    """Events with source != 'user' are excluded."""
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
            data={"entity_id": "light.living_main", "room_id": "living", "action": "dim"},
        ))
    proposals = await analyzer.analyze(_StoreStub(evts))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_ignores_missing_entity_id():
    """Events without entity_id are skipped."""
    analyzer = LightingPatternAnalyzer()
    evts = []
    for i in range(5):
        ts = _WEEK1_TS if i < 3 else _WEEK2_TS
        evts.append(HeimaEvent(
            ts=ts,
            event_type="lighting",
            context=_ctx(),
            source="user",
            data={"room_id": "living", "action": "on"},  # no entity_id
        ))
    proposals = await analyzer.analyze(_StoreStub(evts))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_empty_store():
    """Empty event store → no proposals."""
    analyzer = LightingPatternAnalyzer()
    proposals = await analyzer.analyze(_StoreStub([]))  # type: ignore[arg-type]
    assert proposals == []


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------

async def test_lighting_analyzer_description_contains_room_and_weekday():
    """Proposal description mentions room_id and weekday name."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(
        3, 2,
        entity_id="light.bedroom_main",
        room_id="bedroom",
        weekday=6,
    )
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    desc = proposals[0].description
    assert "bedroom" in desc
    assert "Sunday" in desc
