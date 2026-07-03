#!/usr/bin/env python3
"""Read-only audit for Heima proposal backlog grouping and duplication."""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ha_client import HAClient


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _value(item: dict[str, Any], key: str, default: str = "") -> str:
    return str(item.get(key) or default)


def _print_header(title: str) -> None:
    print(f"\n== {title} ==")


def _print_counter(counter: Counter[str], *, limit: int | None = None) -> None:
    rows = counter.most_common(limit)
    if not rows:
        print("-")
        return
    for key, total in rows:
        print(f"{total:4d}  {key}")


def _proposal_label(proposal: dict[str, Any]) -> str:
    identity = _value(proposal, "identity_key") or _value(proposal, "id")
    description = _value(proposal, "description").strip()
    confidence = proposal.get("confidence")
    kind = _value(proposal, "followup_kind", "unknown")
    stale = " stale" if bool(proposal.get("is_stale")) else ""
    if description:
        return f"{identity} | {kind} | conf={confidence}{stale} | {description}"
    return f"{identity} | {kind} | conf={confidence}{stale}"


def _review_row_label(row: dict[str, Any]) -> str:
    row_type = _value(row, "row_type", "unknown")
    if row_type == "temporal_bundle":
        weekday = row.get("weekday")
        start_hour = row.get("start_hour_bucket")
        end_hour = row.get("end_hour_bucket")
        state = _value(row, "predicted_state", "unknown")
        member_count = row.get("member_count")
        confidence = row.get("confidence_avg")
        support = row.get("support_total")
        return (
            f"bundle {weekday=} {start_hour=}-{end_hour=} state={state} "
            f"members={member_count} avg_conf={confidence} support={support}"
        )
    proposal_id = _value(row, "proposal_id") or _value(row, "id")
    proposal_type = _value(row, "type", "unknown")
    confidence = row.get("confidence")
    return f"proposal {proposal_id} type={proposal_type} conf={confidence}"


def _proposal_context_signature(proposal: dict[str, Any]) -> str:
    context = _as_dict(proposal.get("context_snapshot"))
    config = _as_dict(proposal.get("config_summary"))
    fields = {
        "type": _value(proposal, "type", "unknown"),
        "room": _value(config, "room_id") or _value(context, "room_id"),
        "weekday": str(config.get("weekday") or context.get("weekday") or ""),
        "hour_bucket": str(config.get("hour_bucket") or context.get("hour_bucket") or ""),
        "house_state": (
            _value(config, "house_state")
            or _value(context, "house_state")
            or _value(context, "predicted_state")
        ),
        "followup": _value(proposal, "followup_kind", "unknown"),
    }
    return "|".join(f"{key}={value}" for key, value in fields.items() if value)


def _load_proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    data = _as_dict(_as_dict(raw).get("data"))
    runtime = _as_dict(data.get("runtime"))
    proposals = _as_dict(runtime.get("proposals"))
    if not proposals:
        proposals = _as_dict(data.get("proposals"))
    if not proposals:
        proposals = _as_dict(runtime.get("proposal_engine"))
    if not proposals:
        runtime_data = _as_dict(runtime.get("data"))
        proposals = _as_dict(runtime_data.get("proposal_engine"))
    return proposals


