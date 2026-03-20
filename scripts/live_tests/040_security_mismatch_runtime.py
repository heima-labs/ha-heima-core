#!/usr/bin/env python3
"""Live runtime E2E: security mismatch event type by emission mode."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient
from lib.ha_websocket import HAWebSocketClient, HAWebSocketError


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


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _expect_step(result: dict[str, Any], step_id: str) -> None:
    _assert(isinstance(result, dict), f"invalid flow result type: {type(result)}")
    _assert(result.get("step_id") == step_id, f"expected step_id={step_id}, got={result.get('step_id')}")


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _flow_save(client: HAFlowClient, flow_id: str) -> None:
    result = _menu_next(client, flow_id, "save")
    _assert(result.get("type") == "create_entry", f"expected create_entry on save, got: {result}")


def _notification_payload_from_entry(client: HAFlowClient, entry_id: str) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "recipients": {},
        "recipient_groups": {},
        "route_targets": [],
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
        options = dict(entry.get("options") or {})
        notifications = dict(options.get("notifications") or {})
        merged = dict(defaults)
        merged.update(notifications)
        return merged
    except Exception:  # noqa: BLE001
        return defaults


def _extract_security_cfg(entry: dict[str, Any]) -> dict[str, Any]:
    options = dict(entry.get("options") or {})
    if isinstance(options.get("security"), dict):
        return dict(options.get("security") or {})
    data = dict(entry.get("data") or {})
    if isinstance(data.get("security"), dict):
        return dict(data.get("security") or {})
    return {}


def _resolve_entry_with_security(client: HAFlowClient, requested_entry_id: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if requested_entry_id:
        entry = client.get_entry(requested_entry_id)
        security_cfg = _extract_security_cfg(entry)
        return requested_entry_id, entry, security_cfg

    # Prefer an entry that actually has security configured/enabled.
    for item in client.list_config_entries():
        if str(item.get("domain") or "") != "heima":
            continue
        entry_id = str(item.get("entry_id") or "")
        if not entry_id:
            continue
        entry = client.get_entry(entry_id)
        security_cfg = _extract_security_cfg(entry)
        if security_cfg.get("enabled") and str(security_cfg.get("security_state_entity") or "").strip():
            return entry_id, entry, security_cfg

    # Fallback: first heima entry (for debug/skip messages).
    entry_id = client.find_heima_entry_id()
    entry = client.get_entry(entry_id)
    security_cfg = _extract_security_cfg(entry)
    return entry_id, entry, security_cfg


def _ensure_security_configured_for_lab(
    client: HAFlowClient,
    *,
    entry_id: str,
    security_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Ensure security config exists in Heima options for test-lab runtime scenario.

    If security is missing/disabled but fake alarm entity is present, patch options-flow
    automatically so runtime scenario can execute instead of skipping.
    """
    entity_id = str(security_cfg.get("security_state_entity") or "").strip()
    if security_cfg.get("enabled") and entity_id:
        return security_cfg

    fake_alarm = "alarm_control_panel.test_heima_alarm"

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "security")
    _expect_step(step, "security")
    submit = client.options_flow_configure(
        flow_id,
        {
            "enabled": True,
            "security_state_entity": fake_alarm,
            "armed_away_value": "armed_away",
            "armed_home_value": "armed_home",
        },
    )
    _expect_step(submit, "init")
    _flow_save(client, flow_id)
    # Do not rely on entry detail payload roundtrip: on some HA builds it does not
    # expose full options immediately. Return the applied config directly.
    return {
        "enabled": True,
        "security_state_entity": fake_alarm,
        "armed_away_value": "armed_away",
        "armed_home_value": "armed_home",
    }


def _set_notifications_mode(
    client: HAFlowClient, entry_id: str, payload: dict[str, Any], *, mode: str
) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")
    step = _menu_next(client, flow_id, "notifications")
    _expect_step(step, "notifications")
    data = dict(payload)
    categories = list(data.get("enabled_event_categories") or [])
    if "security" not in categories:
        categories.append("security")
    if "people" not in categories:
        categories.append("people")
    data["enabled_event_categories"] = categories
    data["security_mismatch_policy"] = "strict"
    data["security_mismatch_persist_s"] = 0
    data["dedup_window_s"] = 0
    data["rate_limit_per_key_s"] = 0
    data["security_mismatch_event_mode"] = mode
    submit = client.options_flow_configure(flow_id, data)
    _expect_step(submit, "init")
    _flow_save(client, flow_id)


def _first_person_override_entity(client: HAClient) -> str | None:
    for state in client.all_states():
        entity_id = str(state.get("entity_id") or "")
        if entity_id.startswith("select.heima_person_") and entity_id.endswith("_override"):
            return entity_id
    return None


