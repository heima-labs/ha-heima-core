#!/usr/bin/env python3
"""Live smoke test for the Heima admin observability websocket contract."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient
from lib.ha_websocket import HAWebSocketClient, HAWebSocketError

REQUIRED_SNAPSHOT_SECTIONS = {
    "meta",
    "health",
    "runtime",
    "health_findings",
    "recent_events",
    "decision_traces",
    "reactions",
    "manual_holds",
    "runtime_confirmations",
    "notifications",
    "learning",
    "proposals",
    "house_state",
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _snapshot(ws: HAWebSocketClient, entry_id: str) -> dict[str, Any]:
    result = ws.call("heima/observability/snapshot", entry_id=entry_id)
    _assert(isinstance(result, dict), f"snapshot result must be a dict: {type(result)}")
    return result


def _assert_snapshot_contract(snapshot: dict[str, Any], entry_id: str) -> None:
    missing = sorted(REQUIRED_SNAPSHOT_SECTIONS - set(snapshot))
    _assert(not missing, f"observability snapshot missing sections: {missing}")

    meta = snapshot.get("meta")
    _assert(isinstance(meta, dict), "snapshot.meta must be a dict")
    _assert(meta.get("schema_version") == 1, "snapshot schema_version must be 1")
    _assert(meta.get("entry_id") == entry_id, "snapshot entry_id does not match requested entry")
    _assert(isinstance(meta.get("is_partial"), bool), "snapshot.meta.is_partial must be a bool")
    _assert(
        isinstance(meta.get("partial_reasons"), list),
        "snapshot.meta.partial_reasons must be a list",
    )
    retention = meta.get("retention")
    _assert(isinstance(retention, dict), "snapshot.meta.retention must be a dict")
    _assert(
        retention.get("description") == "history_since_last_restart",
        "snapshot retention description must explain restart volatility",
    )

    _assert(isinstance(snapshot.get("health"), dict), "snapshot.health must be a dict")
    _assert(isinstance(snapshot.get("runtime"), dict), "snapshot.runtime must be a dict")
    _assert(isinstance(snapshot.get("health_findings"), list), "health_findings must be a list")
    _assert(isinstance(snapshot.get("recent_events"), list), "recent_events must be a list")
    _assert(isinstance(snapshot.get("decision_traces"), list), "decision_traces must be a list")
    _assert(isinstance(snapshot.get("reactions"), list), "reactions must be a list")
    _assert(isinstance(snapshot.get("manual_holds"), dict), "manual_holds must be a dict")
    _assert(
        isinstance(snapshot.get("runtime_confirmations"), dict),
        "runtime_confirmations must be a dict",
    )
    _assert(isinstance(snapshot.get("notifications"), dict), "notifications must be a dict")
    delivery_policy = snapshot["notifications"].get("delivery_policy")
    _assert(isinstance(delivery_policy, dict), "notifications.delivery_policy must be a dict")
    _assert(
        isinstance(delivery_policy.get("effective"), dict),
        "notifications.delivery_policy.effective must be a dict",
    )
    _assert(
        isinstance(delivery_policy.get("unresolved_audience_targets"), list),
        "notifications.delivery_policy.unresolved_audience_targets must be a list",
    )
    _assert(isinstance(snapshot.get("learning"), dict), "learning must be a dict")
    _assert(isinstance(snapshot.get("proposals"), dict), "proposals must be a dict")
    house_state = snapshot.get("house_state")
    _assert(isinstance(house_state, dict), "house_state must be a dict")
    _assert(
        isinstance(house_state.get("candidate_trace"), dict),
        "house_state.candidate_trace must be a dict",
    )
    _assert(
        isinstance(house_state.get("candidate_summary"), dict),
        "house_state.candidate_summary must be a dict",
    )
    _assert(
        isinstance(house_state.get("resolution_trace"), dict),
        "house_state.resolution_trace must be a dict",
    )
    _assert_reaction_metadata(snapshot.get("reactions"))


def _assert_reaction_metadata(rows: Any) -> None:
    _assert(isinstance(rows, list), "reactions must be a list")
    if not rows:
        return
    typed = [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("reaction_type") or "") != "unknown"
    ]
    originated = [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("origin") or "") != "unspecified"
    ]
    _assert(typed, "observability reactions all have unknown reaction_type")
    _assert(originated, "observability reactions all have unspecified origin")


def _assert_invalid_action_is_rejected(ws: HAWebSocketClient, entry_id: str) -> None:
    try:
        ws.call(
            "heima/observability/action",
            entry_id=entry_id,
            action="clear_manual_hold",
            payload={"domain": "light"},
        )
    except HAWebSocketError as exc:
        error_text = str(exc).lower()
        _assert(
            "invalid_payload" in error_text or "closed by server" in error_text,
            f"unexpected invalid action error: {exc}",
        )
        return
    raise AssertionError("invalid clear_manual_hold action unexpectedly succeeded")


def _assert_non_admin_rejected(ha_url: str, token: str, entry_id: str) -> None:
    if not token:
        print("SKIP non-admin websocket authorization check (HA_NON_ADMIN_TOKEN not provided)")
        return
    try:
        with HAWebSocketClient(ha_url, token) as ws:
            ws.call("heima/observability/snapshot", entry_id=entry_id)
    except HAWebSocketError as exc:
        error_text = str(exc).lower()
        _assert(
            "unauthorized" in error_text or "closed by server" in error_text,
            f"unexpected non-admin error: {exc}",
        )
        print("PASS non-admin websocket authorization check")
        return
    raise AssertionError("non-admin token unexpectedly retrieved observability snapshot")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima admin observability live smoke test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--ha-non-admin-token", default="")
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()

    with HAWebSocketClient(args.ha_url, args.ha_token) as ws:
        print("Checking admin observability snapshot...")
        snapshot = _snapshot(ws, entry_id)
        _assert_snapshot_contract(snapshot, entry_id)
        print("PASS admin observability snapshot")

        time.sleep(0.5)
        print("Checking invalid admin action rejection...")
        _assert_invalid_action_is_rejected(ws, entry_id)
        print("PASS invalid admin action rejection")

    print("Checking non-admin websocket authorization...")
    _assert_non_admin_rejected(args.ha_url, args.ha_non_admin_token, entry_id)

    print("PASS: admin observability panel websocket contract is live-valid")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
