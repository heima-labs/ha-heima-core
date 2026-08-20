#!/usr/bin/env python3
"""Live E2E check for runtime confirmation promotion and admin revert reset."""

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


REACTION_ID = "live_runtime_confirmation_promotion_revert"
REACTION_LABEL = "Live runtime confirmation promotion revert"
PROMOTION_APPROVE_AUTO_APPLY = "heima.promotion.approve_auto_apply"
RUNTIME_APPROVE_ACTION = "heima.runtime_request.approve"
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


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    _assert(isinstance(raw, dict), f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    _assert(isinstance(data, dict), "diagnostics payload missing data object")
    return data


def _runtime_confirmation(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    confirmation = runtime.get("runtime_confirmation", {}) if isinstance(runtime, dict) else {}
    _assert(isinstance(confirmation, dict), "runtime.runtime_confirmation must be a dict")
    return confirmation


def _engine_snapshot(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
    snapshot = engine.get("snapshot", {}) if isinstance(engine, dict) else {}
    _assert(isinstance(snapshot, dict), "runtime.engine.snapshot must be a dict")
    return snapshot


def _wait_recovery_inactive(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        client.call_service(
            "heima",
            "command",
            {"command": "recompute_now", "target": {"entry_id": entry_id}},
        )
        runtime = _diagnostics_data(client, entry_id).get("runtime", {})
        engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
        runtime_context = engine.get("runtime_context", {}) if isinstance(engine, dict) else {}
        last = dict(runtime_context) if isinstance(runtime_context, dict) else {}
        if not bool(last.get("runtime.recovery.active")):
            return
        time.sleep(poll_s)
    raise AssertionError(f"runtime recovery did not become inactive: {last}")


def _persisted_row(client: HAClient, entry_id: str, reaction_id: str) -> dict[str, Any]:
    persisted = _runtime_confirmation(client, entry_id).get("persisted", {})
    by_reaction = persisted.get("by_reaction", {}) if isinstance(persisted, dict) else {}
    row = by_reaction.get(reaction_id, {}) if isinstance(by_reaction, dict) else {}
    return dict(row) if isinstance(row, dict) else {}


def _configured_reaction(client: HAClient, entry_id: str, reaction_id: str) -> dict[str, Any]:
    entry = client.get_entry(entry_id)
    reactions = dict(dict(entry.get("options") or {}).get("reactions") or {})
    configured = dict(reactions.get("configured") or {})
    cfg = configured.get(reaction_id, {})
    return dict(cfg) if isinstance(cfg, dict) else {}


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
    try:
        entry = client.get_entry(entry_id)
        notifications = dict(dict(entry.get("options") or {}).get("notifications") or {})
    except Exception:  # noqa: BLE001
        notifications = {}
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
    raise AssertionError("no light entity available for runtime confirmation live test")


def _current_context_condition(client: HAClient, entry_id: str) -> dict[str, Any]:
    client.call_service(
        "heima", "command", {"command": "recompute_now", "target": {"entry_id": entry_id}}
    )
    snapshot = _engine_snapshot(client, entry_id)
    signals = snapshot.get("context_signals")
    _assert(isinstance(signals, dict), "snapshot context_signals must be a dict")
    for signal_name, state in sorted(signals.items()):
        clean_signal = str(signal_name or "").strip()
        clean_state = str(state or "").strip()
        if clean_signal and "." not in clean_signal and clean_state:
            return {"signal_name": clean_signal, "state_in": [clean_state]}
    raise AssertionError(
        "no compatible context_signals available; configure at least one abstract "
        "learning/context signal in the lab"
    )


def _build_due_reaction(
    *,
    light_entity: str,
    context_condition: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now().astimezone()
    current_min = now.hour * 60 + now.minute
    return {
        "reaction_type": "context_conditioned_lighting_scene",
        "reaction_class": "ContextConditionedLightingReaction",
        "enabled": True,
        "origin": "admin_authored",
        "author_kind": "admin",
        "room_id": "studio",
        "weekday": now.weekday(),
        "scheduled_min": current_min,
        "window_half_min": 10,
        "entity_steps": [
            {
                "entity_id": light_entity,
                "action": "on",
                "brightness": 77,
            }
        ],
        "context_conditions": [context_condition],
        "source_request": "live_test:runtime_confirmation_promotion_revert",
        "source_template_id": "live_test.runtime_confirmation",
        "execution_policy": {
            "mode": "ask_residents",
            "confirmation": {
                "expires_in_minutes": 10,
                "on_timeout": "skip",
                "target_recipients": [],
                "target_groups": ["live_test_residents"],
                "use_default_route_targets": False,
            },
            "promotion": {
                "enabled": True,
                "min_samples": 1,
                "min_approval_rate": 1.0,
                "min_distinct_days": 1,
                "reminder_interval_days": 1,
            },
        },
    }


def _upsert_reaction(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    cfg: dict[str, Any],
    *,
    label: str = REACTION_LABEL,
) -> None:
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": {reaction_id: cfg},
                "labels": {reaction_id: label},
            },
        },
    )


def _reload_entry(client: HAClient, entry_id: str, settle_s: float) -> None:
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    time.sleep(settle_s)


def _reset_runtime_state_if_present(client: HAFlowClient, entry_id: str, reaction_id: str) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "runtime_confirmation_maintenance")
        if step.get("step_id") != "runtime_confirmation_maintenance":
            return
        try:
            result = client.options_flow_configure(
                flow_id,
                {"reaction": reaction_id, "confirm_reset": True},
            )
        except HAApiError as exc:
            if "value must be one of" in str(exc):
                return
            raise
        _expect_step(result, "init")
    finally:
        client.options_flow_abort(flow_id)


def _wait_for_pending_request(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
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
            if str(row.get("reaction_id") or "") == reaction_id:
                return row
        time.sleep(poll_s)
    raise AssertionError(f"pending runtime request not created; last pending rows={last}")


def _approve_runtime_request(client: HAClient, request_id: str) -> None:
    client.post(
        "/api/events/mobile_app_notification_action",
        {
            "action": RUNTIME_APPROVE_ACTION,
            "tag": request_id,
            "action_data": {"request_id": request_id},
        },
    )


def _wait_for_completed_request(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    request_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        rows = _runtime_confirmation(client, entry_id).get("recent_completed_requests", [])
        last = [dict(row) for row in rows if isinstance(row, dict)]
        for row in last:
            if (
                str(row.get("reaction_id") or "") == reaction_id
                and str(row.get("request_id") or "") == request_id
            ):
                _assert(row.get("status") == "approved", f"request was not approved: {row}")
                return row
        time.sleep(poll_s)
    raise AssertionError(f"approved runtime request not completed; last completed rows={last}")


def _wait_for_promotion_review(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    *,
    status: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        row = _persisted_row(client, entry_id, reaction_id)
        last = row
        review = dict(row.get("promotion_review") or {})
        if str(review.get("status") or "") == status:
            return review
        time.sleep(poll_s)
    raise AssertionError(f"promotion review did not reach {status!r}; last row={last}")


def _approve_promotion(client: HAFlowClient, entry_id: str, reaction_id: str) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "runtime_promotion_reviews")
        _expect_step(step, "runtime_promotion_reviews")
        result = client.options_flow_configure(
            flow_id,
            {
                "reaction": reaction_id,
                "action": PROMOTION_APPROVE_AUTO_APPLY,
            },
        )
        _expect_step(result, "init")
    finally:
        client.options_flow_abort(flow_id)


def _edit_reaction_to_ask_residents(client: HAFlowClient, entry_id: str, reaction_id: str) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "reactions_edit")
        _expect_step(step, "reactions_edit")
        step = client.options_flow_configure(flow_id, {"reaction": reaction_id})
        _expect_step(step, "reactions_edit_form")
        result = client.options_flow_configure(
            flow_id,
            {
                "enabled": True,
                "execution_mode": "ask_residents",
                "confirmation_expires_in_minutes": 10,
                "confirmation_on_timeout": "skip",
                "confirmation_target_recipients": [],
                "confirmation_target_groups": ["live_test_residents"],
                "confirmation_use_default_route_targets": False,
            },
        )
        _expect_step(result, "init")
    finally:
        client.options_flow_abort(flow_id)


def _wait_for_execution_mode(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    *,
    mode: str,
    promoted: bool | None,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        row = _persisted_row(client, entry_id, reaction_id)
        last = row
        if str(row.get("execution_mode") or "") != mode:
            time.sleep(poll_s)
            continue
        review = dict(row.get("promotion_review") or {})
        if promoted is True and str(review.get("status") or "") != "approved":
            time.sleep(poll_s)
            continue
        if promoted is False and review:
            time.sleep(poll_s)
            continue
        return row
        time.sleep(poll_s)
    raise AssertionError(f"execution mode did not reach {mode!r}; last row={last}")


def _assert_runtime_state_cleared(client: HAClient, entry_id: str, reaction_id: str) -> None:
    row = _persisted_row(client, entry_id, reaction_id)
    stats = dict(row.get("confirmation_stats") or {})
    review = dict(row.get("promotion_review") or {})
    _assert(not stats, f"confirmation stats should be cleared after revert: {stats}")
    _assert(not review, f"promotion review should be cleared after revert: {review}")


def _assert_no_immediate_repromotion(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    *,
    settle_s: float,
) -> None:
    client.call_service(
        "heima",
        "command",
        {"command": "recompute_now", "target": {"entry_id": entry_id}},
    )
    time.sleep(settle_s)
    row = _persisted_row(client, entry_id, reaction_id)
    review = dict(row.get("promotion_review") or {})
    _assert(not review, f"old evidence recreated promotion review unexpectedly: {review}")


def _disable_reaction_cleanup(client: HAClient, entry_id: str, reaction_id: str) -> None:
    cfg = _configured_reaction(client, entry_id, reaction_id)
    if not cfg:
        return
    cfg["enabled"] = False
    _upsert_reaction(client, entry_id, reaction_id, cfg, label=REACTION_LABEL)


def _disable_reaction_cleanup_with_cfg(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    cfg: dict[str, Any] | None,
) -> None:
    if not cfg:
        _disable_reaction_cleanup(client, entry_id, reaction_id)
        return
    cleanup_cfg = dict(cfg)
    cleanup_cfg["enabled"] = False
    _upsert_reaction(client, entry_id, reaction_id, cleanup_cfg, label=REACTION_LABEL)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima runtime confirmation promotion/revert live E2E"
    )
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--poll-s", type=float, default=1.0)
    parser.add_argument("--settle-s", type=float, default=2.0)
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    original_notifications = _notification_payload_from_entry(client, entry_id)
    cleanup_reaction_cfg: dict[str, Any] | None = None

    try:
        _reset_runtime_state_if_present(client, entry_id, REACTION_ID)
        _configure_notifications(
            client, entry_id, _live_notification_payload(original_notifications)
        )
        _wait_recovery_inactive(
            client,
            entry_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )

        light_entity = _find_light_entity(client)
        condition = _current_context_condition(client, entry_id)
        reaction_cfg = _build_due_reaction(
            light_entity=light_entity,
            context_condition=condition,
        )
        cleanup_reaction_cfg = reaction_cfg
        _upsert_reaction(client, entry_id, REACTION_ID, reaction_cfg)
        _reload_entry(client, entry_id, args.settle_s)

        pending = _wait_for_pending_request(
            client,
            entry_id,
            REACTION_ID,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        request_id = str(pending.get("request_id") or "")
        _assert(request_id, f"pending request missing request_id: {pending}")

        _approve_runtime_request(client, request_id)
        completed = _wait_for_completed_request(
            client,
            entry_id,
            REACTION_ID,
            request_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        apply_result = dict(completed.get("apply_result") or {})
        _assert(
            int(apply_result.get("applied_steps") or 0) >= 1,
            f"approved request did not apply any step: {completed}",
        )

        review = _wait_for_promotion_review(
            client,
            entry_id,
            REACTION_ID,
            status="pending_admin_review",
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        _assert(review.get("target_mode") == "auto_apply", f"unexpected promotion review: {review}")

        _approve_promotion(client, entry_id, REACTION_ID)
        _wait_for_execution_mode(
            client,
            entry_id,
            REACTION_ID,
            mode="auto_apply",
            promoted=True,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )

        _edit_reaction_to_ask_residents(client, entry_id, REACTION_ID)
        _wait_for_execution_mode(
            client,
            entry_id,
            REACTION_ID,
            mode="ask_residents",
            promoted=False,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        _assert_runtime_state_cleared(client, entry_id, REACTION_ID)
        _assert_no_immediate_repromotion(
            client,
            entry_id,
            REACTION_ID,
            settle_s=args.settle_s,
        )

        print("PASS: runtime confirmation promotion and revert reset are live-valid")
        return 0
    finally:
        try:
            _configure_notifications(client, entry_id, original_notifications)
        finally:
            _disable_reaction_cleanup_with_cfg(
                client,
                entry_id,
                REACTION_ID,
                cleanup_reaction_cfg,
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
