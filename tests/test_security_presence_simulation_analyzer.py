"""Tests for SecurityPresenceSimulationAnalyzer learned proposal bootstrap."""

from __future__ import annotations

from custom_components.heima.runtime.analyzers.security_presence_simulation import (
    SecurityPresenceSimulationAnalyzer,
)
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent

_WEEK1_TS = "2026-03-02T18:00:00+00:00"
_WEEK2_TS = "2026-03-09T18:00:00+00:00"


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(self, *, event_type=None, since=None, limit=None):  # noqa: ARG002
        return [e for e in self._events if event_type is None or e.event_type == event_type]


def _ctx(
    *,
    weekday: int,
    minute: int,
    house_state: str = "home",
    occupants_count: int = 1,
) -> EventContext:
    return EventContext(
        weekday=weekday,
        minute_of_day=minute,
        month=3,
        house_state=house_state,
        occupants_count=occupants_count,
        occupied_rooms=("living",),
        outdoor_lux=None,
        outdoor_temp=None,
        weather_condition=None,
        signals={},
    )


def _lighting(
    *,
    ts: str,
    weekday: int,
    minute: int,
    room_id: str,
    entity_id: str,
    action: str,
    house_state: str = "home",
    occupants_count: int = 1,
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=_ctx(
            weekday=weekday,
            minute=minute,
            house_state=house_state,
            occupants_count=occupants_count,
        ),
        source="user",
        data={
            "entity_id": entity_id,
            "room_id": room_id,
            "action": action,
        },
    )


def _multi_week(
    room_id: str, entity_id: str, action: str, weekday: int, minute: int
) -> list[HeimaEvent]:
    return [
        *[
            _lighting(
                ts=_WEEK1_TS,
                weekday=weekday,
                minute=minute,
                room_id=room_id,
                entity_id=entity_id,
                action=action,
            )
            for _ in range(2)
        ],
        *[
            _lighting(
                ts=_WEEK2_TS,
                weekday=weekday,
                minute=minute,
                room_id=room_id,
                entity_id=entity_id,
                action=action,
            )
            for _ in range(2)
        ],
    ]


async def test_security_presence_simulation_analyzer_emits_home_scoped_proposal():
    analyzer = SecurityPresenceSimulationAnalyzer()
    events = (
        _multi_week("living", "light.living_main", "on", 0, 1135)
        + _multi_week("living", "light.living_main", "off", 0, 1320)
        + _multi_week("kitchen", "light.kitchen_main", "on", 0, 1180)
    )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.reaction_type == "vacation_presence_simulation"
    assert (
        proposal.fingerprint
        == "SecurityPresenceSimulationAnalyzer|vacation_presence_simulation|scope=home"
    )
    cfg = proposal.suggested_reaction_config
    assert cfg["reaction_type"] == "vacation_presence_simulation"
    assert cfg["dynamic_policy"] is True
    assert cfg["learned_source_profile_kind"] == "event_store_evening_lighting"
    assert sorted(cfg["allowed_rooms"]) == ["kitchen", "living"]
    assert "light.living_main" in cfg["allowed_entities"]
    assert len(cfg["learned_source_profiles"]) >= 2
    diagnostics = cfg["learning_diagnostics"]
    assert diagnostics["plugin_family"] == "security_presence_simulation"
    assert diagnostics["excluded_vacation"] is True


async def test_security_presence_simulation_analyzer_excludes_vacation_events():
    analyzer = SecurityPresenceSimulationAnalyzer()
    events = (
        _multi_week("living", "light.living_main", "on", 0, 1135)
        + _multi_week("living", "light.living_main", "off", 0, 1320)
        + [
            _lighting(
                ts=_WEEK2_TS,
                weekday=0,
                minute=1160,
                room_id="kitchen",
                entity_id="light.kitchen_main",
                action="on",
                house_state="vacation",
            )
            for _ in range(4)
        ]
    )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]

    assert len(proposals) == 1
    cfg = proposals[0].suggested_reaction_config
    assert cfg["allowed_rooms"] == ["living"]
    assert all(item["room_id"] == "living" for item in cfg["learned_source_profiles"])


async def test_security_presence_simulation_analyzer_requires_sufficient_profile_mix():
    analyzer = SecurityPresenceSimulationAnalyzer()
    events = _multi_week("living", "light.living_main", "on", 0, 1135)

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]

    assert proposals == []
