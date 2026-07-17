#!/usr/bin/env python3
"""Live E2E check for profile-backed runtime confirmation policies."""

# ruff: noqa: I001

from __future__ import annotations

import argparse
from datetime import datetime
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


REACTION_ID = "live_runtime_confirmation_profile_policy"
INVALID_REF_REACTION_ID = "live_runtime_confirmation_invalid_profile"
REACTION_LABEL = "Live runtime confirmation profile policy"
PROFILE_ID = "live_ask_residents_profile"
MISSING_PROFILE_ID = "live_missing_execution_policy_profile"
NOTIFY_ROUTE = "persistent_notification"


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


def _form_option_containing(step: dict[str, Any], field: str, text: str) -> str:
    for item in step.get("data_schema") or []:
        if not isinstance(item, dict) or item.get("name") != field:
            continue
        for option in item.get("options") or []:
            if isinstance(option, list | tuple) and option:
                value = str(option[0])
            else:
                value = str(option)
            if text in value:
                return value
    raise AssertionError(f"no {field} option containing {text!r}: {step}")


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    _assert(isinstance(raw, dict), f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    _assert(isinstance(data, dict), "diagnostics payload missing data object")
    return data


def _engine_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
    _assert(isinstance(engine, dict), "runtime.engine must be a dict")
    return engine


def _runtime_confirmation(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    confirmation = runtime.get("runtime_confirmation", {}) if isinstance(runtime, dict) else {}
    _assert(isinstance(confirmation, dict), "runtime.runtime_confirmation must be a dict")
    return confirmation


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    entry = client.get_entry(entry_id)
    options = entry.get("options")
    return dict(options) if isinstance(options, dict) else {}


def _notification_payload_from_entry(client: HAClient, entry_id: str) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "recipients": {},
        "recipient_groups": {},
        "route_targets": [],
        "notification_service_capabilities": {},
        "enabled_event_categories": ["people", "occupancy", "lighting", "heating", "security"],
        "dedup_window_s": 60,
        "rate_limit_per_key_s": 300,
        "occupancy_mismatch_policy": "smart",
        "occupancy_mismatch_min_derived_rooms": 2,
        "occupancy_mismatch_persist_s": 600,
        "security_mismatch_policy": "smart",
        "security_mismatch_event_mode": "explicit_only",
        "security_mismatch_persist_s": 300,
    }
    notifications = dict(_entry_options(client, entry_id).get("notifications") or {})
    merged = dict(defaults)
    merged.update(notifications)
    return merged


def _configure_notifications(
    client: HAFlowClient,
    entry_id: str,
    payload: dict[str, Any],
) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "notifications")
        _expect_step(step, "notifications")
        result = client.options_flow_configure(flow_id, payload)
        _expect_step(result, "init")
    finally:
        client.options_flow_abort(flow_id)


def _live_notification_payload(base: dict[str, Any]) -> dict[str, Any]:
    payload = dict(base)
    payload["recipients"] = {"live_test_resident": [NOTIFY_ROUTE]}
    payload["recipient_groups"] = {"live_test_residents": ["live_test_resident"]}
    payload["route_targets"] = ["live_test_residents"]
    payload["notification_service_capabilities"] = {
        NOTIFY_ROUTE: {"supports_actions": True},
    }
    return payload


def _profile_exists(client: HAClient, entry_id: str, profile_id: str) -> bool:
    reactions = dict(_entry_options(client, entry_id).get("reactions") or {})
    profiles = reactions.get("execution_policy_profiles")
    return isinstance(profiles, dict) and profile_id in profiles


def _upsert_profile(client: HAFlowClient, entry_id: str) -> None:
    payload = {
        "profile_id": PROFILE_ID,
        "mode": "ask_residents",
        "confirmation_target_recipients": [],
        "confirmation_target_groups": [],
        "confirmation_use_default_route_targets": True,
        "confirmation_expires_in_minutes": 10,
        "confirmation_on_timeout": "skip",
        "promotion_enabled": True,
        "promotion_target_recipients": [],
        "promotion_target_groups": [],
        "promotion_min_samples": 5,
        "promotion_min_approval_rate": 0.8,
        "promotion_min_distinct_days": 3,
        "promotion_reminder_interval_days": 7,
    }
    if _profile_exists(client, entry_id, PROFILE_ID):
        _edit_existing_profile(client, entry_id, payload)
        return

    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    aborted = False
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "execution_policy_profiles")
        _expect_step(step, "execution_policy_profiles")
        step = _menu_next(client, flow_id, "execution_policy_profile_add")
        _expect_step(step, "execution_policy_profile_add")
        result = client.options_flow_configure(flow_id, payload)
        if (
            result.get("step_id") == "execution_policy_profile_add"
            and dict(result.get("errors") or {}).get("profile_id") == "already_exists"
        ):
            client.options_flow_abort(flow_id)
            aborted = True
            _edit_existing_profile(client, entry_id, payload)
            return
        _expect_step(result, "execution_policy_profiles")
    finally:
        if not aborted:
            client.options_flow_abort(flow_id)