def _set_security_state(client: HAClient, entity_id: str, value: str, *, alarm_code: str) -> bool:
    if entity_id.startswith("input_select."):
        client.call_service(
            "input_select",
            "select_option",
            {"entity_id": entity_id, "option": value},
        )
        return True
    if entity_id.startswith("select."):
        client.call_service(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": value},
        )
        return True
    if entity_id.startswith("alarm_control_panel."):
        if value == "armed_away":
            client.call_service(
                "alarm_control_panel",
                "alarm_arm_away",
                {"entity_id": entity_id, "code": alarm_code},
            )
            return True
        if value == "armed_home":
            client.call_service(
                "alarm_control_panel",
                "alarm_arm_home",
                {"entity_id": entity_id, "code": alarm_code},
            )
            return True
        if value == "disarmed":
            client.call_service(
                "alarm_control_panel",
                "alarm_disarm",
                {"entity_id": entity_id, "code": alarm_code},
            )
            return True
    return False


def _reset_after_test(
    client: HAClient,
    original_mode: str,
    payload: dict[str, Any],
    entry_id: str,
    person_override_entity: str,
    security_entity: str,
    original_security_state: str | None,
    alarm_code: str,
) -> None:
    try:
        _set_notifications_mode(client, entry_id, payload, mode=original_mode)
    except Exception:  # noqa: BLE001
        pass
    try:
        client.call_service("select", "select_option", {"entity_id": person_override_entity, "option": "auto"})
    except Exception:  # noqa: BLE001
        pass
    if original_security_state:
        try:
            _set_security_state(
                client,
                security_entity,
                original_security_state,
                alarm_code=alarm_code,
            )
        except Exception:  # noqa: BLE001
            pass
    try:
        client.call_service("heima", "command", {"command": "recompute_now"})
    except Exception:  # noqa: BLE001
        pass


def _last_event_history(client: HAClient, lookback_minutes: int = 5) -> list[str]:
    from datetime import datetime, timedelta, timezone

    start = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    path = (
        f"/api/history/period/{quote(start.isoformat())}"
        "?filter_entity_id=sensor.heima_last_event&minimal_response=1&no_attributes=1"
    )
    data = client.get(path)
    if not isinstance(data, list) or not data:
        return []
    series = data[0] if isinstance(data[0], list) else []
    states: list[str] = []
    for item in series:
        if isinstance(item, dict):
            value = str(item.get("state") or "")
            if value:
                states.append(value)
    return states


