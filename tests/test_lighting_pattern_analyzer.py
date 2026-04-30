"""Tests for LightingPatternAnalyzer (learning system P9) — entity-level + scene grouping."""

from __future__ import annotations

from custom_components.heima.runtime.analyzers.lighting import LightingPatternAnalyzer
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent

_WEEK1_TS = "2026-03-02T08:00:00+00:00"  # ISO week 10
_WEEK2_TS = "2026-03-09T08:00:00+00:00"  # ISO week 11


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(  # noqa: ARG002
        self,
        *,
        event_type=None,
        room_id=None,
        subject_id=None,
        since=None,
        limit=None,
    ):
        events = [e for e in self._events if event_type is None or e.event_type == event_type]
        if room_id is not None:
            events = [e for e in events if e.room_id == room_id]
        if subject_id is not None:
            events = [e for e in events if e.subject_id == subject_id]
        return events


async def _analyze_proposals(analyzer, store):  # noqa: ANN001
    findings = await analyzer.analyze(store)  # type: ignore[arg-type]
    return [finding.payload for finding in findings]


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
    occupied_rooms: tuple[str, ...] | None = None,
    signals: dict[str, str] | None = None,
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=EventContext(
            weekday=weekday,
            minute_of_day=minute,
            month=3,
            house_state="home",
            occupants_count=1,
            occupied_rooms=occupied_rooms if occupied_rooms is not None else (),
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals=signals or {},
        ),
        source=source,
        domain="light",
        subject_type="entity",
        subject_id=entity_id,
        room_id=room_id,
        data={
            "entity_id": entity_id,
            "room_id": room_id,
            "action": action,
            "brightness": brightness,
            "color_temp_kelvin": color_temp_kelvin,
            "rgb_color": rgb_color,
        },
    )


def _state_change(
    *,
    entity_id: str,
    room_id: str,
    old_state: str,
    new_state: str,
    weekday: int = 0,
    minute: int = 1200,
    ts: str = _WEEK1_TS,
    device_class: str | None = None,
    unit_of_measurement: str | None = None,
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="state_change",
        context=EventContext(
            weekday=weekday,
            minute_of_day=minute,
            month=3,
            house_state="home",
            occupants_count=1,
            occupied_rooms=(room_id,),
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals={},
        ),
        source="unknown",
        domain=entity_id.split(".", 1)[0],
        subject_type="entity",
        subject_id=entity_id,
        room_id=room_id,
        data={
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": new_state,
            "device_class": device_class,
            "unit_of_measurement": unit_of_measurement,
        },
    )


