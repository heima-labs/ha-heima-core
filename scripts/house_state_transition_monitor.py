#!/usr/bin/env python3
"""Capture Heima house-state diagnostics whenever the state changes."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ha_client import HAClient
from lib.ha_websocket import HAWebSocketClient, HAWebSocketError

DEFAULT_ENTITIES = (
    "sensor.heima_house_state",
    "sensor.heima_house_state_reason",
    "sensor.heima_house_state_path",
    "sensor.heima_health",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Watch sensor.heima_house_state and capture diagnostics on transitions."
    )
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--entry-id", default="")
    parser.add_argument("--entity-id", default="sensor.heima_house_state")
    parser.add_argument("--out-dir", default="debug/house_state_transitions")
    parser.add_argument("--timeout-s", type=float, default=24 * 60 * 60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = args.entry_id or client.find_heima_entry_id()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    initial_state = _state_value(client, args.entity_id)
    print(f"Watching {args.entity_id}; initial_state={initial_state}; output={out_dir}")

    with HAWebSocketClient(args.ha_url, args.ha_token) as ws:
        subscription_id = ws.subscribe_events("state_changed")
        deadline = time.monotonic() + args.timeout_s
        last_seen = initial_state
        captured = 0
        while time.monotonic() < deadline:
            remaining = max(1.0, deadline - time.monotonic())
            try:
                events = ws.wait_for_matching_events(
                    subscription_id,
                    timeout_s=remaining,
                    predicate=lambda rows: _has_target_change(rows, args.entity_id),
                )
            except HAWebSocketError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1

            event = _last_target_change(events, args.entity_id)
            if event is None:
                continue
            old_state, new_state = _state_change_values(event)
            if new_state == last_seen:
                continue
            last_seen = new_state
            captured += 1
            capture_dir = _capture_transition(
                client=client,
                ws=ws,
                entry_id=entry_id,
                out_dir=out_dir,
                event=event,
                watched_entity=args.entity_id,
                old_state=old_state,
                new_state=new_state,
            )
            print(f"Captured {old_state}->{new_state}: {capture_dir}")
            if args.once:
                return 0

    print("Timed out without further matching transitions.")
    return 2 if captured == 0 else 0


def _capture_transition(
    *,
    client: HAClient,
    ws: HAWebSocketClient,
    entry_id: str,
    out_dir: Path,
    event: dict[str, Any],
    watched_entity: str,
    old_state: str,
    new_state: str,
) -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_old = _safe_name(old_state or "unknown")
    safe_new = _safe_name(new_state or "unknown")
    capture_dir = out_dir / f"{ts}_{safe_old}_to_{safe_new}"
    capture_dir.mkdir(parents=True, exist_ok=True)

    states = {
        entity_id: _safe_get_state(client, entity_id)
        for entity_id in sorted(set(DEFAULT_ENTITIES + (watched_entity,)))
    }
    snapshot = ws.call("heima/observability/snapshot", entry_id=entry_id)
    summary = _house_state_summary(snapshot)

    _write_json(capture_dir / "state_changed_event.json", event)
    _write_json(capture_dir / "entity_states.json", states)
    _write_json(capture_dir / "observability_snapshot.json", snapshot)
    _write_json(capture_dir / "house_state_summary.json", summary)
    return capture_dir


def _house_state_summary(snapshot: Any) -> dict[str, Any]:
    data = snapshot if isinstance(snapshot, dict) else {}
    runtime = data.get("runtime") if isinstance(data.get("runtime"), dict) else {}
    house = data.get("house_state") if isinstance(data.get("house_state"), dict) else {}
    return {
        "runtime": {
            "house_state": runtime.get("house_state"),
            "house_state_reason": runtime.get("house_state_reason"),
            "last_decision": runtime.get("last_decision"),
            "snapshot_ts": (runtime.get("snapshot") or {}).get("ts")
            if isinstance(runtime.get("snapshot"), dict)
            else None,
        },
        "house_state": {
            "winning_reason": house.get("winning_reason"),
            "resolution_path": house.get("resolution_path"),
            "decision_action": house.get("decision_action"),
            "decision_target_state": house.get("decision_target_state"),
            "pending_candidate": house.get("pending_candidate"),
            "pending_remaining_s": house.get("pending_remaining_s"),
            "active_candidates": house.get("active_candidates"),
            "candidate_summary": house.get("candidate_summary"),
            "candidate_trace": house.get("candidate_trace"),
            "resolution_trace": house.get("resolution_trace"),
            "timers": house.get("timers"),
            "override": house.get("override"),
        },
    }


def _has_target_change(events: list[dict[str, Any]], entity_id: str) -> bool:
    return _last_target_change(events, entity_id) is not None


def _last_target_change(events: list[dict[str, Any]], entity_id: str) -> dict[str, Any] | None:
    for event in reversed(events):
        data = event.get("data")
        if isinstance(data, dict) and data.get("entity_id") == entity_id:
            return event
    return None


def _state_change_values(event: dict[str, Any]) -> tuple[str, str]:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    old_state = data.get("old_state") if isinstance(data.get("old_state"), dict) else {}
    new_state = data.get("new_state") if isinstance(data.get("new_state"), dict) else {}
    return str(old_state.get("state") or ""), str(new_state.get("state") or "")


def _state_value(client: HAClient, entity_id: str) -> str:
    return str(_safe_get_state(client, entity_id).get("state") or "")


def _safe_get_state(client: HAClient, entity_id: str) -> dict[str, Any]:
    try:
        return client.get_state(entity_id)
    except Exception as exc:  # noqa: BLE001
        return {"entity_id": entity_id, "error": f"{type(exc).__name__}: {exc}"}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
    return safe.strip("_") or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
