#!/usr/bin/env python3
"""Live test for binary trigger modes in admin-authored room signal assist."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


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
    _assert(isinstance(result, dict), f"invalid flow result type: {type(result)}")
    _assert(
        result.get("step_id") == step_id,
        f"expected step_id={step_id!r}, got={result.get('step_id')!r}",
    )


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _extract_select_values(step_result: dict[str, Any], field_name: str) -> list[str]:
    data_schema = step_result.get("data_schema")
    if not isinstance(data_schema, list):
        return []
    for field in data_schema:
        if not isinstance(field, dict) or str(field.get("name")) != field_name:
            continue
        values: list[str] = []
        options = field.get("options")
        if isinstance(options, list):
            for item in options:
                if isinstance(item, str):
                    values.append(item)
                elif isinstance(item, (list, tuple)) and item:
                    values.append(str(item[0]))
                elif isinstance(item, dict):
                    value = item.get("value")
                    if value not in (None, ""):
                        values.append(str(value))
        elif isinstance(options, dict):
            values.extend(str(key) for key in options.keys())
        selector_cfg = field.get("selector")
        if isinstance(selector_cfg, dict):
            select_cfg = selector_cfg.get("select")
            if isinstance(select_cfg, dict):
                nested = select_cfg.get("options")
                if isinstance(nested, list):
                    for item in nested:
                        if isinstance(item, str):
                            values.append(item)
                        elif isinstance(item, (list, tuple)) and item:
                            values.append(str(item[0]))
                        elif isinstance(item, dict):
                            value = item.get("value")
                            if value not in (None, ""):
                                values.append(str(value))
        return [value for value in values if value]
    return []


def _proposal_details(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_details") or "")


def _find_duplicate_error(step_result: dict[str, Any]) -> bool:
    errors = step_result.get("errors")
    return isinstance(errors, dict) and str(errors.get("base") or "") == "duplicate"


def _diagnostics_reactions(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    plugins = runtime.get("plugins", {})
    if not isinstance(plugins, dict):
        return {}
    summary = plugins.get("configured_reaction_summary", {})
    return summary if isinstance(summary, dict) else {}


def _wait_for_template_reaction(
    client: HAClient,
    entry_id: str,
    *,
    template_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        summary = _diagnostics_reactions(client, entry_id)
        by_template = summary.get("by_template_id") or {}
        if isinstance(by_template, dict) and int(by_template.get(template_id) or 0) >= 1:
            return summary
        time.sleep(poll_s)
    raise AssertionError(f"{template_id} reaction not visible in diagnostics within timeout")


def _submit_unique_state_change_signal_assist(
    client: HAFlowClient,
    flow_id: str,
    *,
    room_id: str,
) -> dict[str, Any]:
    primary_name_candidates = ["window", "window_state", "binary_state", "projector"]
    for primary_signal_name in primary_name_candidates:
        step = client.options_flow_configure(
            flow_id,
            {
                "room_id": room_id,
                "primary_signal_entities": ["binary_sensor.test_heima_room_bathroom_motion"],
                "primary_signal_name": primary_signal_name,
                "primary_threshold_mode": "state_change",
                "primary_threshold": 1.0,
                "corroboration_signal_entities": [],
                "corroboration_signal_name": "corroboration",
                "corroboration_threshold_mode": "rise",
                "corroboration_threshold": 0.0,
                "action_entities": ["script.test_heima_reset"],
            },
        )
        if step.get("step_id") == "proposals":
            return step
        if _find_duplicate_error(step):
            continue
        raise AssertionError(f"unexpected authoring result: {step}")
    raise AssertionError("unable to find a free state_change room signal assist slot")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima admin-authored room signal assist binary modes live test"
    )
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=20)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")

        step = _menu_next(client, flow_id, "admin_authored_create")
        _expect_step(step, "admin_authored_create")

        step = client.options_flow_configure(flow_id, {"template_id": "room.signal_assist.basic"})
        _expect_step(step, "admin_authored_room_signal_assist")

        mode_options = _extract_select_values(step, "primary_threshold_mode")
        print(f"Primary mode options: {mode_options}")
        for expected in ("switch_on", "switch_off", "state_change"):
            _assert(expected in mode_options, f"missing binary mode {expected!r}: {mode_options}")

        room_ids = _extract_select_values(step, "room_id")
        _assert(room_ids, "no room options available")
        room_id = "bathroom" if "bathroom" in room_ids else room_ids[0]

        step = _submit_unique_state_change_signal_assist(client, flow_id, room_id=room_id)
        _expect_step(step, "proposals")
        details = _proposal_details(step)
        print(f"Proposal details before accept:\n{details}")
        _assert(
            ("Condizione primaria: Cambio stato (1.0)" in details)
            or ("Primary condition: State change (1.0)" in details),
            "proposal details do not expose state_change primary condition",
        )

        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        if result.get("type") == "form":
            _expect_step(result, "proposals")
        elif result.get("type") == "menu":
            _expect_step(result, "init")
        else:
            raise AssertionError(f"unexpected options flow result after accept: {result}")

        summary = _wait_for_template_reaction(
            client,
            entry_id,
            template_id="room.signal_assist.basic",
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print("Diagnostics reactions summary:")
        print(summary)
        print("PASS: binary room-signal modes are exposed and state_change authoring works")
        return 0
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