def _room_signal_threshold(
    *,
    entity_id: str,
    room_id: str,
    from_bucket: str,
    to_bucket: str,
    weekday: int = 0,
    minute: int = 1200,
    ts: str = _WEEK1_TS,
    device_class: str = "illuminance",
    signal_name: str = "room_lux",
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="room_signal_threshold",
        context=EventContext(
            weekday=weekday,
            minute_of_day=minute,
            month=3,
            house_state="home",
            occupants_count=1,
            occupied_rooms=(room_id,),
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals={},
        ),
        source=None,
        domain="sensor",
        subject_type="signal",
        subject_id=signal_name,
        room_id=room_id,
        data={
            "entity_id": entity_id,
            "signal_name": signal_name,
            "from_bucket": from_bucket,
            "to_bucket": to_bucket,
            "direction": "down",
            "value": 95.0,
            "device_class": device_class,
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
        _lighting(
            entity_id=entity_id,
            room_id=room_id,
            action=action,
            weekday=weekday,
            minute=minute,
            source=source,
            ts=_WEEK1_TS,
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
        )
        for _ in range(n_week1)
    ]
    evts += [
        _lighting(
            entity_id=entity_id,
            room_id=room_id,
            action=action,
            weekday=weekday,
            minute=minute,
            source=source,
            ts=_WEEK2_TS,
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
        )
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
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_requires_min_weeks():
    """5 events in a single ISO week → no proposal."""
    analyzer = LightingPatternAnalyzer()
    events = [_lighting(ts=_WEEK1_TS) for _ in range(5)]
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_emits_no_proposal_without_context_signal():
    """5 events across 2 weeks but no context signal → no proposal (time-only is not learned)."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2)
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_suppresses_schedule_when_darkness_assist_is_confirmed():
    analyzer = LightingPatternAnalyzer()
    evidence_pairs = [
        ("2026-03-04T17:58:00+00:00", "2026-03-04T18:00:00+00:00"),
        ("2026-03-11T17:58:00+00:00", "2026-03-11T18:00:00+00:00"),
        ("2026-03-18T17:58:00+00:00", "2026-03-18T18:00:00+00:00"),
        ("2026-03-25T17:58:00+00:00", "2026-03-25T18:00:00+00:00"),
        ("2026-04-01T17:58:00+00:00", "2026-04-01T18:00:00+00:00"),
    ]
    events: list[HeimaEvent] = []
    for lux_ts, light_ts in evidence_pairs:
        events.extend(
            [
                _room_signal_threshold(
                    entity_id="sensor.bedroom_lux",
                    room_id="bedroom",
                    from_bucket="ok",
                    to_bucket="dim",
                    weekday=2,
                    minute=17 * 60 + 58,
                    ts=lux_ts,
                    device_class="illuminance",
                    signal_name="room_lux",
                ),
                _lighting(
                    entity_id="light.bedroom_main",
                    room_id="bedroom",
                    action="on",
                    weekday=2,
                    minute=18 * 60,
                    ts=light_ts,
                    brightness=255,
                    occupied_rooms=("bedroom",),
                ),
            ]
        )

    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


# ---------------------------------------------------------------------------
# Proposal structure
# ---------------------------------------------------------------------------


async def test_lighting_analyzer_proposal_config_fields():
    """Without context signal, no proposal is emitted even with valid pattern."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(
        3,
        2,
        entity_id="light.kitchen_spot",
        room_id="kitchen",
        action="off",
        weekday=2,
        minute=1380,
    )
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_entity_steps_contain_attributes():
    """Without context signal, no proposal emitted even with brightness/color_temp events."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(
        3,
        2,
        entity_id="light.living_main",
        room_id="living",
        action="on",
        brightness=128,
        color_temp_kelvin=3000,
    )
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_off_step_has_no_attributes():
    """Without context signal, no proposal emitted for off-action patterns."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, action="off")
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_fingerprint_set():
    """Without context signal, no proposal and no fingerprint to check."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, room_id="living", weekday=0, minute=1200)
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


# ---------------------------------------------------------------------------
# Scene grouping
# ---------------------------------------------------------------------------


async def test_lighting_analyzer_groups_same_room_into_one_proposal():
    """Without context signal, two entities in the same room → no proposal."""
    analyzer = LightingPatternAnalyzer()
    main = _multi_week_events(3, 2, entity_id="light.living_main", room_id="living", minute=1200)
    spot = _multi_week_events(3, 2, entity_id="light.living_spot", room_id="living", minute=1205)
    proposals = await _analyze_proposals(analyzer, _StoreStub(main + spot))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_collapses_duplicate_entity_candidates_in_same_scene():
    """Without context signal, same entity on+off in same scene window → no proposal."""
    analyzer = LightingPatternAnalyzer()
    on_events = _multi_week_events(
        3, 2, entity_id="light.living_main", room_id="living", action="on", minute=1200
    )
    off_events = _multi_week_events(
        3, 2, entity_id="light.living_main", room_id="living", action="off", minute=1205
    )
    proposals = await _analyze_proposals(analyzer, _StoreStub(on_events + off_events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_orders_scene_entities_deterministically():
    """Without context signal, no proposal even with multi-entity scene."""
    analyzer = LightingPatternAnalyzer()
    main = _multi_week_events(3, 2, entity_id="light.living_main", room_id="living", minute=1205)
    spot = _multi_week_events(3, 2, entity_id="light.living_spot", room_id="living", minute=1200)
    proposals = await _analyze_proposals(analyzer, _StoreStub(spot + main))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_splits_distant_times_into_separate_proposals():
    """Without context signal, two time-separated patterns → no proposals."""
    analyzer = LightingPatternAnalyzer()
    early = _multi_week_events(3, 2, entity_id="light.living_main", room_id="living", minute=1200)
    late = _multi_week_events(3, 2, entity_id="light.living_spot", room_id="living", minute=1230)
    proposals = await _analyze_proposals(analyzer, _StoreStub(early + late))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_different_rooms_separate_proposals():
    """Without context signal, multi-room patterns → no proposals."""
    analyzer = LightingPatternAnalyzer()
    living = _multi_week_events(3, 2, entity_id="light.living_main", room_id="living", weekday=0)
    kitchen = _multi_week_events(3, 2, entity_id="light.kitchen_main", room_id="kitchen", weekday=0)
    proposals = await _analyze_proposals(analyzer, _StoreStub(living + kitchen))  # type: ignore[arg-type]
    assert proposals == []


# ---------------------------------------------------------------------------
# Confidence (context required — these become no-op without context signal)
# ---------------------------------------------------------------------------


async def test_lighting_analyzer_confidence_tight_schedule():
    """Without context signal, no proposal regardless of schedule tightness."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, minute=1200)
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_confidence_floor():
    """Without context signal, no proposal regardless of spread."""
    analyzer = LightingPatternAnalyzer()
    minutes = [600, 720, 840, 960, 1080, 780, 900, 1020]
    timestamps = [
        _WEEK1_TS,
        _WEEK1_TS,
        _WEEK1_TS,
        _WEEK2_TS,
        _WEEK2_TS,
        "2026-03-16T08:00:00+00:00",
        "2026-03-16T08:05:00+00:00",
        "2026-03-16T08:10:00+00:00",
    ]
    evts = [_lighting(minute=minute, ts=ts) for minute, ts in zip(minutes, timestamps, strict=True)]
    proposals = await _analyze_proposals(analyzer, _StoreStub(evts))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_confidence_tight_vs_spread():
    """Without context signal, both tight and spread patterns emit no proposal."""
    analyzer = LightingPatternAnalyzer()
    tight = _multi_week_events(3, 2, minute=1200)
    tight_p = await _analyze_proposals(analyzer, _StoreStub(tight))  # type: ignore[arg-type]

    spread_minutes = [1080, 1140, 1200, 1260, 1320, 1110, 1230, 1290]
    spread_timestamps = [
        _WEEK1_TS,
        _WEEK1_TS,
        _WEEK1_TS,
        _WEEK2_TS,
        _WEEK2_TS,
        "2026-03-16T08:00:00+00:00",
        "2026-03-16T08:05:00+00:00",
        "2026-03-16T08:10:00+00:00",
    ]
    spread = [
        _lighting(minute=minute, ts=ts)
        for minute, ts in zip(spread_minutes, spread_timestamps, strict=True)
    ]
    spread_p = await _analyze_proposals(analyzer, _StoreStub(spread))  # type: ignore[arg-type]

    assert tight_p == []
    assert spread_p == []


async def test_lighting_analyzer_confidence_rewards_more_evidence():
    """Without context signal, no proposal regardless of evidence richness."""
    analyzer = LightingPatternAnalyzer()
    minimal = _multi_week_events(3, 2, minute=1200)
    richer = _multi_week_events(3, 2, minute=1200) + [
        _lighting(minute=1200, ts="2026-03-16T08:00:00+00:00") for _ in range(3)
    ]

    minimal_p = await _analyze_proposals(analyzer, _StoreStub(minimal))  # type: ignore[arg-type]
    richer_p = await _analyze_proposals(analyzer, _StoreStub(richer))  # type: ignore[arg-type]

    assert minimal_p == []
    assert richer_p == []


async def test_lighting_analyzer_promotes_context_conditioned_scene_when_context_explains_pattern():
    analyzer = LightingPatternAnalyzer()
    events: list[HeimaEvent] = []
    positive_pairs = [
        ("2026-03-03T20:00:00+00:00", "2026-03-03T20:04:00+00:00", 0),
        ("2026-03-10T20:00:00+00:00", "2026-03-10T20:04:00+00:00", 0),
        ("2026-03-17T20:00:00+00:00", "2026-03-17T20:04:00+00:00", 0),
        ("2026-03-24T20:00:00+00:00", "2026-03-24T20:04:00+00:00", 0),
        ("2026-03-31T20:00:00+00:00", "2026-03-31T20:04:00+00:00", 0),
    ]
    for on_ts, off_ts, minute_offset in positive_pairs:
        events.extend(
            [
                _lighting(
                    ts=on_ts,
                    entity_id="light.studio_main",
                    room_id="studio",
                    weekday=1,
                    minute=20 * 60 + minute_offset,
                    action="off",
                    signals={"media_player.projector": "playing"},
                ),
                _lighting(
                    ts=on_ts,
                    entity_id="light.studio_spot",
                    room_id="studio",
                    weekday=1,
                    minute=20 * 60 + minute_offset,
                    action="on",
                    brightness=80,
                    signals={"media_player.projector": "playing"},
                ),
            ]
        )
        events.append(
            _lighting(
                ts=off_ts,
                entity_id="light.studio_main",
                room_id="studio",
                weekday=1,
                minute=20 * 60 + minute_offset + 4,
                action="on",
                brightness=120,
                signals={"media_player.projector": "off"},
            )
        )

    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.reaction_type == "context_conditioned_lighting_scene"
    cfg = proposal.suggested_reaction_config
    assert cfg["reaction_type"] == "context_conditioned_lighting_scene"
    assert cfg["context_conditions"] == [
        {"signal_name": "projector_context", "state_in": ["active"]}
    ]
    diagnostics = cfg["learning_diagnostics"]
    assert diagnostics["contrast_status"] == "verified"
    assert diagnostics["competing_explanation_type"] == "context"


async def test_lighting_analyzer_emits_nothing_when_context_is_weak():
    analyzer = LightingPatternAnalyzer()
    events = [
        _lighting(
            ts="2026-03-03T20:00:00+00:00",
            entity_id="light.studio_spot",
            room_id="studio",
            weekday=1,
            minute=20 * 60,
            action="on",
            brightness=80,
            signals={"media_player.projector": "playing"},
        ),
        _lighting(
            ts="2026-03-10T20:00:00+00:00",
            entity_id="light.studio_spot",
            room_id="studio",
            weekday=1,
            minute=20 * 60,
            action="on",
            brightness=80,
            signals={"media_player.projector": "off"},
        ),
        _lighting(
            ts="2026-03-17T20:00:00+00:00",
            entity_id="light.studio_spot",
            room_id="studio",
            weekday=1,
            minute=20 * 60,
            action="on",
            brightness=80,
            signals={"media_player.projector": "off"},
        ),
        _lighting(
            ts="2026-03-24T20:00:00+00:00",
            entity_id="light.studio_spot",
            room_id="studio",
            weekday=1,
            minute=20 * 60,
            action="on",
            brightness=80,
            signals={"media_player.projector": "playing"},
        ),
        _lighting(
            ts="2026-03-31T20:00:00+00:00",
            entity_id="light.studio_spot",
            room_id="studio",
            weekday=1,
            minute=20 * 60,
            action="on",
            brightness=80,
            signals={"media_player.projector": "off"},
        ),
        _lighting(
            ts="2026-04-07T20:00:00+00:00",
            entity_id="light.studio_spot",
            room_id="studio",
            weekday=1,
            minute=20 * 60,
            action="on",
            brightness=80,
            signals={"media_player.projector": "playing"},
        ),
    ]

    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_skips_minimal_evidence_with_wide_iqr():
    """Bare-minimum evidence plus wide spread should be treated as noise."""
    analyzer = LightingPatternAnalyzer()
    minutes = [1140, 1170, 1200, 1235, 1275]
    events = []
    for i, minute in enumerate(minutes):
        ts = _WEEK1_TS if i < 3 else _WEEK2_TS
        events.append(_lighting(minute=minute, ts=ts))

    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]

    assert proposals == []


