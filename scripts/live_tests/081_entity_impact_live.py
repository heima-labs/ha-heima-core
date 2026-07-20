#!/usr/bin/env python3
"""Live smoke test for the Heima observability entity-impact index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient
from lib.ha_websocket import HAWebSocketClient


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _snapshot(ws: HAWebSocketClient, entry_id: str) -> dict[str, Any]:
    result = ws.call("heima/observability/snapshot", entry_id=entry_id)
    _assert(isinstance(result, dict), f"snapshot result must be a dict: {type(result)}")
    return result


def _assert_entity_impact(snapshot: dict[str, Any]) -> None:
    impact = snapshot.get("entity_impact")
    _assert(isinstance(impact, dict), "snapshot.entity_impact must be a dict")
    entities = impact.get("entities")
    _assert(isinstance(entities, list), "entity_impact.entities must be a list")
    by_domain = impact.get("by_domain")
    _assert(isinstance(by_domain, dict), "entity_impact.by_domain must be a dict")
    details = snapshot.get("details")
    _assert(isinstance(details, dict), "snapshot.details must be a dict")
    entity_details = details.get("entities")
    _assert(isinstance(entity_details, dict), "snapshot.details.entities must be a dict")
    by_id = entity_details.get("by_id")
    _assert(isinstance(by_id, dict), "snapshot.details.entities.by_id must be a dict")
    _assert(
        set(by_id) == {str(row.get("entity_id")) for row in entities if row.get("entity_id")},
        "entity detail keys must match entity impact rows",
    )
    for row in entities:
        _assert(isinstance(row, dict), "entity impact rows must be dicts")
        entity_id = str(row.get("entity_id") or "")
        _assert("." in entity_id, f"entity impact row has invalid entity_id: {entity_id}")
        _assert(
            not entity_id.startswith("notify."),
            f"notification route was indexed as an HA entity: {entity_id}",
        )
        _assert(isinstance(row.get("reaction_ids"), list), "reaction_ids must be a list")
        _assert(isinstance(row.get("trace_ids"), list), "trace_ids must be a list")
        _assert(isinstance(row.get("hold_scopes"), list), "hold_scopes must be a list")
        _assert(isinstance(row.get("request_ids"), list), "request_ids must be a list")
        _assert(isinstance(row.get("source_metadata"), list), "source_metadata must be a list")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima entity-impact observability live test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()

    with HAWebSocketClient(args.ha_url, args.ha_token) as ws:
        print("Checking observability entity-impact index...")
        snapshot = _snapshot(ws, entry_id)
        _assert_entity_impact(snapshot)
        print("PASS observability entity-impact index")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
