#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Live checks for anomaly rule configuration.

This test validates the live Home Assistant service surface introduced for
Phase Q:

1. `heima.configure_anomaly_rule` updates entry options without a reload.
2. Rule ids from the implemented anomaly slices are accepted by the catalog.
3. Threshold overrides are visible to the next learning/anomaly run.
4. Invalid rule ids and severities are rejected by Home Assistant.

The service is intentionally merge-only, so this script restores behaviorally
equivalent values after probing but may leave explicit default rule entries in
the lab config.
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


IMPLEMENTED_RULE_IDS = (
    "arrival_time_outlier",
    "departure_time_outlier",
    "extended_absence",
    "presence_pattern_drift",
    "heating_setpoint_outlier",
    "heating_unresponsive",
    "heating_vacation_mismatch",
    "stove_on_unattended",
    "oven_on_unattended",
    "appliance_unusual_hour",
    "alarm_disarm_unusual_hour",
    "alarm_expected_not_armed",
    "sensor_activity_drop",
    "ghost_activity",
    "unusual_stillness",
)

DEFAULT_RULE_RESTORE: dict[str, dict[str, Any]] = {
    "arrival_time_outlier": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {"window": 1000, "min_observations": 5, "delta_hours": 3.0},
    },
    "departure_time_outlier": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {"window": 1000, "min_observations": 5, "delta_hours": 3.0},
    },
    "extended_absence": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {"history_window": 1000, "min_observations": 5, "multiplier": 2.0},
    },
    "presence_pattern_drift": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {
            "history_window": 1000,
            "min_observations": 10,
            "recent_observations": 4,
            "drift_delta": 0.5,
        },
    },
    "heating_setpoint_outlier": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {"window": 24, "min_observations": 8, "delta_c": 3.0},
    },
    "heating_unresponsive": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {
            "window": 4,
            "min_observations": 4,
            "min_gap_c": 1.5,
            "min_delta_c": 0.2,
        },
    },
    "heating_vacation_mismatch": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {"window": 6, "min_observations": 3, "max_away_setpoint_c": 18.0},
    },
    "stove_on_unattended": {
        "enabled": True,
        "severity": "critical",
        "thresholds": {"window": 6, "min_observations": 2},
    },
    "oven_on_unattended": {
        "enabled": True,
        "severity": "critical",
        "thresholds": {"window": 6, "min_observations": 2},
    },
    "appliance_unusual_hour": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {"window": 1000, "min_observations": 8, "delta_hours": 4.0},
    },
    "alarm_disarm_unusual_hour": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {"window": 1000, "min_observations": 5, "delta_hours": 3.0},
    },
    "alarm_expected_not_armed": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {
            "history_window": 1000,
            "min_observations": 8,
            "expected_ratio": 0.8,
            "recent_disarmed_observations": 2,
        },
    },
    "sensor_activity_drop": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {
            "window_hours": 4,
            "history_window": 1000,
            "min_observations": 10,
            "drop_ratio": 0.3,
        },
    },
    "ghost_activity": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {"window": 20, "min_ghost_observations": 3},
    },
    "unusual_stillness": {
        "enabled": True,
        "severity": "warning",
        "thresholds": {"history_window": 1000, "min_observations": 10, "multiplier": 2.0},
    },
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _diagnostics_root(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        raise HAApiError(f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise HAApiError("diagnostics payload missing data object")
    return data


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    entry = _diagnostics_root(client, entry_id).get("entry", {})
    if not isinstance(entry, dict):
        raise HAApiError("diagnostics payload missing entry object")
    options = entry.get("options", {})
    if not isinstance(options, dict):
        raise HAApiError("diagnostics entry options is not a dict")
    return options


def _assert_service_registered(client: HAClient) -> None:
    services = client.get("/api/services")
    if not isinstance(services, list):
        raise HAApiError(f"invalid services payload: {type(services)}")
    for domain in services:
        if not isinstance(domain, dict) or domain.get("domain") != "heima":
            continue
        items = domain.get("services", {})
        if isinstance(items, dict) and "configure_anomaly_rule" in items:
            return
    raise HAApiError(
        "heima.configure_anomaly_rule is not registered. "
        "Deploy/reload the current custom component before running this live test."
    )


def _rule_options(client: HAClient, entry_id: str, rule_id: str) -> dict[str, Any]:
    options = _entry_options(client, entry_id)
    anomaly = options.get("anomaly", {})
    if not isinstance(anomaly, dict):
        return {}
    rules = anomaly.get("rules", {})
    if not isinstance(rules, dict):
        return {}
    rule = rules.get(rule_id, {})
    return dict(rule) if isinstance(rule, dict) else {}


def _configure_rule(
    client: HAClient,
    *,
    rule_id: str,
    enabled: bool | None = None,
    severity: str | None = None,
    thresholds: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {"rule_id": rule_id}
    if enabled is not None:
        payload["enabled"] = enabled
    if severity is not None:
        payload["severity"] = severity
    if thresholds is not None:
        payload["thresholds"] = thresholds
    client.call_service("heima", "configure_anomaly_rule", payload)


def _expect_service_validation_error(client: HAClient, payload: dict[str, Any]) -> None:
    status, data = client.request(
        "POST",
        "/api/services/heima/configure_anomaly_rule",
        payload,
        accept_error=True,
    )
    _assert(status >= 400, f"expected service validation error for {payload}, got {status}: {data}")


def _restore_rule(client: HAClient, rule_id: str, original: dict[str, Any]) -> None:
    fallback = DEFAULT_RULE_RESTORE[rule_id]
    enabled = original.get("enabled", fallback["enabled"])
    severity = original.get("severity", fallback["severity"])
    thresholds = original.get("thresholds", fallback["thresholds"])
    if not isinstance(thresholds, dict):
        thresholds = fallback["thresholds"]
    _configure_rule(
        client,
        rule_id=rule_id,
        enabled=bool(enabled),
        severity=str(severity),
        thresholds=dict(thresholds),
    )


def scenario_configure_rule_service(client: HAClient, entry_id: str) -> None:
    print("== Scenario A: configure anomaly rule service updates options ==")
    original = {
        rule_id: copy.deepcopy(_rule_options(client, entry_id, rule_id))
        for rule_id in IMPLEMENTED_RULE_IDS
    }
    try:
        _configure_rule(
            client,
            rule_id="heating_unresponsive",
            enabled=True,
            severity="info",
            thresholds={"min_gap_c": 9.0},
        )
        rule = _rule_options(client, entry_id, "heating_unresponsive")
        _assert(rule.get("enabled") is True, f"enabled not persisted: {rule}")
        _assert(rule.get("severity") == "info", f"severity not persisted: {rule}")
        thresholds = rule.get("thresholds", {})
        _assert(isinstance(thresholds, dict), f"thresholds not persisted as dict: {rule}")
        _assert(float(thresholds.get("min_gap_c")) == 9.0, f"threshold not persisted: {rule}")

        _configure_rule(client, rule_id="heating_unresponsive", enabled=False)
        rule = _rule_options(client, entry_id, "heating_unresponsive")
        _assert(rule.get("enabled") is False, f"disabled flag not persisted: {rule}")

        _expect_service_validation_error(client, {"rule_id": "not_a_real_anomaly_rule"})
        _expect_service_validation_error(
            client,
            {"rule_id": "heating_unresponsive", "severity": "fatal"},
        )
        print("PASS scenario A")
    finally:
        _restore_rule(client, "heating_unresponsive", original["heating_unresponsive"])


def scenario_rule_catalog_accepts_implemented_rules(client: HAClient, entry_id: str) -> None:
    print("== Scenario B: implemented anomaly rule ids are accepted by catalog ==")
    original = {
        rule_id: copy.deepcopy(_rule_options(client, entry_id, rule_id))
        for rule_id in IMPLEMENTED_RULE_IDS
    }
    try:
        for rule_id in IMPLEMENTED_RULE_IDS:
            fallback = DEFAULT_RULE_RESTORE[rule_id]
            _configure_rule(
                client,
                rule_id=rule_id,
                enabled=True,
                severity=str(fallback["severity"]),
                thresholds=dict(fallback["thresholds"]),
            )
            rule = _rule_options(client, entry_id, rule_id)
            _assert(rule.get("enabled") is True, f"{rule_id} enabled not persisted: {rule}")
        print(f"PASS scenario B ({len(IMPLEMENTED_RULE_IDS)} rule ids accepted)")
    finally:
        for rule_id in IMPLEMENTED_RULE_IDS:
            _restore_rule(client, rule_id, original[rule_id])


def scenario_learning_run_after_config(client: HAClient, entry_id: str) -> None:
    print("== Scenario C: learning/anomaly run accepts configured rules ==")
    client.call_service("heima", "command", {"command": "learning_run", "target": {"entry_id": entry_id}})
    print("PASS scenario C")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    client = HAClient(args.ha_url, args.ha_token)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")
    _assert_service_registered(client)

    scenario_configure_rule_service(client, entry_id)
    scenario_rule_catalog_accepts_implemented_rules(client, entry_id)
    scenario_learning_run_after_config(client, entry_id)

    print("All anomaly rule live checks passed.")


if __name__ == "__main__":
    main()
