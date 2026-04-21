#!/usr/bin/env python3
"""Live E2E: learned darkness -> contextual improvement on the HA test lab."""

from __future__ import annotations

import argparse
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
    _assert(
        result.get("step_id") == step_id,
        f"expected step_id={step_id!r}, got={result.get('step_id')!r}: {result}",
    )


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _proposal_label(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_label") or "")


def _proposal_details(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_details") or "")


def _to_int(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return 0
    return int(float(raw))


def _diagnostics_root(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    return raw if isinstance(raw, dict) else {}


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


def _configured_reactions(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    raw = _diagnostics_root(client, entry_id)
    entry = raw.get("data", {}).get("entry", {})
    if not isinstance(entry, dict):
        return {}
    options = entry.get("options", {})
    if not isinstance(options, dict):
        return {}
    reactions = options.get("reactions", {})
    if not isinstance(reactions, dict):
        return {}
    configured = reactions.get("configured", {})
    if not isinstance(configured, dict):
        return {}
    return {
        str(reaction_id): dict(cfg)
        for reaction_id, cfg in configured.items()
        if isinstance(cfg, dict)
    }


def _event_store_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    event_store = runtime.get("event_store", {})
    return event_store if isinstance(event_store, dict) else {}


def _wait_canonical_darkness_fixture_baseline(
    client: HAClient,
    entry_id: str,
    *,
    minimum_room_signal_thresholds: int,
    minimum_lighting_events: int,
    timeout_s: int,
    poll_s: float,
) -> dict[str, int]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        by_type = diag.get("by_type", {}) or {}
        threshold_count = _to_int(by_type.get("room_signal_threshold"))
        lighting_count = _to_int(by_type.get("lighting"))
        if (
            threshold_count >= minimum_room_signal_thresholds
            and lighting_count >= minimum_lighting_events
        ):
            return {
                "room_signal_threshold": threshold_count,
                "lighting": lighting_count,
            }
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    by_type = diag.get("by_type", {}) or {}
    raise AssertionError(
        "canonical darkness fixture baseline not loaded: "
        f"expected room_signal_threshold>={minimum_room_signal_thresholds} and "
        f"lighting>={minimum_lighting_events}, found "
        f"room_signal_threshold={_to_int(by_type.get('room_signal_threshold'))} "
        f"lighting={_to_int(by_type.get('lighting'))}. "
        "Run scripts/live_tests/006_restore_learning_fixtures.sh first."
    )


def _find_darkness_proposal(diag: dict[str, Any], *, status: str) -> dict[str, Any] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if str(proposal.get("type") or "") != "room_darkness_lighting_assist":
            continue
        if str(proposal.get("status") or "") != status:
            continue
        cfg = dict(proposal.get("suggested_reaction_config") or {})
        if str(cfg.get("room_id") or "") != "studio":
            continue
        return proposal
    return None


def _find_contextual_improvement(diag: dict[str, Any]) -> dict[str, Any] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if str(proposal.get("type") or "") != "room_contextual_lighting_assist":
            continue
        if str(proposal.get("status") or "") != "pending":
            continue
        if str(proposal.get("followup_kind") or "") != "improvement":
            continue
        if str(proposal.get("target_reaction_type") or "") != "room_darkness_lighting_assist":
            continue
        return proposal
    return None


def _find_configured_darkness_reaction(
    client: HAClient, entry_id: str, *, proposal_id: str | None = None
) -> tuple[str, dict[str, Any]] | None:
    configured = _configured_reactions(client, entry_id)
    for reaction_id, cfg in configured.items():
        if str(cfg.get("reaction_type") or "") != "room_darkness_lighting_assist":
            continue
        if str(cfg.get("room_id") or "") != "studio":
            continue
        if proposal_id and reaction_id != proposal_id:
            continue
        return reaction_id, cfg
    return None


def _configured_contextual_reactions(
    client: HAClient,
    entry_id: str,
) -> list[tuple[str, dict[str, Any]]]:
    configured = _configured_reactions(client, entry_id)
    matches: list[tuple[str, dict[str, Any]]] = []
    for reaction_id, cfg in configured.items():
        if str(cfg.get("reaction_type") or "") != "room_contextual_lighting_assist":
            continue
        if str(cfg.get("room_id") or "") != "studio":
            continue
        matches.append((reaction_id, cfg))
    return matches


def _delete_reaction_via_flow(client: HAFlowClient, entry_id: str, reaction_id: str) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        step = _menu_next(client, flow_id, "reactions_edit")
        _expect_step(step, "reactions_edit")
        step = client.options_flow_configure(flow_id, {"reaction": reaction_id})
        _assert(
            str(step.get("step_id") or "").startswith("reactions_edit"),
            f"unexpected edit step for delete: {step}",
        )
        payload = {"delete_reaction": True}
        data_schema = step.get("data_schema")
        if isinstance(data_schema, list):
            names = {
                str(field.get("name") or "") for field in data_schema if isinstance(field, dict)
            }
            if "enabled" in names:
                payload["enabled"] = bool(
                    _configured_reactions(client, entry_id)
                    .get(reaction_id, {})
                    .get("enabled", True)
                )
            if "preset" in names:
                payload["preset"] = "all_day_adaptive"
            if "config_json" in names:
                payload["config_json"] = "{}"
        step = client.options_flow_configure(flow_id, payload)
        _expect_step(step, "reactions_delete_confirm")
        step = client.options_flow_configure(flow_id, {"confirm": True})
        _assert(
            step.get("type") == "menu" and step.get("step_id") == "init",
            f"unexpected result after delete confirm: {step}",
        )
    finally:
        client.options_flow_abort(flow_id)


def _wait_fixture_baseline(
    client: HAClient,
    entry_id: str,
    *,
    minimum_state_changes: int,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        by_type = diag.get("by_type", {}) or {}
        if _to_int(by_type.get("state_change")) >= minimum_state_changes:
            return
        time.sleep(poll_s)
    raise AssertionError("fixture baseline not loaded; restore learning fixtures first")


def _wait_numeric_state(
    client: HAClient,
    entity_id: str,
    expected: float,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        last = client.state_value(entity_id)
        try:
            if abs(float(last) - expected) < 0.05:
                return
        except ValueError:
            pass
        time.sleep(poll_s)
    raise AssertionError(f"timeout waiting for {entity_id}≈{expected}, last={last!r}")


def _wait_light_brightness(
    client: HAClient,
    entity_id: str,
    expected_state: str,
    expected_brightness: int,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last_state = ""
    last_brightness: Any = None
    while time.time() < deadline:
        state = client.get_state(entity_id)
        last_state = str(state.get("state") or "")
        last_brightness = (state.get("attributes") or {}).get("brightness")
        if last_state == expected_state and int(last_brightness or 0) == expected_brightness:
            return
        time.sleep(poll_s)
    raise AssertionError(
        f"timeout waiting for {entity_id}={expected_state} brightness={expected_brightness}, "
        f"last_state={last_state!r} last_brightness={last_brightness!r}"
    )


def _wait_state(
    client: HAClient, entity_id: str, expected: str, timeout_s: int, poll_s: float
) -> None:
    client.wait_state(entity_id, expected, timeout_s, poll_s)


def _recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _wait_for_darkness_pending(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        client.call_service(
            "heima", "command", {"command": "learning_run", "target": {"entry_id": entry_id}}
        )
        diag = _proposal_diagnostics(client, entry_id)
        proposal = _find_darkness_proposal(diag, status="pending")
        if proposal is not None:
            return proposal
        time.sleep(poll_s)
    raise AssertionError("pending darkness proposal not visible within timeout")


def _wait_for_contextual_pending(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        client.call_service(
            "heima", "command", {"command": "learning_run", "target": {"entry_id": entry_id}}
        )
        diag = _proposal_diagnostics(client, entry_id)
        proposal = _find_contextual_improvement(diag)
        if proposal is not None:
            return proposal
        time.sleep(poll_s)
    raise AssertionError("pending contextual improvement not visible within timeout")


def _seek_review_for_proposal(
    client: HAFlowClient, flow_id: str, *, proposal_id: str
) -> dict[str, Any]:
    step = _menu_next(client, flow_id, "proposals")
    _expect_step(step, "proposals")
    for _ in range(32):
        details = _proposal_details(step)
        label = _proposal_label(step)
        normalized_label = label.lower()
        normalized_details = details.lower()
        if proposal_id in details or proposal_id in label:
            return step
        if (
            (
                "illuminazione contestuale stanza: studio" in normalized_label
                and "reaction esistente" in normalized_details
                and "contesto" in normalized_details
            )
            or (
                "contextual room lighting: studio" in normalized_label
                and "existing reaction" in normalized_details
                and "context" in normalized_details
            )
            or (
                "miglioramento:" in normalized_label
                and "studio" in normalized_label
                and "reaction esistente" in normalized_details
                and "contesto" in normalized_details
            )
            or (
                "upgrade:" in normalized_label
                and "studio" in normalized_label
                and "existing reaction" in normalized_details
                and "context" in normalized_details
            )
        ):
            return step
        step = client.options_flow_configure(flow_id, {"review_action": "skip"})
        if step.get("type") == "menu":
            break
        _expect_step(step, "proposals")
    raise AssertionError(f"proposal {proposal_id} not found in review queue")


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
        return [value for value in values if value]
    return []


def _create_admin_authored_darkness_reaction(
    client: HAFlowClient,
    entry_id: str,
    *,
    room_id: str,
) -> tuple[str, dict[str, Any]]:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        step = _menu_next(client, flow_id, "admin_authored_create")
        _expect_step(step, "admin_authored_create")
        template_ids = _extract_select_values(step, "template_id")
        _assert(
            "room.darkness_lighting_assist.basic" in template_ids,
            f"darkness template not exposed: {template_ids}",
        )
        step = client.options_flow_configure(
            flow_id,
            {"template_id": "room.darkness_lighting_assist.basic"},
        )
        _expect_step(step, "admin_authored_room_darkness_lighting_assist")
        step = client.options_flow_configure(
            flow_id,
            {
                "room_id": room_id,
                "primary_signal_name": "room_lux",
                "primary_bucket": "dim",
                "primary_bucket_match_mode": "lte",
                "light_entities": ["light.test_heima_studio_main"],
                "action": "on",
                "brightness": 144,
                "color_temp_kelvin": 2900,
            },
        )
        _assert(
            step.get("step_id") in {"proposals", "init"},
            f"unexpected result after darkness submit: {step}",
        )
        if step.get("step_id") == "proposals":
            step = client.options_flow_configure(flow_id, {"review_action": "accept"})
            _assert(
                (step.get("type") == "menu" and step.get("step_id") == "init")
                or step.get("step_id") == "proposals",
                f"unexpected result after darkness accept: {step}",
            )
    finally:
        client.options_flow_abort(flow_id)

    darkness_reaction = _find_configured_darkness_reaction(client, entry_id)
    _assert(
        darkness_reaction is not None, "configured darkness reaction missing after admin create"
    )
    return darkness_reaction


def _accept_proposal(client: HAFlowClient, entry_id: str, *, proposal_id: str) -> dict[str, Any]:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        review = _seek_review_for_proposal(client, flow_id, proposal_id=proposal_id)
        print(f"Review label:\n{_proposal_label(review)}")
        print(f"Review details:\n{_proposal_details(review)}")
        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        _assert(
            (result.get("type") == "menu" and result.get("step_id") == "init")
            or result.get("step_id") == "proposals",
            f"unexpected result after accept: {result}",
        )
        return result
    finally:
        client.options_flow_abort(flow_id)


def _seed_darkness_episode(
    client: HAClient,
    *,
    timeout_s: int,
    poll_s: float,
    brightness: int,
    kelvin: int,
    work_mode: bool,
) -> None:
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    if work_mode:
        client.call_service("heima", "set_mode", {"mode": "working", "state": True})
        _wait_state(client, "sensor.heima_house_state", "working", timeout_s, poll_s)
    else:
        client.call_service("heima", "set_mode", {"mode": "working", "state": False})
    _wait_state(client, "binary_sensor.test_heima_room_studio_motion", "off", timeout_s, poll_s)
    _wait_state(client, "light.test_heima_studio_main", "off", timeout_s, poll_s)
    _wait_numeric_state(
        client, "sensor.test_heima_studio_lux", 180.0, timeout_s=timeout_s, poll_s=poll_s
    )

    client.call_service(
        "input_boolean",
        "turn_on",
        {"entity_id": "input_boolean.test_heima_room_studio_motion_raw"},
    )
    _wait_state(client, "binary_sensor.test_heima_room_studio_motion", "on", timeout_s, poll_s)
    _recompute(client)
    time.sleep(1.0)

    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_studio_lux", "value": 90},
    )
    _wait_numeric_state(
        client, "sensor.test_heima_studio_lux", 90.0, timeout_s=timeout_s, poll_s=poll_s
    )
    time.sleep(1.0)
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_light_studio_main_brightness", "value": brightness},
    )
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_light_studio_main_color_temp", "value": kelvin},
    )
    client.call_service(
        "light",
        "turn_on",
        {
            "entity_id": "light.test_heima_studio_main",
            "brightness": brightness,
            "color_temp_kelvin": kelvin,
        },
    )
    _wait_light_brightness(
        client,
        "light.test_heima_studio_main",
        "on",
        brightness,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    time.sleep(1.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Live E2E darkness->contextual improvement flow")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    _wait_canonical_darkness_fixture_baseline(
        client,
        entry_id,
        minimum_room_signal_thresholds=4,
        minimum_lighting_events=1,
        timeout_s=min(args.timeout_s, 30),
        poll_s=args.poll_s,
    )

    for reaction_id, _cfg in _configured_contextual_reactions(client, entry_id):
        print(f"Cleaning pre-existing studio contextual reaction: {reaction_id}")
        _delete_reaction_via_flow(client, entry_id, reaction_id)

    darkness_reaction = _find_configured_darkness_reaction(client, entry_id)
    accepted_darkness = _find_darkness_proposal(
        _proposal_diagnostics(client, entry_id), status="accepted"
    )
    if darkness_reaction is None and accepted_darkness is None:
        pending_darkness = _find_darkness_proposal(
            _proposal_diagnostics(client, entry_id), status="pending"
        )
        if pending_darkness is None:
            print("Generating pending darkness proposal from live studio sequence...")
            _seed_darkness_episode(
                client,
                timeout_s=args.timeout_s,
                poll_s=args.poll_s,
                brightness=144,
                kelvin=2900,
                work_mode=False,
            )
            try:
                pending_darkness = _wait_for_darkness_pending(
                    client,
                    entry_id,
                    timeout_s=args.timeout_s,
                    poll_s=args.poll_s,
                )
            except AssertionError:
                pending_darkness = None
        if pending_darkness is None:
            print(
                "No learned darkness proposal available; creating admin-authored darkness baseline..."
            )
            darkness_reaction = _create_admin_authored_darkness_reaction(
                client,
                entry_id,
                room_id="studio",
            )
        else:
            darkness_proposal_id = str(pending_darkness.get("id") or "")
            print(f"Accepting darkness proposal: {darkness_proposal_id}")
            _accept_proposal(client, entry_id, proposal_id=darkness_proposal_id)
            accepted_darkness = _find_darkness_proposal(
                _proposal_diagnostics(client, entry_id), status="accepted"
            )
            _assert(accepted_darkness is not None, "darkness proposal not accepted")

    if darkness_reaction is None:
        darkness_proposal_id = str(accepted_darkness.get("id") or "")
        darkness_reaction = _find_configured_darkness_reaction(
            client, entry_id, proposal_id=darkness_proposal_id
        )
        _assert(darkness_reaction is not None, "configured darkness reaction missing after accept")
    darkness_reaction_id, _ = darkness_reaction
    print(f"Accepted darkness reaction ready: {darkness_reaction_id}")

    client.call_service(
        "heima",
        "command",
        {"command": "mute_reaction", "target": {"reaction_id": darkness_reaction_id}},
    )
    print("Muted darkness reaction to capture user-driven contextual evidence")

    print("Generating generic contextual evidence episode 1 ...")
    _seed_darkness_episode(
        client,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        brightness=144,
        kelvin=2900,
        work_mode=False,
    )
    print("Generating generic contextual evidence episode 2 ...")
    _seed_darkness_episode(
        client,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        brightness=144,
        kelvin=2900,
        work_mode=False,
    )
    print("Generating generic contextual evidence episode 3 ...")
    _seed_darkness_episode(
        client,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        brightness=144,
        kelvin=2900,
        work_mode=False,
    )
    print("Generating workday contextual evidence episode 1 ...")
    _seed_darkness_episode(
        client,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        brightness=180,
        kelvin=4300,
        work_mode=True,
    )
    print("Generating workday contextual evidence episode 2 ...")
    _seed_darkness_episode(
        client,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        brightness=180,
        kelvin=4300,
        work_mode=True,
    )
    print("Generating workday contextual evidence episode 3 ...")
    _seed_darkness_episode(
        client,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        brightness=180,
        kelvin=4300,
        work_mode=True,
    )

    pending_contextual = _wait_for_contextual_pending(
        client,
        entry_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    proposal_id = str(pending_contextual.get("id") or "")
    print(f"Accepting contextual improvement: {proposal_id}")
    _accept_proposal(client, entry_id, proposal_id=proposal_id)

    configured_after = _configured_reactions(client, entry_id)
    cfg = configured_after.get(darkness_reaction_id, {})
    _assert(
        str(cfg.get("reaction_type") or "") == "room_contextual_lighting_assist",
        f"darkness reaction not converted to contextual: {cfg}",
    )
    _assert(
        str(cfg.get("improved_from_reaction_type") or "") == "room_darkness_lighting_assist",
        f"improvement provenance missing: {cfg}",
    )
    print("PASS: darkness learned flow upgraded into contextual reaction end-to-end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