def _sensor_proposal_diagnostics(client: HAClient) -> dict[str, Any]:
    try:
        state = client.get_state("sensor.heima_reaction_proposals")
    except Exception:  # noqa: BLE001
        return {}
    attrs = _as_dict(state.get("attributes"))
    items = _as_dict(attrs.get("items"))
    proposals: list[dict[str, Any]] = []
    for proposal_id, raw in items.items():
        item = _as_dict(raw)
        if not item:
            continue
        proposals.append(
            {
                "id": str(proposal_id),
                "proposal_id": str(proposal_id),
                "type": item.get("type"),
                "confidence": item.get("confidence"),
                "origin": item.get("origin"),
                "followup_kind": item.get("followup_kind"),
                "status": item.get("status"),
                "updated_at": item.get("updated_at"),
                "target_reaction_id": item.get("target_reaction_id"),
                "target_reaction_type": item.get("target_reaction_type"),
                "improves_reaction_type": item.get("improves_reaction_type"),
                "improvement_reason": item.get("improvement_reason"),
                "context_snapshot": item.get("context_snapshot"),
                "is_stale": item.get("is_stale"),
            }
        )
    return {
        "total": attrs.get("total"),
        "pending": attrs.get("pending"),
        "suppressed_in_review_count": attrs.get("suppressed_in_review_count"),
        "pending_stale": None,
        "proposals": proposals,
        "_source": "sensor.heima_reaction_proposals",
        "_sensor_pending_items_total": attrs.get("pending_items_total"),
        "_sensor_pending_items_included": attrs.get("pending_items_included"),
        "_sensor_pending_items_truncated": attrs.get("pending_items_truncated"),
    }


