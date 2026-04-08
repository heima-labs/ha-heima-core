#!/usr/bin/env python3
"""Operational audit summary for Heima."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ha_client import HAClient


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _print_header(title: str) -> None:
    print(f"\n== {title} ==")


def _join_map(data: dict[str, Any]) -> str:
    if not data:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in sorted(data.items()))


def _warning_if(condition: bool, message: str, warnings: list[str]) -> None:
    if condition:
        warnings.append(message)


def _add_issue(condition: bool, severity: str, message: str, issues: list[tuple[str, str]]) -> None:
    if condition:
        issues.append((severity, message))


def _severity_rank(severity: str) -> int:
    return {"info": 1, "warning": 2, "critical": 3}.get(severity, 0)


def _audit_verdict(issues: list[tuple[str, str]]) -> str:
    highest = max((_severity_rank(severity) for severity, _ in issues), default=0)
    if highest >= 3:
        return "degraded"
    if highest >= 2:
        return "attention_needed"
    return "healthy"


def _top_pending_examples(families: dict[str, Any]) -> list[str]:
    examples: list[tuple[float, str]] = []
    for family_name, raw in families.items():
        item = _as_dict(raw)
        for example in _as_list(item.get("top_examples")):
            example_dict = _as_dict(example)
            if str(example_dict.get("status") or "") != "pending":
                continue
            confidence = float(example_dict.get("confidence", 0.0) or 0.0)
            label = (
                f"{family_name}: "
                f"{example_dict.get('type') or '-'} "
                f"({confidence:.2f}) "
                f"{str(example_dict.get('description') or '').strip()}"
            )
            examples.append((confidence, label))
    examples.sort(key=lambda item: item[0], reverse=True)
    return [label for _, label in examples[:3]]


def _build_snapshot(
    *,
    entry_id: str,
    verdict: str,
    snapshot: dict[str, Any],
    house_state: dict[str, Any],
    learning: dict[str, Any],
    reactions: dict[str, Any],
    security_presence: dict[str, Any],
    camera_evidence: dict[str, Any],
    config_issues: int,
    event_total: int,
    emitted_total: int,
    dropped_total: int,
    active_family_total: int,
    pending_total: int,
    stale_pending: int,
    pending_family_names: list[str],
    top_pending: list[str],
    configured_reaction_total: int,
    learned_reaction_total: int,
    breach_candidate_total: int,
    active_camera_evidence: int,
    security_ready_total: int,
    security_waiting_total: int,
    security_blocked_total: int,
    security_muted_total: int,
    issues: list[tuple[str, str]],
) -> dict[str, Any]:
    issues_payload = [{"severity": severity, "message": message} for severity, message in issues]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entry_id": entry_id,
        "verdict": verdict,
        "health": {
            "house_state": snapshot.get("house_state") or "",
            "security_state": snapshot.get("security_state") or "",
            "anyone_home": bool(snapshot.get("anyone_home", False)),
            "people_count": int(snapshot.get("people_count", 0) or 0),
            "config_issue_total": config_issues,
            "event_total": event_total,
            "event_emit_total": emitted_total,
            "event_drop_total": dropped_total,
            "last_reason": snapshot.get("notes") or "",
        },
        "house_state": {
            "state": house_state.get("state") or "",
            "reason": house_state.get("reason") or "",
            "path": house_state.get("resolution_path") or "",
            "winning_reason": house_state.get("winning_reason") or "",
            "pending_candidate": house_state.get("pending_candidate") or "",
            "pending_remaining_s": house_state.get("pending_remaining_s"),
        },
        "learning": {
            "enabled_families": list(learning.get("enabled_plugin_families") or []),
            "family_count": int(learning.get("family_count", 0) or 0),
            "active_family_total": active_family_total,
            "proposal_total": int(learning.get("proposal_total", 0) or 0),
            "pending_total": pending_total,
            "stale_pending_total": stale_pending,
            "pending_families": pending_family_names,
            "top_pending": top_pending,
        },
        "runtime_value": {
            "configured_reaction_total": configured_reaction_total,
            "learned_origin_reaction_total": learned_reaction_total,
            "camera_active_evidence_total": active_camera_evidence,
            "camera_breach_candidate_total": breach_candidate_total,
            "security_presence_ready_total": security_ready_total,
            "security_presence_waiting_total": security_waiting_total,
            "security_presence_blocked_total": security_blocked_total,
            "security_presence_muted_total": security_muted_total,
        },
        "security": {
            "camera_source_status": _as_dict(camera_evidence.get("source_status_counts")),
            "blocked_by_class": _as_dict(security_presence.get("blocked_by_class")),
        },
        "reactions": {
            "by_origin": _as_dict(reactions.get("by_origin")),
            "by_author_kind": _as_dict(reactions.get("by_author_kind")),
            "by_template_id": _as_dict(reactions.get("by_template_id")),
        },
        "issues": issues_payload,
    }


def _load_snapshot(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _compare_lists(previous: list[Any], current: list[Any]) -> tuple[list[str], list[str]]:
    prev_set = {str(item) for item in previous}
    cur_set = {str(item) for item in current}
    added = sorted(cur_set - prev_set)
    removed = sorted(prev_set - cur_set)
    return added, removed


def _compare_int(previous: dict[str, Any], current: dict[str, Any], key: str) -> int:
    return int(current.get(key, 0) or 0) - int(previous.get(key, 0) or 0)


def _print_compare(previous: dict[str, Any], current: dict[str, Any]) -> None:
    prev_health = _as_dict(previous.get("health"))
    cur_health = _as_dict(current.get("health"))
    prev_learning = _as_dict(previous.get("learning"))
    cur_learning = _as_dict(current.get("learning"))
    prev_runtime = _as_dict(previous.get("runtime_value"))
    cur_runtime = _as_dict(current.get("runtime_value"))

    pending_added, pending_removed = _compare_lists(
        _as_list(prev_learning.get("pending_families")),
        _as_list(cur_learning.get("pending_families")),
    )

    prev_active_total = int(prev_learning.get("active_family_total", 0) or 0)
    cur_active_total = int(cur_learning.get("active_family_total", 0) or 0)

    _print_header("Compare")
    print(f"previous_generated_at: {previous.get('generated_at') or '-'}")
    print(f"current_generated_at: {current.get('generated_at') or '-'}")
    print(f"verdict: {previous.get('verdict') or '-'} -> {current.get('verdict') or '-'}")
    print(f"config_issue_delta: {_compare_int(prev_health, cur_health, 'config_issue_total'):+d}")
    print(f"event_total_delta: {_compare_int(prev_health, cur_health, 'event_total'):+d}")
    print(f"active_family_total_delta: {cur_active_total - prev_active_total:+d}")
    print(f"pending_total_delta: {_compare_int(prev_learning, cur_learning, 'pending_total'):+d}")
    print(f"stale_pending_total_delta: {_compare_int(prev_learning, cur_learning, 'stale_pending_total'):+d}")
    print(
        "pending_families_added: "
        + (", ".join(pending_added) if pending_added else "-")
    )
    print(
        "pending_families_removed: "
        + (", ".join(pending_removed) if pending_removed else "-")
    )
    print(
        f"configured_reaction_total_delta: {_compare_int(prev_runtime, cur_runtime, 'configured_reaction_total'):+d}"
    )
    print(
        f"learned_origin_reaction_total_delta: {_compare_int(prev_runtime, cur_runtime, 'learned_origin_reaction_total'):+d}"
    )
    print(
        f"camera_breach_candidate_total_delta: {_compare_int(prev_runtime, cur_runtime, 'camera_breach_candidate_total'):+d}"
    )
    print(
        f"security_presence_blocked_total_delta: {_compare_int(prev_runtime, cur_runtime, 'security_presence_blocked_total'):+d}"
    )


def _review_lines(snapshot_payload: dict[str, Any], previous: dict[str, Any] | None = None) -> list[str]:
    health = _as_dict(snapshot_payload.get("health"))
    learning = _as_dict(snapshot_payload.get("learning"))
    runtime_value = _as_dict(snapshot_payload.get("runtime_value"))
    issues = _as_list(snapshot_payload.get("issues"))

    healthy_signals: list[str] = []
    red_flags: list[str] = []

    if int(health.get("config_issue_total", 0) or 0) == 0:
        healthy_signals.append("no config issues detected")
    if int(learning.get("active_family_total", 0) or 0) > 0:
        healthy_signals.append(
            f"{int(learning.get('active_family_total', 0) or 0)} learning family active"
        )
    if int(runtime_value.get("configured_reaction_total", 0) or 0) > 0:
        healthy_signals.append(
            f"{int(runtime_value.get('configured_reaction_total', 0) or 0)} configured reactions present"
        )
    if int(runtime_value.get("camera_breach_candidate_total", 0) or 0) > 0:
        red_flags.append(
            f"{int(runtime_value.get('camera_breach_candidate_total', 0) or 0)} active security breach candidates"
        )
    if int(learning.get("stale_pending_total", 0) or 0) > 0:
        red_flags.append(
            f"{int(learning.get('stale_pending_total', 0) or 0)} stale pending proposals"
        )
    for item in issues:
        issue = _as_dict(item)
        severity = str(issue.get("severity") or "")
        message = str(issue.get("message") or "").strip()
        if severity in {"warning", "critical"} and message:
            red_flags.append(message)

    lines = [
        f"review_verdict: {snapshot_payload.get('verdict') or '-'}",
        f"generated_at: {snapshot_payload.get('generated_at') or '-'}",
        "healthy_signals: " + (", ".join(sorted(set(healthy_signals))) if healthy_signals else "-"),
        "red_flags: " + (", ".join(sorted(set(red_flags))) if red_flags else "-"),
        "pending_families: "
        + (", ".join(_as_list(learning.get("pending_families"))) if _as_list(learning.get("pending_families")) else "-"),
        "top_pending: "
        + (" | ".join(_as_list(learning.get("top_pending"))) if _as_list(learning.get("top_pending")) else "-"),
    ]

    if previous is not None:
        prev_learning = _as_dict(previous.get("learning"))
        prev_runtime = _as_dict(previous.get("runtime_value"))
        lines.extend(
            [
                f"compare_verdict: {(previous.get('verdict') or '-')} -> {(snapshot_payload.get('verdict') or '-')}",
                f"pending_total_delta: {_compare_int(prev_learning, learning, 'pending_total'):+d}",
                f"active_family_total_delta: {_compare_int(prev_learning, learning, 'active_family_total'):+d}",
                f"configured_reaction_total_delta: {_compare_int(prev_runtime, runtime_value, 'configured_reaction_total'):+d}",
            ]
        )

    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima operations audit")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--show-json", action="store_true")
    parser.add_argument("--snapshot-out", help="Write a stable JSON audit snapshot to this path")
    parser.add_argument("--compare-to", help="Compare the current audit snapshot against a previous snapshot file")
    parser.add_argument("--review", action="store_true", help="Print a compact operator review summary")
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    diagnostics = client.get(f"/api/diagnostics/config_entry/{entry_id}")

    runtime = _as_dict(_as_dict(diagnostics).get("data", {}).get("runtime"))
    engine = _as_dict(runtime.get("engine"))
    plugins = _as_dict(runtime.get("plugins"))
    proposals = _as_dict(runtime.get("proposals"))
    event_store = _as_dict(runtime.get("event_store"))
    events = _as_dict(_as_dict(engine.get("events")).get("stats"))
    snapshot = _as_dict(engine.get("snapshot"))
    house_state = _as_dict(plugins.get("house_state_summary"))
    learning = _as_dict(plugins.get("learning_summary"))
    reactions = _as_dict(plugins.get("configured_reaction_summary"))
    security_presence = _as_dict(plugins.get("security_presence_summary"))
    camera_evidence = _as_dict(plugins.get("security_camera_evidence_summary"))

    config_issues = len(_as_list(_as_dict(events.get("last_event")).get("context", {}).get("issues")))
    families = _as_dict(learning.get("families"))
    pending_total = int(learning.get("pending_total", 0) or 0)
    stale_pending = int(learning.get("pending_stale_total", 0) or 0)
    configured_reaction_total = int(reactions.get("total", 0) or 0)
    learned_reaction_total = int(_as_dict(reactions.get("by_origin")).get("learned", 0) or 0)
    active_camera_evidence = int(camera_evidence.get("active_evidence_total", 0) or 0)
    breach_candidate_total = int(camera_evidence.get("breach_candidate_total", 0) or 0)
    security_ready_total = int(security_presence.get("ready_tonight_total", 0) or 0)
    security_waiting_total = int(security_presence.get("waiting_for_darkness_total", 0) or 0)
    security_blocked_total = int(security_presence.get("blocked_total", 0) or 0)
    security_muted_total = int(security_presence.get("muted_total", 0) or 0)
    event_total = int(event_store.get("total_events", 0) or 0)
    emitted_total = int(events.get("emitted", 0) or 0)
    dropped_total = int(events.get("dropped_dedup", 0) or 0) + int(events.get("dropped_rate_limited", 0) or 0)
    active_family_total = sum(
        1 for item in families.values() if int(_as_dict(item).get("total", 0) or 0) > 0
    )
    pending_family_names = sorted(
        family_name
        for family_name, item in families.items()
        if int(_as_dict(item).get("pending", 0) or 0) > 0
    )
    top_pending = _top_pending_examples(families)
    issues: list[tuple[str, str]] = []

    _add_issue(not snapshot, "critical", "engine snapshot missing", issues)
    _add_issue(config_issues > 0, "critical", f"{config_issues} config issue(s) detected", issues)
    _add_issue(event_total == 0, "warning", "event store is empty", issues)
    _add_issue(configured_reaction_total == 0, "warning", "no configured reactions active", issues)
    _add_issue(pending_total > 10, "warning", f"proposal backlog is high ({pending_total})", issues)
    _add_issue(stale_pending > 0, "warning", f"{stale_pending} stale pending proposal(s)", issues)
    _add_issue(active_family_total == 0, "info", "no learning family currently has active evidence", issues)
    _add_issue(
        security_blocked_total > 0 and security_ready_total == 0,
        "warning",
        "security presence is configured but never ready tonight",
        issues,
    )
    _add_issue(breach_candidate_total > 0, "critical", f"{breach_candidate_total} active security breach candidate(s)", issues)
    verdict = _audit_verdict(issues)
    snapshot_payload = _build_snapshot(
        entry_id=entry_id,
        verdict=verdict,
        snapshot=snapshot,
        house_state=house_state,
        learning=learning,
        reactions=reactions,
        security_presence=security_presence,
        camera_evidence=camera_evidence,
        config_issues=config_issues,
        event_total=event_total,
        emitted_total=emitted_total,
        dropped_total=dropped_total,
        active_family_total=active_family_total,
        pending_total=pending_total,
        stale_pending=stale_pending,
        pending_family_names=pending_family_names,
        top_pending=top_pending,
        configured_reaction_total=configured_reaction_total,
        learned_reaction_total=learned_reaction_total,
        breach_candidate_total=breach_candidate_total,
        active_camera_evidence=active_camera_evidence,
        security_ready_total=security_ready_total,
        security_waiting_total=security_waiting_total,
        security_blocked_total=security_blocked_total,
        security_muted_total=security_muted_total,
        issues=issues,
    )

    _print_header("Health")
    print(f"verdict: {verdict}")
    print(f"entry_id: {entry_id}")
    print(f"house_state: {snapshot.get('house_state') or '-'}")
    print(f"anyone_home: {bool(snapshot.get('anyone_home', False))}")
    print(f"people_count: {int(snapshot.get('people_count', 0) or 0)}")
    print(f"last_reason: {snapshot.get('notes') or '-'}")
    print(f"config_issue_total: {config_issues}")
    print(f"event_total: {event_total}")
    print(f"events_emitted: {emitted_total}")
    print(f"events_dropped: {dropped_total}")
    print(f"last_event_type: {_as_dict(events.get('last_event')).get('type') or '-'}")

    _print_header("House State")
    print(f"state: {house_state.get('state') or '-'}")
    print(f"reason: {house_state.get('reason') or '-'}")
    print(f"path: {house_state.get('resolution_path') or '-'}")
    print(f"winning_reason: {house_state.get('winning_reason') or '-'}")
    active_candidates = [str(item) for item in _as_list(house_state.get('active_candidates')) if str(item).strip()]
    print(f"active_candidates: {', '.join(active_candidates) if active_candidates else '-'}")
    print(f"pending_candidate: {house_state.get('pending_candidate') or '-'}")
    print(f"pending_remaining_s: {house_state.get('pending_remaining_s') if house_state.get('pending_remaining_s') is not None else '-'}")

    _print_header("Learning")
    print(f"enabled_families: {', '.join(_as_list(learning.get('enabled_plugin_families'))) or '-'}")
    print(f"family_count: {int(learning.get('family_count', 0) or 0)}")
    print(f"active_family_total: {active_family_total}")
    print(f"proposal_total: {int(learning.get('proposal_total', 0) or 0)}")
    print(f"pending_total: {pending_total}")
    print(f"pending_stale_total: {stale_pending}")
    print(f"pending_families: {', '.join(pending_family_names) if pending_family_names else '-'}")
    print(f"families: {_join_map(_as_dict({k: _as_dict(v).get('pending', 0) for k, v in families.items()}))}")
    print(f"top_pending: {' | '.join(top_pending) if top_pending else '-'}")

    _print_header("Reactions")
    print(f"configured_total: {configured_reaction_total}")
    print(f"learned_origin_total: {learned_reaction_total}")
    print(f"by_origin: {_join_map(_as_dict(reactions.get('by_origin')))}")
    print(f"by_author_kind: {_join_map(_as_dict(reactions.get('by_author_kind')))}")
    print(f"by_template_id: {_join_map(_as_dict(reactions.get('by_template_id')))}")

    _print_header("Security")
    print(f"security_state: {snapshot.get('security_state') or '-'}")
    print(f"camera_active_evidence_total: {active_camera_evidence}")
    print(f"camera_breach_candidate_total: {breach_candidate_total}")
    print(f"camera_active_by_role: {_join_map(_as_dict(camera_evidence.get('active_by_role')))}")
    print(f"camera_active_by_kind: {_join_map(_as_dict(camera_evidence.get('active_by_kind')))}")
    print(f"camera_source_status: {_join_map(_as_dict(camera_evidence.get('source_status_counts')))}")
    print(f"camera_return_home_hint: {bool(camera_evidence.get('return_home_hint_active', False))}")

    _print_header("Security Presence")
    print(f"configured_total: {int(security_presence.get('configured_total', 0) or 0)}")
    print(f"ready_tonight_total: {security_ready_total}")
    print(f"waiting_for_darkness_total: {security_waiting_total}")
    print(f"insufficient_evidence_total: {int(security_presence.get('insufficient_evidence_total', 0) or 0)}")
    print(f"muted_total: {security_muted_total}")
    print(f"blocked_total: {security_blocked_total}")
    print(f"blocked_by_class: {_join_map(_as_dict(security_presence.get('blocked_by_class')))}")

    _print_header("Warnings")
    if issues:
        for severity, message in issues:
            print(f"- [{severity}] {message}")
    else:
        print("none")

    previous_snapshot: dict[str, Any] | None = None

    if args.show_json:
        _print_header("RAW PLUGINS")
        print(json.dumps(plugins, indent=2, ensure_ascii=False))

    if args.snapshot_out:
        out_path = Path(args.snapshot_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(snapshot_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nSNAPSHOT: {out_path}")

    if args.compare_to:
        previous_snapshot = _load_snapshot(args.compare_to)
        _print_compare(previous_snapshot, snapshot_payload)

    if args.review:
        _print_header("Review")
        for line in _review_lines(snapshot_payload, previous_snapshot):
            print(line)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