def _last_event_history_since(client: HAClient, *, since_ts: float, lookback_minutes: int = 5) -> list[str]:
    from datetime import datetime, timedelta, timezone

    start = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    path = f"/api/history/period/{quote(start.isoformat())}?filter_entity_id=sensor.heima_last_event"
    data = client.get(path)
    if not isinstance(data, list) or not data:
        return []
    series = data[0] if isinstance(data[0], list) else []
    states: list[str] = []
    for item in series:
        if not isinstance(item, dict):
            continue
        last_changed_raw = str(item.get("last_changed") or item.get("last_updated") or "")
        if not last_changed_raw:
            continue
        try:
            last_changed = datetime.fromisoformat(last_changed_raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if last_changed < since_ts:
            continue
        value = str(item.get("state") or "")
        if value:
            states.append(value)
    return states


def _wait_dual_emit_history(
    client: HAClient,
    *,
    since_ts: float,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        tail = _last_event_history_since(client, since_ts=since_ts, lookback_minutes=5)
        has_specific = "security.armed_away_but_home" in tail
        has_generic = "security.mismatch" in tail
        if has_specific and has_generic:
            return
        time.sleep(poll_s)
    tail = _last_event_history_since(client, since_ts=since_ts, lookback_minutes=5)
    raise RuntimeError(
        "Dual emit not observed in heima_last_event history "
        f"(tail={tail[-8:]})"
    )


def _wait_dual_emit_bus(
    base_url: str,
    token: str,
    *,
    timeout_s: int,
    trigger: callable,
) -> None:
    last_error: Exception | None = None
    last_event_types: list[str] = []
    for _ in range(2):
        try:
            with HAWebSocketClient(base_url, token, timeout=timeout_s) as ws:
                subscription_id = ws.subscribe_events("heima_event")
                trigger()
                events = ws.wait_for_matching_events(
                    subscription_id,
                    timeout_s=timeout_s,
                    predicate=lambda items: _dual_emit_seen(items),
                )
            event_types = _heima_event_types(events)
            has_specific = "security.armed_away_but_home" in event_types
            has_generic = "security.mismatch" in event_types
            if has_specific and has_generic:
                return
            last_event_types = event_types
            last_error = RuntimeError(
                "Dual emit not observed on heima_event bus "
                f"(types={event_types[-12:]})"
            )
        except HAWebSocketError as exc:
            last_error = exc
            time.sleep(0.5)
    if last_error is not None:
        raise last_error
    raise RuntimeError(
        "Dual emit not observed on heima_event bus "
        f"(types={last_event_types[-12:]})"
    )


def _heima_event_types(events: list[dict[str, Any]]) -> list[str]:
    event_types: list[str] = []
    for event in events:
        if str(event.get("event_type") or "") != "heima_event":
            continue
        payload = event.get("data") or {}
        if not isinstance(payload, dict):
            continue
        event_type = str(payload.get("type") or "")
        if event_type:
            event_types.append(event_type)
    return event_types


def _dual_emit_seen(events: list[dict[str, Any]]) -> bool:
    event_types = _heima_event_types(events)
    return (
        "security.armed_away_but_home" in event_types
        and "security.mismatch" in event_types
    )


def _trigger_security_mismatch_once(
    client: HAFlowClient,
    *,
    person_override_entity: str,
    security_entity: str,
    armed_away_value: str,
    alarm_code: str,
    settle_s: float = 0.5,
) -> None:
    """Force a fresh mismatch transition to avoid one-shot suppression state."""
    # 1) Clear mismatch path
    client.call_service("select", "select_option", {"entity_id": person_override_entity, "option": "force_away"})
    client.call_service("heima", "command", {"command": "recompute_now"})
    time.sleep(settle_s)

    # 2) Re-arm desired security state and reactivate mismatch
    _set_security_state(
        client,
        security_entity,
        armed_away_value,
        alarm_code=alarm_code,
    )
    client.call_service("select", "select_option", {"entity_id": person_override_entity, "option": "force_home"})
    client.call_service("heima", "command", {"command": "recompute_now"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima security mismatch runtime live test")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--entry-id", default="")
    parser.add_argument("--timeout-s", type=int, default=45)
    parser.add_argument("--poll-s", type=float, default=1.0)
    parser.add_argument("--alarm-code", default="1234")
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id, entry, security_cfg = _resolve_entry_with_security(client, args.entry_id)
    print(f"Using heima entry_id={entry_id}")
    security_cfg = _ensure_security_configured_for_lab(
        client,
        entry_id=entry_id,
        security_cfg=security_cfg,
    )
    security_entity = str(security_cfg.get("security_state_entity") or "")
    armed_away_value = str(security_cfg.get("armed_away_value") or "armed_away")

    if not security_cfg.get("enabled") or not security_entity:
        print(
            "SKIP runtime mismatch scenario "
            f"(security not configured in selected entry: {entry_id})"
        )
        return 0

    person_override_entity = _first_person_override_entity(client)
    if not person_override_entity:
        print("SKIP runtime mismatch scenario (no heima person override select found)")
        return 0

    original_security_state = None
    try:
        original_security_state = client.state_value(security_entity)
    except Exception:  # noqa: BLE001
        pass
    if not _set_security_state(
        client,
        security_entity,
        armed_away_value,
        alarm_code=args.alarm_code,
    ):
        print(
            "SKIP runtime mismatch scenario "
            f"(unsupported security_state_entity for live forcing: {security_entity})"
        )
        return 0

    payload = _notification_payload_from_entry(client, entry_id)
    original_mode = str(payload.get("security_mismatch_event_mode", "explicit_only"))

    try:
        print("== Scenario E1: explicit_only emits security.armed_away_but_home ==")
        _set_notifications_mode(client, entry_id, payload, mode="explicit_only")
        _trigger_security_mismatch_once(
            client,
            person_override_entity=person_override_entity,
            security_entity=security_entity,
            armed_away_value=armed_away_value,
            alarm_code=args.alarm_code,
        )
        client.wait_state("sensor.heima_last_event", "security.armed_away_but_home", args.timeout_s, args.poll_s)
        print("PASS scenario E1")

        print("== Scenario E2: generic_only emits security.mismatch ==")
        _set_notifications_mode(client, entry_id, payload, mode="generic_only")
        _trigger_security_mismatch_once(
            client,
            person_override_entity=person_override_entity,
            security_entity=security_entity,
            armed_away_value=armed_away_value,
            alarm_code=args.alarm_code,
        )
        client.wait_state("sensor.heima_last_event", "security.mismatch", args.timeout_s, args.poll_s)
        print("PASS scenario E2")

        print("== Scenario E3: dual_emit emits both explicit and generic ==")
        _set_notifications_mode(client, entry_id, payload, mode="dual_emit")
        since_ts = time.time()
        try:
            _wait_dual_emit_bus(
                args.ha_url,
                args.ha_token,
                timeout_s=args.timeout_s,
                trigger=lambda: _trigger_security_mismatch_once(
                    client,
                    person_override_entity=person_override_entity,
                    security_entity=security_entity,
                    armed_away_value=armed_away_value,
                    alarm_code=args.alarm_code,
                ),
            )
        except HAWebSocketError:
            _trigger_security_mismatch_once(
                client,
                person_override_entity=person_override_entity,
                security_entity=security_entity,
                armed_away_value=armed_away_value,
                alarm_code=args.alarm_code,
            )
            _wait_dual_emit_history(
                client,
                since_ts=since_ts,
                timeout_s=args.timeout_s,
                poll_s=args.poll_s,
            )
        print("PASS scenario E3")
    finally:
        _reset_after_test(
            client,
            original_mode,
            payload,
            entry_id,
            person_override_entity,
            security_entity,
            original_security_state,
            args.alarm_code,
        )

    print("Security mismatch runtime live scenarios passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