def run(ha_url: str, ha_token: str, *, limit: int) -> None:
    client = HAClient(base_url=ha_url, token=ha_token, timeout_s=30)
    entry_id = client.find_heima_entry_id()
    diag = _load_proposal_diagnostics(client, entry_id)
    if not _as_list(diag.get("proposals")):
        sensor_diag = _sensor_proposal_diagnostics(client)
        if _as_list(sensor_diag.get("proposals")):
            diag = sensor_diag
    proposals = [_as_dict(item) for item in _as_list(diag.get("proposals")) if item]

    pending_all = [item for item in proposals if _value(item, "status") == "pending"]
    pending_visible = [
        item for item in pending_all if not bool(item.get("suppressed_by_review_group"))
    ]
    pending_suppressed = [
        item for item in pending_all if bool(item.get("suppressed_by_review_group"))
    ]
    accepted = [item for item in proposals if _value(item, "status") == "accepted"]
    rejected = [item for item in proposals if _value(item, "status") == "rejected"]

    _print_header("Proposal Backlog Summary")
    print(f"entry_id: {entry_id}")
    if diag.get("_source"):
        print(f"source: {diag.get('_source')}")
        print(f"sensor_pending_items_total: {diag.get('_sensor_pending_items_total')}")
        print(f"sensor_pending_items_included: {diag.get('_sensor_pending_items_included')}")
        print(f"sensor_pending_items_truncated: {diag.get('_sensor_pending_items_truncated')}")
    print(f"stored_total_reported: {diag.get('total')}")
    print(f"stored_total_in_diagnostics: {len(proposals)}")
    print(f"accepted: {len(accepted)}")
    print(f"rejected: {len(rejected)}")
    print(f"pending_all_in_diagnostics: {len(pending_all)}")
    print(f"pending_visible_reported: {diag.get('pending')}")
    print(f"pending_visible_computed: {len(pending_visible)}")
    print(f"pending_suppressed_by_review_group: {len(pending_suppressed)}")
    print(f"suppressed_in_review_count: {diag.get('suppressed_in_review_count')}")
    review_rows = [_as_dict(item) for item in _as_list(diag.get("review_rows")) if item]
    temporal_bundles = [
        _as_dict(item) for item in _as_list(diag.get("temporal_bundles")) if item
    ]
    print(f"review_row_count_reported: {diag.get('review_row_count')}")
    print(f"review_row_count_computed: {len(review_rows) if review_rows else None}")
    print(
        "reviewable_after_temporal_bundles: "
        f"{len(review_rows) if review_rows else len(pending_visible)}"
    )
    print(f"temporal_bundle_count_reported: {diag.get('temporal_bundle_count')}")
    print(f"temporal_bundle_count_computed: {len(temporal_bundles)}")
    print(f"temporal_bundle_member_count: {diag.get('temporal_bundle_member_count')}")
    print(f"pending_stale: {diag.get('pending_stale')}")

    _print_header("Pending By Type")
    _print_counter(Counter(_value(item, "type", "unknown") for item in pending_all))

    _print_header("Visible Pending By Type")
    _print_counter(Counter(_value(item, "type", "unknown") for item in pending_visible))

    _print_header("Suppressed Pending By Type")
    _print_counter(Counter(_value(item, "type", "unknown") for item in pending_suppressed))

    _print_header("Pending By Followup Kind")
    _print_counter(Counter(_value(item, "followup_kind", "unknown") for item in pending_all))

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for proposal in pending_all:
        group_key = _value(proposal, "review_group_key")
        if group_key:
            groups[group_key].append(proposal)

    _print_header("Top Review Groups")
    if not groups:
        print("-")
    for group_key, items in sorted(groups.items(), key=lambda row: len(row[1]), reverse=True)[
        :limit
    ]:
        visible = [item for item in items if not bool(item.get("suppressed_by_review_group"))]
        suppressed = [item for item in items if bool(item.get("suppressed_by_review_group"))]
        type_counts = Counter(_value(item, "type", "unknown") for item in items)
        print(
            f"{len(items):4d} total | {len(visible):2d} visible | "
            f"{len(suppressed):2d} suppressed | {group_key}"
        )
        print(f"     types: {dict(type_counts)}")
        for proposal in visible[:3]:
            print(f"     visible: {_proposal_label(proposal)}")

    _print_header("Top Temporal Review Bundles")
    if not temporal_bundles:
        print("-")
    for bundle in sorted(
        temporal_bundles,
        key=lambda item: (
            -int(item.get("member_count") or 0),
            int(item.get("weekday") or 0),
            int(item.get("start_hour_bucket") or 0),
            _value(item, "predicted_state"),
        ),
    )[:limit]:
        proposal_ids = _as_list(bundle.get("proposal_ids"))
        identity_keys = _as_list(bundle.get("identity_keys"))
        print(
            f"{int(bundle.get('member_count') or 0):4d} members | "
            f"weekday={bundle.get('weekday')} | "
            f"hours={bundle.get('start_hour_bucket')}-{bundle.get('end_hour_bucket')} | "
            f"anyone_home={bundle.get('anyone_home')} | "
            f"state={_value(bundle, 'predicted_state', 'unknown')} | "
            f"avg_conf={bundle.get('confidence_avg')} | "
            f"support={bundle.get('support_total')}"
        )
        for identity_key in identity_keys[:3]:
            print(f"     identity: {identity_key}")
        if len(proposal_ids) > 3:
            print(f"     ... {len(proposal_ids) - 3} more member(s)")

    ungrouped = [item for item in pending_all if not _value(item, "review_group_key")]
    _print_header("Ungrouped Pending By Type")
    _print_counter(Counter(_value(item, "type", "unknown") for item in ungrouped))

    _print_header("Top Ungrouped Similarity Buckets")
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for proposal in ungrouped:
        buckets[_proposal_context_signature(proposal)].append(proposal)
    repeated = [(key, items) for key, items in buckets.items() if len(items) > 1]
    if not repeated:
        print("-")
    for bucket_key, items in sorted(repeated, key=lambda row: len(row[1]), reverse=True)[:limit]:
        type_counts = Counter(_value(item, "type", "unknown") for item in items)
        print(f"{len(items):4d} total | {bucket_key}")
        print(f"     types: {dict(type_counts)}")
        for proposal in sorted(
            items,
            key=lambda item: float(item.get("confidence") or 0.0),
            reverse=True,
        )[:3]:
            print(f"     example: {_proposal_label(proposal)}")

    _print_header("Visible Pending Examples")
    for proposal in pending_visible[:limit]:
        print(f"- type={_value(proposal, 'type', 'unknown')} | {_proposal_label(proposal)}")

    _print_header("Review Row Examples")
    if not review_rows:
        print("-")
    for row in review_rows[:limit]:
        print(f"- {_review_row_label(row)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    run(args.ha_url, args.ha_token, limit=max(1, int(args.limit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
