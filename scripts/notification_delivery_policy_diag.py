#!/usr/bin/env python3
"""Simulate Heima Notification Delivery Policy decisions without sending push."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from lib.ha_client import HAClient

from custom_components.heima.const import DEFAULT_ENABLED_EVENT_CATEGORIES, EVENT_CATEGORIES_ALL
from custom_components.heima.runtime.contracts import HeimaEvent
from custom_components.heima.runtime.notifications import NotificationDeliveryPolicy


def _event_cases() -> list[HeimaEvent]:
    return [
        HeimaEvent(
            type="reaction.fired",
            key="reaction.fired.diagnostic",
            severity="info",
            title="Reaction fired",
            message="Reaction produced 1 step.",
            context={"reaction_label": "Diagnostic reaction"},
        ),
        HeimaEvent(
            type="people.arrive",
            key="people.arrive.diagnostic",
            severity="info",
            title="Person arrived",
            message="Person arrived.",
            context={"display_name": "Diagnostic person"},
        ),
        HeimaEvent(
            type="system.config_invalid",
            key="system.config_invalid.diagnostic",
            severity="warn",
            title="Heima configuration issue",
            message="Configuration issue detected.",
        ),
        HeimaEvent(
            type="security.alarm_triggered",
            key="security.alarm_triggered.diagnostic",
            severity="critical",
            title="Alarm triggered",
            message="Alarm triggered.",
        ),
        HeimaEvent(
            type="security.armed_away_but_home",
            key="security.armed_away_but_home.diagnostic",
            severity="warn",
            title="Security inconsistency",
            message="Security is armed away while someone is home.",
            context={"security_state": "armed_away", "people_home_list": ["diagnostic"]},
        ),
        HeimaEvent(
            type="occupancy.inconsistency",
            key="occupancy.inconsistency.diagnostic",
            severity="warn",
            title="Occupancy inconsistency",
            message="Presence says someone is home, but no room is currently occupied.",
        ),
    ]


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    entry = client.get_entry(entry_id)
    options = entry.get("options")
    return dict(options) if isinstance(options, dict) else {}


def _decision_row(decision: Any) -> dict[str, Any]:
    return {
        "outcome": decision.outcome,
        "reason": decision.reason,
        "event_family": decision.event_family,
        "push_policy": decision.push_policy,
        "target_roles": list(decision.target_roles),
        "route_targets": list(decision.route_targets),
        "security_critical": decision.security_critical,
    }


def _category_enabled(event: HeimaEvent, notifications: dict[str, Any]) -> bool:
    category = str(event.type or "").split(".", 1)[0] or "system"
    if category == "system" or category not in set(EVENT_CATEGORIES_ALL):
        return True
    raw = notifications.get("enabled_event_categories")
    if raw is None:
        enabled = set(DEFAULT_ENABLED_EVENT_CATEGORIES) | {"system"}
    else:
        enabled = {str(value) for value in list(raw) if str(value)}
        enabled.add("system")
    return category in enabled


def _assert_expected(rows: dict[str, dict[str, Any]], notifications: dict[str, Any]) -> None:
    failures: list[str] = []
    if rows["reaction.fired"]["outcome"] not in {"observability_only", "suppressed_category"}:
        failures.append("reaction.fired should not push by default")
    if _category_enabled(_event_by_type("people.arrive"), notifications):
        if rows["people.arrive"]["outcome"] != "observability_only":
            failures.append("people.arrive should be observability-only by default")
    elif rows["people.arrive"]["outcome"] != "suppressed_category":
        failures.append(
            "people.arrive should be category-suppressed when people events are disabled"
        )
    if rows["system.config_invalid"]["push_policy"] != "admins":
        failures.append("system.config_invalid should be admin-facing by default")
    if rows["security.alarm_triggered"]["push_policy"] != "residents_and_admins":
        failures.append("alarm triggered should target residents and admins")
    if rows["security.armed_away_but_home"]["push_policy"] != "residents_and_admins":
        failures.append("armed-away while home should target residents and admins")
    if rows["occupancy.inconsistency"]["outcome"] != "waiting_persistence":
        failures.append("occupancy mismatch should wait for persistence before push")
    if failures:
        raise AssertionError("; ".join(failures))


def _event_by_type(event_type: str) -> HeimaEvent:
    for event in _event_cases():
        if event.type == event_type:
            return event
    raise KeyError(event_type)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--entry-id", default="")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--no-assert", action="store_true", help="Do not fail on expected checks")
    parser.add_argument(
        "--include-startup-grace",
        action="store_true",
        help="Evaluate with the configured startup grace instead of steady-state behavior",
    )
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = args.entry_id or client.find_heima_entry_id()
    notifications = dict(_entry_options(client, entry_id).get("notifications") or {})
    if not args.include_startup_grace:
        notifications["startup_notification_grace_s"] = 0
    policy = NotificationDeliveryPolicy()
    rows = {
        event.type: _decision_row(
            policy.decide(
                event,
                notifications,
                category_enabled=_category_enabled(event, notifications),
            )
        )
        for event in _event_cases()
    }
    if not args.no_assert:
        _assert_expected(rows, notifications)
    output = {"entry_id": entry_id, "decisions": rows}
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(f"entry_id: {entry_id}")
        for event_type, row in rows.items():
            print(
                f"{event_type}: outcome={row['outcome']} reason={row['reason']} "
                f"policy={row['push_policy']} targets={row['route_targets']}"
            )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
