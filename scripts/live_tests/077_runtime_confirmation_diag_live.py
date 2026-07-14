#!/usr/bin/env python3
"""Read-only live diagnostics for runtime confirmation observability."""

# ruff: noqa: I001

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


REQUIRED_ROOT_FIELDS = {
    "pending",
    "recent_completed",
    "stale_responses",
    "duplicate_occurrences",
    "completed_by_status",
    "pending_requests",
    "recent_completed_requests",
    "completed_step_counts",
    "completed_blocked_reasons",
    "completed_failed_reasons",
    "completed_skipped_reasons",
    "failed_request_reasons",
    "scheduled_timeouts",
    "action_event_subscription_active",
    "persisted",
}

REQUIRED_STEP_COUNT_FIELDS = {"applied", "blocked", "failed", "skipped"}
REQUIRED_PERSISTED_FIELDS = {
    "confirmation_stats_total",
    "promotion_reviews_total",
    "promotion_review_status_counts",
    "by_reaction",
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    _assert(isinstance(raw, dict), f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    _assert(isinstance(data, dict), "diagnostics payload missing data object")
    return data


def _runtime_confirmation(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    _assert(isinstance(runtime, dict), "diagnostics runtime must be a dict")
    confirmation = runtime.get("runtime_confirmation", {})
    _assert(isinstance(confirmation, dict), "runtime.runtime_confirmation must be a dict")
    return confirmation


def _as_non_negative_int(value: Any, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise AssertionError(f"{field} must be integer-compatible: {value!r}") from exc
    _assert(result >= 0, f"{field} must be non-negative")
    return result


def _assert_count_mapping(value: Any, *, field: str) -> None:
    _assert(isinstance(value, dict), f"{field} must be a dict")
    for key, count in value.items():
        _assert(str(key or ""), f"{field} contains an empty key")
        _as_non_negative_int(count, field=f"{field}.{key}")


def _assert_request_rows(rows: Any, *, field: str) -> None:
    _assert(isinstance(rows, list), f"{field} must be a list")
    for row in rows:
        _assert(isinstance(row, dict), f"{field} rows must be dicts")
        for required in (
            "request_id",
            "reaction_id",
            "reaction_type",
            "occurrence_key",
            "status",
            "created_at",
            "expires_at",
            "on_timeout",
            "apply_steps",
        ):
            _assert(required in row, f"{field} row missing {required}")
        _assert(isinstance(row.get("apply_steps"), list), f"{field}.apply_steps must be a list")
        apply_result = row.get("apply_result")
        _assert(
            apply_result is None or isinstance(apply_result, dict),
            f"{field}.apply_result must be null or dict",
        )


def _assert_persisted(persisted: Any) -> None:
    _assert(isinstance(persisted, dict), "runtime_confirmation.persisted must be a dict")
    missing = sorted(REQUIRED_PERSISTED_FIELDS - set(persisted))
    _assert(not missing, f"persisted diagnostics missing fields: {missing}")
    _as_non_negative_int(
        persisted.get("confirmation_stats_total"),
        field="persisted.confirmation_stats_total",
    )
    _as_non_negative_int(
        persisted.get("promotion_reviews_total"),
        field="persisted.promotion_reviews_total",
    )
    _assert_count_mapping(
        persisted.get("promotion_review_status_counts"),
        field="persisted.promotion_review_status_counts",
    )
    by_reaction = persisted.get("by_reaction")
    _assert(isinstance(by_reaction, dict), "persisted.by_reaction must be a dict")
    for reaction_id, row in by_reaction.items():
        _assert(str(reaction_id or ""), "persisted.by_reaction contains an empty reaction id")
        _assert(isinstance(row, dict), "persisted.by_reaction rows must be dicts")
        _assert("confirmation_stats" in row, f"{reaction_id} missing confirmation_stats")
        _assert("promotion_review" in row, f"{reaction_id} missing promotion_review")
        _assert("promotion_eligibility" in row, f"{reaction_id} missing promotion_eligibility")


def _assert_runtime_confirmation(confirmation: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_ROOT_FIELDS - set(confirmation))
    _assert(not missing, f"runtime_confirmation diagnostics missing fields: {missing}")
    for field in ("pending", "recent_completed", "stale_responses", "duplicate_occurrences"):
        _as_non_negative_int(confirmation.get(field), field=field)

    _assert_count_mapping(confirmation.get("completed_by_status"), field="completed_by_status")
    step_counts = confirmation.get("completed_step_counts")
    _assert(isinstance(step_counts, dict), "completed_step_counts must be a dict")
    missing_step_counts = sorted(REQUIRED_STEP_COUNT_FIELDS - set(step_counts))
    _assert(not missing_step_counts, f"completed_step_counts missing {missing_step_counts}")
    for field in REQUIRED_STEP_COUNT_FIELDS:
        _as_non_negative_int(step_counts.get(field), field=f"completed_step_counts.{field}")

    _assert_count_mapping(
        confirmation.get("completed_blocked_reasons"),
        field="completed_blocked_reasons",
    )
    _assert_count_mapping(
        confirmation.get("completed_failed_reasons"),
        field="completed_failed_reasons",
    )
    _assert_count_mapping(
        confirmation.get("completed_skipped_reasons"),
        field="completed_skipped_reasons",
    )
    _assert_count_mapping(confirmation.get("failed_request_reasons"), field="failed_request_reasons")
    _assert_request_rows(confirmation.get("pending_requests"), field="pending_requests")
    _assert_request_rows(
        confirmation.get("recent_completed_requests"),
        field="recent_completed_requests",
    )
    _assert(
        isinstance(confirmation.get("scheduled_timeouts"), list),
        "scheduled_timeouts must be a list",
    )
    _assert(
        isinstance(confirmation.get("action_event_subscription_active"), bool),
        "action_event_subscription_active must be a bool",
    )
    _assert_persisted(confirmation.get("persisted"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima runtime confirmation diagnostics")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    confirmation = _runtime_confirmation(client, entry_id)
    _assert_runtime_confirmation(confirmation)

    print(f"pending_runtime_requests={confirmation.get('pending')}")
    print(f"recent_completed_runtime_requests={confirmation.get('recent_completed')}")
    print(
        "promotion_reviews="
        f"{confirmation.get('persisted', {}).get('promotion_reviews_total', 0)}"
    )
    print("PASS: runtime confirmation diagnostics are coherent")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
