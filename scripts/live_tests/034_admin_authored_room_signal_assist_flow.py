#!/usr/bin/env python3
"""Live test for admin-authored room signal assist flow."""

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
        options = field.get("options")
        values: list[str] = []
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


def _wait_for_admin_authored_reaction(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        summary = _diagnostics_reactions(client, entry_id)
        by_origin = summary.get("by_origin") or {}
        if isinstance(by_origin, dict) and int(by_origin.get("admin_authored") or 0) >= 1:
            return summary
        time.sleep(poll_s)
    raise AssertionError("admin_authored reaction not visible in diagnostics within timeout")


def _submit_unique_admin_authored_room_signal_assist(
    client: HAFlowClient,
    flow_id: str,
    *,
    room_id: str,
) -> dict[str, Any]:
    primary_name_candidates = ["humidity", "humidity_burst", "steam", "moisture"]
    for primary_signal_name in primary_name_candidates:
        step = client.options_flow_configure(
            flow_id,
            {
                "room_id": room_id,
                "primary_signal_entities": ["sensor.test_heima_bathroom_humidity"],
                "primary_signal_name": primary_signal_name,
                "primary_threshold_mode": "rise",
                "primary_threshold": 8.0,
                "corroboration_signal_entities": ["sensor.test_heima_bathroom_temperature"],
                "corroboration_signal_name": "temperature",
                "corroboration_threshold_mode": "rise",
                "corroboration_threshold": 0.8,
                "action_entities": ["script.test_heima_reset"],
            },
        )
        if step.get("step_id") == "proposals":
            return step
        if _find_duplicate_error(step):
            continue
        raise AssertionError(f"unexpected authoring result: {step}")
    raise AssertionError("unable to find a free room signal assist slot for admin-authored proposal")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima admin-authored room signal assist flow live test"
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
        template_ids = _extract_select_values(step, "template_id")
        print(f"Templates exposed: {template_ids}")
        _assert(
            "room.signal_assist.basic" in template_ids,
            f"room.signal_assist template not exposed: {template_ids}",
        )

        step = client.options_flow_configure(flow_id, {"template_id": "room.signal_assist.basic"})
        _expect_step(step, "admin_authored_room_signal_assist")

        room_ids = _extract_select_values(step, "room_id")
        _assert(room_ids, "no room options available")
        room_id = "bathroom" if "bathroom" in room_ids else room_ids[0]

        step = _submit_unique_admin_authored_room_signal_assist(
            client,
            flow_id,
            room_id=room_id,
        )
        _expect_step(step, "proposals")
        details = _proposal_details(step)
        print(f"Proposal details before accept:\n{details}")
        _assert(
            "Template: room.signal_assist.basic" in details,
            "proposal details do not expose room.signal_assist template id",
        )
        _assert(
            ("Segnale primario:" in details) or ("Primary signal:" in details),
            "proposal details do not expose primary signal",
        )
        _assert(
            ("Azioni configurate:" in details) or ("Configured actions:" in details),
            "proposal details do not expose configured actions",
        )

        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        if result.get("type") == "form":
            _expect_step(result, "proposals")
        elif result.get("type") == "menu":
            _expect_step(result, "init")
        else:
            raise AssertionError(f"unexpected options flow result after accept: {result}")

        summary = _wait_for_admin_authored_reaction(
            client,
            entry_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print("Diagnostics reactions summary:")
        print(summary)

        by_origin = summary.get("by_origin") or {}
        by_author_kind = summary.get("by_author_kind") or {}
        _assert(
            int(by_origin.get("admin_authored") or 0) >= 1,
            f"admin_authored reaction not counted in by_origin: {by_origin}",
        )
        _assert(
            int(by_author_kind.get("admin") or 0) >= 1,
            f"admin reaction not counted in by_author_kind: {by_author_kind}",
        )

        print("PASS: admin-authored room signal assist flow created an accepted reaction")
        return 0
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
