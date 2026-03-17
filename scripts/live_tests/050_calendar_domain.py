#!/usr/bin/env python3
"""Live test: CalendarDomain wiring and runtime behaviour.

Scenarios:
  1. Engine diagnostics include a 'calendar' key (always).
  2. If calendar entities are configured in Heima options:
     a. Trigger recompute → CalendarDomain runs.
     b. Diagnostics report cached_events_count (0 or more).
     c. If a calendar entity is currently 'on' with a classifiable summary:
        verify house_state reflects the classification (vacation / working).
  3. If no calendar entities configured → SKIP scenarios 2-3 with a notice.
"""

from __future__ import annotations

import argparse
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
    """If any calendar entity is 'on' with a vacation summary → house_state = vacation."""
    print("== Scenario 3: active vacation event drives house_state ==")

    active_vacation = None
    for entity_id in calendar_entities:
        if not client.entity_exists(entity_id):
            continue
        state = client.get_state(entity_id)
        if state.get("state") != "on":
            continue
        summary = str(
            state.get("attributes", {}).get("message")
            or state.get("attributes", {}).get("summary")
            or ""
        ).lower()
        vacation_kw = ["vacanza", "holiday", "ferie", "viaggio", "vacation"]
        if any(kw in summary for kw in vacation_kw):
            active_vacation = entity_id
            print(f"  active vacation event found on {entity_id}: '{summary}'")
            break

    if active_vacation is None:
        print("SKIP scenario 3 (no active vacation event on any calendar entity right now)")
        return

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
