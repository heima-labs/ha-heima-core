#!/usr/bin/env python3
"""Live options-flow checks for the camera privacy policy editor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient

CAMERA_SOURCE_ID = "live_privacy_policy_cam"
PRIVACY_SWITCH = "switch.test_heima_heater_relay"
RAW_REACTION_ID = "live-raw-camera-privacy-policy"
STALE_REACTION_ID = "live-stale-camera-privacy-policy"
MANAGED_REACTION_ID = "camera_privacy_policy__live_privacy_policy_cam__armed_away__any__turn_off"
STALE_MATERIALIZED_REACTION_ID = (
    "camera_privacy_policy__missing_live_camera__disarmed__any__turn_on"
)


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


def _configured_reactions(client: HAClient, entry_id: str) -> dict[str, Any]:
    reactions = dict(_entry_options(client, entry_id).get("reactions") or {})
    configured = reactions.get("configured", {})
    return dict(configured) if isinstance(configured, dict) else {}


def _configure_security_source(client: HAFlowClient, entry_id: str) -> None:
    options = _entry_options(client, entry_id)
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
        "display_name": "Live Privacy Policy Camera",
        "enabled": True,
        "role": "interior",
        "privacy_entity": PRIVACY_SWITCH,
    }
    security["camera_evidence_sources"] = source_map

    flow = client.options_flow_init(entry_id)
    flow_id = str(flow["flow_id"])
    try:
        _expect_step(flow, "init")
        step = _menu_next(client, flow_id, "security")
        _expect_step(step, "security")
        step = client.options_flow_configure(flow_id, security)
        _expect_step(step, "init")
        saved = _menu_next(client, flow_id, "save")
        _assert(saved.get("type") == "create_entry", f"unexpected save result: {saved}")
    finally:
        client.options_flow_abort(flow_id)


def _upsert_live_reactions(client: HAClient, entry_id: str) -> None:
    raw_cfg = {
        "reaction_type": "alarm_state_action",
        "enabled": True,
        "alarm_states": ["armed_away"],
        "steps": [
            {
                "domain": "switch",
                "target": PRIVACY_SWITCH,
                "action": "switch.turn_off",
                "params": {"entity_id": PRIVACY_SWITCH},
            }
        ],
    }
    stale_cfg = {
        "reaction_type": "alarm_state_action",
        "enabled": True,
        "source_template_id": "security.camera_privacy_policy",
        "alarm_states": ["disarmed"],
        "steps": [
            {
                "domain": "switch",
                "target": "switch.live_missing_privacy",
                "action": "switch.turn_on",
                "params": {"entity_id": "switch.live_missing_privacy"},
            }
        ],
        "camera_privacy_policy": {
            "camera_source_id": "missing_live_camera",
            "privacy_entity": "switch.live_missing_privacy",
            "house_filter_mode": "always",
            "house_states": [],
            "privacy_action": "turn_on",
        },
    }
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {
                    RAW_REACTION_ID: raw_cfg,
                    STALE_REACTION_ID: stale_cfg,
                },
                "labels": {
                    RAW_REACTION_ID: "Live raw camera privacy",
                    STALE_REACTION_ID: "Live stale camera privacy",
                },
            },
        },
    )
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})


def _save_current_flow(client: HAFlowClient, flow_id: str) -> None:
    step = client.options_flow_configure(flow_id, {"action": "back"})
    _expect_step(step, "init")
    saved = _menu_next(client, flow_id, "save")
    _assert(saved.get("type") == "create_entry", f"unexpected save result: {saved}")


def _adopt_imported_policy(client: HAFlowClient, entry_id: str) -> None:
    flow = client.options_flow_init(entry_id)
    flow_id = str(flow["flow_id"])
    try:
        _expect_step(flow, "init")
        step = _menu_next(client, flow_id, "camera_privacy_policies")
        _expect_step(step, "camera_privacy_policies")
        step = client.options_flow_configure(
            flow_id,
            {"action": "edit", "policy": RAW_REACTION_ID},
        )
        _expect_step(step, "camera_privacy_policy_form")
        step = client.options_flow_configure(
            flow_id,
            {
                "camera_source_id": CAMERA_SOURCE_ID,
                "alarm_states": ["armed_away"],
                "house_filter_mode": "always",
                "house_states": [],
                "privacy_action": "turn_off",
                "enabled": True,
            },
        )
        _expect_step(step, "camera_privacy_policies")
        _save_current_flow(client, flow_id)
    finally:
        client.options_flow_abort(flow_id)


def _delete_managed_policy(client: HAFlowClient, entry_id: str) -> None:
    flow = client.options_flow_init(entry_id)
    flow_id = str(flow["flow_id"])
    try:
        _expect_step(flow, "init")
        step = _menu_next(client, flow_id, "camera_privacy_policies")
        _expect_step(step, "camera_privacy_policies")
        step = client.options_flow_configure(
            flow_id,
            {"action": "delete", "policy": MANAGED_REACTION_ID},
        )
        _expect_step(step, "camera_privacy_policy_delete_confirm")
        step = client.options_flow_configure(flow_id, {"confirm": True})
        _expect_step(step, "camera_privacy_policies")
        _save_current_flow(client, flow_id)
    finally:
        client.options_flow_abort(flow_id)


def _delete_generic_reaction(client: HAFlowClient, entry_id: str, reaction_id: str) -> None:
    if reaction_id not in _configured_reactions(client, entry_id):
        return
    flow = client.options_flow_init(entry_id)
    flow_id = str(flow["flow_id"])
    try:
        _expect_step(flow, "init")
        step = _menu_next(client, flow_id, "reactions_edit")
        if step.get("step_id") == "init":
            return
        _expect_step(step, "reactions_edit")
        step = client.options_flow_configure(flow_id, {"reaction": reaction_id})
        if step.get("step_id") == "init":
            return
        _expect_step(step, "reactions_edit_form")
        step = client.options_flow_configure(flow_id, {"delete_reaction": True})
        _expect_step(step, "reactions_delete_confirm")
        step = client.options_flow_configure(flow_id, {"confirm": True})
        _expect_step(step, "init")
        saved = _menu_next(client, flow_id, "save")
        _assert(saved.get("type") == "create_entry", f"unexpected save result: {saved}")
    finally:
        client.options_flow_abort(flow_id)


def run(ha_url: str, ha_token: str) -> None:
    client = HAFlowClient(ha_url, ha_token)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")
    try:
        print("Configuring live privacy source and raw/stale policies...")
        _configure_security_source(client, entry_id)
        _upsert_live_reactions(client, entry_id)

        print("Adopting imported camera privacy policy through domain editor...")
        _adopt_imported_policy(client, entry_id)
        configured = _configured_reactions(client, entry_id)
        _assert(RAW_REACTION_ID not in configured, "raw imported policy was not removed")
        _assert(MANAGED_REACTION_ID in configured, "managed camera policy was not created")
        _assert(STALE_REACTION_ID in configured, "stale managed policy was not preserved")

        print("Deleting managed camera privacy policy through domain editor...")
        _delete_managed_policy(client, entry_id)
        configured = _configured_reactions(client, entry_id)
        _assert(MANAGED_REACTION_ID not in configured, "managed camera policy was not deleted")
        _assert(STALE_REACTION_ID in configured, "stale managed policy was removed by delete")
    finally:
        print("Cleaning up live camera privacy policy artifacts...")
        for reaction_id in (
            MANAGED_REACTION_ID,
            RAW_REACTION_ID,
            STALE_REACTION_ID,
            STALE_MATERIALIZED_REACTION_ID,
        ):
            try:
                _delete_generic_reaction(client, entry_id, reaction_id)
            except Exception as err:  # noqa: BLE001
                print(f"WARN: cleanup could not delete {reaction_id}: {err}")

    print("PASS: camera privacy policy editor live checks passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()
    run(args.ha_url, args.ha_token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
