"""Tests for the Phase AB room smart lighting assist reaction."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.domains.lighting import LightingDomain
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.reactions.smart_lighting_assist import (
    RoomSmartLightingAssistReaction,
    build_room_smart_lighting_assist_reaction,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _snapshot(*, occupied_rooms: list[str], ts: str, house_state: str = "home") -> DecisionSnapshot:
    base = DecisionSnapshot.empty()
    return replace(base, ts=ts, occupied_rooms=occupied_rooms, house_state=house_state)


def test_smart_lighting_turns_on_when_presence_and_indoor_lux_match() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="off")
    buckets = {"studio:room_lux": "dark"}
    reaction = RoomSmartLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: buckets.get(f"{room_id}:{signal_name}"),
        room_id="studio",
        indoor_lux_signal="room_lux",
        lux_on_buckets=["dark", "dim"],
        entity_steps=[{"entity_id": "light.studio_main", "action": "on", "brightness": 144}],
        reaction_id="smart-studio",
    )

    steps = reaction.evaluate(
        [_snapshot(occupied_rooms=["studio"], ts=datetime(2026, 6, 11, 10, tzinfo=UTC).isoformat())]
    )

    assert len(steps) == 1
    assert steps[0].action == "light.turn_on"
    assert steps[0].params["entity_id"] == "light.studio_main"
    assert steps[0].params["brightness"] == 144
    assert reaction.diagnostics()["effective_suppress_states"] == []


def test_smart_lighting_pre_registers_one_context_per_evaluate_batch() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="off")
    reaction = RoomSmartLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        room_id="studio",
        indoor_lux_signal="room_lux",
        lux_on_buckets=["dark"],
        entity_steps=[
            {"entity_id": "light.studio_main", "action": "on", "brightness": 144},
            {"entity_id": "light.studio_desk", "action": "on", "brightness": 120},
        ],
        reaction_id="smart-studio",
    )

    steps = reaction.evaluate(
        [_snapshot(occupied_rooms=["studio"], ts=datetime(2026, 6, 11, 10, tzinfo=UTC).isoformat())]
    )

    assert len(steps) == 2
    context_ids = {step.context_id for step in steps}
    assert len(context_ids) == 1
    context_id = next(iter(context_ids))
    assert context_id
    assert reaction.owns_context_id(context_id)
    assert reaction.diagnostics()["issued_context_ids"] == 1


def test_smart_lighting_sleeping_is_suppressed_for_studio() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="off")
    reaction = RoomSmartLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        room_id="studio",
        indoor_lux_signal="room_lux",
        lux_on_buckets=["dark"],
        room_type="studio",
        night_mode_states=["sleeping"],
        entity_steps=[{"entity_id": "light.studio_main", "action": "on", "brightness": 144}],
    )

    steps = reaction.evaluate(
        [
            _snapshot(
                occupied_rooms=["studio"],
                ts=datetime(2026, 6, 11, 23, tzinfo=UTC).isoformat(),
                house_state="sleeping",
            )
        ]
    )

    assert steps == []
    assert reaction.diagnostics()["effective_suppress_states"] == ["sleeping"]


def test_smart_lighting_sleeping_uses_night_fallback_for_bathroom() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="off")
    reaction = RoomSmartLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        room_id="bathroom",
        indoor_lux_signal="room_lux",
        lux_on_buckets=["dark"],
        room_type="bagno",
        night_mode_states=["sleeping"],
        entity_steps=[{"entity_id": "light.bathroom_main", "action": "on", "brightness": 144}],
    )

    steps = reaction.evaluate(
        [
            _snapshot(
                occupied_rooms=["bathroom"],
                ts=datetime(2026, 6, 11, 23, tzinfo=UTC).isoformat(),
                house_state="sleeping",
            )
        ]
    )

    assert len(steps) == 1
    assert steps[0].params["brightness"] == 26
    assert steps[0].params["color_temp_kelvin"] == 2200
    assert reaction.diagnostics()["selected_profile"] == "night_fallback"


def test_smart_lighting_reapplies_when_outdoor_scale_changes() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="on")
    buckets = {"studio:room_lux": "dark", "studio:outdoor_lux": "bright"}
    reaction = RoomSmartLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: buckets.get(f"{room_id}:{signal_name}"),
        room_id="studio",
        indoor_lux_signal="room_lux",
        outdoor_lux_signal="outdoor_lux",
        lux_on_buckets=["dark"],
        outdoor_lux_scale={"bright": 0.5, "dark": 1.2},
        entity_steps=[{"entity_id": "light.studio_main", "action": "on", "brightness": 100}],
    )
    ts1 = datetime(2026, 6, 11, 10, tzinfo=UTC).isoformat()
    ts2 = datetime(2026, 6, 11, 10, 1, tzinfo=UTC).isoformat()

    first = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1)])
    assert len(first) == 1
    assert first[0].params["brightness"] == 50

    buckets["studio:outdoor_lux"] = "dark"
    second = reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts2)])

    assert len(second) == 1
    assert second[0].params["brightness"] == 120
    assert reaction.diagnostics()["current_outdoor_scale"] == 1.2


def test_smart_lighting_external_off_sets_manual_override() -> None:
    hass = MagicMock()
    states = {"light.studio_main": "off"}
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state=states[eid])
    reaction = RoomSmartLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        room_id="studio",
        indoor_lux_signal="room_lux",
        lux_on_buckets=["dark"],
        entity_steps=[{"entity_id": "light.studio_main", "action": "on", "brightness": 144}],
    )
    ts = datetime(2026, 6, 11, 10, tzinfo=UTC).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts)])
    reaction.handle_external_light_change("light.studio_main", "off")

    assert reaction.diagnostics()["manual_override_active"] is True
    assert reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts)]) == []


def test_smart_lighting_external_on_sets_manual_hold() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="on")
    buckets = {"studio:room_lux": "dark", "studio:outdoor_lux": "bright"}
    reaction = RoomSmartLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: buckets.get(f"{room_id}:{signal_name}"),
        room_id="studio",
        indoor_lux_signal="room_lux",
        outdoor_lux_signal="outdoor_lux",
        lux_on_buckets=["dark"],
        outdoor_lux_scale={"bright": 0.5, "dark": 1.2},
        entity_steps=[{"entity_id": "light.studio_main", "action": "on", "brightness": 100}],
    )
    ts1 = datetime(2026, 6, 11, 10, tzinfo=UTC).isoformat()
    ts2 = datetime(2026, 6, 11, 10, 1, tzinfo=UTC).isoformat()

    assert reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts1)])
    reaction.handle_external_light_change("light.studio_main", "on")
    buckets["studio:outdoor_lux"] = "dark"

    assert reaction.diagnostics()["manual_on_hold"] is True
    assert reaction.evaluate([_snapshot(occupied_rooms=["studio"], ts=ts2)]) == []


def test_smart_lighting_dispatcher_ignores_owned_context_and_routes_external_change() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="off")
    reaction = RoomSmartLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        room_id="studio",
        indoor_lux_signal="room_lux",
        lux_on_buckets=["dark"],
        entity_steps=[{"entity_id": "light.studio_main", "action": "on"}],
    )
    steps = reaction.evaluate(
        [_snapshot(occupied_rooms=["studio"], ts=datetime(2026, 6, 11, 10, tzinfo=UTC).isoformat())]
    )
    context_id = steps[0].context_id
    engine = HeimaEngine.__new__(HeimaEngine)
    engine._reactions = [reaction]

    owned_event = SimpleNamespace(
        data={
            "entity_id": "light.studio_main",
            "new_state": SimpleNamespace(state="off", context=SimpleNamespace(parent_id=context_id)),
        },
        context=SimpleNamespace(parent_id=None),
    )
    engine.handle_smart_lighting_state_changed(owned_event)
    assert reaction.diagnostics()["manual_override_active"] is False

    external_event = SimpleNamespace(
        data={
            "entity_id": "light.studio_main",
            "new_state": SimpleNamespace(state="off", context=SimpleNamespace(parent_id=None)),
        },
        context=SimpleNamespace(parent_id=None),
    )
    engine.handle_smart_lighting_state_changed(external_event)
    assert reaction.diagnostics()["manual_override_active"] is True


@pytest.mark.asyncio
async def test_lighting_domain_passes_step_context_id_to_service_call() -> None:
    class _FakeServices:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def async_call(self, domain, service, data, **kwargs):  # noqa: ANN001
            self.calls.append(
                {
                    "domain": domain,
                    "service": service,
                    "data": dict(data),
                    "kwargs": dict(kwargs),
                }
            )

    services = _FakeServices()
    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda entity_id: SimpleNamespace(state="off")),
        services=services,
    )
    domain = LightingDomain(hass, MagicMock())

    await domain.execute_lighting_steps(
        [
            ApplyStep(
                domain="lighting",
                target="studio",
                action="light.turn_on",
                params={"entity_id": "light.studio_main"},
                context_id="ctx-smart",
            )
        ]
    )

    assert len(services.calls) == 1
    context = services.calls[0]["kwargs"]["context"]
    assert context.id == "ctx-smart"


def test_smart_lighting_schedules_dim_then_off_after_absence() -> None:
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state="on")
    reaction = RoomSmartLightingAssistReaction(
        hass=hass,
        bucket_getter=lambda room_id, signal_name: "dark",
        room_id="corridor",
        indoor_lux_signal="room_lux",
        lux_on_buckets=["dark"],
        room_type="corridoio",
        timeout_mode="fixed",
        base_timeout_min=1,
        fast_exit_timeout_s=1,
        dim_ratio=0.5,
        entity_steps=[{"entity_id": "light.corridor", "action": "on", "brightness": 100}],
    )
    ts = datetime(2026, 6, 11, 10, tzinfo=UTC)

    assert reaction.evaluate([_snapshot(occupied_rooms=["corridor"], ts=ts.isoformat())])
    assert reaction.evaluate([_snapshot(occupied_rooms=[], ts=(ts + timedelta(seconds=2)).isoformat())]) == []

    jobs = reaction.scheduled_jobs("entry-1")
    assert sorted(jobs) == [
        f"smart_lighting_dim:{reaction.reaction_id}",
        f"smart_lighting_off:{reaction.reaction_id}",
    ]

    time.sleep(1.1)
    dim_steps = reaction.evaluate(
        [_snapshot(occupied_rooms=[], ts=(ts + timedelta(seconds=3)).isoformat())]
    )
    assert len(dim_steps) == 1
    assert dim_steps[0].action == "light.turn_on"
    assert dim_steps[0].params["brightness"] == 38

    off_steps = reaction.evaluate(
        [_snapshot(occupied_rooms=[], ts=(ts + timedelta(seconds=4)).isoformat())]
    )
    assert len(off_steps) == 1
    assert off_steps[0].action == "light.turn_off"


def test_build_smart_lighting_reaction_accepts_valid_contract() -> None:
    engine = SimpleNamespace(
        _hass=MagicMock(),
        _entry=SimpleNamespace(
            options={
                "rooms": [
                    {
                        "room_id": "studio",
                        "signals": [
                            {
                                "signal_name": "room_lux",
                                "buckets": [{"label": "dark"}, {"label": "dim"}],
                            }
                        ],
                    }
                ]
            }
        ),
        signal_bucket=lambda room_id, signal_name: None,
    )

    reaction = build_room_smart_lighting_assist_reaction(
        engine,
        "smart-test",
        {
            "room_id": "studio",
            "indoor_lux_signal": "room_lux",
            "lux_on_buckets": ["dark"],
            "entity_steps": [{"entity_id": "light.studio_main", "action": "on"}],
        },
    )

    assert reaction is not None
    assert reaction.reaction_id == "smart-test"
