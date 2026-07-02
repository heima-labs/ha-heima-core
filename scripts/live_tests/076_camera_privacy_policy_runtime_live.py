#!/usr/bin/env python3
"""Live E2E check for camera privacy policy runtime actions."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient

ALARM_ENTITY = "alarm_control_panel.test_heima_alarm"
CAMERA_SOURCE_ID = "live_privacy_runtime_cam"
PRIVACY_SWITCH = "switch.test_heima_heater_relay"
PRIVACY_SWITCH_RAW = "input_boolean.test_heima_heater_relay_raw"
RESET_SCRIPT = "script.test_heima_reset"
POLICY_ON_ID = "camera_privacy_policy__live_privacy_runtime_cam__disarmed__any__turn_on"
POLICY_OFF_ID = "camera_privacy_policy__live_privacy_runtime_cam__armed_night__any__turn_off"
SCOPE = f"switch:entity:{PRIVACY_SWITCH}"


class HAFlowClient(HAClient):
    def options_flow_init(self, entry_id: str) -> dict[str, Any]:
        data = self.post("/api/config/config_entries/options/flow", {"handler": entry_id})
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow init response: {type(data)}")
        return data

    def options_flow_configure(self, flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.post(f"/api/config/config_entries/options/flow/{flow_id}", payload)
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow response: {type(data)}")
        return data

    def options_flow_abort(self, flow_id: str) -> None:
        self.delete(f"/api/config/config_entries/options/flow/{flow_id}")


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _expect_step(result: dict[str, Any], step_id: str) -> None:
    got = result.get("step_id")
    _assert(got == step_id, f"expected step_id={step_id!r}, got={got!r}: {result}")


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        raise HAApiError(f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise HAApiError("diagnostics payload missing data object")
    return data


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    entry = _diagnostics_data(client, entry_id).get("entry", {})
    options = entry.get("options", {}) if isinstance(entry, dict) else {}
    return dict(options) if isinstance(options, dict) else {}


def _runtime_engine(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
    return dict(engine) if isinstance(engine, dict) else {}


def _configure_security(client: HAFlowClient, entry_id: str, security_cfg: dict[str, Any]) -> None:
    flow = client.options_flow_init(entry_id)
    flow_id = str(flow["flow_id"])
    try:
        _expect_step(flow, "init")
        step = _menu_next(client, flow_id, "security")
        _expect_step(step, "security")
        result = client.options_flow_configure(flow_id, security_cfg)
        _expect_step(result, "init")
        saved = _menu_next(client, flow_id, "save")
        _assert(saved.get("type") == "create_entry", f"unexpected save result: {saved}")
    finally:
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


def _security_with_live_camera(options: dict[str, Any]) -> dict[str, Any]:
    security = dict(options.get("security") or {})
    sources = security.get("camera_evidence_sources", {})
    if isinstance(sources, dict):
        source_map = {
            str(key): dict(value) for key, value in sources.items() if isinstance(value, dict)
        }
    else:
        source_map = {
            str(item.get("id") or f"source_{idx}"): dict(item)
            for idx, item in enumerate(sources if isinstance(sources, list) else [])
            if isinstance(item, dict)
        }
    source_map[CAMERA_SOURCE_ID] = {
        "id": CAMERA_SOURCE_ID,
        "display_name": "Live Privacy Runtime Camera",
        "enabled": True,
        "role": "interior",
        "privacy_entity": PRIVACY_SWITCH,
    }
    security["camera_evidence_sources"] = source_map
    return security


def _policy_config(*, alarm_states: list[str], privacy_action: str) -> dict[str, Any]:
    action = f"switch.{privacy_action}"
    return {
        "reaction_type": "alarm_state_action",
        "enabled": True,
        "alarm_states": alarm_states,
        "only_house_states": [],
        "skip_house_states": [],
        "origin": "admin_authored",
        "author_kind": "admin",
        "source_request": "template:security.camera_privacy_policy",
        "source_template_id": "security.camera_privacy_policy",
        "admin_authored_template_id": "security.camera_privacy_policy",
        "camera_privacy_policy": {
            "camera_source_id": CAMERA_SOURCE_ID,
            "privacy_entity": PRIVACY_SWITCH,
            "house_filter_mode": "always",
            "house_states": [],
            "privacy_action": privacy_action,
        },
        "steps": [
            {
                "domain": "switch",
                "target": PRIVACY_SWITCH,
                "action": action,
                "params": {"entity_id": PRIVACY_SWITCH},
            }
        ],
    }


def _upsert_policies(client: HAClient, entry_id: str) -> None:
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {
                    POLICY_ON_ID: _policy_config(
                        alarm_states=["disarmed"],
                        privacy_action="turn_on",
                    ),
                    POLICY_OFF_ID: _policy_config(
                        alarm_states=["armed_night"],
                        privacy_action="turn_off",
                    ),
                },
                "labels": {
                    POLICY_ON_ID: "Live camera privacy on when disarmed",
                    POLICY_OFF_ID: "Live camera privacy off when armed night",
                },
            },
        },
    )


def _disable_policies(client: HAClient, entry_id: str) -> None:
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {
                    POLICY_ON_ID: {
                        "reaction_type": "alarm_state_action",
                        "enabled": False,
                        "alarm_states": [],
                        "steps": [],
                    },
                    POLICY_OFF_ID: {
                        "reaction_type": "alarm_state_action",
                        "enabled": False,
                        "alarm_states": [],
                        "steps": [],
                    },
                },
                "labels": {},
            },
        },
    )


def _call_recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _clear_privacy_hold(client: HAClient, entry_id: str) -> None:
    client.call_service(
        "heima",
        "command",
        {
            "command": "clear_manual_hold",
            "target": {"entry_id": entry_id},
            "params": {
                "domain": "switch",
                "subject_type": "entity",
                "subject_id": PRIVACY_SWITCH,
            },
        },
    )


def _set_alarm_state(client: HAClient, state: str, *, timeout_s: int, poll_s: float) -> None:
    if state == "disarmed":
        client.call_service(
            "alarm_control_panel",
            "alarm_disarm",
            {"entity_id": ALARM_ENTITY, "code": "1234"},
        )
    elif state == "armed_night":
        client.call_service(
            "alarm_control_panel",
            "alarm_arm_night",
            {"entity_id": ALARM_ENTITY, "code": "1234"},
        )
    else:
        raise ValueError(state)
    client.wait_state(ALARM_ENTITY, state, timeout_s, poll_s)
    _call_recompute(client)


def _wait_switch(client: HAClient, expected: str, *, timeout_s: int, poll_s: float) -> None:
    deadline = time.time() + timeout_s
    last = "<missing>"
    while time.time() < deadline:
        last = client.state_value(PRIVACY_SWITCH)
        if last == expected:
            return
        time.sleep(poll_s)
    raise AssertionError(f"timeout waiting for {PRIVACY_SWITCH}={expected!r}; last={last!r}")


def _wait_runtime_reactions(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        reactions = _runtime_engine(client, entry_id).get("reactions", {})
        last = dict(reactions) if isinstance(reactions, dict) else {}
        if POLICY_ON_ID in last and POLICY_OFF_ID in last:
            return
        time.sleep(poll_s)
    raise AssertionError(
        f"camera privacy policy reactions not visible; "
        f"expected={[POLICY_ON_ID, POLICY_OFF_ID]}, got={sorted(last)}"
    )


def _wait_last_fired_state(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    expected: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last: Any = None
    while time.time() < deadline:
        reactions = _runtime_engine(client, entry_id).get("reactions", {})
        row = dict(reactions).get(reaction_id) if isinstance(reactions, dict) else {}
        last = dict(row).get("last_fired_state") if isinstance(row, dict) else None
        if last == expected:
            return
        time.sleep(poll_s)
    raise AssertionError(f"{reaction_id} last_fired_state={expected!r} missing; last={last!r}")


def _active_holds_for_scope(client: HAClient, entry_id: str) -> list[dict[str, Any]]:
    manual_hold = _runtime_engine(client, entry_id).get("manual_hold", {})
    active = dict(manual_hold).get("active_holds", []) if isinstance(manual_hold, dict) else []
    return [
        dict(item)
        for item in active
        if isinstance(item, dict) and str(item.get("scope") or "") == SCOPE
    ]


def _assert_no_privacy_hold(client: HAClient, entry_id: str) -> None:
    holds = _active_holds_for_scope(client, entry_id)
    _assert(not holds, f"unexpected active privacy hold for {SCOPE}: {holds}")


def run(ha_url: str, ha_token: str, *, timeout_s: int, poll_s: float) -> None:
    client = HAFlowClient(ha_url, ha_token, timeout_s=timeout_s)
    required = [ALARM_ENTITY, PRIVACY_SWITCH, PRIVACY_SWITCH_RAW, RESET_SCRIPT]
    missing = [entity_id for entity_id in required if not client.entity_exists(entity_id)]
    _assert(not missing, "missing required entities:\n- " + "\n- ".join(missing))

    entry_id = client.find_heima_entry_id()
    original_security = dict(_entry_options(client, entry_id).get("security") or {})

    try:
        print("Configuring live camera privacy source...")
        _configure_security(
            client, entry_id, _security_with_live_camera(_entry_options(client, entry_id))
        )

        print("Installing disarmed->privacy-on and armed_night->privacy-off policies...")
        _upsert_policies(client, entry_id)
        client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
        _wait_runtime_reactions(client, entry_id, timeout_s=timeout_s, poll_s=poll_s)

        print("Scenario A: armed_night turns camera privacy off...")
        _clear_privacy_hold(client, entry_id)
        _set_alarm_state(client, "armed_night", timeout_s=timeout_s, poll_s=poll_s)
        _wait_last_fired_state(
            client,
            entry_id,
            POLICY_OFF_ID,
            "armed_night",
            timeout_s=timeout_s,
            poll_s=poll_s,
        )
        _wait_switch(client, "off", timeout_s=timeout_s, poll_s=poll_s)
        _assert_no_privacy_hold(client, entry_id)
        print("PASS scenario A")

        print("Scenario B: disarmed turns camera privacy on...")
        _clear_privacy_hold(client, entry_id)
        _set_alarm_state(client, "disarmed", timeout_s=timeout_s, poll_s=poll_s)
        _wait_last_fired_state(
            client,
            entry_id,
            POLICY_ON_ID,
            "disarmed",
            timeout_s=timeout_s,
            poll_s=poll_s,
        )
        _wait_switch(client, "on", timeout_s=timeout_s, poll_s=poll_s)
        _assert_no_privacy_hold(client, entry_id)
        print("PASS scenario B")

        print("Scenario C: armed_night turns camera privacy off after disarmed...")
        _clear_privacy_hold(client, entry_id)
        _set_alarm_state(client, "armed_night", timeout_s=timeout_s, poll_s=poll_s)
        _wait_last_fired_state(
            client,
            entry_id,
            POLICY_OFF_ID,
            "armed_night",
            timeout_s=timeout_s,
            poll_s=poll_s,
        )
        _wait_switch(client, "off", timeout_s=timeout_s, poll_s=poll_s)
        _assert_no_privacy_hold(client, entry_id)
        print("PASS scenario C")
    finally:
        print("Cleaning up live camera privacy runtime policy artifacts...")
        try:
            _configure_security(client, entry_id, original_security)
            _disable_policies(client, entry_id)
            client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
            client.call_service("input_boolean", "turn_off", {"entity_id": PRIVACY_SWITCH_RAW})
            _set_alarm_state(client, "disarmed", timeout_s=timeout_s, poll_s=poll_s)
            _clear_privacy_hold(client, entry_id)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: cleanup failed: {exc}", file=sys.stderr)

    print("PASS: camera privacy policy runtime live checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()
    run(args.ha_url, args.ha_token, timeout_s=args.timeout_s, poll_s=args.poll_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
