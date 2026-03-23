#!/usr/bin/env python3
"""Generate deterministic learning fixture storage for the Docker test lab.

The live learning scenarios need real historical events, but analyzers require
enough prior repetitions to emit proposals. This generator prepares:
- lighting baseline: 4 historical occurrences per weekday for the living-evening scene
- cross-domain baseline: 4 historical bathroom shower/ventilation episodes
- cross-domain baseline: 4 historical studio cooling/fan episodes
- cross-domain baseline: 4 historical studio CO2/ventilation episodes

A live test can then add the final real occurrence through HA entities without
using seeded runtime commands.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_STORAGE_DIR = Path(
    "docs/examples/ha_test_instance/docker/ha_config/.storage"
)
LOCAL_TZ = ZoneInfo("Europe/Rome")
SCENE_MINUTE_OF_DAY = 19 * 60 + 30


def _recent_past_weekday_dates(today_local: date, weekday: int, count: int) -> list[date]:
    """Return the previous `count` occurrences of weekday strictly before today."""
    delta = (today_local.weekday() - weekday) % 7
    latest = today_local - timedelta(days=delta)
    if latest >= today_local:
        latest -= timedelta(weeks=1)
    dates: list[date] = []
    cursor = latest
    for _ in range(count):
        dates.append(cursor)
        cursor -= timedelta(weeks=1)
    dates.reverse()
    return dates


def _event_context(*, day: date, weekday: int) -> dict[str, object]:
    return {
        "weekday": weekday,
        "minute_of_day": SCENE_MINUTE_OF_DAY,
        "month": day.month,
        "house_state": "home",
        "occupants_count": 1,
        "occupied_rooms": ["living"],
        "outdoor_lux": None,
        "outdoor_temp": None,
        "weather_condition": None,
        "signals": {},
    }


def _room_event_context(*, day: date, room_id: str, at: time) -> dict[str, object]:
    local_dt = datetime.combine(day, at, tzinfo=LOCAL_TZ)
    return {
        "weekday": local_dt.weekday(),
        "minute_of_day": at.hour * 60 + at.minute,
        "month": day.month,
        "house_state": "home",
        "occupants_count": 1,
        "occupied_rooms": [room_id],
        "outdoor_lux": None,
        "outdoor_temp": None,
        "weather_condition": None,
        "signals": {},
    }


def _lighting_event(
    *,
    day: date,
    weekday: int,
    entity_id: str,
    action: str,
    brightness: int | None,
    color_temp_kelvin: int | None,
    correlation_id: str,
) -> dict[str, object]:
    local_dt = datetime.combine(day, time(19, 30), tzinfo=LOCAL_TZ)
    utc_ts = local_dt.astimezone(UTC).isoformat()
    return {
        "ts": utc_ts,
        "event_type": "lighting",
        "context": _event_context(day=day, weekday=weekday),
        "source": "user",
        "data": {
            "entity_id": entity_id,
            "room_id": "living",
            "action": action,
            "scene": None,
            "brightness": brightness,
            "color_temp_kelvin": color_temp_kelvin,
            "rgb_color": None,
        },
        "domain": "lighting",
        "subject_type": "entity",
        "subject_id": entity_id,
        "room_id": "living",
        "correlation_id": correlation_id,
    }


def _state_change_event(
    *,
    day: date,
    at: time,
    entity_id: str,
    room_id: str,
    context_at: time,
    old_state: str,
    new_state: str,
    unit_of_measurement: str | None,
    device_class: str | None,
    correlation_id: str,
) -> dict[str, object]:
    local_dt = datetime.combine(day, at, tzinfo=LOCAL_TZ)
    utc_ts = local_dt.astimezone(UTC).isoformat()
    domain = entity_id.split(".", 1)[0]
    return {
        "ts": utc_ts,
        "event_type": "state_change",
        "context": _room_event_context(day=day, room_id=room_id, at=context_at),
        "source": "unknown",
        "data": {
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": new_state,
            "unit_of_measurement": unit_of_measurement,
            "device_class": device_class,
        },
        "domain": domain,
        "subject_type": "entity",
        "subject_id": entity_id,
        "room_id": room_id,
        "correlation_id": correlation_id,
    }


def build_pattern_events(today_local: date) -> dict[str, object]:
    events: list[dict[str, object]] = []
    scene_entities = [
        ("light.test_heima_living_main", "on", 190, 2850),
        ("light.test_heima_living_spot", "on", 96, 3200),
        ("light.test_heima_living_floor", "off", None, None),
    ]
    for weekday in range(7):
        for day in _recent_past_weekday_dates(today_local, weekday, count=4):
            correlation_id = f"fixture-living-evening-{day.isoformat()}"
            for entity_id, action, brightness, color_temp_kelvin in scene_entities:
                events.append(
                    _lighting_event(
                        day=day,
                        weekday=weekday,
                        entity_id=entity_id,
                        action=action,
                        brightness=brightness,
                        color_temp_kelvin=color_temp_kelvin,
                        correlation_id=correlation_id,
                    )
                )
    return {
        "version": 1,
        "minor_version": 1,
        "key": "heima_pattern_events",
        "data": {"data": {"events": events}},
    }


def build_cross_domain_events(today_local: date) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base_days = _recent_past_weekday_dates(today_local, today_local.weekday(), count=4)
    for day in base_days:
        correlation_id = f"fixture-bathroom-shower-{day.isoformat()}"
        events.extend(
            [
                _state_change_event(
                    day=day,
                    at=time(7, 30),
                    entity_id="sensor.test_heima_bathroom_humidity",
                    room_id="bathroom",
                    context_at=time(7, 30),
                    old_state="55",
                    new_state="66",
                    unit_of_measurement="%",
                    device_class="humidity",
                    correlation_id=correlation_id,
                ),
                _state_change_event(
                    day=day,
                    at=time(7, 33),
                    entity_id="sensor.test_heima_bathroom_temperature",
                    room_id="bathroom",
                    context_at=time(7, 30),
                    old_state="21.0",
                    new_state="22.1",
                    unit_of_measurement="°C",
                    device_class="temperature",
                    correlation_id=correlation_id,
                ),
                _state_change_event(
                    day=day,
                    at=time(7, 35),
                    entity_id="switch.test_heima_bathroom_fan",
                    room_id="bathroom",
                    context_at=time(7, 30),
                    old_state="off",
                    new_state="on",
                    unit_of_measurement=None,
                    device_class=None,
                    correlation_id=correlation_id,
                ),
            ]
        )
    return events


def build_cooling_events(today_local: date) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base_days = _recent_past_weekday_dates(today_local, today_local.weekday(), count=4)
    for day in base_days:
        correlation_id = f"fixture-studio-cooling-{day.isoformat()}"
        events.extend(
            [
                _state_change_event(
                    day=day,
                    at=time(15, 0),
                    entity_id="sensor.test_heima_studio_temperature",
                    room_id="studio",
                    context_at=time(15, 0),
                    old_state="24.0",
                    new_state="25.8",
                    unit_of_measurement="°C",
                    device_class="temperature",
                    correlation_id=correlation_id,
                ),
                _state_change_event(
                    day=day,
                    at=time(15, 2),
                    entity_id="sensor.test_heima_studio_humidity",
                    room_id="studio",
                    context_at=time(15, 0),
                    old_state="52",
                    new_state="58",
                    unit_of_measurement="%",
                    device_class="humidity",
                    correlation_id=correlation_id,
                ),
                _state_change_event(
                    day=day,
                    at=time(15, 5),
                    entity_id="switch.test_heima_studio_fan",
                    room_id="studio",
                    context_at=time(15, 0),
                    old_state="off",
                    new_state="on",
                    unit_of_measurement=None,
                    device_class=None,
                    correlation_id=correlation_id,
                ),
            ]
        )
    return events


def build_air_quality_events(today_local: date) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base_days = _recent_past_weekday_dates(today_local, today_local.weekday(), count=4)
    for day in base_days:
        correlation_id = f"fixture-studio-air-quality-{day.isoformat()}"
        events.extend(
            [
                _state_change_event(
                    day=day,
                    at=time(10, 0),
                    entity_id="sensor.test_heima_studio_co2",
                    room_id="studio",
                    context_at=time(10, 0),
                    old_state="700",
                    new_state="940",
                    unit_of_measurement="ppm",
                    device_class="carbon_dioxide",
                    correlation_id=correlation_id,
                ),
                _state_change_event(
                    day=day,
                    at=time(10, 4),
                    entity_id="switch.test_heima_studio_fan",
                    room_id="studio",
                    context_at=time(10, 0),
                    old_state="off",
                    new_state="on",
                    unit_of_measurement=None,
                    device_class=None,
                    correlation_id=correlation_id,
                ),
            ]
        )
    return events


def build_proposals_fixture() -> dict[str, object]:
    return {
        "version": 1,
        "minor_version": 1,
        "key": "heima_proposals",
        "data": {"data": {"proposals": []}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Docker lab learning fixtures")
    parser.add_argument(
        "--storage-dir",
        default=str(DEFAULT_STORAGE_DIR),
        help="Target .storage directory for fixture files",
    )
    args = parser.parse_args()

    storage_dir = Path(args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    today_local = datetime.now(LOCAL_TZ).date()
    events_fixture = build_pattern_events(today_local)
    combined_events = list(events_fixture["data"]["data"]["events"])
    combined_events.extend(build_cross_domain_events(today_local))
    combined_events.extend(build_cooling_events(today_local))
    combined_events.extend(build_air_quality_events(today_local))
    events_fixture["data"]["data"]["events"] = combined_events
    proposals_fixture = build_proposals_fixture()

    events_path = storage_dir / "heima_pattern_events"
    proposals_path = storage_dir / "heima_proposals"
    events_path.write_text(json.dumps(events_fixture, indent=2) + "\n")
    proposals_path.write_text(json.dumps(proposals_fixture, indent=2) + "\n")

    print(f"Wrote {events_path}")
    print(f"Wrote {proposals_path}")
    print(
        "Generated lighting baseline: "
        f"{len(events_fixture['data']['data']['events'])} events "
        "("
        "lighting history + 4 bathroom humidity/ventilation episodes + "
        "4 studio cooling episodes + 4 studio CO2/ventilation episodes"
        ")"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
