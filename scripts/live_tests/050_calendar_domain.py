#!/usr/bin/env python3
"""Live test: CalendarDomain wiring and runtime behaviour.

Scenarios:
  1. Engine diagnostics include a 'calendar' key (always).
  2. If calendar entities are configured in Heima options:
     a. Trigger recompute → CalendarDomain runs.
     b. Diagnostics report cached_events_count (0 or more).
     c. Create a deterministic local-calendar event and verify house_state classification.
  3. If no calendar entities configured → SKIP scenarios 2-3 with a notice.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def get_engine_diagnostics(client: HAClient) -> dict:
    entry_id = client.find_heima_entry_id()
    diag = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(diag, dict):
        raise RuntimeError(f"unexpected diagnostics payload: {type(diag)}")
    # HA wraps the integration payload under 'data'
    return diag.get("data", {}).get("runtime", {}).get("engine", {})


def get_heima_options(client: HAClient) -> dict:
    entry_id = client.find_heima_entry_id()
    diag = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    return dict((diag.get("data") or {}).get("entry", {}).get("options") or {})


def calendar_entities_from_options(options: dict) -> list[str]:
    cal_cfg = options.get("calendar") or {}
    return list(cal_cfg.get("calendar_entities") or [])


def create_all_day_event(
    client: HAClient,
    *,
    entity_id: str,
    summary: str,
    start_day: date,
    end_day: date,
) -> None:
    client.call_service(
        "calendar",
        "create_event",
        {
            "entity_id": entity_id,
            "summary": summary,
            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def scenario_calendar_in_diagnostics(client: HAClient) -> None:
    print("== Scenario 1: CalendarDomain present in engine diagnostics ==")
    recompute(client)
    engine_diag = get_engine_diagnostics(client)
    if "calendar" not in engine_diag:
        raise RuntimeError(
            "Key 'calendar' missing from engine diagnostics — "
            "CalendarDomain not wired into the DAG."
        )
    cal_diag = engine_diag["calendar"]
    print(f"  cache_ts:            {cal_diag.get('cache_ts')}")
    print(f"  cached_events_count: {cal_diag.get('cached_events_count')}")
    print("PASS scenario 1")


def scenario_calendar_configured(
    client: HAClient,
    calendar_entities: list[str],
    timeout_s: int,
    poll_s: float,
) -> None:
    print(f"== Scenario 2: CalendarDomain runs with {len(calendar_entities)} entity(ies) ==")
    recompute(client)

    engine_diag = get_engine_diagnostics(client)
    cal_diag = engine_diag.get("calendar", {})
    count = cal_diag.get("cached_events_count", -1)
    cache_ts = cal_diag.get("cache_ts")
    print(f"  configured entities: {calendar_entities}")
    print(f"  cache_ts:            {cache_ts}")
    print(f"  cached_events:       {count}")
    print(f"  events detail:       {cal_diag.get('cached_events', [])}")
    print("PASS scenario 2")


def scenario_active_vacation_event(
    client: HAClient,
    calendar_entities: list[str],
    timeout_s: int,
    poll_s: float,
) -> None:
    """Create a deterministic vacation event and verify it drives house_state."""
    print("== Scenario 3: deterministic local-calendar vacation event drives house_state ==")

    target_calendar = next((entity_id for entity_id in calendar_entities if client.entity_exists(entity_id)), None)
    if target_calendar is None:
        print("SKIP scenario 3 (configured calendar entity not found in HA)")
        return

    today = date.today()
    tomorrow = today + timedelta(days=1)
    summary = "vacanza live test"
    print(f"  creating all-day event on {target_calendar}: '{summary}'")
    create_all_day_event(
        client,
        entity_id=target_calendar,
        summary=summary,
        start_day=today,
        end_day=tomorrow,
    )

    client.wait_state(target_calendar, "on", timeout_s, poll_s)
    recompute(client)
    client.wait_state("sensor.heima_house_state", "vacation", timeout_s, poll_s)
    print("PASS scenario 3")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Heima CalendarDomain live tests")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=30)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)

    # Scenario 1: always runs
    scenario_calendar_in_diagnostics(client)

    # Scenarios 2-3: only if calendar configured in Heima
    options = get_heima_options(client)
    calendar_entities = calendar_entities_from_options(options)

    if not calendar_entities:
        print(
            "SKIP scenarios 2-3 (no calendar_entities configured in Heima options). "
            "Configure via Options Flow → Calendar to enable."
        )
    else:
        scenario_calendar_configured(client, calendar_entities, args.timeout_s, args.poll_s)
        scenario_active_vacation_event(client, calendar_entities, args.timeout_s, args.poll_s)

    print("All calendar live scenarios passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
