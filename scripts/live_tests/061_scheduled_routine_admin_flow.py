#!/usr/bin/env python3
# ruff: noqa: I001
"""Live E2E for admin-authored scheduled_routine."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


TARGET_ENTITY = "switch.test_heima_bathroom_fan"
RESET_SCRIPT = "script.test_heima_reset"
HA_TEST_CONTAINER = "homeassistant-test"


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
    got = str(result.get("step_id") or "")
    _assert(got == step_id, f"expected step_id={step_id!r}, got={got!r}: {result}")


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _finalize_flow(client: HAFlowClient, flow_id: str) -> dict[str, Any]:
    result = _menu_next(client, flow_id, "save")
    _assert(result.get("type") == "create_entry", f"expected create_entry on save, got: {result}")
    return result


def _extract_select_values(step_result: dict[str, Any], field_name: str) -> list[str]:
    data_schema = step_result.get("data_schema")
    if not isinstance(data_schema, list):
        return []
    for field in data_schema:
        if not isinstance(field, dict) or str(field.get("name") or "") != field_name:
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
        selector = field.get("selector")
        if isinstance(selector, dict):
            select_cfg = selector.get("select")
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


def _diagnostics_root(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    return raw if isinstance(raw, dict) else {}


def _engine_reactions(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    runtime = _diagnostics_root(client, entry_id).get("data", {}).get("runtime", {})
    engine = runtime.get("engine", {})
    reactions = engine.get("reactions", {})
    if not isinstance(reactions, dict):
        return {}
    return {str(k): dict(v) for k, v in reactions.items() if isinstance(v, dict)}


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    entry = client.get_entry(entry_id)
    options = entry.get("options", {})
    return dict(options) if isinstance(options, dict) else {}


def _configured_reactions(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    options = _entry_options(client, entry_id)
    reactions = dict(options.get("reactions", {}) or {})
    configured = reactions.get("configured", {})
    configured_map = (
        {str(k): dict(v) for k, v in configured.items() if isinstance(v, dict)}
        if isinstance(configured, dict)
        else {}
    )
    configured_map.update(_configured_reactions_from_container(entry_id))
    return configured_map


def _configured_reactions_from_container(entry_id: str) -> dict[str, dict[str, Any]]:
    cmd = [
        "docker",
        "exec",
        HA_TEST_CONTAINER,
        "cat",
        "/config/.storage/core.config_entries",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {}
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    entries = payload.get("data", {}).get("entries", []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("entry_id") or "") != entry_id:
            continue
        options = dict(entry.get("options") or {})
        reactions = dict(options.get("reactions") or {})
        configured = reactions.get("configured", {})
        if not isinstance(configured, dict):
            return {}
        return {str(k): dict(v) for k, v in configured.items() if isinstance(v, dict)}
    return {}


def _reaction_inventory(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    inventory = _engine_reactions(client, entry_id)
    inventory.update(_configured_reactions(client, entry_id))
    return inventory


def _wait_until_safe_current_minute() -> tuple[str, str]:
    while True:
        now = datetime.now().astimezone()
        if now.second <= 40:
            return str(now.weekday()), now.strftime("%H:%M")
        sleep_s = max(1.5, 61 - now.second)
        print(f"Waiting {sleep_s:.1f}s to avoid minute rollover during authoring...")
        time.sleep(sleep_s)


def _configured_scheduled_routines(
    client: HAClient,
    entry_id: str,
    *,
    target_entity: str,
) -> list[tuple[str, dict[str, Any]]]:
    matches: list[tuple[str, dict[str, Any]]] = []
    for reaction_id, cfg in _reaction_inventory(client, entry_id).items():
        if str(cfg.get("reaction_type") or "") != "scheduled_routine":
            continue
        targets = {str(item).strip() for item in list(cfg.get("target_entities") or [])}
        if target_entity in targets:
            matches.append((reaction_id, cfg))
            continue
        steps = list(cfg.get("steps") or [])
        step_targets = {
            str(step.get("target") or "").strip()
            for step in steps
            if isinstance(step, dict) and str(step.get("target") or "").strip()
        }
        if target_entity in step_targets:
            matches.append((reaction_id, cfg))
    matches.sort(key=lambda item: item[0])
    return matches


def _delete_reaction_via_flow(client: HAFlowClient, entry_id: str, reaction_id: str) -> None:
    cfg = _configured_reactions(client, entry_id).get(reaction_id, {})
    targets = list(cfg.get("target_entities") or [])
    steps = list(cfg.get("steps") or [])
    if not targets:
        targets = [
            str(step.get("target") or "").strip()
            for step in steps
            if isinstance(step, dict) and str(step.get("target") or "").strip()
        ]
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    flow_closed = False
    try:
        step = _menu_next(client, flow_id, "reactions_edit")
        _expect_step(step, "reactions_edit")
        step = client.options_flow_configure(flow_id, {"reaction": reaction_id})
        _expect_step(step, "reactions_edit_form")
        step = client.options_flow_configure(
            flow_id,
            {
                "enabled": bool(cfg.get("enabled", True)),
                "weekday": str(cfg.get("weekday", 0)),
                "scheduled_time": _format_hhmm(int(cfg.get("scheduled_min", 0))),
                "routine_kind": str(cfg.get("routine_kind") or "entity_action"),
                "target_entities": targets,
                "entity_action": str(cfg.get("entity_action") or "turn_on"),
                "house_state_in": list(cfg.get("house_state_in") or []),
                "skip_if_anyone_home": bool(cfg.get("skip_if_anyone_home", False)),
                "delete_reaction": True,
            },
        )
        _expect_step(step, "reactions_delete_confirm")
        step = client.options_flow_configure(flow_id, {"confirm": True})
        _expect_step(step, "init")
        if reaction_id in _configured_reactions(client, entry_id):
            save_result = _finalize_flow(client, flow_id)
            print(f"Delete save result keys: {sorted(save_result.keys())}")
        flow_closed = True
    finally:
        if not flow_closed:
            try:
                client.options_flow_abort(flow_id)
            except Exception:
                pass


def _cleanup_test_routines(client: HAFlowClient, entry_id: str) -> None:
    for reaction_id, _cfg in _configured_scheduled_routines(
        client, entry_id, target_entity=TARGET_ENTITY
    ):
        print(f"Deleting pre-existing scheduled routine: {reaction_id}")
        _delete_reaction_via_flow(client, entry_id, reaction_id)


def _wait_for_configured_routine(
    client: HAClient,
    entry_id: str,
    *,
    target_entity: str,
    weekday: str,
    scheduled_time: str,
    timeout_s: int,
    poll_s: float,
) -> tuple[str, dict[str, Any]]:
    deadline = time.time() + timeout_s
    expected_min = _parse_hhmm_to_min(scheduled_time)
    while time.time() < deadline:
        matches = _configured_scheduled_routines(client, entry_id, target_entity=target_entity)
        for reaction_id, cfg in matches:
            if str(cfg.get("weekday", "")) != weekday:
                continue
            if int(cfg.get("scheduled_min", -1)) != expected_min:
                continue
            return reaction_id, cfg
        time.sleep(poll_s)
    raise AssertionError("configured scheduled_routine not visible within timeout")


def _maybe_find_configured_routine(
    client: HAClient,
    entry_id: str,
    *,
    target_entity: str,
    weekday: str,
    scheduled_time: str,
) -> tuple[str, dict[str, Any]] | None:
    expected_min = _parse_hhmm_to_min(scheduled_time)
    matches = _configured_scheduled_routines(client, entry_id, target_entity=target_entity)
    for reaction_id, cfg in matches:
        if str(cfg.get("weekday", "")) != weekday:
            continue
        if int(cfg.get("scheduled_min", -1)) != expected_min:
            continue
        return reaction_id, cfg
    return None


def _parse_hhmm_to_min(value: str) -> int:
    hour_s, minute_s = value.split(":", 1)
    return int(hour_s) * 60 + int(minute_s)


def _format_hhmm(minute_of_day: int) -> str:
    hour = minute_of_day // 60
    minute = minute_of_day % 60
    return f"{hour:02d}:{minute:02d}"


def _wait_for_reaction_gone(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if reaction_id not in _reaction_inventory(client, entry_id):
            return
        time.sleep(poll_s)
    raise AssertionError(f"reaction still configured after delete: {reaction_id}")


def _find_security_presence_reaction_id(client: HAClient, entry_id: str) -> str:
    for reaction_id, cfg in _reaction_inventory(client, entry_id).items():
        if str(cfg.get("reaction_type") or "") == "vacation_presence_simulation":
            return reaction_id
    raise AssertionError("vacation_presence_simulation reaction not configured")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima scheduled_routine live E2E")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=30)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")
    created_reaction_id = ""

    print("Resetting test lab baseline...")
    client.call_service("script", "turn_on", {"entity_id": RESET_SCRIPT})
    client.wait_state(TARGET_ENTITY, "off", args.timeout_s, args.poll_s)

    _cleanup_test_routines(client, entry_id)

    weekday, scheduled_time = _wait_until_safe_current_minute()
    print(f"Authoring routine for current slot: weekday={weekday} time={scheduled_time}")

    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    flow_closed = False
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "admin_authored_create")
        _expect_step(step, "admin_authored_create")
        template_ids = _extract_select_values(step, "template_id")
        print(f"Templates exposed: {template_ids}")
        _assert(
            "scheduled_routine.basic" in template_ids,
            f"scheduled routine template not exposed: {template_ids}",
        )

        step = client.options_flow_configure(flow_id, {"template_id": "scheduled_routine.basic"})
        _expect_step(step, "admin_authored_scheduled_routine")

        step = client.options_flow_configure(
            flow_id,
            {
                "weekday": weekday,
                "scheduled_time": scheduled_time,
                "routine_kind": "entity_action",
                "target_entities": [TARGET_ENTITY],
                "entity_action": "turn_on",
                "house_state_in": [],
                "skip_if_anyone_home": False,
            },
        )
        _assert(step.get("type") == "create_entry", f"expected create_entry, got: {step}")
        print(f"Create result keys: {sorted(step.keys())}")
        print(f"Create result data keys: {sorted(dict(step.get('data') or {}).keys())}")
        flow_closed = True
    finally:
        if not flow_closed:
            try:
                client.options_flow_abort(flow_id)
            except Exception:
                pass

    try:
        created_reaction_id, cfg = _wait_for_configured_routine(
            client,
            entry_id,
            target_entity=TARGET_ENTITY,
            weekday=weekday,
            scheduled_time=scheduled_time,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print(f"Configured scheduled_routine id={created_reaction_id}")
        print(cfg)

        client.wait_state(TARGET_ENTITY, "on", args.timeout_s, args.poll_s)
        print(f"{TARGET_ENTITY} turned on as expected")

        reactions = _engine_reactions(client, entry_id)
        security_reaction_id = _find_security_presence_reaction_id(client, entry_id)
        _assert(
            security_reaction_id in reactions,
            f"{security_reaction_id} diagnostics not available in engine reactions",
        )
        security_diag = reactions[security_reaction_id]
        source_ids = list(security_diag.get("source_reaction_ids") or [])
        print(f"{security_reaction_id} source_reaction_ids: {source_ids}")
        _assert(
            created_reaction_id not in source_ids,
            "scheduled_routine leaked into vacation_presence_simulation source_reaction_ids",
        )

        print(
            "PASS: scheduled_routine admin flow configured and executed without affecting security presence sources"
        )
        return 0
    finally:
        if created_reaction_id:
            print("Cleaning up scheduled routine and restoring lab baseline...")
            _delete_reaction_via_flow(client, entry_id, created_reaction_id)
            _wait_for_reaction_gone(
                client,
                entry_id,
                reaction_id=created_reaction_id,
                timeout_s=args.timeout_s,
                poll_s=args.poll_s,
            )
        client.call_service("script", "turn_on", {"entity_id": RESET_SCRIPT})
        client.wait_state(TARGET_ENTITY, "off", args.timeout_s, args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
