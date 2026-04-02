#!/usr/bin/env python3
"""Live test for lighting slot collision diagnostics."""

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
    _assert(
        result.get("step_id") == step_id,
        f"expected step_id={step_id!r}, got={result.get('step_id')!r}: {result}",
    )


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _used_lighting_buckets(client: HAFlowClient, entry_id: str, room_id: str) -> set[int]:
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "reactions_edit")
        if step.get("step_id") != "reactions_edit":
            return set()
        data_schema = step.get("data_schema")
        if not isinstance(data_schema, list):
            return set()
        buckets: set[int] = set()
        for field in data_schema:
            if not isinstance(field, dict):
                continue
            options = field.get("options")
            if not isinstance(options, list):
                continue
            for item in options:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label") or item.get("value") or "")
                if not label.startswith(f"Luci {room_id} — Lunedì ~"):
                    continue
                try:
                    hhmm = label.split("~", 1)[1].split(" ", 1)[0]
                    minute = int(hhmm.split(":", 1)[0]) * 60 + int(hhmm.split(":", 1)[1])
                except Exception:
                    continue
                buckets.add((minute // 30) * 30)
        return buckets
    finally:
        time.sleep(0.1)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


def _find_unused_bucket(entry_id: str, client: HAFlowClient, room_id: str) -> int:
    used = _used_lighting_buckets(client, entry_id, room_id)
    for hour in range(23, -1, -1):
        for minute in (30, 0):
            bucket = (hour * 60 + minute) // 30 * 30
            if bucket not in used:
                return bucket
    raise AssertionError(f"no free lighting bucket found for room {room_id}")


def _reaction_summary(client: HAClient, entry_id: str) -> dict[str, Any]:
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


def _wait_for_heima_entry_id(client: HAClient, *, timeout_s: int, poll_s: float) -> str:
    probe = HAClient(client.base_url, client.token, timeout_s=min(5, client.timeout_s))
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            return probe.find_heima_entry_id()
        except Exception:
            time.sleep(poll_s)
    raise AssertionError("heima config entry not available within timeout")


def _wait_for_slot_collision(
    client: HAClient,
    entry_id: str,
    *,
    expected_slot_key: str,
    expected_ids: set[str],
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        summary = _reaction_summary(client, entry_id)
        slot_collisions = dict(summary.get("lighting_slot_collisions") or {})
        collision_ids = slot_collisions.get(expected_slot_key) or []
        if expected_ids.issubset(set(str(item) for item in collision_ids)):
            return summary
        time.sleep(poll_s)
    raise AssertionError(
        f"lighting slot collision {expected_slot_key!r} with ids {sorted(expected_ids)!r} "
        "not visible in diagnostics"
    )


def _lighting_cfg(
    *,
    room_id: str,
    weekday: int,
    scheduled_min: int,
    entity_id: str,
    brightness: int,
    color_temp_kelvin: int,
    scene_tag: str,
) -> dict[str, Any]:
    return {
        "reaction_class": "LightingScheduleReaction",
        "reaction_type": "lighting_scene_schedule",
        "origin": "admin_authored",
        "author_kind": "admin",
        "source_template_id": "lighting.scene_schedule.basic",
        "room_id": room_id,
        "weekday": weekday,
        "scheduled_min": scheduled_min,
        "window_half_min": 10,
        "entity_steps": [
            {
                "entity_id": entity_id,
                "action": "on",
                "brightness": brightness,
                "color_temp_kelvin": color_temp_kelvin,
            }
        ],
        "source_proposal_identity_key": (
            f"lighting_scene_schedule|room={room_id}|weekday={weekday}"
            f"|bucket={(scheduled_min // 30) * 30}|scene={scene_tag}"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima lighting slot collision diagnostics live test")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--entry-id")
    parser.add_argument("--timeout-s", type=int, default=25)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = str(args.entry_id or "").strip() or _wait_for_heima_entry_id(
        client, timeout_s=args.timeout_s, poll_s=args.poll_s
    )
    print(f"Using heima entry_id={entry_id}")

    room_id = "living"
    weekday = 0
    bucket = _find_unused_bucket(entry_id, client, room_id)
    time_a = f"{bucket // 60:02d}:{bucket % 60:02d}"
    time_b = f"{bucket // 60:02d}:{(bucket % 60) + 10:02d}"
    slot_key = f"lighting_scene_schedule|room={room_id}|weekday=0|bucket={bucket}"
    print(f"Using free lighting bucket {slot_key} with times {time_a} and {time_b}")

    suffix = str(int(time.time()))
    reaction_a = f"live-slot-a-{suffix}"
    reaction_b = f"live-slot-b-{suffix}"
    configured = {
        reaction_a: _lighting_cfg(
            room_id=room_id,
            weekday=weekday,
            scheduled_min=bucket,
            entity_id="light.test_heima_living_main",
            brightness=190,
            color_temp_kelvin=2850,
            scene_tag="a",
        ),
        reaction_b: _lighting_cfg(
            room_id=room_id,
            weekday=weekday,
            scheduled_min=bucket + 10,
            entity_id="light.test_heima_living_spot",
            brightness=160,
            color_temp_kelvin=2600,
            scene_tag="b",
        ),
    }
    labels = {
        reaction_a: f"Luci {room_id} — Lunedì ~{time_a} (1 entità)",
        reaction_b: f"Luci {room_id} — Lunedì ~{time_b} (1 entità)",
    }

    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {"configured": configured, "labels": labels},
        },
    )
    print("Injected two configured lighting reactions in the same slot.")

    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    summary = _wait_for_slot_collision(
        client,
        entry_id,
        expected_slot_key=slot_key,
        expected_ids={reaction_a, reaction_b},
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    print(f"Reactions summary: {summary}")

    slot_collisions = dict(summary.get("lighting_slot_collisions") or {})
    _assert(slot_key in slot_collisions, f"missing slot collision entry for {slot_key!r}: {slot_collisions}")
    _assert(
        {reaction_a, reaction_b}.issubset(set(str(item) for item in slot_collisions[slot_key])),
        f"slot collision entry missing expected ids: {slot_collisions[slot_key]!r}",
    )

    print("PASS: lighting slot collisions are visible in diagnostics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