def _edit_existing_profile(
    client: HAFlowClient,
    entry_id: str,
    payload: dict[str, Any],
) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "execution_policy_profiles")
        _expect_step(step, "execution_policy_profiles")
        step = _menu_next(client, flow_id, "execution_policy_profile_edit")
        _expect_step(step, "execution_policy_profile_edit")
        step = client.options_flow_configure(
            flow_id,
            {"profile_id": _form_option_containing(step, "profile_id", PROFILE_ID)},
        )
        _expect_step(step, "execution_policy_profile_edit_form")
        result = client.options_flow_configure(flow_id, payload)
        _expect_step(result, "execution_policy_profiles")
    finally:
        client.options_flow_abort(flow_id)


def _delete_profile_if_present(client: HAFlowClient, entry_id: str) -> None:
    if not _profile_exists(client, entry_id, PROFILE_ID):
        return
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "execution_policy_profiles")
        _expect_step(step, "execution_policy_profiles")
        step = _menu_next(client, flow_id, "execution_policy_profile_delete")
        _expect_step(step, "execution_policy_profile_delete")
        step = client.options_flow_configure(
            flow_id,
            {"profile_id": _form_option_containing(step, "profile_id", PROFILE_ID)},
        )
        _expect_step(step, "execution_policy_profile_delete_confirm")
        result = client.options_flow_configure(flow_id, {"confirm": True})
        _expect_step(result, "execution_policy_profiles")
    finally:
        client.options_flow_abort(flow_id)


def _find_light_entity(client: HAClient) -> str:
    preferred = "light.test_heima_studio_desk"
    if client.entity_exists(preferred):
        return preferred
    for state in client.all_states():
        entity_id = str(state.get("entity_id") or "")
        if entity_id.startswith("light.") and "test_heima" in entity_id:
            return entity_id
    for state in client.all_states():
        entity_id = str(state.get("entity_id") or "")
        if entity_id.startswith("light."):
            return entity_id
    raise AssertionError("no light entity available for runtime confirmation profile live test")


def _current_context_condition(client: HAClient, entry_id: str) -> dict[str, Any]:
    client.call_service(
        "heima",
        "command",
        {"command": "recompute_now", "target": {"entry_id": entry_id}},
    )
    snapshot = _engine_diagnostics(client, entry_id).get("snapshot", {})
    signals = snapshot.get("context_signals")
    _assert(isinstance(signals, dict), "snapshot context_signals must be a dict")
    for signal_name, state in sorted(signals.items()):
        clean_signal = str(signal_name or "").strip()
        clean_state = str(state or "").strip()
        if clean_signal and clean_state:
            return {"signal_name": clean_signal, "state_in": [clean_state]}
    raise AssertionError("no context_signals available for runtime confirmation profile live test")


def _build_due_profile_reaction(
    *,
    light_entity: str,
    context_condition: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now().astimezone()
    return {
        "reaction_type": "context_conditioned_lighting_scene",
        "reaction_class": "ContextConditionedLightingReaction",
        "enabled": True,
        "origin": "admin_authored",
        "author_kind": "admin",
        "room_id": "studio",
        "weekday": now.weekday(),
        "scheduled_min": now.hour * 60 + now.minute,
        "window_half_min": 10,
        "entity_steps": [{"entity_id": light_entity, "action": "on", "brightness": 67}],
        "context_conditions": [context_condition],
        "source_request": "live_test:runtime_confirmation_profile_policy",
        "source_template_id": "live_test.runtime_confirmation_profile_policy",
        "execution_policy_ref": PROFILE_ID,
    }


def _build_due_invalid_ref_reaction(
    *,
    light_entity: str,
    context_condition: dict[str, Any],
) -> dict[str, Any]:
    cfg = _build_due_profile_reaction(
        light_entity=light_entity,
        context_condition=context_condition,
    )
    cfg["source_request"] = "live_test:runtime_confirmation_invalid_profile"
    cfg["source_template_id"] = "live_test.runtime_confirmation_invalid_profile"
    cfg["execution_policy_ref"] = MISSING_PROFILE_ID
    return cfg


def _upsert_reaction(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    cfg: dict[str, Any],
) -> None:
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {reaction_id: cfg},
                "labels": {reaction_id: REACTION_LABEL},
            },
        },
    )


def _cleanup_reaction(client: HAClient, entry_id: str) -> None:
    for reaction_id in (REACTION_ID, INVALID_REF_REACTION_ID):
        _upsert_reaction(
            client,
            entry_id,
            reaction_id,
            {
                "reaction_type": "context_conditioned_lighting_scene",
                "enabled": False,
                "execution_policy": {"mode": "auto_apply"},
            },
        )


