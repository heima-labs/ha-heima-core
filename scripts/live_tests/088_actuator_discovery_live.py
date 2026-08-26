#!/usr/bin/env python3
"""Live smoke test for Heima actuator discovery (Phase AV: AV1-3).

Covers what tests/test_discovery_l.py, tests/test_actuator_entity_picker.py, and
tests/test_actuator_registry_panel_e2e.py structurally cannot: the real discovery rule table
(AV1) running against the real entity/device/area registries, the real Options Flow discovery
step (AV2) persisting a candidate through the actual config-entry options boundary, and the real
actuators websocket snapshot (AV3) reflecting both states — using the test lab's baseline fixture
entity switch.test_heima_studio_fan (already assigned to the "Test Heima Studio" HA Area, which
resolves to Heima room "studio") instead of hand-built fixtures.

Non-destructive: if the fixture entity is already registered as an Actuator from a previous run,
it is deleted first to restore a clean starting state; the Actuator created by this test is always
deleted in `finally`, regardless of outcome. The Options Flow step is scoped to
action=accept_selected with exactly one candidate_id — never accept_all/accept_non_ambiguous,
which would also accept and persist any other currently-discoverable candidate on the shared test
lab instance (unrelated presence/security/activity candidates), which this test must not touch.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient
from lib.ha_websocket import HAWebSocketClient, HAWebSocketError

TEST_ROOM_ID = "studio"
TEST_ACTUATOR_ENTITY = "switch.test_heima_studio_fan"


class HAFlowClient(HAClient):
    """Adds Options Flow REST driving on top of the shared HAClient, mirroring
    010_config_flow.py's own subclass (not shared in lib/ha_client.py — kept local there too)."""

    def _post_with_retry(self, path: str, payload: dict[str, Any]) -> Any:
        last: Exception | None = None
        for attempt in range(3):
            try:
                return self.post(path, payload)
            except HAApiError as err:
                last = err
                if "connection reset by peer" not in str(err).lower():
                    raise
                if attempt == 2:
                    raise
                time.sleep(1.0 * (attempt + 1))
        raise last or HAApiError(f"POST failed for {path}")

    def options_flow_init(self, entry_id: str) -> dict[str, Any]:
        data = self._post_with_retry(
            "/api/config/config_entries/options/flow", {"handler": entry_id}
        )
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow init response: {type(data)}")
        return data

    def options_flow_configure(self, flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._post_with_retry(f"/api/config/config_entries/options/flow/{flow_id}", payload)
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow response: {type(data)}")
        return data

    def options_flow_abort(self, flow_id: str) -> None:
        self.delete(f"/api/config/config_entries/options/flow/{flow_id}")


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _actuators_snapshot(ws: HAWebSocketClient, entry_id: str) -> dict[str, Any]:
    result = ws.call("heima/actuators/snapshot", entry_id=entry_id)
    _assert(isinstance(result, dict), f"actuators snapshot must be a dict: {type(result)}")
    _assert("entity_candidates" in result, "actuators snapshot missing entity_candidates (AV3)")
    return result


def _find_actuator_id(snapshot: dict[str, Any], entity_id: str) -> str | None:
    for actuator in snapshot.get("actuators", []) or []:
        if actuator.get("entity_id") == entity_id:
            return str(actuator.get("actuator_id") or "") or None
    return None


def _delete_actuator(ws: HAWebSocketClient, entry_id: str, actuator_id: str) -> None:
    ws.call(
        "heima/actuators/action",
        entry_id=entry_id,
        action="delete_actuator",
        payload={"actuator_id": actuator_id},
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima actuator discovery (Phase AV) live smoke test"
    )
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()

    actuator_id: str | None = None

    with HAWebSocketClient(args.ha_url, args.ha_token) as ws:
        try:
            print(f"Ensuring {TEST_ACTUATOR_ENTITY!r} starts unregistered (clean slate)...")
            snapshot = _actuators_snapshot(ws, entry_id)
            leftover_id = _find_actuator_id(snapshot, TEST_ACTUATOR_ENTITY)
            if leftover_id:
                _delete_actuator(ws, entry_id, leftover_id)
                print(f"PASS cleaned up leftover Actuator from a previous run: {leftover_id}")

            print(
                "Checking the fixture entity is suggested as an actuator candidate (AV1 + AV3)..."
            )
            snapshot = _actuators_snapshot(ws, entry_id)
            candidates = {c.get("entity_id"): c for c in snapshot.get("entity_candidates", [])}
            _assert(
                TEST_ACTUATOR_ENTITY in candidates,
                f"expected {TEST_ACTUATOR_ENTITY!r} in entity_candidates, got {list(candidates)}",
            )
            _assert(
                candidates[TEST_ACTUATOR_ENTITY].get("room_id") == TEST_ROOM_ID,
                f"expected candidate room_id={TEST_ROOM_ID!r}, "
                f"got {candidates[TEST_ACTUATOR_ENTITY].get('room_id')!r}",
            )
            print(f"PASS {TEST_ACTUATOR_ENTITY!r} suggested for room {TEST_ROOM_ID!r}")

            print("Accepting the candidate via the real Options Flow discovery step (AV2)...")
            init_result = client.options_flow_init(entry_id)
            _assert(init_result.get("step_id") == "init", f"unexpected init step: {init_result}")
            flow_id = str(init_result["flow_id"])
            try:
                discovery_result = client.options_flow_configure(
                    flow_id, {"next_step_id": "discovery"}
                )
                _assert(
                    discovery_result.get("step_id") == "discovery",
                    f"unexpected step after next_step_id=discovery: {discovery_result}",
                )
                candidate_id = f"actuator_candidate:{TEST_ACTUATOR_ENTITY}"
                # Scoped to exactly this one candidate_id — never accept_all/accept_non_ambiguous,
                # which would also persist any other currently-discoverable candidate on this
                # shared test lab instance.
                accept_result = client.options_flow_configure(
                    flow_id,
                    {"action": "accept_selected", "accepted_candidates": [candidate_id]},
                )
                _assert(
                    accept_result.get("step_id") == "init",
                    f"expected return to the init menu after accept_selected: {accept_result}",
                )
            finally:
                client.options_flow_abort(flow_id)
            print(f"PASS discovery step accepted candidate {candidate_id!r}")

            print("Verifying the Actuator was persisted via the real config-entry options...")
            snapshot = _actuators_snapshot(ws, entry_id)
            actuator_id = _find_actuator_id(snapshot, TEST_ACTUATOR_ENTITY)
            _assert(
                bool(actuator_id),
                f"expected an Actuator for {TEST_ACTUATOR_ENTITY!r} after discovery accept, "
                f"got actuators={snapshot.get('actuators')}",
            )
            registered = next(
                a for a in snapshot["actuators"] if a.get("actuator_id") == actuator_id
            )
            _assert(
                registered.get("room_id") == TEST_ROOM_ID,
                f"expected persisted Actuator room_id={TEST_ROOM_ID!r}, got {registered.get('room_id')!r}",
            )
            print(f"PASS Actuator persisted via discovery: {actuator_id}")

            print("Verifying the now-registered entity no longer appears as a candidate (AV3)...")
            remaining_candidate_entity_ids = {
                c.get("entity_id") for c in snapshot.get("entity_candidates", [])
            }
            _assert(
                TEST_ACTUATOR_ENTITY not in remaining_candidate_entity_ids,
                f"expected {TEST_ACTUATOR_ENTITY!r} excluded from entity_candidates once "
                f"registered, still present: {remaining_candidate_entity_ids}",
            )
            print("PASS idempotency guard: registered entity no longer suggested")
        finally:
            if actuator_id:
                try:
                    _delete_actuator(ws, entry_id, actuator_id)
                except HAWebSocketError as exc:
                    print(f"WARN cleanup delete_actuator failed: {exc}", file=sys.stderr)

    print("PASS: actuator discovery (Phase AV, AV1-3) is live-valid")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
