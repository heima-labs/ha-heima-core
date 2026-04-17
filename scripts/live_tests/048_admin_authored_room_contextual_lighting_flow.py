#!/usr/bin/env python3
"""Live test for admin-authored room contextual lighting assist flow."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
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


def _configured_contextual_reaction(client: HAClient, entry_id: str) -> tuple[str, dict[str, Any]] | None:
    entry = client.get_entry(entry_id)
    options = dict(entry.get("options") or {})
    reactions = dict(options.get("reactions") or {})
    configured = dict(reactions.get("configured") or {})
    for reaction_id, raw in configured.items():
        cfg = dict(raw) if isinstance(raw, dict) else {}
        if str(cfg.get("reaction_type") or "") != "room_contextual_lighting_assist":
            continue
        if str(cfg.get("room_id") or "") != "studio":
            continue
        return str(reaction_id), cfg
    return None


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


def _wait_for_contextual_reaction(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> tuple[str, dict[str, Any]]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        found = _configured_contextual_reaction(client, entry_id)
        if found is not None:
            return found
        time.sleep(poll_s)
    entry = client.get_entry(entry_id)
    options = dict(entry.get("options") or {})
    reactions = dict(options.get("reactions") or {})
    configured = dict(reactions.get("configured") or {})
    compact = {
        reaction_id: {
            "reaction_type": str(dict(raw).get("reaction_type") or ""),
            "room_id": str(dict(raw).get("room_id") or ""),
            "source_template_id": str(dict(raw).get("source_template_id") or ""),
        }
        for reaction_id, raw in configured.items()
        if isinstance(raw, dict)
    }
    raise AssertionError(
        "contextual lighting reaction not visible in config entry within timeout; "
        f"configured snapshot={compact}"
    )


def _is_duplicate_error(result: dict[str, Any]) -> bool:
    errors = result.get("errors")
    return isinstance(errors, dict) and str(errors.get("base") or "") == "duplicate"


def _policy_json(light_entity: str) -> str:
    payload = {
        "profiles": {
            "workday_focus": {
                "entity_steps": [
                    {
                        "entity_id": light_entity,
                        "action": "on",
                        "brightness": 180,
                        "color_temp_kelvin": 4300,
                    }
                ]
            },
            "day_generic": {
                "entity_steps": [
                    {
                        "entity_id": light_entity,
                        "action": "on",
                        "brightness": 140,
                        "color_temp_kelvin": 3600,
                    }
                ]
            },
            "evening_relax": {
                "entity_steps": [
                    {
                        "entity_id": light_entity,
                        "action": "on",
                        "brightness": 100,
                        "color_temp_kelvin": 2700,
                    }
                ]
            },
            "night_navigation": {
                "entity_steps": [
                    {
                        "entity_id": light_entity,
                        "action": "on",
                        "brightness": 25,
                        "color_temp_kelvin": 2200,
                    }
                ]
            },
        },
        "rules": [
            {
                "profile": "workday_focus",
                "house_state_in": ["working"],
                "time_window": {"start": "08:00", "end": "18:30"},
            },
            {
                "profile": "day_generic",
                "house_state_in": ["home", "relax"],
                "time_window": {"start": "08:00", "end": "18:30"},
            },
            {
                "profile": "evening_relax",
                "time_window": {"start": "18:30", "end": "23:30"},
            },
            {
                "profile": "night_navigation",
                "time_window": {"start": "23:30", "end": "06:30"},
            },
        ],
        "default_profile": "day_generic",
        "followup_window_s": 900,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima admin-authored room contextual lighting flow live test"
    )
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=20)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    existing = _configured_contextual_reaction(client, entry_id)
    if existing is not None:
        reaction_id, cfg = existing
        print(f"Preexisting contextual reaction found: {reaction_id}")
        print(f"default_profile={cfg.get('default_profile')} profiles={sorted(dict(cfg.get('profiles') or {}))}")
        print("PASS: contextual lighting reaction already configured in lab")
        return 0

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")

        step = _menu_next(client, flow_id, "admin_authored_create")
        _expect_step(step, "admin_authored_create")
        template_ids = _extract_select_values(step, "template_id")
        print(f"Templates exposed: {template_ids}")
        _assert(
            "room.contextual_lighting_assist.basic" in template_ids,
            f"contextual lighting template not exposed: {template_ids}",
        )

        step = client.options_flow_configure(
            flow_id, {"template_id": "room.contextual_lighting_assist.basic"}
        )
        _expect_step(step, "admin_authored_room_contextual_lighting_assist")

        room_ids = _extract_select_values(step, "room_id")
        _assert(room_ids, "no room options available")
        room_id = "studio" if "studio" in room_ids else room_ids[0]

        step = client.options_flow_configure(
            flow_id,
            {
                "room_id": room_id,
                "primary_signal_name": "room_lux",
                "primary_bucket": "ok",
                "primary_bucket_match_mode": "lte",
                "preset": "all_day_adaptive",
                "light_entities": ["light.test_heima_studio_desk"],
            },
        )
        _expect_step(step, "admin_authored_room_contextual_lighting_assist_json")

        details = str((step.get("description_placeholders") or {}).get("policy_summary") or "")
        print(f"Generated policy summary: {details}")
        _assert("profiles=" in details, "policy summary missing profiles count")

        result = client.options_flow_configure(
            flow_id,
            {"config_json": _policy_json("light.test_heima_studio_desk")},
        )
        if _is_duplicate_error(result):
            print("Contextual reaction already configured: duplicate slot detected")
            summary = _diagnostics_reactions(client, entry_id)
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
            print("PASS: contextual lighting reaction already present in lab")
            return 0
        if result.get("step_id") != "init":
            print(f"Unexpected JSON submit result: {result}")
        _expect_step(result, "init")

        reaction_id, cfg = _wait_for_contextual_reaction(
            client,
            entry_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print(f"Configured contextual reaction: {reaction_id}")
        print(
            f"default_profile={cfg.get('default_profile')} "
            f"profiles={sorted(dict(cfg.get('profiles') or {}))}"
        )
        _assert(
            str(cfg.get("source_template_id") or "") == "room.contextual_lighting_assist.basic",
            f"unexpected source_template_id: {cfg.get('source_template_id')!r}",
        )
        _assert(
            str(cfg.get("reaction_type") or "") == "room_contextual_lighting_assist",
            f"unexpected reaction_type: {cfg.get('reaction_type')!r}",
        )
        _assert(
            str(cfg.get("default_profile") or "") == "day_generic",
            f"unexpected default_profile: {cfg.get('default_profile')!r}",
        )

        summary = _diagnostics_reactions(client, entry_id)
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

        print("PASS: admin-authored contextual lighting flow created an accepted reaction")
        return 0
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
