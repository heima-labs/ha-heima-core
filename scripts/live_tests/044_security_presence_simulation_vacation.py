#!/usr/bin/env python3
"""Live test for security presence simulation admin-authored vacation flow."""

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
                elif isinstance(item, dict):
                    value = item.get("value")
                    if value not in (None, ""):
                        values.append(str(value))
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


def _find_duplicate_error(step_result: dict[str, Any]) -> bool:
    errors = step_result.get("errors")
    return isinstance(errors, dict) and str(errors.get("base") or "") == "duplicate"


def _diagnostics_root(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    return raw if isinstance(raw, dict) else {}


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    entry = client.get_entry(entry_id)
    options = entry.get("options", {})
    return dict(options) if isinstance(options, dict) else {}


def _configured_reactions(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    raw = _diagnostics_root(client, entry_id)
    options = raw.get("data", {}).get("entry", {}).get("options", {})
    reactions = dict(options.get("reactions", {}) or {})
    configured = reactions.get("configured", {})
    if not isinstance(configured, dict):
        return {}
    return {str(k): dict(v) for k, v in configured.items() if isinstance(v, dict)}


def _engine_reactions(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    engine = runtime.get("engine", {})
    reactions = engine.get("reactions", {})
    if not isinstance(reactions, dict):
        return {}
    return {str(k): dict(v) for k, v in reactions.items() if isinstance(v, dict)}


def _scheduler_pending_jobs(client: HAClient, entry_id: str) -> list[dict[str, Any]]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    scheduler = runtime.get("scheduler", {})
    pending = scheduler.get("pending_jobs", {})
    if isinstance(pending, list):
        return [item for item in pending if isinstance(item, dict)]
    return []


def _find_presence_reaction_id(client: HAClient, entry_id: str) -> str | None:
    configured = _configured_reactions(client, entry_id)
    candidates: list[tuple[str, str]] = []
    for reaction_id, cfg in configured.items():
        if str(cfg.get("reaction_class") or "") != "VacationPresenceSimulationReaction":
            continue
        created_at = str(cfg.get("created_at") or "")
        candidates.append((created_at, reaction_id))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _wait_for_presence_reaction(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        reaction_id = _find_presence_reaction_id(client, entry_id)
        if reaction_id:
            return reaction_id
        time.sleep(poll_s)
    raise AssertionError("presence simulation reaction not visible in configured reactions within timeout")


def _first_person_override_entity(client: HAClient) -> str | None:
    for state in client.all_states():
        entity_id = str(state.get("entity_id") or "")
        if entity_id.startswith("select.heima_person_") and entity_id.endswith("_override"):
            return entity_id
    return None


def _set_person_override(client: HAClient, entity_id: str, option: str) -> None:
    client.call_service("select", "select_option", {"entity_id": entity_id, "option": option})


def _wait_reaction_ready(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        reactions = _engine_reactions(client, entry_id)
        diag = reactions.get(reaction_id)
        if isinstance(diag, dict):
            if bool(diag.get("source_profile_ready")) and int(diag.get("tonight_plan_count") or 0) >= 1:
                return diag
        time.sleep(poll_s)
    reactions = _engine_reactions(client, entry_id)
    raise AssertionError(f"presence simulation diagnostics not ready: {reactions.get(reaction_id)}")


def _wait_scheduler_job(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    prefix = f"security_presence_simulation:{reaction_id}:"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for job in _scheduler_pending_jobs(client, entry_id):
            if str(job.get("job_id") or "").startswith(prefix):
                return job
        time.sleep(poll_s)
    raise AssertionError(f"scheduler job for {reaction_id!r} not visible within timeout")


def _ensure_security_presence_learning_enabled(client: HAFlowClient, entry_id: str) -> None:
    options = _entry_options(client, entry_id)
    learning = dict(options.get("learning", {}) or {})
    enabled = [
        str(item).strip()
        for item in learning.get("enabled_plugin_families") or []
        if str(item).strip()
    ]
    required_families = {"lighting", "security_presence_simulation"}
    if required_families.issubset(set(enabled)):
        return

    for family in ("lighting", "security_presence_simulation"):
        if family not in enabled:
            enabled.append(family)
    payload = {
        "context_signal_entities": list(learning.get("context_signal_entities") or []),
        "enabled_plugin_families": enabled,
    }
    for key in ("outdoor_lux_entity", "outdoor_temp_entity", "weather_entity"):
        value = learning.get(key)
        if value not in (None, ""):
            payload[key] = value

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "learning")
        _expect_step(step, "learning")
        result = client.options_flow_configure(flow_id, payload)
        _expect_step(result, "init")
        save = _menu_next(client, flow_id, "save")
        _assert(save.get("type") == "create_entry", f"expected create_entry on save, got: {save}")
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


def _ensure_lighting_source_reaction(client: HAFlowClient, entry_id: str) -> None:
    configured = _configured_reactions(client, entry_id)
    for cfg in configured.values():
        if str(cfg.get("reaction_class") or "") == "LightingScheduleReaction":
            return

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "admin_authored_create")
        _expect_step(step, "admin_authored_create")
        step = client.options_flow_configure(
            flow_id, {"template_id": "lighting.scene_schedule.basic"}
        )
        _expect_step(step, "admin_authored_lighting_schedule")
        room_ids = _extract_select_values(step, "room_id")
        weekday_values = _extract_select_values(step, "weekday")
        _assert(room_ids, "no room options available for lighting bootstrap")
        _assert(weekday_values, "no weekday options available for lighting bootstrap")
        created = False
        candidate_rooms: list[tuple[str, str]] = []
        if "living" in room_ids:
            candidate_rooms.append(("living", "light.test_heima_living_main"))
        if "studio" in room_ids:
            candidate_rooms.append(("studio", "light.test_heima_studio_main"))
        for room_id in room_ids:
            if room_id not in {item[0] for item in candidate_rooms}:
                if room_id == "bathroom":
                    continue
                candidate_rooms.append((room_id, f"light.test_heima_{room_id}_main"))

        for room_id, entity_id in candidate_rooms:
            for weekday in weekday_values:
                for scheduled_time in ("19:00", "19:30", "20:00", "20:30", "21:00", "21:30"):
                    step = client.options_flow_configure(
                        flow_id,
                        {
                            "room_id": room_id,
                            "weekday": weekday,
                            "scheduled_time": scheduled_time,
                            "light_entities": [entity_id],
                            "action": "on",
                            "brightness": 180,
                            "color_temp_kelvin": 2850,
                        },
                    )
                    if _find_duplicate_error(step):
                        continue
                    _expect_step(step, "proposals")
                    created = True
                    break
                if created:
                    break
            if created:
                break
        if not created:
            configured = _configured_reactions(client, entry_id)
            if any(str(cfg.get("reaction_class") or "") == "LightingScheduleReaction" for cfg in configured.values()):
                return
            raise AssertionError("unable to create a configured lighting source reaction for presence simulation")
        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        if result.get("type") == "menu":
            _expect_step(result, "init")
            save = _menu_next(client, flow_id, "save")
            _assert(save.get("type") == "create_entry", f"expected create_entry on save, got: {save}")
        elif result.get("type") == "form":
            _expect_step(result, "proposals")
        else:
            raise AssertionError(f"unexpected options flow result after lighting accept: {result}")
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima security presence simulation live test")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=30)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    person_override_entity = _first_person_override_entity(client)
    if not person_override_entity:
        raise AssertionError("no heima person override select found")

    print(f"Using heima entry_id={entry_id}")
    print(f"Using person override entity={person_override_entity}")

    _ensure_security_presence_learning_enabled(client, entry_id)
    _ensure_lighting_source_reaction(client, entry_id)

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")

        step = _menu_next(client, flow_id, "admin_authored_create")
        _expect_step(step, "admin_authored_create")
        template_ids = _extract_select_values(step, "template_id")
        print(f"Templates exposed: {template_ids}")
        _assert(
            "security.vacation_presence_simulation.basic" in template_ids,
            f"presence simulation template not exposed: {template_ids}",
        )

        step = client.options_flow_configure(
            flow_id, {"template_id": "security.vacation_presence_simulation.basic"}
        )
        _expect_step(step, "admin_authored_security_presence_simulation")

        room_ids = _extract_select_values(step, "allowed_rooms")
        allowed_rooms = ["living"] if "living" in room_ids else ([room_ids[0]] if room_ids else [])
        step = client.options_flow_configure(
            flow_id,
            {
                "enabled": True,
                "allowed_rooms": allowed_rooms,
                "allowed_entities": [],
                "requires_dark_outside": False,
                "simulation_aggressiveness": "medium",
                "min_jitter_override_min": 0,
                "max_jitter_override_min": 0,
                "max_events_per_evening_override": 2,
                "latest_end_time_override": "",
                "skip_if_presence_detected": True,
            },
        )
        if not _find_duplicate_error(step):
            _expect_step(step, "proposals")
            result = client.options_flow_configure(flow_id, {"review_action": "accept"})
            if result.get("type") == "menu":
                _expect_step(result, "init")
                save = _menu_next(client, flow_id, "save")
                _assert(save.get("type") == "create_entry", f"expected create_entry on save, got: {save}")
            elif result.get("type") == "form":
                _expect_step(result, "proposals")
            else:
                raise AssertionError(f"unexpected options flow result after accept: {result}")

        reaction_id = _wait_for_presence_reaction(
            client, entry_id, timeout_s=args.timeout_s, poll_s=args.poll_s
        )
        print(f"Accepted reaction_id={reaction_id}")

        _set_person_override(client, person_override_entity, "force_away")
        client.call_service("heima", "set_mode", {"mode": "vacation", "state": True})
        client.call_service("heima", "command", {"command": "recompute_now"})
        client.wait_state("sensor.heima_house_state", "vacation", args.timeout_s, args.poll_s)

        diag = _wait_reaction_ready(
            client,
            entry_id,
            reaction_id=reaction_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print("Reaction diagnostics:")
        print(diag)

        _assert(diag.get("source_profile_kind") == "accepted_lighting_reactions", "unexpected source_profile_kind")
        _assert(bool(diag.get("source_profile_ready")), "source_profile_ready is false")
        _assert(int(diag.get("recent_source_reaction_count") or 0) >= 1, "recent source profile is empty")
        _assert(int(diag.get("tonight_plan_count") or 0) >= 1, "tonight plan is empty")
        preview = diag.get("tonight_plan_preview")
        _assert(isinstance(preview, list) and preview, "tonight_plan_preview missing")
        _assert(str(diag.get("blocked_reason") or "") in {"", "awaiting_next_planned_activation"}, f"unexpected blocked_reason: {diag.get('blocked_reason')!r}")

        job = _wait_scheduler_job(
            client,
            entry_id,
            reaction_id=reaction_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print("Scheduler job:")
        print(job)
        _assert(str(job.get("owner") or "") == "VacationPresenceSimulationReaction", f"unexpected scheduler owner: {job}")

        print("PASS: security presence simulation created a derived nightly plan in vacation")
        return 0
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass
        try:
            client.call_service("heima", "set_mode", {"mode": "vacation", "state": False})
        except Exception:
            pass
        try:
            _set_person_override(client, person_override_entity, "auto")
        except Exception:
            pass
        try:
            client.call_service("heima", "command", {"command": "recompute_now"})
        except Exception:
            pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
