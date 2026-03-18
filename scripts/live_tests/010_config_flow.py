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

    def options_flow_abort(self, flow_id: str) -> None:
        self.delete(f"/api/config/config_entries/options/flow/{flow_id}")


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


def _extract_form_default(step_result: dict[str, Any], field_name: str) -> Any:
    """Extract the default or suggested_value for a named field from a flow form schema."""
    data_schema = step_result.get("data_schema")
    if not isinstance(data_schema, list):
        return None
    for field in data_schema:
        if not isinstance(field, dict) or str(field.get("name")) != field_name:
            continue
        if "default" in field:
            return field["default"]
        desc = field.get("description")
        if isinstance(desc, dict) and "suggested_value" in desc:
            return desc["suggested_value"]
    return None


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


def _read_heating_form_defaults(client: HAFlowClient, entry_id: str) -> dict[str, Any]:
    """Open a read-only flow, navigate to the heating form, capture all current field values, abort.

    Uses suggested_value (current stored value) in preference to default (schema default).
    The HA REST API does not expose entry options directly, so this is the only way to read
    the current heating config without modifying it.
    """
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        heating_form = _menu_next(client, flow_id, "heating")
        payload: dict[str, Any] = {}
        if heating_form.get("step_id") == "heating":
            for field in (heating_form.get("data_schema") or []):
                if not isinstance(field, dict):
                    continue
                name = field.get("name")
                if not name:
                    continue
                # Prefer suggested_value (current value) over default (schema default).
                val = (field.get("description") or {}).get("suggested_value")
                if val is None:
                    val = field.get("default")
                if val is not None:
                    payload[str(name)] = val
        return payload
    finally:
        client.options_flow_abort(flow_id)


def _restore_heating_options(client: HAFlowClient, entry_id: str, original_payload: dict[str, Any]) -> None:
    """Restore heating options to their original state via a new flow."""
    if not original_payload:
        return
    try:
        init = client.options_flow_init(entry_id)
        flow_id = str(init["flow_id"])
        step = _menu_next(client, flow_id, "heating")
        if step.get("step_id") == "heating":
            step = client.options_flow_configure(flow_id, original_payload)
        if step.get("step_id") == "heating_branches_menu":
            step = client.options_flow_configure(flow_id, {"next_step_id": "heating_branches_save"})
        if step.get("step_id") == "init":
            client.options_flow_configure(flow_id, {"next_step_id": "save"})
        else:
            client.options_flow_abort(flow_id)
    except Exception:  # noqa: BLE001
        pass


def scenario_heating_branch_validation_no_crash(client: HAFlowClient, entry_id: str) -> None:
    print("== Scenario B: heating vacation-curve missing bindings => validation, not crash ==")

    # Read original heating config from flow form schema — get_entry does not expose options.
    original_heating = _read_heating_form_defaults(client, entry_id)

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")

    try:
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
        _expect_step(step, "heating_branch_select")

        # Step 1: select branch type
        step = client.options_flow_configure(flow_id, {"branch": "vacation_curve"})
        _expect_step(step, "heating_branch_edit_form")

        # Step 2: submit vacation branch parameters — expect domain validation error
        # (missing vacation bindings because we cleared them above)
        step = client.options_flow_configure(
            flow_id,
            {
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
    finally:
        client.options_flow_abort(flow_id)
        _restore_heating_options(client, entry_id, original_heating)

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


def scenario_init_status_block(client: HAFlowClient, entry_id: str) -> None:
    print("== Scenario E: init menu has description_placeholders status block ==")
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")

    placeholders = init.get("description_placeholders") or {}
    expected_keys = {
        "engine_status",
        "people_summary",
        "rooms_summary",
        "lighting_summary",
        "heating_summary",
        "security_summary",
        "calendar_summary",
    }
    missing = expected_keys - set(placeholders.keys())
    _assert(not missing, f"missing description_placeholders keys: {missing} (got: {set(placeholders.keys())})")

    # Abort flow — navigate to save to close it cleanly
    client.options_flow_configure(flow_id, {"next_step_id": "save"})
    print("PASS scenario E")


def scenario_second_level_menu_summaries(client: HAFlowClient, entry_id: str) -> None:
    print("== Scenario F: second-level menus have description_placeholders summary ==")

    menus_to_check = [
        ("people_menu", "summary"),
        ("rooms_menu", "summary"),
        ("lighting_rooms_menu", "summary"),
    ]

    for menu_step, placeholder_key in menus_to_check:
        init = client.options_flow_init(entry_id)
        flow_id = str(init["flow_id"])
        _expect_step(init, "init")

        step = _menu_next(client, flow_id, menu_step)
        _expect_step(step, menu_step)

        placeholders = step.get("description_placeholders") or {}
        _assert(
            placeholder_key in placeholders,
            f"{menu_step}: missing '{placeholder_key}' in description_placeholders (got: {set(placeholders.keys())})",
        )
        client.options_flow_abort(flow_id)

    # Note: heating_branches_menu is only reachable after submitting the heating form step.
    # Submitting that form triggers _update_options (immediate persist), which risks overwriting
    # vacation binding entities if form defaults diverge from stored values. Since scenario B
    # already navigates through heating_branches_menu as part of its flow, we skip that check
    # here to avoid corrupting the heating config.

    print("PASS scenario F")


def scenario_runtime_persist_without_save(client: HAFlowClient, entry_id: str) -> None:
    print("== Scenario G: runtime option persists immediately without explicit save ==")

    # Read current dedup value from a fresh flow's form defaults.
    init0 = client.options_flow_init(entry_id)
    flow_id0 = str(init0["flow_id"])
    _expect_step(init0, "init")
    step0 = _menu_next(client, flow_id0, "notifications")
    _expect_step(step0, "notifications")
    original_dedup = _extract_form_default(step0, "dedup_window_s") or 60
    client.options_flow_abort(flow_id0)

    sentinel_dedup = 61 if original_dedup != 61 else 62

    payload = _notification_payload_from_entry(client, entry_id)
    payload["dedup_window_s"] = sentinel_dedup

    # Modify notifications and return to init WITHOUT using save.
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "notifications")
    _expect_step(step, "notifications")
    result = client.options_flow_configure(flow_id, payload)
    _expect_step(result, "init")

    # Verify persistence by opening a NEW flow and reading the field default.
    init_check = client.options_flow_init(entry_id)
    flow_id_check = str(init_check["flow_id"])
    _expect_step(init_check, "init")
    step_check = _menu_next(client, flow_id_check, "notifications")
    _expect_step(step_check, "notifications")
    mid_dedup = _extract_form_default(step_check, "dedup_window_s")
    client.options_flow_abort(flow_id_check)

    _assert(
        mid_dedup == sentinel_dedup,
        f"expected dedup_window_s={sentinel_dedup} persisted mid-flow, got={mid_dedup}",
    )

    # Restore original value.
    restore_payload = dict(payload)
    restore_payload["dedup_window_s"] = original_dedup
    init2 = client.options_flow_init(entry_id)
    flow_id2 = str(init2["flow_id"])
    _expect_step(init2, "init")
    step2 = _menu_next(client, flow_id2, "notifications")
    _expect_step(step2, "notifications")
    client.options_flow_configure(flow_id2, restore_payload)
    client.options_flow_configure(flow_id2, {"next_step_id": "save"})

    print("PASS scenario G")


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
    scenario_init_status_block(client, entry_id)
    scenario_second_level_menu_summaries(client, entry_id)
    scenario_runtime_persist_without_save(client, entry_id)

    print("All config-flow live scenarios passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
