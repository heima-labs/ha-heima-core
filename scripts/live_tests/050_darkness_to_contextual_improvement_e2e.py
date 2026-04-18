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
        if proposal_id in details or proposal_id in label:
            return step
        step = client.options_flow_configure(flow_id, {"review_action": "skip"})
        if step.get("type") == "menu":
            break
        _expect_step(step, "proposals")
    raise AssertionError(f"proposal {proposal_id} not found in review queue")


def _accept_proposal(client: HAFlowClient, entry_id: str, *, proposal_id: str) -> dict[str, Any]:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        review = _seek_review_for_proposal(client, flow_id, proposal_id=proposal_id)
        print(f"Review label:\n{_proposal_label(review)}")
        print(f"Review details:\n{_proposal_details(review)}")
        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        _assert(
            result.get("type") == "menu" and result.get("step_id") == "init",
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
        client.call_service(
            "input_boolean",
            "turn_on",
            {"entity_id": "input_boolean.test_heima_work_mode"},
        )
        _wait_state(client, "binary_sensor.test_heima_work_window", "on", timeout_s, poll_s)
        _wait_state(client, "sensor.heima_house_state", "working", timeout_s, poll_s)
    else:
        client.call_service(
            "input_boolean",
            "turn_off",
            {"entity_id": "input_boolean.test_heima_work_mode"},
        )
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
        "input_boolean",
        "turn_on",
        {"entity_id": "input_boolean.test_heima_light_studio_main_raw"},
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

    _wait_fixture_baseline(
        client,
        entry_id,
        minimum_state_changes=36,
        timeout_s=min(args.timeout_s, 30),
        poll_s=args.poll_s,
    )

    configured_before = _configured_reactions(client, entry_id)
    if any(
        str(cfg.get("reaction_type") or "") == "room_contextual_lighting_assist"
        and str(cfg.get("room_id") or "") == "studio"
        for cfg in configured_before.values()
    ):
        raise AssertionError(
            "studio contextual reaction already configured; recover the test lab first"
        )

    accepted_darkness = _find_darkness_proposal(
        _proposal_diagnostics(client, entry_id), status="accepted"
    )
    if accepted_darkness is None:
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
            pending_darkness = _wait_for_darkness_pending(
                client,
                entry_id,
                timeout_s=args.timeout_s,
                poll_s=args.poll_s,
            )
        darkness_proposal_id = str(pending_darkness.get("id") or "")
        print(f"Accepting darkness proposal: {darkness_proposal_id}")
        _accept_proposal(client, entry_id, proposal_id=darkness_proposal_id)
        accepted_darkness = _find_darkness_proposal(
            _proposal_diagnostics(client, entry_id), status="accepted"
        )
        _assert(accepted_darkness is not None, "darkness proposal not accepted")

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
