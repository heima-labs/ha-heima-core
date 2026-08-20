#!/usr/bin/env python3
"""Active live check for invariant-driven health degraded -> ok clearing."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient

CHECK_ID = "security_presence_mismatch"
ALARM_CODE = "1234"


def _load_security_helpers() -> Any:
    path = Path(__file__).resolve().with_name("040_security_mismatch_runtime.py")
    spec = importlib.util.spec_from_file_location("heima_live_040_security_mismatch_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        raise HAApiError(f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise HAApiError("diagnostics payload missing data object")
    return data


def _engine_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
    return dict(engine) if isinstance(engine, dict) else {}


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
        _call_recompute(client)
        runtime_context = _engine_diagnostics(client, entry_id).get("runtime_context", {})
        last = dict(runtime_context) if isinstance(runtime_context, dict) else {}
        if not bool(last.get("runtime.recovery.active")):
            return
        time.sleep(poll_s)
    raise AssertionError(f"runtime recovery did not become inactive: {last}")


def _health_payload(client: HAClient) -> dict[str, Any]:
    return client.get_state("sensor.heima_health")


def _health_state(client: HAClient) -> str:
    return str(_health_payload(client).get("state") or "")


def _health_attrs(client: HAClient) -> dict[str, Any]:
    attrs = _health_payload(client).get("attributes")
    return dict(attrs) if isinstance(attrs, dict) else {}


def _unresolved_check_ids(client: HAClient, entry_id: str) -> set[str]:
    invariants = _engine_diagnostics(client, entry_id).get("invariants", {})
    raw = dict(invariants).get("unresolved_check_ids", []) if isinstance(invariants, dict) else []
    return {str(item) for item in raw if str(item)}


def _call_recompute(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def _wait_health(
    client: HAClient,
    entry_id: str,
    *,
    expected: str,
    check_unresolved: bool | None,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last_state = ""
    last_attrs: dict[str, Any] = {}
    last_unresolved: set[str] = set()
    while time.time() < deadline:
        _call_recompute(client)
        last_state = _health_state(client)
        last_attrs = _health_attrs(client)
        last_unresolved = _unresolved_check_ids(client, entry_id)
        unresolved_ok = (
            True if check_unresolved is None else (CHECK_ID in last_unresolved) is check_unresolved
        )
        if last_state == expected and unresolved_ok:
            return
        time.sleep(poll_s)
    raise AssertionError(
        f"timeout waiting health={expected!r} unresolved={check_unresolved}; "
        f"last_state={last_state!r} last_unresolved={sorted(last_unresolved)} "
        f"last_attrs={last_attrs}"
    )


def run(ha_url: str, ha_token: str, *, timeout_s: int, poll_s: float) -> None:
    helpers = _load_security_helpers()
    client = helpers.HAFlowClient(base_url=ha_url, token=ha_token, timeout_s=30)
    entry_id, _entry, security_cfg = helpers._resolve_entry_with_security(client, "")
    print(f"Using heima entry_id={entry_id}")
    security_cfg = helpers._ensure_security_configured_for_lab(
        client,
        entry_id=entry_id,
        security_cfg=security_cfg,
    )
    security_entity = str(security_cfg.get("security_state_entity") or "")
    armed_away_value = str(security_cfg.get("armed_away_value") or "armed_away")
    if not security_entity:
        raise AssertionError("security state entity is not configured")

    person_override_entity = helpers._first_person_override_entity(client)
    if not person_override_entity:
        raise AssertionError("no heima person override select found")

    original_security_state = None
    try:
        original_security_state = client.state_value(security_entity)
    except Exception:  # noqa: BLE001
        pass

    try:
        _wait_recovery_inactive(
            client,
            entry_id,
            timeout_s=timeout_s,
            poll_s=poll_s,
        )
        print("Scenario A: force security_presence_mismatch and wait for degraded health...")
        client.call_service(
            "select",
            "select_option",
            {"entity_id": person_override_entity, "option": "force_home"},
        )
        if not helpers._set_security_state(
            client,
            security_entity,
            armed_away_value,
            alarm_code=ALARM_CODE,
        ):
            raise AssertionError(f"unsupported security entity for live forcing: {security_entity}")
        _call_recompute(client)
        _wait_health(
            client,
            entry_id,
            expected="degraded",
            check_unresolved=True,
            timeout_s=timeout_s,
            poll_s=poll_s,
        )
        print("PASS scenario A")

        print("Scenario B: clear mismatch and wait for health ok...")
        client.call_service(
            "select",
            "select_option",
            {"entity_id": person_override_entity, "option": "force_away"},
        )
        helpers._set_security_state(
            client,
            security_entity,
            "disarmed",
            alarm_code=ALARM_CODE,
        )
        _call_recompute(client)
        _wait_health(
            client,
            entry_id,
            expected="ok",
            check_unresolved=False,
            timeout_s=timeout_s,
            poll_s=poll_s,
        )
        print("PASS scenario B")
    finally:
        try:
            client.call_service(
                "select",
                "select_option",
                {"entity_id": person_override_entity, "option": "auto"},
            )
        except Exception:  # noqa: BLE001
            pass
        if original_security_state:
            try:
                helpers._set_security_state(
                    client,
                    security_entity,
                    original_security_state,
                    alarm_code=ALARM_CODE,
                )
            except Exception:  # noqa: BLE001
                pass
        try:
            _call_recompute(client)
        except Exception:  # noqa: BLE001
            pass

    print("PASS: active health invariant clear live check passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--poll-s", type=float, default=2.0)
    args = parser.parse_args()
    run(args.ha_url, args.ha_token, timeout_s=args.timeout_s, poll_s=args.poll_s)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
