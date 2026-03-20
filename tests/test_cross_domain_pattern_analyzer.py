"""Tests for CrossDomainPatternAnalyzer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.heima.runtime.analyzers.cross_domain import (
    CrossDomainPatternAnalyzer,
    RoomCoolingPatternAnalyzer,
)
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(self, *, event_type=None, since=None, limit=None):  # noqa: ARG002
        return [e for e in self._events if event_type is None or e.event_type == event_type]


def _ctx(*, room: str, minute: int = 480) -> EventContext:
    return EventContext(
        weekday=0,
        minute_of_day=minute,
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
    domain = entity_id.split(".", 1)[0]
    return HeimaEvent(
        ts=ts,
        event_type="state_change",
        context=_ctx(room=room),
        source="unknown",
        domain=domain,
        subject_type="entity",
        subject_id=entity_id,
        room_id=room,
        data={
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": new_state,
            "unit_of_measurement": "%",
            "device_class": device_class,
        },
    )


async def test_cross_domain_analyzer_requires_min_confirmed_episodes():
    analyzer = CrossDomainPatternAnalyzer()
    base = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    events = []
    for i in range(4):
        ts = (base + timedelta(days=i * 7)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=5)).isoformat()
        events.append(
            _state_change(
                entity_id="sensor.bathroom_humidity",
                room="bathroom",
                ts=ts,
                old_state="55",
                new_state="64",
                device_class="humidity",
            )
        )
        events.append(
            _state_change(
                entity_id="fan.bathroom_fan",
                room="bathroom",
                ts=fan_ts,
                old_state="off",
                new_state="on",
            )
        )
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_cross_domain_analyzer_emits_room_signal_assist_proposal():
    analyzer = CrossDomainPatternAnalyzer()
    base = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        ts = (base + timedelta(days=i * 7)).isoformat()
        temp_ts = (base + timedelta(days=i * 7, minutes=3)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=5)).isoformat()
        events.extend(
            [
                _state_change(
                    entity_id="sensor.bathroom_humidity",
                    room="bathroom",
                    ts=ts,
                    old_state="55",
                    new_state="66",
                    device_class="humidity",
                ),
                _state_change(
                    entity_id="sensor.bathroom_temperature",
                    room="bathroom",
                    ts=temp_ts,
                    old_state="21.0",
                    new_state="22.1",
                    device_class="temperature",
                ),
                _state_change(
                    entity_id="fan.bathroom_fan",
                    room="bathroom",
                    ts=fan_ts,
                    old_state="off",
                    new_state="on",
                ),
            ]
        )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.reaction_type == "room_signal_assist"
    assert proposal.suggested_reaction_config["reaction_class"] == "RoomSignalAssistReaction"
    assert proposal.suggested_reaction_config["room_id"] == "bathroom"
    assert proposal.suggested_reaction_config["trigger_signal_entities"] == ["sensor.bathroom_humidity"]
    assert proposal.suggested_reaction_config["temperature_signal_entities"] == [
        "sensor.bathroom_temperature"
    ]
    assert proposal.suggested_reaction_config["observed_followup_entities"] == [
        "fan.bathroom_fan"
    ]
    assert proposal.suggested_reaction_config["episodes_observed"] >= 5


async def test_room_cooling_pattern_analyzer_emits_room_cooling_assist_proposal():
    analyzer = RoomCoolingPatternAnalyzer()
    base = datetime(2026, 3, 1, 15, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        ts = (base + timedelta(days=i * 7)).isoformat()
        humidity_ts = (base + timedelta(days=i * 7, minutes=2)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=5)).isoformat()
        events.extend(
            [
                _state_change(
                    entity_id="sensor.studio_temperature",
                    room="studio",
                    ts=ts,
                    old_state="24.0",
                    new_state="25.8",
                    device_class="temperature",
                ),
                _state_change(
                    entity_id="sensor.studio_humidity",
                    room="studio",
                    ts=humidity_ts,
                    old_state="52",
                    new_state="58",
                    device_class="humidity",
                ),
                _state_change(
                    entity_id="fan.studio_fan",
                    room="studio",
                    ts=fan_ts,
                    old_state="off",
                    new_state="on",
                ),
            ]
        )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.reaction_type == "room_cooling_assist"
    assert proposal.suggested_reaction_config["reaction_class"] == "RoomSignalAssistReaction"
    assert proposal.suggested_reaction_config["room_id"] == "studio"
    assert proposal.suggested_reaction_config["primary_signal_entities"] == [
        "sensor.studio_temperature"
    ]
    assert proposal.suggested_reaction_config["corroboration_signal_entities"] == [
        "sensor.studio_humidity"
    ]
    assert proposal.suggested_reaction_config["observed_followup_entities"] == [
        "fan.studio_fan"
    ]
