#!/usr/bin/env python3
"""Read-only live diagnostics for proposal/reaction lifecycle state.

This probe does not reset learning state and does not approve, reject, or run
proposals. It validates that Phase AD lifecycle monitoring is observable from
the public config-entry diagnostics surface.
"""

# ruff: noqa: I001

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


LIFECYCLE_SUGGESTION_TYPE = "proposal_lifecycle_suggestion"
HOUSE_STATE_PROPOSAL_TYPE = "house_state_learned_context"
LINK_STATES = {
    "linked_clean",
    "linked_user_baseline",
    "linked_uninterpretable",
    "reaction_missing",
}
SUGGESTION_KINDS = {
    "replacement_suggestion",
    "retirement_suggestion",
    "maintenance_suggestion",
}
RECORD_REQUIRED_FIELDS = {
    "proposal_id",
    "identity_key",
    "plugin_family",
    "proposal_type",
    "accepted_at",
    "linked_reaction_id",
    "linked_reaction_type",
    "reaction_link_state",
    "reaction_link_state_reason",
    "lifecycle_generation",
    "monitoring_window_start",
    "confirmed_count",
    "outcome_contradiction_count",
    "context_miss_count",
    "unknown_transient_count",
    "dependency_unavailable_count",
    "evaluated_window_count",
    "replacement_candidate_state",
    "replacement_candidate_count",
    "lifecycle_review_kind",
    "last_lifecycle_review_at",
    "replaced_by",
    "retired_at",
    "policy",
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


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    _assert(isinstance(runtime, dict), "diagnostics runtime must be a dict")
    proposals = runtime.get("proposals", {})
    _assert(isinstance(proposals, dict), "runtime.proposals must be a dict")
    return proposals


def _as_int(value: Any, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise AssertionError(f"{field} must be an integer-compatible value: {value!r}") from exc
    _assert(result >= 0, f"{field} must be non-negative")
    return result


def _assert_lifecycle_root(proposals_diag: dict[str, Any]) -> dict[str, Any]:
    lifecycle = proposals_diag.get("lifecycle_monitoring")
    _assert(isinstance(lifecycle, dict), "missing proposals.lifecycle_monitoring diagnostics")
    _assert(lifecycle.get("enabled") is True, "lifecycle monitoring diagnostics must be enabled")
    _assert(str(lifecycle.get("storage_key") or ""), "lifecycle diagnostics missing storage_key")
    _assert(isinstance(lifecycle.get("loaded"), bool), "lifecycle loaded flag must be boolean")
    _as_int(lifecycle.get("load_errors", 0), field="lifecycle.load_errors")

    records = lifecycle.get("records")
    _assert(isinstance(records, list), "lifecycle records must be a list")
    record_count = _as_int(lifecycle.get("record_count", len(records)), field="record_count")
    _assert(record_count == len(records), "lifecycle record_count does not match records length")
    return lifecycle


def _assert_lifecycle_records(lifecycle: dict[str, Any]) -> None:
    records = [item for item in lifecycle.get("records", []) if isinstance(item, dict)]
    for record in records:
        missing = sorted(RECORD_REQUIRED_FIELDS - set(record))
        _assert(not missing, f"lifecycle record missing required fields: {missing}")
        _assert(str(record.get("proposal_id") or ""), "lifecycle record missing proposal_id")
        _assert(str(record.get("identity_key") or ""), "lifecycle record missing identity_key")
        _assert(str(record.get("accepted_at") or ""), "lifecycle record missing accepted_at")
        _assert(
            str(record.get("reaction_link_state") or "") in LINK_STATES,
            f"unexpected reaction_link_state: {record.get('reaction_link_state')!r}",
        )
        _assert(
            not (str(record.get("replaced_by") or "") and str(record.get("retired_at") or "")),
            f"record {record.get('proposal_id')} cannot be both replaced and retired",
        )
        review_kind = str(record.get("lifecycle_review_kind") or "")
        _assert(
            not review_kind or review_kind in SUGGESTION_KINDS,
            f"unexpected lifecycle_review_kind: {review_kind!r}",
        )
        policy = record.get("policy")
        _assert(isinstance(policy, dict), "lifecycle record policy must be a dict")
        for field in (
            "required_observations",
            "replacement_threshold",
            "retirement_threshold",
            "maintenance_threshold",
            "rolling_window_limit",
        ):
            _as_int(policy.get(field), field=f"policy.{field}")
        for field in (
            "confirmed_count",
            "outcome_contradiction_count",
            "context_miss_count",
            "unknown_transient_count",
            "dependency_unavailable_count",
            "evaluated_window_count",
            "replacement_candidate_count",
        ):
            _as_int(record.get(field), field=field)


def _assert_lifecycle_suggestions(proposals_diag: dict[str, Any]) -> list[dict[str, Any]]:
    raw = proposals_diag.get("proposals")
    _assert(isinstance(raw, list), "proposals diagnostics must expose proposal rows")
    rows = [item for item in raw if isinstance(item, dict)]
    suggestions = [
        row
        for row in rows
        if str(row.get("type") or "") == LIFECYCLE_SUGGESTION_TYPE
        or str(row.get("followup_kind") or "") in SUGGESTION_KINDS
    ]
    for suggestion in suggestions:
        kind = str(suggestion.get("followup_kind") or "")
        _assert(kind in SUGGESTION_KINDS, f"unexpected lifecycle suggestion kind: {kind!r}")
        _assert(
            str(suggestion.get("type") or "") == LIFECYCLE_SUGGESTION_TYPE,
            f"lifecycle suggestion {suggestion.get('id')} has wrong type",
        )
        _assert(str(suggestion.get("id") or ""), "lifecycle suggestion missing id")
        _assert(
            str(suggestion.get("status") or "") in {"pending", "accepted", "rejected"},
            f"unexpected lifecycle suggestion status: {suggestion.get('status')!r}",
        )
        _assert(
            str(suggestion.get("target_reaction_id") or ""),
            f"lifecycle suggestion {suggestion.get('id')} missing target_reaction_id",
        )
        _assert(
            str(suggestion.get("description") or ""),
            f"lifecycle suggestion {suggestion.get('id')} missing description",
        )
    return suggestions


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima proposal lifecycle diagnostics")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    proposals_diag = _proposal_diagnostics(client, entry_id)

    lifecycle = _assert_lifecycle_root(proposals_diag)
    _assert_lifecycle_records(lifecycle)
    suggestions = _assert_lifecycle_suggestions(proposals_diag)

    records = lifecycle.get("records") or []
    house_state_records = [
        record
        for record in records
        if isinstance(record, dict)
        and str(record.get("proposal_type") or "") == HOUSE_STATE_PROPOSAL_TYPE
    ]

    print(f"lifecycle_records={len(records)}")
    print(f"house_state_lifecycle_records={len(house_state_records)}")
    print(f"lifecycle_suggestions={len(suggestions)}")
    print("PASS: proposal lifecycle diagnostics are coherent")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
