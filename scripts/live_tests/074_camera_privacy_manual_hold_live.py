#!/usr/bin/env python3
"""Live test for AE camera privacy manual-hold behavior."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient

ALARM_ENTITY = "alarm_control_panel.test_heima_alarm"
PRIVACY_SWITCH = "switch.test_heima_studio_fan"
PRIVACY_SWITCH_RAW = "input_boolean.test_heima_studio_fan_raw"
MANUAL_HOLD_ENTITY = "input_boolean.test_heima_heater_relay_raw"
RESET_SCRIPT = "script.test_heima_reset"
REACTION_ID = "live-camera-privacy-manual-hold"
PROPOSAL_KEY = "alarm_night_camera_privacy"
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


def _proposal_map(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    proposals = runtime.get("proposals", {}) if isinstance(runtime, dict) else {}
    items = proposals.get("proposals", []) if isinstance(proposals, dict) else []
    mapped: dict[str, dict[str, Any]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("identity_key") or "").strip()
        if key:
            mapped[key] = item
    return mapped


def _manual_hold_diag(client: HAClient, entry_id: str) -> dict[str, Any]:
    value = _runtime_engine(client, entry_id).get("manual_hold", {})
    return dict(value) if isinstance(value, dict) else {}


def _active_hold_reasons(client: HAClient, entry_id: str, scope: str = SCOPE) -> set[str]:
    diag = _manual_hold_diag(client, entry_id)
    holds = diag.get("active_holds", [])
    reasons: set[str] = set()
    for item in holds if isinstance(holds, list) else []:
        if isinstance(item, dict) and item.get("scope") == scope:
            reasons.add(str(item.get("reason") or ""))
    return reasons


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


def _privacy_security_cfg(options: dict[str, Any]) -> dict[str, Any]:
    original = options.get("security", {})
    security = dict(original) if isinstance(original, dict) else {}
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
    entry = dict(source_map.get("entry_cam") or {})
    entry.update(
        {
            "id": "entry_cam",
            "display_name": entry.get("display_name") or "Front Door Camera",
            "enabled": True,
            "role": entry.get("role") or "entry",
            "privacy_entity": PRIVACY_SWITCH,
            "privacy_action": "turn_on",
            "manual_hold_entity": MANUAL_HOLD_ENTITY,
        }
    )
    source_map["entry_cam"] = entry
    security["camera_evidence_sources"] = source_map
    return security


def _upsert_reaction(client: HAClient, entry_id: str) -> None:
    cfg = {
        "reaction_type": "alarm_state_action",
        "alarm_states": ["armed_night"],
        "steps": [
            {
                "domain": "switch",
                "target": PRIVACY_SWITCH,
                "action": "switch.turn_on",
                "params": {"entity_id": PRIVACY_SWITCH},
            }
        ],
        "skip_house_states": ["guest", "vacation"],
        "enabled": True,
        "source_request": "live-test:camera-privacy-manual-hold",
    }
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {REACTION_ID: cfg},
                "labels": {REACTION_ID: "Live camera privacy manual hold"},
            },
        },
    )


def _call_recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _wait_for_semantic_proposal(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, dict[str, Any]] = {}
    while time.time() < deadline:
        client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
        time.sleep(poll_s)
        last = _proposal_map(client, entry_id)
        proposal = last.get(PROPOSAL_KEY)
        if isinstance(proposal, dict):
            return proposal
    raise AssertionError(f"semantic camera privacy proposal missing; last={last}")


def _wait_for_reaction(client: HAClient, entry_id: str, *, timeout_s: int, poll_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        reactions = _runtime_engine(client, entry_id).get("reactions", {})
        if isinstance(reactions, dict) and REACTION_ID in reactions:
            return
        time.sleep(poll_s)
    raise AssertionError(f"configured reaction {REACTION_ID!r} not visible in diagnostics")


def _wait_switch(client: HAClient, expected: str, *, timeout_s: int, poll_s: float) -> None:
    deadline = time.time() + timeout_s
    last = "<missing>"
    while time.time() < deadline:
        last = client.state_value(PRIVACY_SWITCH)
        if last == expected:
            return
        time.sleep(poll_s)
    raise AssertionError(f"timeout waiting for {PRIVACY_SWITCH}={expected!r}; last={last!r}")


def _wait_hold_reason(
    client: HAClient,
    entry_id: str,
    reason: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last: set[str] = set()
    while time.time() < deadline:
        _call_recompute(client)
        last = _active_hold_reasons(client, entry_id)
        if reason in last:
            return
        time.sleep(poll_s)
    raise AssertionError(f"manual hold reason {reason!r} not active; last={sorted(last)}")


def _wait_no_hold_for_scope(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last: set[str] = set()
    while time.time() < deadline:
        _call_recompute(client)
        last = _active_hold_reasons(client, entry_id)
        if not last:
            return
        time.sleep(poll_s)
    raise AssertionError(f"unexpected active manual hold for {SCOPE}: {sorted(last)}")


def _wait_blocked_step(
    client: HAClient,
    entry_id: str,
    expected_reason: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_steps: list[Any] = []
    while time.time() < deadline:
        _call_recompute(client)
        plan = _runtime_engine(client, entry_id).get("apply_plan", {})
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        last_steps = list(steps) if isinstance(steps, list) else []
        for step in last_steps:
            if not isinstance(step, dict):
                continue
            if (
                step.get("action") == "switch.turn_on"
                and step.get("target") == PRIVACY_SWITCH
                and str(step.get("blocked_by") or "") == expected_reason
            ):
                return step
        time.sleep(poll_s)
    raise AssertionError(f"blocked switch step not found; last_steps={last_steps}")


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


def _reset_lab(client: HAClient, *, timeout_s: int, poll_s: float) -> None:
    client.call_service("script", "turn_on", {"entity_id": RESET_SCRIPT})
    client.wait_state(PRIVACY_SWITCH, "off", timeout_s, poll_s)
    client.call_service("input_boolean", "turn_off", {"entity_id": MANUAL_HOLD_ENTITY})
    client.call_service("input_boolean", "turn_off", {"entity_id": PRIVACY_SWITCH_RAW})
    _set_alarm_state(client, "disarmed", timeout_s=timeout_s, poll_s=poll_s)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    required = [ALARM_ENTITY, PRIVACY_SWITCH, PRIVACY_SWITCH_RAW, MANUAL_HOLD_ENTITY, RESET_SCRIPT]
    missing = [entity_id for entity_id in required if not client.entity_exists(entity_id)]
    _assert(not missing, "missing required entities:\n- " + "\n- ".join(missing))

    entry_id = client.find_heima_entry_id()
    original_security = dict(_entry_options(client, entry_id).get("security") or {})
    try:
        print("Configuring camera privacy source...")
        _configure_security(
            client, entry_id, _privacy_security_cfg(_entry_options(client, entry_id))
        )
        proposal = _wait_for_semantic_proposal(
            client,
            entry_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        steps = proposal.get("steps", [])
        _assert(proposal.get("type") == "alarm_state_action", f"unexpected proposal: {proposal}")
        _assert(
            any(
                isinstance(step, dict)
                and step.get("action") == "switch.turn_on"
                and step.get("target") == PRIVACY_SWITCH
                for step in steps
                if isinstance(steps, list)
            ),
            f"proposal missing switch privacy step: {proposal}",
        )

        print("Installing live camera privacy reaction...")
        _upsert_reaction(client, entry_id)
        client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
        _wait_for_reaction(client, entry_id, timeout_s=args.timeout_s, poll_s=args.poll_s)

        print("Scenario A: explicit manual_hold_entity blocks camera privacy apply...")
        _reset_lab(client, timeout_s=args.timeout_s, poll_s=args.poll_s)
        client.call_service("input_boolean", "turn_on", {"entity_id": MANUAL_HOLD_ENTITY})
        _wait_hold_reason(
            client, entry_id, "helper_on", timeout_s=args.timeout_s, poll_s=args.poll_s
        )
        _set_alarm_state(client, "armed_night", timeout_s=args.timeout_s, poll_s=args.poll_s)
        _wait_blocked_step(
            client,
            entry_id,
            f"manual_hold:{SCOPE}:helper_on",
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        _wait_switch(client, "off", timeout_s=args.timeout_s, poll_s=args.poll_s)
        print("PASS scenario A")

        print("Scenario B: Heima-owned privacy switch apply does not activate hold...")
        client.call_service("input_boolean", "turn_off", {"entity_id": MANUAL_HOLD_ENTITY})
        _set_alarm_state(client, "disarmed", timeout_s=args.timeout_s, poll_s=args.poll_s)
        _wait_no_hold_for_scope(client, entry_id, timeout_s=args.timeout_s, poll_s=args.poll_s)
        _set_alarm_state(client, "armed_night", timeout_s=args.timeout_s, poll_s=args.poll_s)
        _wait_switch(client, "on", timeout_s=args.timeout_s, poll_s=args.poll_s)
        _wait_no_hold_for_scope(client, entry_id, timeout_s=args.timeout_s, poll_s=args.poll_s)
        print("PASS scenario B")

        print("Scenario C: external privacy switch change activates hold and blocks next apply...")
        client.call_service("switch", "turn_off", {"entity_id": PRIVACY_SWITCH})
        _wait_switch(client, "off", timeout_s=args.timeout_s, poll_s=args.poll_s)
        _wait_hold_reason(
            client, entry_id, "external_off", timeout_s=args.timeout_s, poll_s=args.poll_s
        )
        _set_alarm_state(client, "disarmed", timeout_s=args.timeout_s, poll_s=args.poll_s)
        _set_alarm_state(client, "armed_night", timeout_s=args.timeout_s, poll_s=args.poll_s)
        _wait_blocked_step(
            client,
            entry_id,
            f"manual_hold:{SCOPE}:external_off",
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        _wait_switch(client, "off", timeout_s=args.timeout_s, poll_s=args.poll_s)
        print("PASS scenario C")
    finally:
        print("Restoring original security config...")
        try:
            _configure_security(client, entry_id, original_security)
            client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
            client.call_service("input_boolean", "turn_off", {"entity_id": MANUAL_HOLD_ENTITY})
            client.call_service("input_boolean", "turn_off", {"entity_id": PRIVACY_SWITCH_RAW})
            _set_alarm_state(client, "disarmed", timeout_s=args.timeout_s, poll_s=args.poll_s)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: cleanup failed: {exc}", file=sys.stderr)

    print("PASS: camera privacy manual hold live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
