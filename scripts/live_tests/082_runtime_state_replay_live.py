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

    findings = [
        *validate_payload(diagnostics, source=f"diagnostics:{entry_id}"),
        *validate_payload(health, source="sensor.heima_health"),
    ]
    _print_findings(findings)

    errors = [item for item in findings if item.severity == "error"]
    if errors:
        raise AssertionError(f"stale runtime state replay found {len(errors)} error(s)")

    print("PASS: live runtime-state replay found no stale-state errors")


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
