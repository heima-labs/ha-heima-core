#!/usr/bin/env python3
"""Destructive live checks for AQ runtime recovery.

This script intentionally mutates HA state-machine values and may restart the
local test Home Assistant container. It must never be part of default live
tiers.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient
from lib.ha_websocket import HAWebSocketClient

OFFLINE_DRIFT_ENTITY = "binary_sensor.test_heima_room_studio_motion"
OFFLINE_DRIFT_RESTORE_ENTITY = "input_boolean.test_heima_room_studio_motion_raw"
OFFLINE_DRIFT_EXPECTED_KIND = "unknown_during_downtime"
DEFAULT_RESTORE_STATE_PATH = (
    "docs/examples/ha_test_instance/docker/ha_config/.storage/core.restore_state"
)
DEFAULT_CHECKPOINT_STATE_PATH = (
    "docs/examples/ha_test_instance/docker/ha_config/.storage/heima_runtime_checkpoints"
)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _snapshot(base_url: str, token: str, entry_id: str) -> dict[str, Any]:
    with HAWebSocketClient(base_url, token, timeout=30) as ws:
        result = ws.call("heima/observability/snapshot", entry_id=entry_id)
    _assert(isinstance(result, dict), f"snapshot result must be a dict: {type(result)}")
    return cast(dict[str, Any], result)


def _recovery(snapshot: dict[str, Any]) -> dict[str, Any]:
    recovery = snapshot.get("recovery")
    _assert(isinstance(recovery, dict), "snapshot.recovery must be a dict")
    return cast(dict[str, Any], recovery)


def _critical_entities(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    critical = _recovery(snapshot).get("critical_entities")
    _assert(isinstance(critical, dict), "recovery.critical_entities must be a dict")
    items = critical.get("items")
    _assert(isinstance(items, list), "recovery.critical_entities.items must be a list")
    rows = [dict(item) for item in items if isinstance(item, dict)]
    _assert(len(rows) >= 3, f"expected at least 3 recovery critical entities, got {len(rows)}")
    return rows


def _event_types(snapshot: dict[str, Any]) -> set[str]:
    events = _recovery(snapshot).get("recent_events")
    if not isinstance(events, list):
        return set()
    return {
        str(item.get("reason_code") or item.get("type") or item.get("key") or "")
        for item in events
        if isinstance(item, dict)
    }


def _call_recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _write_runtime_checkpoint(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "write_runtime_checkpoint"})


def _wait_snapshot(
    client: HAClient,
    *,
    entry_id: str,
    predicate: Any,
    timeout_s: int,
    poll_s: float,
    description: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last: dict[str, Any] | None = None
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            _call_recompute(client)
            last = _snapshot(client.base_url, client.token, entry_id)
            if predicate(last):
                return last
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(poll_s)
    if last is None:
        raise AssertionError(f"Timed out waiting for {description}; last error={last_error}")
    recovery = _recovery(last)
    raise AssertionError(
        f"Timed out waiting for {description}; "
        f"last recovery state={recovery.get('state')!r} reason={recovery.get('reason')!r}"
    )


def _set_state(client: HAClient, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
    client.post(f"/api/states/{entity_id}", {"state": state, "attributes": attributes})


def _entity_ids_for_unavailable_burst(snapshot: dict[str, Any]) -> list[str]:
    rows = _critical_entities(snapshot)
    available_rows = [row for row in rows if row.get("available") is True]
    _assert(available_rows, "no available critical entities can be forced unavailable")
    total = len(rows)
    needed = max(1, math.ceil(total * 0.35))
    selected = [
        str(row.get("entity_id"))
        for row in available_rows[:needed]
        if str(row.get("entity_id") or "").strip()
    ]
    _assert(
        len(selected) >= needed,
        f"not enough selectable critical entities: needed={needed}, selected={len(selected)}",
    )
    return selected


def _restore_states(client: HAClient, originals: dict[str, dict[str, Any]]) -> None:
    for entity_id, original in originals.items():
        state = str(original.get("state") or "unknown")
        attributes = original.get("attributes")
        _set_state(client, entity_id, state, attributes if isinstance(attributes, dict) else {})


def _docker(args: argparse.Namespace, command: str) -> None:
    _assert(args.docker_container, f"docker {command} requires --docker-container")
    proc = subprocess.run(
        ["docker", command, args.docker_container],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=args.restart_timeout_s,
    )
    _assert(
        proc.returncode == 0,
        f"docker {command} failed: stdout={proc.stdout.strip()} stderr={proc.stderr.strip()}",
    )


def _assert_checkpoint_usable(snapshot: dict[str, Any]) -> None:
    checkpoint = _recovery(snapshot).get("checkpoint")
    _assert(isinstance(checkpoint, dict), "recovery.checkpoint must be a dict")
    _assert(checkpoint.get("available") is True, "runtime checkpoint must be available")
    _assert(checkpoint.get("usable") is True, f"runtime checkpoint is not usable: {checkpoint}")
    store = checkpoint.get("store")
    _assert(isinstance(store, dict), "recovery.checkpoint.store must be a dict")
    _assert(int(store.get("entry_count") or 0) >= 1, "checkpoint store must contain an entry")


def _ensure_checkpoint_usable(
    client: HAClient,
    *,
    entry_id: str,
    timeout_s: int,
    poll_s: float,
    description: str,
) -> dict[str, Any]:
    _write_runtime_checkpoint(client)
    snapshot = _wait_snapshot(
        client,
        entry_id=entry_id,
        predicate=lambda snap: bool(_recovery(snap).get("checkpoint", {}).get("usable")),
        timeout_s=timeout_s,
        poll_s=poll_s,
        description=description,
    )
    _assert_checkpoint_usable(snapshot)
    return snapshot


def _run_unavailable_burst(client: HAClient, entry_id: str, args: argparse.Namespace) -> None:
    print("== AQ destructive: critical entity unavailable burst ==")
    baseline = _wait_snapshot(
        client,
        entry_id=entry_id,
        predicate=lambda snap: not bool(_recovery(snap).get("active")),
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        description="recovery inactive before destructive burst",
    )
    _ensure_checkpoint_usable(
        client,
        entry_id=entry_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        description="usable checkpoint before destructive burst",
    )
    selected = _entity_ids_for_unavailable_burst(baseline)
    originals: dict[str, dict[str, Any]] = {}
    try:
        for entity_id in selected:
            originals[entity_id] = client.get_state(entity_id)
            attrs = originals[entity_id].get("attributes")
            _set_state(client, entity_id, "unavailable", attrs if isinstance(attrs, dict) else {})

        power_snapshot = _wait_snapshot(
            client,
            entry_id=entry_id,
            predicate=lambda snap: _recovery(snap).get("state") == "power_recovery",
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
            description="power_recovery after forcing critical entities unavailable",
        )
        recovery = _recovery(power_snapshot)
        _assert(
            int(recovery.get("critical_entities", {}).get("unavailable") or 0) >= len(selected),
            "forced unavailable entities are not reflected in recovery observability",
        )
        _assert(
            "recovery_power_outage_suspected" in _event_types(power_snapshot),
            "missing recovery power outage event",
        )
    finally:
        _restore_states(client, originals)
        _call_recompute(client)

    restored = _wait_snapshot(
        client,
        entry_id=entry_id,
        predicate=lambda snap: _recovery(snap).get("state") in {"recovery_settling", "normal"},
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        description="recovery_settling after restoring critical entities",
    )
    event_types = _event_types(restored)
    _assert(
        event_types.intersection({"recovery_power_restored", "recovery_stabilization_started"}),
        f"missing restoration recovery event, observed={sorted(event_types)}",
    )

    final = _wait_snapshot(
        client,
        entry_id=entry_id,
        predicate=lambda snap: not bool(_recovery(snap).get("active")),
        timeout_s=max(args.timeout_s, 90),
        poll_s=args.poll_s,
        description="normal recovery after stabilization",
    )
    _assert(
        "recovery_completed" in _event_types(final),
        "missing recovery completed event after stabilization",
    )


def _wait_ha_api(client: HAClient, *, timeout_s: int, poll_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            client.get("/api/")
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(poll_s)
    raise HAApiError(f"Home Assistant API did not return after restart: {last}")


def _run_restart_checkpoint_check(
    client: HAClient, entry_id: str, args: argparse.Namespace
) -> None:
    if not args.docker_container:
        print("SKIP: restart checkpoint check requires --docker-container")
        return

    print("== AQ destructive: HA restart checkpoint recovery ==")
    _wait_snapshot(
        client,
        entry_id=entry_id,
        predicate=lambda snap: not bool(_recovery(snap).get("active")),
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        description="recovery inactive before HA restart",
    )
    _ensure_checkpoint_usable(
        client,
        entry_id=entry_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        description="usable checkpoint before HA restart",
    )

    _docker(args, "restart")

    _wait_ha_api(client, timeout_s=args.restart_timeout_s, poll_s=args.poll_s)
    restarted_client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=30)
    restarted_entry_id = restarted_client.find_heima_entry_id()
    _assert(
        restarted_entry_id == entry_id,
        f"Heima entry changed across restart: before={entry_id}, after={restarted_entry_id}",
    )

    after = _wait_snapshot(
        restarted_client,
        entry_id=entry_id,
        predicate=lambda snap: bool(_recovery(snap).get("checkpoint", {}).get("available")),
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        description="checkpoint available after HA restart",
    )
    _assert_checkpoint_usable(after)
    _assert(
        _event_types(after).intersection(
            {
                "recovery_startup_started",
                "recovery_stabilization_started",
                "recovery_completed",
            }
        ),
        "missing startup recovery event after HA restart",
    )


def _set_raw_helper(client: HAClient, entity_id: str, state: str) -> None:
    service = "turn_on" if state == "on" else "turn_off"
    client.call_service("input_boolean", service, {"entity_id": entity_id})


def _restore_state_file_path(args: argparse.Namespace) -> Path:
    path = Path(args.restore_state_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    _assert(path.exists(), f"restore state file not found: {path}")
    return path


def _checkpoint_state_file_path(args: argparse.Namespace) -> Path:
    path = Path(args.checkpoint_state_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    _assert(path.exists(), f"checkpoint state file not found: {path}")
    return path


def _mutate_restore_state(path: Path, entity_id: str, state: str) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    data = raw.get("data")
    _assert(isinstance(data, list), "core.restore_state data must be a list")
    for item in data:
        if not isinstance(item, dict):
            continue
        state_obj = item.get("state")
        if not isinstance(state_obj, dict):
            continue
        if state_obj.get("entity_id") != entity_id:
            continue
        state_obj["state"] = state
        path.write_text(json.dumps(raw, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        return
    raise AssertionError(f"{entity_id} not found in {path}")


def _mutate_checkpoint_entity(
    path: Path,
    *,
    entry_id: str,
    entity_id: str,
    state: str,
) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = ((raw.get("data") or {}).get("data") or {}).get("entries") or {}
    _assert(isinstance(entries, dict), "heima_runtime_checkpoints entries must be a dict")
    checkpoint = entries.get(entry_id)
    _assert(isinstance(checkpoint, dict), f"checkpoint not found for entry {entry_id}")
    checkpoint["created_at"] = datetime.now(UTC).isoformat()
    checkpoint["reason"] = "live_test:offline_restore_drift"
    runtime = checkpoint.get("runtime")
    if isinstance(runtime, dict):
        runtime_context = runtime.get("runtime_context")
        if isinstance(runtime_context, dict):
            runtime_context.update(
                {
                    "runtime.recovery.state": "normal",
                    "runtime.recovery.reason": "normal",
                    "runtime.recovery.active": False,
                    "runtime.recovery.unavailable_ratio": 0.0,
                    "runtime.recovery.unavailable_count": 0,
                }
            )
    for item in checkpoint.get("critical_entities") or []:
        if not isinstance(item, dict):
            continue
        if item.get("entity_id") != entity_id:
            continue
        item["state"] = state
        path.write_text(json.dumps(raw, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        return
    raise AssertionError(f"{entity_id} not found in checkpoint critical entities")


def _wait_checkpoint_difference(
    client: HAClient,
    entry_id: str,
    *,
    entity_id: str,
    expected_kind: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    def predicate(snapshot: dict[str, Any]) -> bool:
        checkpoint = _recovery(snapshot).get("checkpoint")
        if not isinstance(checkpoint, dict):
            return False
        for difference in checkpoint.get("differences") or []:
            if not isinstance(difference, dict):
                continue
            if difference.get("entity_id") == entity_id and difference.get("kind") == expected_kind:
                return True
        return False

    return _wait_snapshot(
        client,
        entry_id=entry_id,
        predicate=predicate,
        timeout_s=timeout_s,
        poll_s=poll_s,
        description=f"checkpoint difference for {entity_id}",
    )


def _run_offline_restore_drift_check(
    client: HAClient, entry_id: str, args: argparse.Namespace
) -> None:
    if not args.docker_container:
        print("SKIP: offline restore drift check requires --docker-container")
        return

    print("== AQ destructive: offline restore-state drift ==")
    restore_path = _restore_state_file_path(args)
    checkpoint_path = _checkpoint_state_file_path(args)
    restore_backup = restore_path.read_bytes()
    checkpoint_backup = checkpoint_path.read_bytes()
    original_restore_state = client.state_value(OFFLINE_DRIFT_RESTORE_ENTITY)
    original_derived_state = client.state_value(OFFLINE_DRIFT_ENTITY)
    try:
        _set_raw_helper(client, OFFLINE_DRIFT_RESTORE_ENTITY, "off")
        client.wait_state(OFFLINE_DRIFT_ENTITY, "off", args.timeout_s, args.poll_s)
        _call_recompute(client)
        _ensure_checkpoint_usable(
            client,
            entry_id=entry_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
            description="usable checkpoint before offline restore drift",
        )

        _docker(args, "stop")
        _mutate_checkpoint_entity(
            checkpoint_path,
            entry_id=entry_id,
            entity_id=OFFLINE_DRIFT_ENTITY,
            state="off",
        )
        _mutate_restore_state(restore_path, OFFLINE_DRIFT_RESTORE_ENTITY, "on")
        _docker(args, "start")
        _wait_ha_api(client, timeout_s=args.restart_timeout_s, poll_s=args.poll_s)

        restarted_client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=30)
        restarted_client.wait_state(OFFLINE_DRIFT_ENTITY, "on", args.timeout_s, args.poll_s)
        drift_snapshot = _wait_checkpoint_difference(
            restarted_client,
            entry_id,
            entity_id=OFFLINE_DRIFT_ENTITY,
            expected_kind=OFFLINE_DRIFT_EXPECTED_KIND,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        differences = _recovery(drift_snapshot).get("checkpoint", {}).get("differences") or []
        matching = [
            item
            for item in differences
            if isinstance(item, dict) and item.get("entity_id") == OFFLINE_DRIFT_ENTITY
        ]
        _assert(matching, "missing offline drift checkpoint difference details")
        _assert(
            matching[0].get("checkpoint_state") == "off"
            and matching[0].get("current_state") == "on",
            f"unexpected checkpoint difference: {matching[0]}",
        )
    finally:
        try:
            if args.docker_container:
                subprocess.run(
                    ["docker", "stop", args.docker_container],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=args.restart_timeout_s,
                )
            restore_path.write_bytes(restore_backup)
            checkpoint_path.write_bytes(checkpoint_backup)
            if args.docker_container:
                subprocess.run(
                    ["docker", "start", args.docker_container],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=args.restart_timeout_s,
                )
            restored_client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=30)
            _wait_ha_api(restored_client, timeout_s=args.restart_timeout_s, poll_s=args.poll_s)
            if original_restore_state in {"on", "off"}:
                _set_raw_helper(
                    restored_client,
                    OFFLINE_DRIFT_RESTORE_ENTITY,
                    original_restore_state,
                )
                restored_client.wait_state(
                    OFFLINE_DRIFT_ENTITY,
                    original_derived_state,
                    args.timeout_s,
                    args.poll_s,
                )
            _call_recompute(restored_client)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: failed to restore offline drift state completely: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--allow-destructive", action="store_true")
    parser.add_argument("--docker-container", default="")
    parser.add_argument("--restore-state-path", default=DEFAULT_RESTORE_STATE_PATH)
    parser.add_argument("--checkpoint-state-path", default=DEFAULT_CHECKPOINT_STATE_PATH)
    parser.add_argument("--timeout-s", type=int, default=240)
    parser.add_argument("--restart-timeout-s", type=int, default=180)
    parser.add_argument("--poll-s", type=float, default=2.0)
    args = parser.parse_args()

    if not args.allow_destructive:
        raise SystemExit("--allow-destructive is required")

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=30)
    entry_id = client.find_heima_entry_id()
    _run_unavailable_burst(client, entry_id, args)
    _run_restart_checkpoint_check(client, entry_id, args)
    _run_offline_restore_drift_check(client, entry_id, args)

    print("PASS: AQ destructive recovery live checks")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
