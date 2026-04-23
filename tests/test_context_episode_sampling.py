from __future__ import annotations

from custom_components.heima.runtime.analyzers.context_episode_sampling import (
    build_lighting_context_dataset,
    canonical_context_signal_name,
    canonical_context_state,
    canonicalize_context_snapshot,
)
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent


def _lighting(
    *,
    ts: str,
    entity_id: str,
    room_id: str = "studio",
    weekday: int = 1,
    minute: int = 20 * 60,
    action: str = "on",
    brightness: int | None = None,
    signals: dict[str, str] | None = None,
    house_state: str = "home",
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=EventContext(
            weekday=weekday,
            minute_of_day=minute,
            month=4,
            house_state=house_state,
            occupants_count=1,
            occupied_rooms=(room_id,),
            outdoor_lux=None,
            outdoor_temp=None,
            weather_condition=None,
            signals=signals or {},
        ),
        source="user",
        domain="light",
        subject_type="entity",
        subject_id=entity_id,
        room_id=room_id,
        data={
            "entity_id": entity_id,
            "room_id": room_id,
            "action": action,
            "brightness": brightness,
            "color_temp_kelvin": None,
            "rgb_color": None,
        },
    )


def test_canonical_context_signal_name_is_abstract():
    assert canonical_context_signal_name("media_player.projector") == "projector_context"
    assert canonical_context_signal_name("binary_sensor.tv") == "tv_context"
    assert canonical_context_signal_name("bad") is None


def test_canonical_context_state_maps_to_bounded_states():
    assert canonical_context_state("playing") == "active"
    assert canonical_context_state("on") == "active"
    assert canonical_context_state("paused") == "idle"
    assert canonical_context_state("standby") == "inactive"
    assert canonical_context_state("weird_custom_state") is None


def test_canonical_context_snapshot_uses_abstract_signal_names():
    snapshot = canonicalize_context_snapshot(
        {
            "media_player.projector": "playing",
            "binary_sensor.tv": "off",
            "sensor.ignored": "42",
        }
    )

    assert snapshot == {
        "projector_context": "active",
        "tv_context": "inactive",
    }


def test_build_lighting_context_dataset_extracts_positive_and_negative_episodes():
    target_steps = [
        {"entity_id": "light.studio_main", "action": "off"},
        {"entity_id": "light.studio_spot", "action": "on", "brightness": 80},
    ]
    events = [
        _lighting(
            ts="2026-04-07T18:00:00+00:00",
            entity_id="light.studio_main",
            action="off",
            signals={"media_player.projector": "playing"},
        ),
        _lighting(
            ts="2026-04-07T18:00:00+00:00",
            entity_id="light.studio_spot",
            action="on",
            brightness=80,
            signals={"media_player.projector": "playing"},
        ),
        _lighting(
            ts="2026-04-14T18:04:00+00:00",
            entity_id="light.studio_main",
            action="off",
            minute=20 * 60 + 4,
            signals={"media_player.projector": "playing"},
        ),
        _lighting(
            ts="2026-04-14T18:04:00+00:00",
            entity_id="light.studio_spot",
            action="on",
            brightness=80,
            minute=20 * 60 + 4,
            signals={"media_player.projector": "playing"},
        ),
        _lighting(
            ts="2026-04-21T18:03:00+00:00",
            entity_id="light.studio_main",
            action="on",
            brightness=120,
            minute=20 * 60 + 3,
            signals={"media_player.projector": "off"},
        ),
    ]

    dataset = build_lighting_context_dataset(
        events=events,
        room_id="studio",
        weekday=1,
        scheduled_min=20 * 60,
        window_half_min=10,
        entity_steps=target_steps,
    )

    assert len(dataset.positive_episodes) == 2
    assert len(dataset.negative_episodes) == 1
    assert dataset.positive_episodes[0].context_signals == {"projector_context": "active"}
    assert dataset.negative_episodes[0].context_signals == {"projector_context": "inactive"}


def test_build_lighting_context_dataset_excludes_unrelated_room_and_time():
    target_steps = [{"entity_id": "light.studio_spot", "action": "on", "brightness": 80}]
    events = [
        _lighting(
            ts="2026-04-07T18:00:00+00:00",
            entity_id="light.studio_spot",
            action="on",
            brightness=80,
            signals={"media_player.projector": "playing"},
        ),
        _lighting(
            ts="2026-04-14T18:45:00+00:00",
            entity_id="light.studio_spot",
            action="off",
            minute=20 * 60 + 45,
            signals={"media_player.projector": "off"},
        ),
        _lighting(
            ts="2026-04-14T18:03:00+00:00",
            entity_id="light.living_spot",
            room_id="living",
            action="off",
            minute=20 * 60 + 3,
            signals={"media_player.projector": "off"},
        ),
        _lighting(
            ts="2026-04-14T18:04:00+00:00",
            entity_id="light.studio_spot",
            action="off",
            weekday=2,
            minute=20 * 60 + 4,
            signals={"media_player.projector": "off"},
        ),
    ]

    dataset = build_lighting_context_dataset(
        events=events,
        room_id="studio",
        weekday=1,
        scheduled_min=20 * 60,
        window_half_min=10,
        entity_steps=target_steps,
    )

    assert len(dataset.positive_episodes) == 1
    assert len(dataset.negative_episodes) == 0


def test_build_lighting_context_dataset_respects_house_state_filter():
    target_steps = [{"entity_id": "light.studio_spot", "action": "on", "brightness": 80}]
    events = [
        _lighting(
            ts="2026-04-07T18:00:00+00:00",
            entity_id="light.studio_spot",
            action="on",
            brightness=80,
            house_state="home",
            signals={"media_player.projector": "playing"},
        ),
        _lighting(
            ts="2026-04-14T18:00:00+00:00",
            entity_id="light.studio_spot",
            action="off",
            house_state="working",
            signals={"media_player.projector": "off"},
        ),
    ]

    dataset = build_lighting_context_dataset(
        events=events,
        room_id="studio",
        weekday=1,
        scheduled_min=20 * 60,
        window_half_min=10,
        entity_steps=target_steps,
        house_state_filter="home",
    )

    assert len(dataset.positive_episodes) == 1
    assert len(dataset.negative_episodes) == 0
