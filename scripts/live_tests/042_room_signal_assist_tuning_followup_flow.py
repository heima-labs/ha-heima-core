#!/usr/bin/env python3
"""Live test for composite tuning follow-up over an active room signal assist reaction."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


TARGET_IDENTITY = "room_signal_assist|room=bathroom|primary=humidity"


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


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


def _configured_reaction_cfg(client: HAClient, entry_id: str, reaction_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
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
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    event_store = runtime.get("event_store", {})
    return event_store if isinstance(event_store, dict) else {}


def _engine_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
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
        if str(proposal.get("type") or "") != "room_signal_assist":
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


def _wait_for_state_change_growth(
    client: HAClient,
    entry_id: str,
    previous: int,
    timeout_s: int,
    poll_s: float,
) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        current = _to_int((diag.get("by_type", {}) or {}).get("state_change"))
        if current >= previous + 3:
            return current
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    current = _to_int((diag.get("by_type", {}) or {}).get("state_change"))
    raise RuntimeError(
        f"timeout waiting state_change events to grow by 3 (before={previous}, after={current})"
    )


def _wait_for_fixture_baseline(
    client: HAClient,
    entry_id: str,
    *,
    minimum: int,
    timeout_s: int,
    poll_s: float,
) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        current = _to_int((diag.get("by_type", {}) or {}).get("state_change"))
        if current >= minimum:
            return current
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    current = _to_int((diag.get("by_type", {}) or {}).get("state_change"))
    raise RuntimeError(
        f"fixture baseline not loaded: expected at least {minimum} state_change events, found {current}"
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
    raise AssertionError("pending room_signal_assist tuning proposal not visible within timeout")


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
    raise AssertionError("matching room signal tuning proposal not found in review queue")


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
    raise RuntimeError(f"timeout waiting for {entity_id}≈{expected}, last={last!r}")


def _seed_live_bathroom_sequence(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    client.wait_state("binary_sensor.test_heima_room_bathroom_motion", "off", timeout_s, poll_s)
    client.wait_state("switch.test_heima_bathroom_fan", "off", timeout_s, poll_s)
    _wait_numeric_state(
        client,
        "sensor.test_heima_bathroom_humidity",
        55.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    _wait_numeric_state(
        client,
        "sensor.test_heima_bathroom_temperature",
        21.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )

    client.call_service(
        "input_boolean",
        "turn_on",
        {"entity_id": "input_boolean.test_heima_room_bathroom_motion_raw"},
    )
    client.wait_state("binary_sensor.test_heima_room_bathroom_motion", "on", timeout_s, poll_s)
    _recompute(client)
    _wait_for_room_occupancy_context(
        client,
        entry_id,
        room_id="bathroom",
        timeout_s=timeout_s,
        poll_s=poll_s,
    )

    before_events = _to_int((_event_store_diagnostics(client, entry_id).get("by_type", {}) or {}).get("state_change"))
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_bathroom_humidity", "value": 66},
    )
    _wait_numeric_state(
        client,
        "sensor.test_heima_bathroom_humidity",
        66.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    time.sleep(1.0)
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_bathroom_temperature", "value": 22.1},
    )
    _wait_numeric_state(
        client,
        "sensor.test_heima_bathroom_temperature",
        22.1,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    time.sleep(1.0)
    client.call_service("switch", "turn_on", {"entity_id": "switch.test_heima_bathroom_fan"})
    client.wait_state("switch.test_heima_bathroom_fan", "on", timeout_s, poll_s)
    after_events = _wait_for_state_change_growth(client, entry_id, before_events, timeout_s, poll_s)
    print(f"state_change events after live bathroom sequence: {after_events}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima room signal assist tuning follow-up live test"
    )
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=40)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    baseline = _wait_for_fixture_baseline(
        client,
        entry_id,
        minimum=12,
        timeout_s=min(args.timeout_s, 20),
        poll_s=args.poll_s,
    )
    print(f"Fixture baseline state_change events: {baseline}")

    summary_before = _reaction_summary(client, entry_id)
    total_before = int(summary_before.get("total") or 0)
    reaction_id = f"live-room-signal-admin-{int(time.time())}"

    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {
                    reaction_id: {
                        "reaction_class": "RoomSignalAssistReaction",
                        "reaction_type": "room_signal_assist",
                        "room_id": "bathroom",
                        "origin": "admin_authored",
                        "author_kind": "admin",
                        "source_template_id": "room.signal_assist.basic",
                        "source_request": "template:room.signal_assist.basic",
                        "source_proposal_identity_key": TARGET_IDENTITY,
                        "primary_signal_name": "humidity",
                        "primary_threshold_mode": "rise",
                        "primary_threshold": 9.0,
                        "primary_signal_entities": ["sensor.test_heima_bathroom_humidity"],
                        "corroboration_signal_name": "temperature",
                        "corroboration_threshold_mode": "rise",
                        "corroboration_threshold": 1.0,
                        "corroboration_signal_entities": ["sensor.test_heima_bathroom_temperature"],
                        "steps": [],
                        "last_tuned_at": None,
                    }
                },
                "labels": {
                    reaction_id: "Assist bathroom — hum:1 — temp:1",
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
    print(f"Admin-authored room signal reaction created: {reaction_id}")

    print("Executing live bathroom humidity + temperature + fan sequence...")
    _seed_live_bathroom_sequence(
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
            "Affinamento assist" in label or "Assist tuning" in label,
            "review title does not mark composite tuning",
        )
        _assert(
            "automazione esistente" in details.lower() or "existing automation" in details.lower(),
            "review details do not describe tuning semantics",
        )
        _assert(
            "Template target: room.signal_assist.basic" in details,
            "review details do not expose target template",
        )
        _assert(
            "Soglia primaria:" in details or "Primary threshold:" in details,
            "review details do not show primary threshold diff",
        )

        result = client.options_flow_configure(tuning_flow_id, {"review_action": "accept"})
        if result.get("step_id") == "proposal_configure_action":
            result = client.options_flow_configure(
                tuning_flow_id,
                {
                    "action_entities": [],
                    "pre_condition_min": 20,
                },
            )
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
        f"tuning accept should update existing reaction without growing count: {summary_after_accept}",
    )
    target_cfg = _configured_reaction_cfg(client, entry_id, reaction_id)
    print(f"Configured reaction after tuning: {target_cfg}")
    _assert(
        str(target_cfg.get("last_tuning_proposal_id") or "") == proposal_id,
        "configured reaction does not record last_tuning_proposal_id",
    )
    _assert(
        str(target_cfg.get("last_tuning_followup_kind") or "") == "tuning_suggestion",
        "configured reaction does not record tuning followup kind",
    )
    _assert(
        str(target_cfg.get("origin") or "") == "admin_authored",
        "configured reaction origin regressed after tuning",
    )

    print("PASS: room signal assist tuning follow-up updated the existing admin-authored reaction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
