#!/usr/bin/env python3
"""Live E2E: room signal assist -> cooling improvement on the HA test lab."""

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


def _canonicalizer_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    plugins = runtime.get("plugins", {})
    if isinstance(plugins, dict):
        summary = plugins.get("canonical_signals_summary", {})
        if isinstance(summary, dict) and summary:
            return summary
    behaviors = runtime.get("behaviors", {})
    if isinstance(behaviors, dict):
        canonicalizer = behaviors.get("event_canonicalizer", {})
        if isinstance(canonicalizer, dict):
            return canonicalizer
    return {}


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


def _proposal_label(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_label") or "")


def _proposal_details(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_details") or "")


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


def _wait_state(
    client: HAClient, entity_id: str, expected: str, timeout_s: int, poll_s: float
) -> None:
    client.wait_state(entity_id, expected, timeout_s, poll_s)


def _recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _wait_for_fixture_baseline(
    client: HAClient,
    entry_id: str,
    *,
    minimum_room_signal_burst: int,
    minimum_actuation: int,
    timeout_s: int,
    poll_s: float,
) -> tuple[int, int]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        by_type = dict(diag.get("by_type") or {})
        bursts = _to_int(by_type.get("room_signal_burst"))
        actuations = _to_int(by_type.get("actuation"))
        if bursts >= minimum_room_signal_burst and actuations >= minimum_actuation:
            return bursts, actuations
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    by_type = dict(diag.get("by_type") or {})
    bursts = _to_int(by_type.get("room_signal_burst"))
    actuations = _to_int(by_type.get("actuation"))
    raise AssertionError(
        "cooling fixture baseline not loaded: "
        f"need room_signal_burst>={minimum_room_signal_burst} and actuation>={minimum_actuation}, "
        f"found room_signal_burst={bursts}, actuation={actuations}. "
        "Run scripts/live_tests/006_restore_learning_fixtures.sh first."
    )


def _wait_for_canonicalizer_baseline(
    client: HAClient,
    entry_id: str,
    *,
    room_id: str,
    signal_name: str,
    expected_value: float,
    timeout_s: int,
    poll_s: float,
) -> None:
    key = f"{room_id}:{signal_name}"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        _recompute(client)
        diag = _canonicalizer_diagnostics(client, entry_id)
        baseline = diag.get("burst_baseline", {})
        if isinstance(baseline, dict):
            payload = baseline.get(key, {})
            if isinstance(payload, dict):
                value = payload.get("value")
                try:
                    if abs(float(value) - expected_value) < 0.05:
                        return
                except (TypeError, ValueError):
                    pass
        time.sleep(poll_s)
    raise AssertionError(f"canonicalizer baseline for {key} not ready at {expected_value}")


def _wait_for_canonicalizer_burst(
    client: HAClient,
    entry_id: str,
    *,
    room_id: str,
    signal_name: str,
    timeout_s: int,
    poll_s: float,
) -> None:
    key = f"{room_id}:{signal_name}"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _canonicalizer_diagnostics(client, entry_id)
        last_burst_ts = diag.get("last_burst_ts", {})
        if isinstance(last_burst_ts, dict) and str(last_burst_ts.get(key) or "").strip():
            return
        time.sleep(poll_s)
    raise AssertionError(f"canonicalizer burst not observed for {key}")


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
        existing_cfg = _configured_reactions(client, entry_id).get(reaction_id, {})
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
            if "primary_signal_name" in names:
                payload["primary_signal_name"] = str(
                    existing_cfg.get("primary_signal_name") or "room_temperature"
                )
            if "primary_trigger_mode" in names:
                payload["primary_trigger_mode"] = str(
                    existing_cfg.get("primary_trigger_mode") or "bucket"
                )
            if "primary_bucket" in names:
                payload["primary_bucket"] = str(existing_cfg.get("primary_bucket") or "")
            if "primary_bucket_match_mode" in names:
                payload["primary_bucket_match_mode"] = str(
                    existing_cfg.get("primary_bucket_match_mode") or "eq"
                )
            if "corroboration_signal_name" in names:
                payload["corroboration_signal_name"] = str(
                    existing_cfg.get("corroboration_signal_name") or ""
                )
            if "corroboration_bucket" in names:
                payload["corroboration_bucket"] = str(
                    existing_cfg.get("corroboration_bucket") or ""
                )
            if "corroboration_bucket_match_mode" in names:
                payload["corroboration_bucket_match_mode"] = str(
                    existing_cfg.get("corroboration_bucket_match_mode") or "eq"
                )
            if "action_entities" in names:
                action_entities: list[str] = []
                for step_cfg in existing_cfg.get("steps") or []:
                    if not isinstance(step_cfg, dict):
                        continue
                    target = str(step_cfg.get("target") or "").strip()
                    if target.startswith(("script.", "scene.")):
                        action_entities.append(target)
                        continue
                    params = step_cfg.get("params") or {}
                    if isinstance(params, dict):
                        entity_id = str(params.get("entity_id") or "").strip()
                        if entity_id.startswith(("script.", "scene.")):
                            action_entities.append(entity_id)
                payload["action_entities"] = action_entities
        step = client.options_flow_configure(flow_id, payload)
        _expect_step(step, "reactions_delete_confirm")
        step = client.options_flow_configure(flow_id, {"confirm": True})
        _assert(
            step.get("type") == "menu" and step.get("step_id") == "init",
            f"unexpected result after delete confirm: {step}",
        )
    finally:
        client.options_flow_abort(flow_id)


def _configured_studio_reactions_of_type(
    client: HAClient, entry_id: str, reaction_type: str
) -> list[tuple[str, dict[str, Any]]]:
    configured = _configured_reactions(client, entry_id)
    matches: list[tuple[str, dict[str, Any]]] = []
    for reaction_id, cfg in configured.items():
        if str(cfg.get("reaction_type") or "") != reaction_type:
            continue
        if str(cfg.get("room_id") or "") != "studio":
            continue
        matches.append((reaction_id, cfg))
    return matches


def _cleanup_studio_signal_and_cooling_reactions(client: HAFlowClient, entry_id: str) -> None:
    for reaction_type in ("room_cooling_assist", "room_signal_assist"):
        for reaction_id, _ in _configured_studio_reactions_of_type(client, entry_id, reaction_type):
            print(f"Cleaning pre-existing studio {reaction_type}: {reaction_id}")
            _delete_reaction_via_flow(client, entry_id, reaction_id)


def _create_admin_authored_signal_reaction(
    client: HAFlowClient,
    entry_id: str,
) -> tuple[str, dict[str, Any]]:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        step = _menu_next(client, flow_id, "admin_authored_create")
        _expect_step(step, "admin_authored_create")
        template_ids = _extract_select_values(step, "template_id")
        _assert(
            "room.signal_assist.basic" in template_ids,
            f"room.signal_assist template not exposed: {template_ids}",
        )
        step = client.options_flow_configure(flow_id, {"template_id": "room.signal_assist.basic"})
        _expect_step(step, "admin_authored_room_signal_assist")
        step = client.options_flow_configure(
            flow_id,
            {
                "room_id": "studio",
                "primary_signal_name": "room_temperature",
                "primary_trigger_mode": "bucket",
                "primary_bucket": "warm",
                "primary_bucket_match_mode": "eq",
                "corroboration_signal_name": "",
                "corroboration_bucket": "",
                "corroboration_bucket_match_mode": "eq",
                "action_entities": ["script.test_heima_reset"],
            },
        )
        _assert(
            step.get("step_id") in {"proposals", "init"},
            f"unexpected result after signal submit: {step}",
        )
        if step.get("step_id") == "proposals":
            step = client.options_flow_configure(flow_id, {"review_action": "accept"})
            _assert(
                (step.get("type") == "menu" and step.get("step_id") == "init")
                or step.get("step_id") == "proposals",
                f"unexpected result after signal accept: {step}",
            )
    finally:
        client.options_flow_abort(flow_id)

    matches = _configured_studio_reactions_of_type(client, entry_id, "room_signal_assist")
    _assert(matches, "configured studio room_signal_assist missing after admin create")
    return matches[0]


def _find_cooling_improvement(
    diag: dict[str, Any],
    *,
    target_reaction_id: str,
) -> dict[str, Any] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if str(proposal.get("type") or "") != "room_cooling_assist":
            continue
        if str(proposal.get("status") or "") != "pending":
            continue
        if str(proposal.get("followup_kind") or "") != "improvement":
            continue
        if str(proposal.get("target_reaction_type") or "") != "room_signal_assist":
            continue
        if str(proposal.get("target_reaction_id") or "") != target_reaction_id:
            continue
        return proposal
    return None


def _wait_for_cooling_improvement_pending(
    client: HAClient,
    entry_id: str,
    *,
    target_reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        client.call_service(
            "heima", "command", {"command": "learning_run", "target": {"entry_id": entry_id}}
        )
        diag = _proposal_diagnostics(client, entry_id)
        proposal = _find_cooling_improvement(diag, target_reaction_id=target_reaction_id)
        if proposal is not None:
            return proposal
        time.sleep(poll_s)
    raise AssertionError("pending cooling improvement not visible within timeout")


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
            ("cooling" in normalized_label and "existing reaction" in normalized_details)
            or ("raffresc" in normalized_label and "reaction esistente" in normalized_details)
            or ("cooling assist" in normalized_label and "room signal assist" in normalized_details)
            or (
                "affinamento assist" in normalized_label
                and "studio" in normalized_label
                and "temperature" in normalized_label
                and "reaction esistente" in normalized_details
                and "raffrescamento" in normalized_details
            )
            or (
                "assist refinement" in normalized_label
                and "studio" in normalized_label
                and "temperature" in normalized_label
                and "existing reaction" in normalized_details
                and "cooling" in normalized_details
            )
        ):
            return step
        step = client.options_flow_configure(flow_id, {"review_action": "skip"})
        if step.get("type") == "menu":
            break
        _expect_step(step, "proposals")
    raise AssertionError(f"proposal {proposal_id} not found in review queue")


def _accept_proposal(client: HAFlowClient, entry_id: str, *, proposal_id: str) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        review = _seek_review_for_proposal(client, flow_id, proposal_id=proposal_id)
        print(f"Review label:\n{_proposal_label(review)}")
        print(f"Review details:\n{_proposal_details(review)}")
        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        if result.get("step_id") == "proposal_configure_action":
            result = client.options_flow_configure(
                flow_id,
                {
                    "action_entities": [],
                    "pre_condition_min": 20,
                },
            )
        _assert(
            (result.get("type") == "menu" and result.get("step_id") == "init")
            or result.get("step_id") == "proposals",
            f"unexpected result after accept: {result}",
        )
    finally:
        client.options_flow_abort(flow_id)


def _generate_live_cooling_episode(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    _wait_state(
        client,
        "binary_sensor.test_heima_room_studio_motion",
        "off",
        timeout_s,
        poll_s,
    )
    _wait_state(client, "switch.test_heima_studio_fan", "off", timeout_s, poll_s)
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_temperature",
        24.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_humidity",
        52.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    time.sleep(2.0)
    _wait_for_canonicalizer_baseline(
        client,
        entry_id,
        room_id="studio",
        signal_name="room_temperature",
        expected_value=24.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    _wait_for_canonicalizer_baseline(
        client,
        entry_id,
        room_id="studio",
        signal_name="room_humidity",
        expected_value=52.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )

    client.call_service(
        "input_boolean",
        "turn_on",
        {"entity_id": "input_boolean.test_heima_room_studio_motion_raw"},
    )
    _wait_state(
        client,
        "binary_sensor.test_heima_room_studio_motion",
        "on",
        timeout_s,
        poll_s,
    )
    _recompute(client)
    _wait_state(client, "binary_sensor.heima_occupancy_studio", "on", timeout_s, poll_s)

    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_studio_temperature", "value": 25.8},
    )
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_temperature",
        25.8,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    _recompute(client)
    _wait_for_canonicalizer_burst(
        client,
        entry_id,
        room_id="studio",
        signal_name="room_temperature",
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": "input_number.test_heima_studio_humidity", "value": 58.0},
    )
    _wait_numeric_state(
        client,
        "sensor.test_heima_studio_humidity",
        58.0,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    _recompute(client)
    _wait_for_canonicalizer_burst(
        client,
        entry_id,
        room_id="studio",
        signal_name="room_humidity",
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    client.call_service("switch", "turn_on", {"entity_id": "switch.test_heima_studio_fan"})
    _wait_state(client, "switch.test_heima_studio_fan", "on", timeout_s, poll_s)
    _recompute(client)


def _wait_for_converted_cooling_reaction(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        cfg = _configured_reactions(client, entry_id).get(reaction_id, {})
        if str(cfg.get("reaction_type") or "") == "room_cooling_assist":
            return cfg
        time.sleep(poll_s)
    raise AssertionError("converted room_cooling_assist not visible within timeout")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima room signal assist -> cooling improvement live test"
    )
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")
    bursts_before, actuations_before = _wait_for_fixture_baseline(
        client,
        entry_id,
        minimum_room_signal_burst=8,
        minimum_actuation=8,
        timeout_s=min(args.timeout_s, 60),
        poll_s=args.poll_s,
    )
    print(
        f"Fixture baseline ready: room_signal_burst={bursts_before} actuation={actuations_before}"
    )

    _cleanup_studio_signal_and_cooling_reactions(client, entry_id)
    signal_reaction_id, _ = _create_admin_authored_signal_reaction(client, entry_id)
    print(f"Created baseline studio room_signal_assist: {signal_reaction_id}")
    print("Reloading Heima config entry to refresh room signals and runtime wiring...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    time.sleep(2.0)

    existing = _find_cooling_improvement(
        _proposal_diagnostics(client, entry_id),
        target_reaction_id=signal_reaction_id,
    )
    if existing is None:
        print("Generating live cooling evidence...")
        _generate_live_cooling_episode(
            client,
            entry_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        existing = _wait_for_cooling_improvement_pending(
            client,
            entry_id,
            target_reaction_id=signal_reaction_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )

    proposal_id = str(existing.get("id") or "")
    _assert(proposal_id, f"cooling improvement proposal missing id: {existing}")
    print(f"Cooling improvement pending: {proposal_id}")
    _accept_proposal(client, entry_id, proposal_id=proposal_id)

    converted = _wait_for_converted_cooling_reaction(
        client,
        entry_id,
        reaction_id=signal_reaction_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    _assert(
        str(converted.get("improved_from_reaction_type") or "") == "room_signal_assist",
        f"unexpected improvement provenance: {converted}",
    )
    _assert(
        str(converted.get("improvement_reason") or "") == "cooling_specialization",
        f"unexpected improvement reason: {converted}",
    )
    print("PASS: signal learned/admin baseline upgraded into cooling reaction end-to-end")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
