"""Tests for reusable room-scoped composite pattern matcher utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.heima.runtime.analyzers.composite import (
    CompositePatternSpec,
    CompositeSignalSpec,
    RoomScopedCompositeMatcher,
)
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent


def _ctx(*, room: str) -> EventContext:
    return EventContext(
        weekday=0,
        minute_of_day=480,
        month=3,
        house_state="home",
        occupants_count=1,
        occupied_rooms=(room,),
        outdoor_lux=None,
        outdoor_temp=None,
        weather_condition=None,
        signals={},
    )


def _state_change(
    *,
    entity_id: str,
    room: str,
    ts: str,
    old_state: str,
    new_state: str,
    device_class: str | None = None,
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="state_change",
        context=_ctx(room=room),
        source="unknown",
        domain=entity_id.split(".", 1)[0],
        subject_type="entity",
        subject_id=entity_id,
        room_id=room,
        data={
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": new_state,
            "device_class": device_class,
        },
    )


def test_room_scoped_composite_matcher_detects_primary_corroboration_and_followup():
    matcher = RoomScopedCompositeMatcher()
    base = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    events = [
        _state_change(
            entity_id="sensor.bathroom_humidity",
            room="bathroom",
            ts=base.isoformat(),
            old_state="55",
            new_state="66",
            device_class="humidity",
        ),
        _state_change(
            entity_id="sensor.bathroom_temperature",
            room="bathroom",
            ts=(base + timedelta(minutes=3)).isoformat(),
            old_state="21.0",
            new_state="22.0",
            device_class="temperature",
        ),
        _state_change(
            entity_id="switch.bathroom_fan",
            room="bathroom",
            ts=(base + timedelta(minutes=5)).isoformat(),
            old_state="off",
            new_state="on",
        ),
    ]
    spec = CompositePatternSpec(
        primary=CompositeSignalSpec(
            name="humidity",
            predicate=lambda e: e.data.get("device_class") == "humidity",
            min_delta=8.0,
        ),
        corroborations=(
            CompositeSignalSpec(
                name="temperature",
                predicate=lambda e: e.data.get("device_class") == "temperature",
                min_delta=0.8,
            ),
        ),
        followup=CompositeSignalSpec(
            name="ventilation",
            predicate=lambda e: str(e.data.get("new_state")) == "on",
        ),
        correlation_window_s=10 * 60,
        followup_window_s=15 * 60,
    )

    episodes = matcher.detect(room_id="bathroom", events=events, spec=spec)

    assert len(episodes) == 1
    episode = episodes[0]
    assert episode.primary_entity == "sensor.bathroom_humidity"
    assert episode.corroboration_matches["temperature"] == ("sensor.bathroom_temperature",)
    assert episode.followup_entities == ("switch.bathroom_fan",)


def test_room_scoped_composite_matcher_skips_when_required_corroboration_missing():
    matcher = RoomScopedCompositeMatcher()
    base = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    events = [
        _state_change(
            entity_id="sensor.bathroom_humidity",
            room="bathroom",
            ts=base.isoformat(),
            old_state="55",
            new_state="66",
            device_class="humidity",
        )
    ]
    spec = CompositePatternSpec(
        primary=CompositeSignalSpec(
            name="humidity",
            predicate=lambda e: e.data.get("device_class") == "humidity",
            min_delta=8.0,
        ),
        corroborations=(
            CompositeSignalSpec(
                name="temperature",
                predicate=lambda e: e.data.get("device_class") == "temperature",
                min_delta=0.8,
                required=True,
            ),
        ),
        correlation_window_s=10 * 60,
        followup_window_s=15 * 60,
    )

    assert matcher.detect(room_id="bathroom", events=events, spec=spec) == []
