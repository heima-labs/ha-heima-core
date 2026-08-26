#!/usr/bin/env python3
"""Live smoke test for the Heima actuator registry (AU4) websocket contract.

Covers what tests/test_actuator_registry_panel_e2e.py structurally cannot: the real HA
websocket layer against a real config entry in the local test lab, using a real baseline
room ("studio") and a real fixture entity (climate.test_heima_thermostat) instead of hand-
built fixtures. Non-destructive: seeds one Opening and one Actuator, exercises the AU4
referential-integrity check against the real coordinator, and cleans up in `finally`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient
from lib.ha_websocket import HAWebSocketClient, HAWebSocketError

TEST_ROOM_ID = "studio"
TEST_ACTUATOR_ENTITY = "climate.test_heima_thermostat"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _actuators_snapshot(ws: HAWebSocketClient, entry_id: str) -> dict[str, Any]:
    result = ws.call("heima/actuators/snapshot", entry_id=entry_id)
    _assert(isinstance(result, dict), f"actuators snapshot must be a dict: {type(result)}")
    return result


def _assert_snapshot_contract(snapshot: dict[str, Any]) -> None:
    for key in ("rooms", "openings", "actuators", "issues"):
        _assert(key in snapshot, f"actuators snapshot missing key: {key}")
        _assert(isinstance(snapshot[key], list), f"actuators snapshot.{key} must be a list")
    room_ids = {str(room.get("room_id") or "") for room in snapshot["rooms"]}
    _assert(
        TEST_ROOM_ID in room_ids,
        f"expected baseline room {TEST_ROOM_ID!r} in snapshot.rooms, got {room_ids}",
    )


def _seed_opening(ws: HAWebSocketClient, entry_id: str) -> str:
    result = ws.call(
        "heima/topology/action",
        entry_id=entry_id,
        action="upsert_opening",
        payload={"room_id": TEST_ROOM_ID, "type": "window"},
    )
    _assert(result.get("ok") is True, f"seed upsert_opening failed: {result}")
    links = result.get("object_links") or []
    _assert(
        len(links) == 1 and links[0].get("kind") == "opening",
        f"unexpected object_links from upsert_opening: {links}",
    )
    opening_id = str(links[0].get("id") or "")
    _assert(bool(opening_id), "seed upsert_opening did not return a generated opening_id")
    return opening_id


def _assert_actuators_action_rejected(
    ws: HAWebSocketClient,
    entry_id: str,
    payload: dict[str, Any],
    *,
    error_code: str,
    expected_fragment: str | None = None,
) -> None:
    try:
        ws.call(
            "heima/actuators/action",
            entry_id=entry_id,
            action="upsert_actuator",
            payload=payload,
        )
    except HAWebSocketError as exc:
        error_text = str(exc).lower()
        _assert(
            error_code in error_text or "closed by server" in error_text,
            f"unexpected rejection error for payload {payload}: {exc}",
        )
        if expected_fragment:
            _assert(
                expected_fragment.lower() in error_text,
                f"expected {expected_fragment!r} in rejection error: {exc}",
            )
        return
    raise AssertionError(f"upsert_actuator with payload {payload} unexpectedly succeeded")


def _assert_delete_opening_blocked_by_actuator(
    ws: HAWebSocketClient, entry_id: str, opening_id: str
) -> None:
    try:
        ws.call(
            "heima/topology/action",
            entry_id=entry_id,
            action="delete_opening",
            payload={"opening_id": opening_id},
        )
    except HAWebSocketError as exc:
        error_text = str(exc).lower()
        _assert("validation_failed" in error_text, f"unexpected delete_opening error: {exc}")
        _assert(
            "referenced by an actuator" in error_text,
            f"expected actuator-reference reason in delete_opening error: {exc}",
        )
        return
    raise AssertionError(
        f"delete_opening for {opening_id!r} unexpectedly succeeded while referenced by an Actuator"
    )


def _assert_non_admin_rejected(ha_url: str, token: str, entry_id: str) -> None:
    if not token:
        print("SKIP non-admin websocket authorization check (HA_NON_ADMIN_TOKEN not provided)")
        return
    try:
        with HAWebSocketClient(ha_url, token) as ws:
            ws.call("heima/actuators/snapshot", entry_id=entry_id)
    except HAWebSocketError as exc:
        error_text = str(exc).lower()
        _assert(
            "unauthorized" in error_text or "closed by server" in error_text,
            f"unexpected non-admin error: {exc}",
        )
        print("PASS non-admin websocket authorization check")
        return
    raise AssertionError("non-admin token unexpectedly retrieved actuators snapshot")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima actuator registry (AU4) live smoke test")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--ha-non-admin-token", default="")
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()

    opening_id: str | None = None
    actuator_id: str | None = None

    with HAWebSocketClient(args.ha_url, args.ha_token) as ws:
        try:
            print("Checking actuator registry snapshot contract...")
            snapshot = _actuators_snapshot(ws, entry_id)
            _assert_snapshot_contract(snapshot)
            print("PASS actuator registry snapshot contract")

            print(f"Seeding a test Opening in room {TEST_ROOM_ID!r} via heima/topology/action...")
            opening_id = _seed_opening(ws, entry_id)
            print(f"PASS opening seeded: {opening_id}")

            print("Checking upsert_actuator creates a record and returns the generated id...")
            result = ws.call(
                "heima/actuators/action",
                entry_id=entry_id,
                action="upsert_actuator",
                payload={
                    "entity_id": TEST_ACTUATOR_ENTITY,
                    "room_id": TEST_ROOM_ID,
                    "opening_id": opening_id,
                },
            )
            _assert(result.get("ok") is True, f"upsert_actuator failed: {result}")
            links = result.get("object_links") or []
            _assert(
                len(links) == 1 and links[0].get("kind") == "actuator",
                f"unexpected object_links from upsert_actuator: {links}",
            )
            actuator_id = str(links[0].get("id") or "")
            _assert(bool(actuator_id), "upsert_actuator did not return a generated actuator_id")
            created = [
                a
                for a in result.get("snapshot", {}).get("actuators", [])
                if a.get("actuator_id") == actuator_id
            ]
            _assert(
                len(created) == 1 and created[0].get("entity_id") == TEST_ACTUATOR_ENTITY,
                f"created actuator not found in snapshot: {result.get('snapshot')}",
            )
            print(f"PASS upsert_actuator created and returned id: {actuator_id}")

            print("Checking edit-in-place (same actuator_id, new display_name)...")
            result = ws.call(
                "heima/actuators/action",
                entry_id=entry_id,
                action="upsert_actuator",
                payload={
                    "actuator_id": actuator_id,
                    "entity_id": TEST_ACTUATOR_ENTITY,
                    "room_id": TEST_ROOM_ID,
                    "opening_id": opening_id,
                    "display_name": "Live Test Thermostat",
                },
            )
            _assert(result.get("ok") is True, f"edit upsert_actuator failed: {result}")
            matching = [
                a
                for a in result.get("snapshot", {}).get("actuators", [])
                if a.get("actuator_id") == actuator_id
            ]
            _assert(
                len(matching) == 1,
                f"expected exactly one actuator with id {actuator_id}, got {matching}",
            )
            _assert(
                matching[0].get("display_name") == "Live Test Thermostat",
                f"edit did not apply: {matching[0]}",
            )
            print("PASS edit-in-place replaces the record, does not duplicate it")

            print("Checking opening_room_mismatch is rejected as validation_failed...")
            _assert_actuators_action_rejected(
                ws,
                entry_id,
                {
                    "entity_id": TEST_ACTUATOR_ENTITY,
                    "room_id": "does_not_exist_room",
                    "opening_id": opening_id,
                },
                error_code="validation_failed",
                expected_fragment="belongs to room",
            )
            print("PASS opening_room_mismatch rejection")

            print("Checking missing entity_id is rejected as invalid_payload...")
            _assert_actuators_action_rejected(
                ws,
                entry_id,
                {"room_id": TEST_ROOM_ID},
                error_code="invalid_payload",
            )
            print("PASS invalid payload rejection")

            print("Checking Opening delete is blocked while referenced by the Actuator (AU4)...")
            _assert_delete_opening_blocked_by_actuator(ws, entry_id, opening_id)
            print("PASS opening-delete-blocked-by-actuator")
        finally:
            if actuator_id:
                try:
                    ws.call(
                        "heima/actuators/action",
                        entry_id=entry_id,
                        action="delete_actuator",
                        payload={"actuator_id": actuator_id},
                    )
                except HAWebSocketError as exc:
                    print(f"WARN cleanup delete_actuator failed: {exc}", file=sys.stderr)
            if opening_id:
                try:
                    ws.call(
                        "heima/topology/action",
                        entry_id=entry_id,
                        action="delete_opening",
                        payload={"opening_id": opening_id},
                    )
                except HAWebSocketError as exc:
                    print(f"WARN cleanup delete_opening failed: {exc}", file=sys.stderr)

    print("Checking non-admin websocket authorization...")
    _assert_non_admin_rejected(args.ha_url, args.ha_non_admin_token, entry_id)

    print("PASS: actuator registry (AU4) websocket contract is live-valid")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