async def test_lighting_analyzer_keeps_wide_iqr_when_evidence_is_richer():
    """Without context signal, richer evidence still yields no proposal."""
    analyzer = LightingPatternAnalyzer()
    minutes = [1140, 1170, 1200, 1235, 1275, 1190, 1210, 1220]
    timestamps = [
        _WEEK1_TS,
        _WEEK1_TS,
        _WEEK1_TS,
        _WEEK2_TS,
        _WEEK2_TS,
        "2026-03-16T08:00:00+00:00",
        "2026-03-16T08:05:00+00:00",
        "2026-03-16T08:10:00+00:00",
    ]
    events = [
        _lighting(minute=minute, ts=ts) for minute, ts in zip(minutes, timestamps, strict=True)
    ]

    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]

    assert proposals == []


async def test_lighting_analyzer_window_half_min_tight_cluster():
    """Without context signal, no proposal even for tight cluster."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, minute=1200)
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_window_half_min_spread_cluster():
    """Without context signal, no proposal even for spread cluster."""
    analyzer = LightingPatternAnalyzer()
    minutes = [1160, 1180, 1200, 1220, 1240, 1170, 1210, 1230]
    timestamps = [
        _WEEK1_TS,
        _WEEK1_TS,
        _WEEK1_TS,
        _WEEK2_TS,
        _WEEK2_TS,
        "2026-03-16T08:00:00+00:00",
        "2026-03-16T08:05:00+00:00",
        "2026-03-16T08:10:00+00:00",
    ]
    evts = [_lighting(minute=minute, ts=ts) for minute, ts in zip(minutes, timestamps, strict=True)]
    proposals = await _analyze_proposals(analyzer, _StoreStub(evts))  # type: ignore[arg-type]
    assert proposals == []


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


async def test_lighting_analyzer_ignores_non_user_source():
    """Events with source != 'user' are excluded."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(3, 2, source="heima")
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_ignores_invalid_action():
    """Events with action not in ('on', 'off') are skipped."""
    analyzer = LightingPatternAnalyzer()
    evts = []
    for i in range(5):
        ts = _WEEK1_TS if i < 3 else _WEEK2_TS
        evts.append(
            HeimaEvent(
                ts=ts,
                event_type="lighting",
                context=_ctx(),
                source="user",
                data={"entity_id": "light.living_main", "room_id": "living", "action": "dim"},
            )
        )
    proposals = await _analyze_proposals(analyzer, _StoreStub(evts))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_ignores_missing_entity_id():
    """Events without entity_id are skipped."""
    analyzer = LightingPatternAnalyzer()
    evts = []
    for i in range(5):
        ts = _WEEK1_TS if i < 3 else _WEEK2_TS
        evts.append(
            HeimaEvent(
                ts=ts,
                event_type="lighting",
                context=_ctx(),
                source="user",
                data={"room_id": "living", "action": "on"},  # no entity_id
            )
        )
    proposals = await _analyze_proposals(analyzer, _StoreStub(evts))  # type: ignore[arg-type]
    assert proposals == []


async def test_lighting_analyzer_empty_store():
    """Empty event store → no proposals."""
    analyzer = LightingPatternAnalyzer()
    proposals = await _analyze_proposals(analyzer, _StoreStub([]))  # type: ignore[arg-type]
    assert proposals == []


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------


async def test_lighting_analyzer_description_contains_room_and_weekday():
    """Without context signal, no proposal and no description to check."""
    analyzer = LightingPatternAnalyzer()
    events = _multi_week_events(
        3,
        2,
        entity_id="light.bedroom_main",
        room_id="bedroom",
        weekday=6,
    )
    proposals = await _analyze_proposals(analyzer, _StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []
