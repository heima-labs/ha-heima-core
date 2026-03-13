#!/usr/bin/env python3
"""Live config-flow E2E checks for Heima.

This script runs against a real Home Assistant instance using the config entry
options-flow REST API and validates that critical config-flow scenarios do not
crash with server-side errors.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
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


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _expect_step(result: dict[str, Any], step_id: str) -> None:
    _assert(isinstance(result, dict), f"invalid flow result type: {type(result)}")
    _assert(result.get("step_id") == step_id, f"expected step_id={step_id}, got={result.get('step_id')}")


def _menu_next(client: HAClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _extract_select_values(step_result: dict[str, Any], field_name: str) -> list[str]:
    """Best-effort extraction of selectable values from HA flow JSON."""
    data_schema = step_result.get("data_schema")
    if not isinstance(data_schema, list):
        return []

    for field in data_schema:
        if not isinstance(field, dict):
            continue
        if str(field.get("name")) != field_name:
            continue

        def _collect_from_options(options: Any) -> list[str]:
            values: list[str] = []
            if isinstance(options, list):
                for item in options:
                    if isinstance(item, str):
                        values.append(item)
                    elif isinstance(item, dict):
                        value = item.get("value")
                        if value not in (None, ""):
                            values.append(str(value))
                    elif isinstance(item, (list, tuple)) and item:
                        values.append(str(item[0]))
            elif isinstance(options, dict):
                for key in options:
                    values.append(str(key))
            return [v for v in values if v]

        # Common shape: {"options": [...]}
        direct = _collect_from_options(field.get("options"))
        if direct:
            return direct

        # Selector shape: {"selector": {"select": {"options": [...]}}}
        selector_cfg = field.get("selector")
        if isinstance(selector_cfg, dict):
            select_cfg = selector_cfg.get("select")
            if isinstance(select_cfg, dict):
                nested = _collect_from_options(select_cfg.get("options"))
                if nested:
                    return nested
    return []


def scenario_notifications_no_crash(client: HAClient, entry_id: str) -> None:
    print("== Scenario A: notifications malformed payload does not crash ==")
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")

    step = _menu_next(client, flow_id, "notifications")
    _expect_step(step, "notifications")

    # Intentionally noisy/odd payload. Expected behavior: no 500 crash.
    payload = {
        "routes": ["persistent_notification"],
        "recipients": {"family": ["notify.mobile_app_a"]},
        "recipient_groups": {"admins": ["missing_user"]},
        "route_targets": ["admins", "missing_target"],
        "enabled_event_categories": ["people", "invalid_category"],
        "dedup_window_s": 60,
        "rate_limit_per_key_s": 300,
        "occupancy_mismatch_policy": "smart",
        "occupancy_mismatch_min_derived_rooms": 2,
        "occupancy_mismatch_persist_s": 600,
        "security_mismatch_policy": "smart",
        "security_mismatch_persist_s": 300,
    }
    try:
        submit = client.options_flow_configure(flow_id, payload)
        _expect_step(submit, "init")
        print("PASS scenario A (accepted malformed payload without crash)")
        return
    except HAApiError as err:
        # For multi_select fields, HA may reject invalid options with HTTP 400.
        # This is valid schema behavior and still proves "no server crash".
        text = str(err)
        if "HTTP 400" in text and "enabled_event_categories" in text:
            print("PASS scenario A (schema validation 400, no crash)")
            return
        raise


def scenario_heating_branch_validation_no_crash(client: HAClient, entry_id: str) -> None:
    print("== Scenario B: heating vacation-curve missing bindings => validation, not crash ==")
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")

    step = _menu_next(client, flow_id, "heating")
    _expect_step(step, "heating")

    # Remove vacation bindings on purpose.
    step = client.options_flow_configure(
        flow_id,
        {
            "climate_entity": "climate.test_heima_thermostat",
            "apply_mode": "delegate_to_scheduler",
            "temperature_step": 0.5,
            "manual_override_guard": True,
        },
    )
    _expect_step(step, "heating_branches_menu")

    step = _menu_next(client, flow_id, "heating_branches_edit")
    _expect_step(step, "heating_branches_edit")

    step = client.options_flow_configure(flow_id, {"house_state": "vacation"})
    _expect_step(step, "heating_branch_edit_form")

    # Phase 1: with branch currently "disabled", schema does not yet expose
    # vacation_* fields. First submit only flips branch and lets HA rebuild form schema.
    step = client.options_flow_configure(
        flow_id,
        {
            "house_state": "vacation",
            "branch": "vacation_curve",
        },
    )
    _expect_step(step, "heating_branch_edit_form")

    # Phase 2: now submit vacation branch parameters and expect domain validation.
    step = client.options_flow_configure(
        flow_id,
        {
            "house_state": "vacation",
            "branch": "vacation_curve",
            "vacation_ramp_down_h": 8,
            "vacation_ramp_up_h": 1,
            "vacation_min_temp": 16.5,
            "vacation_comfort_temp": 19.5,
            "vacation_min_total_hours_for_ramp": 24,
        },
    )
    _expect_step(step, "heating_branch_edit_form")
    errors = step.get("errors", {}) or {}
    _assert(errors.get("branch") == "missing_vacation_bindings", f"unexpected errors: {errors}")
    print("PASS scenario B")


def scenario_people_quorum_drops_person_entity(client: HAClient, entry_id: str) -> None:
    print("== Scenario C: edit person ha_person -> quorum and check stale person_entity ==")
    entry_before = client.get_entry(entry_id)
    options_before = dict(entry_before.get("options") or {})

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")

    step = _menu_next(client, flow_id, "people_menu")
    _expect_step(step, "people_menu")
    step = _menu_next(client, flow_id, "people_edit")
    _expect_step(step, "people_edit")

    slugs = _extract_select_values(step, "person")
    if not slugs:
        print("SKIP scenario C (no selectable people in people_edit step)")
        return
    slug = slugs[0]

    step = client.options_flow_configure(flow_id, {"person": slug})
    _expect_step(step, "people_edit_form")

    # Keep slug immutable, switch to quorum with explicit source.
    step = client.options_flow_configure(
        flow_id,
        {
            "slug": slug,
            "display_name": f"{slug}-live-test",
            "presence_method": "quorum",
            "sources": ["binary_sensor.test_heima_room_studio_motion"],
            "group_strategy": "quorum",
            "required": 1,
            "arrive_hold_s": 10,
            "leave_hold_s": 120,
            "enable_override": True,
        },
    )
    _expect_step(step, "people_menu")

    end = _menu_next(client, flow_id, "people_save")
    _assert(end.get("type") == "create_entry", f"expected create_entry, got: {end}")

    entry_after = client.get_entry(entry_id)
    options_after = dict(entry_after.get("options") or {})
    data_after = dict(entry_after.get("data") or {})
    people_after = list(options_after.get("people_named") or data_after.get("people_named") or [])
    if people_after:
        edited = next((p for p in people_after if str(p.get("slug")) == slug), None)
        _assert(edited is not None, f"edited person not found: {slug}")
        _assert(str(edited.get("presence_method")) == "quorum", f"unexpected method: {edited}")
        if "person_entity" in edited and edited.get("person_entity"):
            raise AssertionError(
                "stale person_entity still present for quorum method "
                f"(slug={slug}, person_entity={edited.get('person_entity')})"
            )
    else:
        # Fallback for HA builds where entry detail does not expose full options payload:
        # reopen person form and ensure we can roundtrip quorum payload without person_entity.
        init2 = client.options_flow_init(entry_id)
        flow_id2 = str(init2["flow_id"])
        _expect_step(init2, "init")
        step2 = _menu_next(client, flow_id2, "people_menu")
        _expect_step(step2, "people_menu")
        step2 = _menu_next(client, flow_id2, "people_edit")
        _expect_step(step2, "people_edit")
        step2 = client.options_flow_configure(flow_id2, {"person": slug})
        _expect_step(step2, "people_edit_form")
        step2 = client.options_flow_configure(
            flow_id2,
            {
                "slug": slug,
                "display_name": f"{slug}-live-test",
                "presence_method": "quorum",
                "sources": ["binary_sensor.test_heima_room_studio_motion"],
                "group_strategy": "quorum",
                "required": 1,
                "arrive_hold_s": 10,
                "leave_hold_s": 120,
                "enable_override": True,
            },
        )
        _expect_step(step2, "people_menu")
        end2 = _menu_next(client, flow_id2, "people_save")
        _assert(end2.get("type") == "create_entry", f"expected create_entry, got: {end2}")

    print("PASS scenario C")


def _notification_payload_from_entry(client: HAClient, entry_id: str) -> dict[str, Any]:
    """Best-effort snapshot of current notifications options for safe roundtrip edits."""
    defaults: dict[str, Any] = {
        "routes": [],
        "recipients": {},
        "recipient_groups": {},
        "route_targets": [],
        "enabled_event_categories": ["people", "occupancy", "lighting", "heating", "security"],
        "dedup_window_s": 60,
        "rate_limit_per_key_s": 300,
        "occupancy_mismatch_policy": "smart",
        "occupancy_mismatch_min_derived_rooms": 2,
        "occupancy_mismatch_persist_s": 600,
        "security_mismatch_policy": "smart",
        "security_mismatch_event_mode": "explicit_only",
        "security_mismatch_persist_s": 300,
    }
    try:
        entry = client.get_entry(entry_id)
        options = dict(entry.get("options") or {})
        notifications = dict(options.get("notifications") or {})
        merged = dict(defaults)
        merged.update(notifications)
        return merged
    except Exception:  # noqa: BLE001
        return defaults


def scenario_security_mismatch_event_modes_roundtrip(client: HAFlowClient, entry_id: str) -> None:
    print("== Scenario D: security mismatch event mode roundtrip ==")
    payload = _notification_payload_from_entry(client, entry_id)
    original_mode = str(payload.get("security_mismatch_event_mode", "explicit_only"))
    accepted_modes = ["explicit_only", "generic_only", "dual_emit"]

    for mode in accepted_modes:
        init = client.options_flow_init(entry_id)
        flow_id = str(init["flow_id"])
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "notifications")
        _expect_step(step, "notifications")
        submit_payload = dict(payload)
        submit_payload["security_mismatch_event_mode"] = mode
        submit = client.options_flow_configure(flow_id, submit_payload)
        _expect_step(submit, "init")

    # Restore original mode to avoid persisting unexpected state in shared test labs.
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "notifications")
    _expect_step(step, "notifications")
    restore_payload = dict(payload)
    restore_payload["security_mismatch_event_mode"] = original_mode
    submit = client.options_flow_configure(flow_id, restore_payload)
    _expect_step(submit, "init")

    print("PASS scenario D")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--entry-id", default="")
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = args.entry_id or client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    scenario_notifications_no_crash(client, entry_id)
    scenario_heating_branch_validation_no_crash(client, entry_id)
    scenario_people_quorum_drops_person_entity(client, entry_id)
    scenario_security_mismatch_event_modes_roundtrip(client, entry_id)

    print("All config-flow live scenarios passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
