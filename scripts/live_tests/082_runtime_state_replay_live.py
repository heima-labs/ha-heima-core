#!/usr/bin/env python3
"""Live replay check for stale Heima runtime state."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.ha_client import HAApiError, HAClient

from scripts.runtime_state_replay import ReplayFinding, validate_payload


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        raise HAApiError(f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise HAApiError("diagnostics payload missing data object")
    return data


def _health_state_payload(client: HAClient) -> dict[str, Any]:
    state = client.get_state("sensor.heima_health")
    if not isinstance(state, dict):
        raise HAApiError("sensor.heima_health payload is not a dict")
    return state


def _print_findings(findings: list[ReplayFinding]) -> None:
    for finding in findings:
        print(f"{finding.severity.upper()} {finding.code}: {finding.message}")


def run(ha_url: str, ha_token: str) -> None:
    client = HAClient(base_url=ha_url, token=ha_token, timeout_s=30)
    entry_id = client.find_heima_entry_id()
    diagnostics = _diagnostics_data(client, entry_id)
    health = _health_state_payload(client)
    entity_states = _entity_states_payload(client)
    combined = _combined_health_runtime_payload(health, diagnostics, entity_states)

    findings = [
        *validate_payload(diagnostics, source=f"diagnostics:{entry_id}"),
        *validate_payload(health, source="sensor.heima_health"),
        *validate_payload(combined, source="combined:sensor.heima_health+diagnostics"),
    ]
    _print_findings(findings)

    errors = [item for item in findings if item.severity == "error"]
    if errors:
        raise AssertionError(f"stale runtime state replay found {len(errors)} error(s)")

    print("PASS: live runtime-state replay found no stale-state errors")


def _combined_health_runtime_payload(
    health_state: dict[str, Any],
    diagnostics: dict[str, Any],
    entity_states: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    attrs = health_state.get("attributes")
    health = dict(attrs) if isinstance(attrs, dict) else {}
    health["status"] = str(health_state.get("state") or "")
    if "health_reason" in health:
        health["reason"] = str(health.get("health_reason") or "")
    runtime = diagnostics.get("runtime")
    return {
        "entry": dict(diagnostics.get("entry")) if isinstance(diagnostics.get("entry"), dict) else {},
        "health": health,
        "runtime": dict(runtime) if isinstance(runtime, dict) else {},
        "entity_states": dict(entity_states or {}),
    }


def _entity_states_payload(client: HAClient) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for state in client.all_states():
        entity_id = str(state.get("entity_id") or "").strip()
        if entity_id:
            rows[entity_id] = state
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()
    run(args.ha_url, args.ha_token)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