def _reload_entry(client: HAClient, entry_id: str, settle_s: float) -> None:
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    time.sleep(settle_s)


def _wait_for_pending_request(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        client.call_service(
            "heima",
            "command",
            {"command": "recompute_now", "target": {"entry_id": entry_id}},
        )
        rows = _runtime_confirmation(client, entry_id).get("pending_requests", [])
        last = [dict(row) for row in rows if isinstance(row, dict)]
        for row in last:
            if str(row.get("reaction_id") or "") == REACTION_ID:
                return row
        time.sleep(poll_s)
    raise AssertionError(f"profile-backed pending request not created; last pending rows={last}")


def _assert_effective_policy_diagnostics(client: HAClient, entry_id: str) -> None:
    policies = _engine_diagnostics(client, entry_id).get("reaction_execution_policies", {})
    _assert(isinstance(policies, dict), "reaction_execution_policies must be a dict")
    policy = policies.get(REACTION_ID)
    _assert(isinstance(policy, dict), f"missing policy diagnostics for {REACTION_ID}: {policies}")
    _assert(policy.get("source") == "profile", f"expected profile source, got {policy}")
    _assert(policy.get("profile_id") == PROFILE_ID, f"expected profile id, got {policy}")
    _assert(policy.get("mode") == "ask_residents", f"expected ask_residents, got {policy}")
    confirmation = policy.get("confirmation")
    _assert(isinstance(confirmation, dict), f"missing confirmation diagnostics: {policy}")
    _assert(
        "live_test_residents" in confirmation.get("effective_targets", []),
        f"default route group missing from effective targets: {confirmation}",
    )


def _assert_invalid_ref_fails_closed(client: HAClient, entry_id: str) -> None:
    client.call_service(
        "heima",
        "command",
        {"command": "recompute_now", "target": {"entry_id": entry_id}},
    )
    rows = _runtime_confirmation(client, entry_id).get("pending_requests", [])
    pending_ids = {str(row.get("reaction_id") or "") for row in rows if isinstance(row, dict)}
    _assert(
        INVALID_REF_REACTION_ID not in pending_ids,
        f"invalid profile ref created a pending request unexpectedly: {rows}",
    )
    policies = _engine_diagnostics(client, entry_id).get("reaction_execution_policies", {})
    _assert(isinstance(policies, dict), "reaction_execution_policies must be a dict")
    policy = policies.get(INVALID_REF_REACTION_ID)
    _assert(
        isinstance(policy, dict),
        f"missing invalid-ref diagnostics for {INVALID_REF_REACTION_ID}: {policies}",
    )
    _assert(policy.get("source") == "unresolved_reference", f"unexpected source: {policy}")
    _assert(policy.get("profile_id") == MISSING_PROFILE_ID, f"unexpected profile id: {policy}")
    _assert(
        policy.get("config_error") == "unresolved_execution_policy_ref",
        f"unexpected config error: {policy}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima profile-backed runtime confirmation live E2E"
    )
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--poll-s", type=float, default=1.0)
    parser.add_argument("--settle-s", type=float, default=2.0)
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    original_notifications = _notification_payload_from_entry(client, entry_id)

    try:
        _cleanup_reaction(client, entry_id)
        _delete_profile_if_present(client, entry_id)
        _configure_notifications(
            client, entry_id, _live_notification_payload(original_notifications)
        )
        _upsert_profile(client, entry_id)

        light_entity = _find_light_entity(client)
        condition = _current_context_condition(client, entry_id)
        reaction_cfg = _build_due_profile_reaction(
            light_entity=light_entity,
            context_condition=condition,
        )
        _upsert_reaction(client, entry_id, REACTION_ID, reaction_cfg)
        _reload_entry(client, entry_id, args.settle_s)

        pending = _wait_for_pending_request(
            client,
            entry_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        _assert(str(pending.get("request_id") or ""), f"pending request missing id: {pending}")
        _assert_effective_policy_diagnostics(client, entry_id)

        invalid_cfg = _build_due_invalid_ref_reaction(
            light_entity=light_entity,
            context_condition=condition,
        )
        _upsert_reaction(client, entry_id, INVALID_REF_REACTION_ID, invalid_cfg)
        _reload_entry(client, entry_id, args.settle_s)
        _assert_invalid_ref_fails_closed(client, entry_id)

        print("PASS: profile-backed runtime confirmation is live-valid")
        return 0
    finally:
        try:
            _configure_notifications(client, entry_id, original_notifications)
        finally:
            _cleanup_reaction(client, entry_id)
            try:
                _delete_profile_if_present(client, entry_id)
            except Exception:
                pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
