#!/usr/bin/env python3
"""Generate deterministic learning fixture storage for the Docker test lab.

The lighting-learning live scenario needs real historical events, but the
analyzer requires at least 5 user lighting events spanning at least 2 weeks.
This generator prepares a baseline with 4 historical occurrences per weekday
for the living-evening scene. A live test can then add the 5th occurrence for
the current weekday through real HA entity changes, without using seeded
runtime commands.
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
        "(4 historical occurrences per weekday for the living evening scene)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
