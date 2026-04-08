#!/usr/bin/env python3
"""Operational audit summary for Heima."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima operations audit")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--show-json", action="store_true")
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

    if args.show_json:
        _print_header("RAW PLUGINS")
        print(json.dumps(plugins, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
