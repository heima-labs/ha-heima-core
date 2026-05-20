#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Live diagnostic check for Phase O snapshot field alignment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient

HA_TEST_CONTAINER = "homeassistant-test"
SNAPSHOT_STORAGE_PATH = "/config/.storage/heima_snapshots"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        raise HAApiError(f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise HAApiError("diagnostics payload missing data object")
    return data


def _engine_snapshot(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
    snapshot = engine.get("snapshot", {}) if isinstance(engine, dict) else {}
    if not isinstance(snapshot, dict):
        raise HAApiError(f"invalid engine snapshot payload: {type(snapshot)}")
    return snapshot


def _load_snapshot_storage(container: str) -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["docker", "exec", container, "cat", SNAPSHOT_STORAGE_PATH],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"unable to read {SNAPSHOT_STORAGE_PATH} from {container}: "
            f"{(proc.stderr or proc.stdout or '').strip()}"
        )
    payload = json.loads(proc.stdout or "{}")
    data = payload.get("data", {})
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    snapshots = data.get("snapshots", []) if isinstance(data, dict) else []
    if not isinstance(snapshots, list):
        raise RuntimeError("heima_snapshots storage does not contain a snapshot list")
    return [item for item in snapshots if isinstance(item, dict)]


def _wait_for_snapshots(container: str, *, timeout_s: int, poll_s: float) -> list[dict[str, Any]]:
    deadline = time.time() + timeout_s
    last: list[dict[str, Any]] = []
    last_error: str = ""
    while time.time() < deadline:
        try:
            last = _load_snapshot_storage(container)
            last_error = ""
        except Exception as err:  # noqa: BLE001
            last = []
            last_error = str(err)
        if last:
            return last
        time.sleep(poll_s)
    detail = f"; last_error={last_error}" if last_error else ""
    raise AssertionError(f"no persisted HouseSnapshot records found; last={last}{detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--container", default=HA_TEST_CONTAINER)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--poll-s", type=float, default=2.0)
    args = parser.parse_args()

    client = HAClient(args.ha_url, args.ha_token)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    client.call_service("heima", "command", {"command": "recompute_now", "target": {"entry_id": entry_id}})
    snapshot = _engine_snapshot(client, entry_id)
    _assert("security_state" in snapshot, f"engine snapshot missing security_state: {snapshot}")
    _assert("security_armed" not in snapshot, f"legacy security_armed leaked into engine snapshot: {snapshot}")

    snapshots = _wait_for_snapshots(args.container, timeout_s=args.timeout_s, poll_s=args.poll_s)
    latest = snapshots[-1]
    _assert("security_state" in latest, f"HouseSnapshot missing security_state: {latest}")
    _assert(
        "heating_current_temperature" in latest,
        f"HouseSnapshot missing heating_current_temperature: {latest}",
    )
    _assert("security_armed" not in latest, f"legacy security_armed leaked into HouseSnapshot: {latest}")

    print(
        "PASS: runtime and persisted snapshots use Phase O fields "
        f"(stored snapshots={len(snapshots)})"
    )


if __name__ == "__main__":
    main()
