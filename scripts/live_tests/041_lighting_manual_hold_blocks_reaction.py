#!/usr/bin/env python3
"""Live test: lighting manual hold blocks runtime lighting reactions."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
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
    _assert(
        result.get("step_id") == step_id,
        f"expected step_id={step_id!r}, got={result.get('step_id')!r}: {result}",
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
                elif isinstance(item, dict) and item.get("value") not in (None, ""):
                    values.append(str(item["value"]))
        return [value for value in values if value]
    return []


def _diagnostics_engine(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    engine = runtime.get("engine", {})
    return engine if isinstance(engine, dict) else {}


def _diagnostics_reactions_summary(client: HAClient, entry_id: str) -> dict[str, Any]:
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


def _wait_for_reaction_id(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        summary = _diagnostics_reactions_summary(client, entry_id)
        reaction_ids = {str(item) for item in summary.get("reaction_ids") or []}
        if reaction_id in reaction_ids:
            return
        time.sleep(poll_s)
    raise AssertionError(f"configured reaction {reaction_id!r} not visible in diagnostics")


def _configure_lighting_room_hold(
    client: HAFlowClient,
    entry_id: str,
    *,
    room_id: str,
) -> None:
    flow = client.options_flow_init(entry_id)
    flow_id = str(flow["flow_id"])
    try:
        _expect_step(flow, "init")
        step = _menu_next(client, flow_id, "lighting_rooms_menu")
        _expect_step(step, "lighting_rooms_menu")
        step = _menu_next(client, flow_id, "lighting_rooms_edit")
        _expect_step(step, "lighting_rooms_edit")
        room_ids = _extract_select_values(step, "room")
        _assert(room_id in room_ids, f"room {room_id!r} not available in lighting config: {room_ids}")
        step = client.options_flow_configure(flow_id, {"room": room_id})
        _expect_step(step, "lighting_rooms_edit_form")
        step = client.options_flow_configure(
            flow_id,
            {
                "room_id": room_id,
                "enable_manual_hold": True,
            },
        )
        _expect_step(step, "lighting_rooms_menu")
        saved = _menu_next(client, flow_id, "lighting_rooms_save")
        _assert(saved.get("type") == "create_entry", f"unexpected lighting room save result: {saved}")
    finally:
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


def _pick_room_id(client: HAFlowClient, entry_id: str) -> str:
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "admin_authored_create")
        _expect_step(step, "admin_authored_create")
        step = client.options_flow_configure(flow_id, {"template_id": "lighting.scene_schedule.basic"})
        _expect_step(step, "admin_authored_lighting_schedule")
        room_ids = _extract_select_values(step, "room_id")
        _assert(room_ids, "no room options available")
        return room_ids[0]
    finally:
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


def _wait_for_guard_block(
    client: HAClient,
    entry_id: str,
    *,
    room_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        engine = _diagnostics_engine(client, entry_id)
        behaviors = engine.get("behaviors", {})
        if isinstance(behaviors, dict):
            guard = behaviors.get("LightingReactionGuardBehavior", {})
            if isinstance(guard, dict):
                blocked_total = int(guard.get("blocked_total") or 0)
                blocked_by_room = dict(guard.get("blocked_by_room") or {})
                if blocked_total > 0 and int(blocked_by_room.get(room_id) or 0) > 0:
                    return guard
        time.sleep(poll_s)
    raise AssertionError(f"manual hold blocker for room {room_id!r} not visible in guard diagnostics")


def _room_light_entity(room_id: str) -> str:
    mapping = {
        "living": "light.test_heima_living_main",
        "studio": "light.test_heima_studio_main",
    }
    return mapping.get(room_id, "light.test_heima_living_main")


def _lighting_cfg(
    *,
    room_id: str,
    weekday: int,
    scheduled_min: int,
    entity_id: str,
) -> dict[str, Any]:
    bucket = (scheduled_min // 30) * 30
    return {
        "reaction_class": "LightingScheduleReaction",
        "reaction_type": "lighting_scene_schedule",
        "origin": "admin_authored",
        "author_kind": "admin",
        "source_template_id": "lighting.scene_schedule.basic",
        "room_id": room_id,
        "weekday": weekday,
        "scheduled_min": scheduled_min,
        "window_half_min": 0,
        "entity_steps": [
            {
                "entity_id": entity_id,
                "action": "on",
                "brightness": 128,
                "color_temp_kelvin": 3200,
            }
        ],
        "source_proposal_identity_key": (
            f"lighting_scene_schedule|room={room_id}|weekday={weekday}"
            f"|bucket={bucket}|scene={entity_id}|on|b=128|k=3200|rgb=-"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima live test: manual hold blocks reaction-generated lighting steps"
    )
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    client.call_service("heima", "command", {"command": "learning_reset", "target": {"entry_id": entry_id}})

    room_id = _pick_room_id(client, entry_id)
    print(f"Selected room for test: {room_id}")
    _configure_lighting_room_hold(client, entry_id, room_id=room_id)
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})

    now_local = datetime.now().astimezone()
    scheduled_dt = now_local + timedelta(minutes=1)
    weekday = scheduled_dt.weekday()
    scheduled_min = scheduled_dt.hour * 60 + scheduled_dt.minute
    hhmm = f"{scheduled_dt.hour:02d}:{scheduled_dt.minute:02d}"
    print(f"Using next slot: room={room_id} weekday={weekday} time={hhmm}")

    reaction_id = f"live-manual-hold-{int(time.time())}"
    entity_id = _room_light_entity(room_id)
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {
                    reaction_id: _lighting_cfg(
                        room_id=room_id,
                        weekday=weekday,
                        scheduled_min=scheduled_min,
                        entity_id=entity_id,
                    )
                },
                "labels": {reaction_id: f"Luci {room_id} — ~{hhmm}"},
            },
        },
    )
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    _wait_for_reaction_id(
        client,
        entry_id,
        reaction_id=reaction_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    print(f"Reaction created: {reaction_id}")

    client.call_service(
        "heima",
        "set_override",
        {"scope": "lighting_room_hold", "id": room_id, "override": True},
    )
    print("Manual hold enabled before due slot.")

    guard = _wait_for_guard_block(
        client,
        entry_id,
        room_id=room_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    print(f"Guard diagnostics: {guard}")
    _assert(room_id in set(guard.get("manual_hold_rooms") or []), f"room {room_id!r} missing in guard diagnostics: {guard}")
    _assert(int(guard.get("blocked_total") or 0) > 0, f"guard did not block any step: {guard}")
    _assert(int(dict(guard.get("blocked_by_room") or {}).get(room_id) or 0) > 0, f"guard did not block room {room_id!r}: {guard}")
    print("PASS: manual lighting hold blocks reaction-generated lighting steps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
