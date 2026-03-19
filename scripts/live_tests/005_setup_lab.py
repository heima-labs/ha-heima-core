#!/usr/bin/env python3
"""Setup script for Heima test lab: creates HA areas and assigns light entities.

This script is idempotent and must run before the lighting tests (060+) so that
LightingRecorderBehavior can map light entities to rooms via the HA area registry.

What it does:
  1. Creates (or finds) HA areas for each test lab room via WebSocket API.
  2. Assigns the corresponding light entity to each area via WebSocket API.
  3. Updates area_id on existing Heima rooms via options flow.

Usage:
    python3 scripts/live_tests/005_setup_lab.py \\
        --ha-url http://127.0.0.1:8123 \\
        --ha-token <token>
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient
from lib.ha_websocket import HAWebSocketClient, HAWebSocketError

# Import recover_rooms from the recovery script (handles full room payload correctly)
_recover_script = Path(__file__).resolve().parent.parent / "recover_test_lab_config.py"
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("recover_test_lab_config", _recover_script)
assert _spec and _spec.loader
_recover_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_recover_mod)  # type: ignore[union-attr]
recover_rooms = _recover_mod.recover_rooms
HAFlowClient = _recover_mod.HAFlowClient

ROOM_AREA_NAMES: dict[str, str] = _recover_mod.ROOM_AREA_NAMES
ROOM_LIGHT_ENTITIES: dict[str, list[str]] = _recover_mod.ROOM_LIGHT_ENTITIES


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_create_areas(ws: HAWebSocketClient) -> dict[str, str]:
    """Create (or find) HA areas for each room. Returns {room_id: area_id}."""
    area_ids: dict[str, str] = {}
    for room_id, area_name in ROOM_AREA_NAMES.items():
        area_id = ws.get_or_create_area(area_name)
        area_ids[room_id] = area_id
        print(f"  area '{area_name}' → {area_id}")
    return area_ids


def step_assign_entities(ws: HAWebSocketClient, client: HAClient, area_ids: dict[str, str]) -> None:
    """Assign each light entity to its area."""
    for room_id, entity_ids in ROOM_LIGHT_ENTITIES.items():
        area_id = area_ids.get(room_id)
        if not area_id:
            print(f"  WARN: no area_id for room {room_id}, skip light assignment")
            continue
        for entity_id in entity_ids:
            if not client.entity_exists(entity_id):
                print(f"  WARN: entity {entity_id} not found in HA — skip")
                continue
            ws.assign_entity_to_area(entity_id, area_id)
            print(f"  {entity_id} → area {area_id}")


def step_update_heima_rooms(client: "HAFlowClient", entry_id: str, area_ids: dict[str, str]) -> None:
    """Update Heima rooms with area_id via options flow (reuses recover_rooms logic)."""
    recover_rooms(client, entry_id, area_ids=area_ids)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Heima test lab setup (areas + entity assignment)")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--ws-retries", type=int, default=5)
    parser.add_argument("--ws-retry-delay-s", type=float, default=2.0)
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token)

    print("1. Creazione/verifica aree HA (WebSocket)")
    last_ws_error: Exception | None = None
    area_ids: dict[str, str] = {}
    for attempt in range(1, args.ws_retries + 1):
        try:
            with HAWebSocketClient(args.ha_url, args.ha_token) as ws:
                area_ids = step_create_areas(ws)

                print("2. Assegnazione entità luce alle aree")
                step_assign_entities(ws, client, area_ids)
            last_ws_error = None
            break
        except HAWebSocketError as exc:
            last_ws_error = exc
            if attempt >= args.ws_retries:
                raise
            print(
                f"  WARN: websocket attempt {attempt}/{args.ws_retries} failed: {exc}; "
                f"retry in {args.ws_retry_delay_s:.1f}s"
            )
            time.sleep(args.ws_retry_delay_s)

    if last_ws_error is not None:
        raise last_ws_error

    print("3. Aggiornamento area_id nelle room Heima (options flow)")
    try:
        entry_id = client.find_heima_entry_id()
        step_update_heima_rooms(client, entry_id, area_ids)
    except HAApiError as exc:
        print(f"  WARN: impossibile aggiornare room Heima: {exc}")

    print("PASS: lab setup completato")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HAWebSocketError, Exception) as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
