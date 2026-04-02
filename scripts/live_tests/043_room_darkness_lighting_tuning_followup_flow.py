#!/usr/bin/env python3
"""Live test for composite tuning follow-up over an active room darkness lighting reaction."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


TARGET_IDENTITY = "room_darkness_lighting_assist|room=studio|primary=room_lux"


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


def _to_int(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return 0
    return int(float(raw))


def _proposal_details(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_details") or "")


def _proposal_label(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_label") or "")


def _diagnostics_root(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    return raw if isinstance(raw, dict) else {}


def _reaction_summary(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    plugins = runtime.get("plugins", {})
    if not isinstance(plugins, dict):
        return {}
    summary = plugins.get("configured_reaction_summary", {})
    return summary if isinstance(summary, dict) else {}


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


def _configured_reaction_cfg(client: HAClient, entry_id: str, reaction_id: str) -> dict[str, Any]:
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
    cfg = configured.get(reaction_id, {})
    return dict(cfg) if isinstance(cfg, dict) else {}


def _event_store_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    event_store = runtime.get("event_store", {})
    return event_store if isinstance(event_store, dict) else {}


def _engine_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    engine = runtime.get("engine", {})
    return engine if isinstance(engine, dict) else {}


def _find_pending_tuning(diag: dict[str, Any]) -> dict[str, Any] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if str(proposal.get("type") or "") != "room_darkness_lighting_assist":
            continue
        if str(proposal.get("status") or "") != "pending":
            continue
        if str(proposal.get("identity_key") or "") != TARGET_IDENTITY:
            continue
        if str(proposal.get("followup_kind") or "") != "tuning_suggestion":
            continue
        return proposal
    return None


def _wait_for_reaction_id(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        summary = _reaction_summary(client, entry_id)
        reaction_ids = {str(item) for item in summary.get("reaction_ids") or []}
        if reaction_id in reaction_ids:
            return summary
        time.sleep(poll_s)
    raise AssertionError(f"reaction_id {reaction_id!r} not visible in diagnostics within timeout")


def _wait_for_fixture_baseline(
    client: HAClient,
    entry_id: str,
    *,
    minimum_state_changes: int,
    timeout_s: int,
    poll_s: float,
) -> dict[str, int]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        by_type = diag.get("by_type", {}) or {}
        state_change = _to_int(by_type.get("state_change"))
        lighting = _to_int(by_type.get("lighting"))
        if state_change >= minimum_state_changes and lighting > 0:
            return {"state_change": state_change, "lighting": lighting}
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    by_type = diag.get("by_type", {}) or {}
    raise AssertionError(
        "fixture baseline not loaded: "
        f"state_change={_to_int(by_type.get('state_change'))} lighting={_to_int(by_type.get('lighting'))}"
    )


def _wait_for_event_growth(
    client: HAClient,
    entry_id: str,
    *,
    previous_state_changes: int,
    previous_lighting: int,
    timeout_s: int,
    poll_s: float,
) -> dict[str, int]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        by_type = diag.get("by_type", {}) or {}
        state_change = _to_int(by_type.get("state_change"))
        lighting = _to_int(by_type.get("lighting"))
        if lighting >= previous_lighting + 1:
            return {"state_change": state_change, "lighting": lighting}
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    by_type = diag.get("by_type", {}) or {}
    raise AssertionError(
        "timeout waiting darkness live sequence to grow lighting count "
        f"(state_change {previous_state_changes}->{_to_int(by_type.get('state_change'))}, "
        f"lighting {previous_lighting}->{_to_int(by_type.get('lighting'))})"
    )


def _wait_for_pending_tuning(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        client.call_service("heima", "command", {"command": "learning_run", "target": {"entry_id": entry_id}})
        diag = _proposal_diagnostics(client, entry_id)
        found = _find_pending_tuning(diag)
        if found is not None:
            return found
        time.sleep(poll_s)
    raise AssertionError("pending room_darkness_lighting_assist tuning proposal not visible within timeout")


def _seek_matching_tuning_review(
    client: HAFlowClient,
    flow_id: str,
    *,
    expected_description: str,
    max_steps: int = 16,
) -> dict[str, Any]:
    step = _menu_next(client, flow_id, "proposals")
    _expect_step(step, "proposals")
    for _ in range(max_steps):
        label = _proposal_label(step)
        details = _proposal_details(step)
        if expected_description in details or expected_description in label:
            return step
        step = client.options_flow_configure(flow_id, {"review_action": "skip"})
        if step.get("type") == "menu":
            break
        _expect_step(step, "proposals")
    raise AssertionError("matching room darkness tuning proposal not found in review queue")


def _recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


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


def _wait_for_room_occupancy_context(
    client: HAClient,
    entry_id: str,
    *,
    room_id: str,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        engine = _engine_diagnostics(client, entry_id)
        occupancy = engine.get("occupancy", {})
        if not isinstance(occupancy, dict):
            time.sleep(poll_s)
            continue
        room_trace = occupancy.get("room_trace", {})
        if not isinstance(room_trace, dict):
            time.sleep(poll_s)
            continue
        trace = room_trace.get(room_id, {})
        if not isinstance(trace, dict):
            time.sleep(poll_s)
            continue
        if str(trace.get("effective_state") or "").strip().lower() == "on":
            return
        time.sleep(poll_s)
    raise AssertionError(
        f"occupancy trace effective_state=on not visible within timeout for room={room_id}"
    )


def _seed_live_studio_sequence(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    client.wait_state("binary_sensor.test_heima_room_studio_motion", "off", timeout_s, poll_s)
    client.wait_state("light.test_heima_studio_main", "off", timeout_s, poll_s)
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_lux",
        180.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )

    client.call_service(
        "input_boolean",
        "turn_on",
        {"entity_id": "input_boolean.test_heima_room_studio_motion_raw"},
    )
    client.wait_state("binary_sensor.test_heima_room_studio_motion", "on", timeout_s, poll_s)
    _recompute(client)
    _wait_for_room_occupancy_context(
        client,
        entry_id,
        room_id="studio",
        timeout_s=timeout_s,
        poll_s=poll_s,
    )

    before = _wait_for_fixture_baseline(
        client,
        entry_id,
        minimum_state_changes=36,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_studio_lux", "value": 90},
    )
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_lux",
        90.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    time.sleep(1.0)
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_light_studio_main_brightness", "value": 144},
    )
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_light_studio_main_color_temp", "value": 2900},
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
        144,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    after = _wait_for_event_growth(
        client,
        entry_id,
        previous_state_changes=before["state_change"],
        previous_lighting=before["lighting"],
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    print(
        "Events after live sequence: "
        f"state_change={after['state_change']} lighting={after['lighting']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima room darkness lighting tuning follow-up live test"
    )
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    baseline = _wait_for_fixture_baseline(
        client,
        entry_id,
        minimum_state_changes=36,
        timeout_s=min(args.timeout_s, 20),
        poll_s=args.poll_s,
    )
    print(
        f"Fixture baseline events: state_change={baseline['state_change']} "
        f"lighting={baseline['lighting']}"
    )

    summary_before = _reaction_summary(client, entry_id)
    total_before = int(summary_before.get("total") or 0)
    reaction_id = f"live-room-darkness-admin-{int(time.time())}"

    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {
                    reaction_id: {
                        "reaction_class": "RoomLightingAssistReaction",
                        "reaction_type": "room_darkness_lighting_assist",
                        "room_id": "studio",
                        "origin": "admin_authored",
                        "author_kind": "admin",
                        "source_template_id": "room.darkness_lighting_assist.basic",
                        "source_request": "template:room.darkness_lighting_assist.basic",
                        "source_proposal_identity_key": TARGET_IDENTITY,
                        "primary_signal_name": "room_lux",
                        "primary_threshold_mode": "below",
                        "primary_threshold": 10.0,
                        "primary_signal_entities": ["sensor.test_heima_studio_lux"],
                        "corroboration_signal_name": "corroboration",
                        "corroboration_threshold_mode": "below",
                        "corroboration_threshold": None,
                        "corroboration_signal_entities": [],
                        "entity_steps": [
                            {
                                "entity_id": "light.test_heima_studio_main",
                                "action": "on",
                                "brightness": 190,
                                "color_temp_kelvin": 2850,
                                "rgb_color": None,
                            },
                            {
                                "entity_id": "light.test_heima_studio_spot",
                                "action": "on",
                                "brightness": 160,
                                "color_temp_kelvin": 2850,
                                "rgb_color": None,
                            },
                        ],
                        "last_tuned_at": None,
                    }
                },
                "labels": {
                    reaction_id: "Luce studio — buio:1 — luci:2",
                },
            },
        },
    )
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    summary_after_setup = _wait_for_reaction_id(
        client,
        entry_id,
        reaction_id=reaction_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    _assert(
        int(summary_after_setup.get("total") or 0) == total_before + 1,
        f"expected one additional configured reaction, got before={total_before} after={summary_after_setup}",
    )
    print(f"Admin-authored room darkness reaction created: {reaction_id}")

    print("Executing live studio darkness + lighting sequence...")
    _seed_live_studio_sequence(
        client,
        entry_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )

    print("Reloading Heima config entry to trigger proposal run...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})

    tuning = _wait_for_pending_tuning(
        client,
        entry_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    proposal_id = str(tuning.get("id") or "")
    print(f"Tuning proposal found: {proposal_id}")
    print(f"Tuning diagnostics: {tuning}")
    _assert(
        str(tuning.get("target_reaction_origin") or "") in {"", "admin_authored"},
        f"unexpected target_reaction_origin: {tuning}",
    )

    tuning_flow = client.options_flow_init(entry_id)
    tuning_flow_id = str(tuning_flow["flow_id"])
    try:
        _expect_step(tuning_flow, "init")
        review = _seek_matching_tuning_review(
            client,
            tuning_flow_id,
            expected_description=str(tuning.get("description") or ""),
        )
        label = _proposal_label(review)
        details = _proposal_details(review)
        print(f"Review label: {label}")
        print(f"Review details:\n{details}")
        _assert(
            "Affinamento luce" in label or "Lighting tuning" in label,
            "review title does not mark darkness-lighting tuning",
        )
        _assert(
            "automazione esistente" in details.lower() or "existing automation" in details.lower(),
            "review details do not describe tuning semantics",
        )
        _assert(
            "Template target: room.darkness_lighting_assist.basic" in details,
            "review details do not expose target template",
        )
        _assert(
            "Soglia: 10.0 -> 120.0" in details or "Threshold: 10.0 -> 120.0" in details,
            "review details do not show darkness threshold diff",
        )
        _assert(
            "Luci: 2 -> 1" in details or "Lights: 2 -> 1" in details,
            "review details do not show bounded entity_steps diff",
        )

        result = client.options_flow_configure(tuning_flow_id, {"review_action": "accept"})
        _assert(result.get("type") == "menu", f"unexpected result after tuning accept: {result}")
    finally:
        time.sleep(0.1)
        try:
            client.options_flow_abort(tuning_flow_id)
        except Exception:
            pass

    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    summary_after_accept = _wait_for_reaction_id(
        client,
        entry_id,
        reaction_id=reaction_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    _assert(
        int(summary_after_accept.get("total") or 0) == total_before + 1,
        f"tuning accept created a duplicate reaction: {summary_after_accept}",
    )
    target_cfg = _configured_reaction_cfg(client, entry_id, reaction_id)
    print(f"Configured reaction after tuning: {target_cfg}")
    _assert(
        float(target_cfg.get("primary_threshold") or 0.0) == 120.0,
        "tuned darkness reaction did not adopt learned threshold",
    )
    _assert(
        len(target_cfg.get("entity_steps") or []) == 1,
        "tuned darkness reaction did not adopt learned light payload size",
    )
    _assert(
        str(target_cfg.get("last_tuning_proposal_id") or "") == proposal_id,
        "tuned darkness reaction missing last_tuning_proposal_id",
    )
    _assert(
        str(target_cfg.get("last_tuning_followup_kind") or "") == "tuning_suggestion",
        "tuned darkness reaction missing tuning followup provenance",
    )
    _assert(
        str(target_cfg.get("origin") or "") == "admin_authored",
        "tuning should preserve original admin_authored provenance",
    )

    print("PASS: room darkness lighting tuning follow-up updated the existing admin-authored reaction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
