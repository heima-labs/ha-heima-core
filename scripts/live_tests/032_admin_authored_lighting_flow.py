#!/usr/bin/env python3
"""Live test for admin-authored lighting proposal flow."""

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


def _has_entity_selector(
    step_result: dict[str, Any], field_name: str, *, expected_domain: str
) -> bool:
    data_schema = step_result.get("data_schema")
    if not isinstance(data_schema, list):
        return False
    for field in data_schema:
        if not isinstance(field, dict) or str(field.get("name")) != field_name:
            continue
        selector_cfg = field.get("selector")
        if not isinstance(selector_cfg, dict):
            return False
        entity_cfg = selector_cfg.get("entity")
        if not isinstance(entity_cfg, dict):
            return False
        domains = entity_cfg.get("domain") or []
        if isinstance(domains, str):
            domains = [domains]
        return expected_domain in {str(item) for item in domains}
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima admin-authored lighting flow live test")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=20)
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
            "lighting.scene_schedule.basic" in template_ids,
            f"lighting template not exposed: {template_ids}",
        )

        step = client.options_flow_configure(
            flow_id, {"template_id": "lighting.scene_schedule.basic"}
        )
        _expect_step(step, "admin_authored_lighting_schedule")

        room_ids = _extract_select_values(step, "room_id")
        weekday_values = _extract_select_values(step, "weekday")
        print(f"Rooms: {room_ids}")
        print(f"Weekdays: {weekday_values}")
        has_light_selector = _has_entity_selector(
            step, "light_entities", expected_domain="light"
        )
        print(f"Light entity selector present: {has_light_selector}")

        _assert(room_ids, "no room options available")
        _assert(weekday_values, "no weekday options available")
        _assert(has_light_selector, "light_entities is not exposed as a light entity selector")

        payload = {
            "room_id": room_ids[0],
            "weekday": "0" if "0" in weekday_values else weekday_values[0],
            "scheduled_time": "20:00",
            "light_entities": ["light.test_heima_living_main"],
            "action": "on",
            "brightness": 190,
            "color_temp_kelvin": 2850,
        }
        step = client.options_flow_configure(flow_id, payload)
        _expect_step(step, "proposals")

        placeholders = step.get("description_placeholders") or {}
        proposal_label = str(placeholders.get("proposal_label") or "")
        proposal_details = str(placeholders.get("proposal_details") or "")
        print(f"Proposal label: {proposal_label}")
        print(f"Proposal details:\n{proposal_details}")

        _assert("admin" in proposal_label.lower(), "proposal label does not mark admin origin")
        _assert(
            "lighting.scene_schedule.basic" in proposal_details,
            "proposal details do not expose template id",
        )
        _assert(
            ("bozza richiesta dall'amministratore" in proposal_details.lower())
            or ("draft requested by the administrator" in proposal_details.lower()),
            "proposal details do not expose admin-authored origin",
        )

        print("PASS: admin-authored lighting flow created a reviewable proposal")
        return 0
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
