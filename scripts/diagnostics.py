#!/usr/bin/env python3
"""Stampa i diagnostics Heima in modo leggibile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.ha_client import HAClient


def _print_learning_summary(data: dict[str, Any]) -> None:
    print(f"plugin_count: {data.get('plugin_count', 0)}")
    print(f"family_count: {data.get('family_count', 0)}")
    print(f"proposal_total: {data.get('proposal_total', 0)}")
    print(f"pending_total: {data.get('pending_total', 0)}")
    print(f"pending_stale_total: {data.get('pending_stale_total', 0)}")
    print(f"config_source: {data.get('config_source', 'n/a')}")

    enabled = list(data.get("enabled_plugin_families") or [])
    disabled = list(data.get("disabled_plugin_families") or [])
    if enabled:
        print("enabled_families: " + ", ".join(enabled))
    if disabled:
        print("disabled_families: " + ", ".join(disabled))

    families = dict(data.get("families") or {})
    if families:
        print("\nFamilies:")
        for family in sorted(families):
            item = dict(families[family] or {})
            print(
                f"- {family}: total={item.get('total', 0)} "
                f"pending={item.get('pending', 0)} "
                f"accepted={item.get('accepted', 0)} "
                f"rejected={item.get('rejected', 0)} "
                f"stale_pending={item.get('stale_pending', 0)}"
            )
            implemented_templates = list(item.get("implemented_admin_authored_templates") or [])
            unimplemented_templates = list(item.get("unimplemented_admin_authored_templates") or [])
            if implemented_templates:
                print("  implemented_templates: " + ", ".join(implemented_templates))
            if unimplemented_templates:
                print("  declared_only_templates: " + ", ".join(unimplemented_templates))


def _print_reaction_summary(data: dict[str, Any]) -> None:
    print(f"total: {data.get('total', 0)}")

    by_origin = dict(data.get("by_origin") or {})
    if by_origin:
        print(
            "by_origin: "
            + ", ".join(f"{key}={value}" for key, value in sorted(by_origin.items()))
        )

    by_author_kind = dict(data.get("by_author_kind") or {})
    if by_author_kind:
        print(
            "by_author_kind: "
            + ", ".join(f"{key}={value}" for key, value in sorted(by_author_kind.items()))
        )

    by_template_id = dict(data.get("by_template_id") or {})
    if by_template_id:
        print(
            "by_template_id: "
            + ", ".join(f"{key}={value}" for key, value in sorted(by_template_id.items()))
        )

    identity_collisions = dict(data.get("identity_collisions") or {})
    if identity_collisions:
        print("identity_collisions:")
        for identity_key, reaction_ids in sorted(identity_collisions.items()):
            ids = ", ".join(str(item) for item in reaction_ids)
            print(f"  {identity_key}: {ids}")

    lighting_slot_collisions = dict(data.get("lighting_slot_collisions") or {})
    if lighting_slot_collisions:
        print("lighting_slot_collisions:")
        for slot_key, reaction_ids in sorted(lighting_slot_collisions.items()):
            ids = ", ".join(str(item) for item in reaction_ids)
            print(f"  {slot_key}: {ids}")


def _print_lighting_summary(data: dict[str, Any]) -> None:
    print(f"configured_total: {data.get('configured_total', 0)}")
    print(f"pending_total: {data.get('pending_total', 0)}")
    print(f"pending_tuning_total: {data.get('pending_tuning_total', 0)}")
    print(f"pending_discovery_total: {data.get('pending_discovery_total', 0)}")

    configured_by_room = dict(data.get("configured_by_room") or {})
    if configured_by_room:
        print(
            "configured_by_room: "
            + ", ".join(f"{key}={value}" for key, value in sorted(configured_by_room.items()))
        )

    pending_by_room = dict(data.get("pending_by_room") or {})
    if pending_by_room:
        print(
            "pending_by_room: "
            + ", ".join(f"{key}={value}" for key, value in sorted(pending_by_room.items()))
        )

    configured_by_slot = dict(data.get("configured_by_slot") or {})
    if configured_by_slot:
        print("configured_by_slot:")
        for slot_key, total in sorted(configured_by_slot.items()):
            print(f"  {slot_key}: {total}")

    tuning_examples = list(data.get("pending_tuning_examples") or [])
    if tuning_examples:
        print("pending_tuning_examples:")
        for item in tuning_examples:
            print(
                f"  {item.get('room_id') or '-'} | {item.get('slot_key') or '-'} | "
                f"{item.get('confidence')} | {item.get('label') or '-'}"
            )

    discovery_examples = list(data.get("pending_discovery_examples") or [])
    if discovery_examples:
        print("pending_discovery_examples:")
        for item in discovery_examples:
            print(
                f"  {item.get('room_id') or '-'} | {item.get('slot_key') or '-'} | "
                f"{item.get('confidence')} | {item.get('label') or '-'}"
            )

    slot_collisions = dict(data.get("slot_collisions") or {})
    if slot_collisions:
        print("slot_collisions:")
        for slot_key, reaction_ids in sorted(slot_collisions.items()):
            ids = ", ".join(str(item) for item in reaction_ids)
            print(f"  {slot_key}: {ids}")


def _print_composite_summary(data: dict[str, Any]) -> None:
    print(f"configured_total: {data.get('configured_total', 0)}")
    print(f"pending_total: {data.get('pending_total', 0)}")
    print(f"pending_tuning_total: {data.get('pending_tuning_total', 0)}")
    print(f"pending_discovery_total: {data.get('pending_discovery_total', 0)}")

    configured_by_room = dict(data.get("configured_by_room") or {})
    if configured_by_room:
        print(
            "configured_by_room: "
            + ", ".join(f"{key}={value}" for key, value in sorted(configured_by_room.items()))
        )

    configured_by_type = dict(data.get("configured_by_type") or {})
    if configured_by_type:
        print(
            "configured_by_type: "
            + ", ".join(f"{key}={value}" for key, value in sorted(configured_by_type.items()))
        )

    configured_by_primary_signal = dict(data.get("configured_by_primary_signal") or {})
    if configured_by_primary_signal:
        print(
            "configured_by_primary_signal: "
            + ", ".join(
                f"{key}={value}" for key, value in sorted(configured_by_primary_signal.items())
            )
        )

    pending_by_room = dict(data.get("pending_by_room") or {})
    if pending_by_room:
        print(
            "pending_by_room: "
            + ", ".join(f"{key}={value}" for key, value in sorted(pending_by_room.items()))
        )

    pending_by_type = dict(data.get("pending_by_type") or {})
    if pending_by_type:
        print(
            "pending_by_type: "
            + ", ".join(f"{key}={value}" for key, value in sorted(pending_by_type.items()))
        )

    pending_by_primary_signal = dict(data.get("pending_by_primary_signal") or {})
    if pending_by_primary_signal:
        print(
            "pending_by_primary_signal: "
            + ", ".join(
                f"{key}={value}" for key, value in sorted(pending_by_primary_signal.items())
            )
        )

    tuning_examples = list(data.get("pending_tuning_examples") or [])
    if tuning_examples:
        print("pending_tuning_examples:")
        for item in tuning_examples:
            print(
                f"  {item.get('room_id') or '-'} | {item.get('primary_signal_name') or '-'} | "
                f"{item.get('confidence')} | {item.get('label') or '-'}"
            )


def _print_calendar_summary(data: dict[str, Any]) -> None:
    configured_entities = list(data.get("configured_entities") or [])
    print(f"configured_entities_count: {len(configured_entities)}")
    if configured_entities:
        print("configured_entities: " + ", ".join(configured_entities))
    print(f"current_events_count: {data.get('current_events_count', 0)}")
    print(f"upcoming_events_count: {data.get('upcoming_events_count', 0)}")
    print(f"cached_events_count: {data.get('cached_events_count', 0)}")
    print(f"is_vacation_active: {bool(data.get('is_vacation_active', False))}")
    print(f"is_wfh_today: {bool(data.get('is_wfh_today', False))}")
    print(f"is_office_today: {bool(data.get('is_office_today', False))}")
    if data.get("cache_ts"):
        print(f"cache_ts: {data.get('cache_ts')}")
    next_vacation = dict(data.get("next_vacation") or {})
    if next_vacation:
        print(
            "next_vacation: "
            f"{next_vacation.get('summary') or '-'} | "
            f"{next_vacation.get('start') or '-'} | "
            f"{next_vacation.get('calendar_entity') or '-'}"
        )


def _print_house_state_summary(data: dict[str, Any]) -> None:
    print(f"state: {data.get('state') or '-'}")
    print(f"reason: {data.get('reason') or '-'}")
    print(f"resolution_path: {data.get('resolution_path') or '-'}")
    print(f"winning_reason: {data.get('winning_reason') or '-'}")
    print(f"sticky_retention: {bool(data.get('sticky_retention', False))}")
    active_candidates = list(data.get("active_candidates") or [])
    if active_candidates:
        print("active_candidates: " + ", ".join(active_candidates))
    pending_candidate = str(data.get("pending_candidate") or "").strip()
    if pending_candidate:
        print(f"pending_candidate: {pending_candidate}")
    if data.get("pending_remaining_s") is not None:
        print(f"pending_remaining_s: {data.get('pending_remaining_s')}")
    calendar_context = dict(data.get("calendar_context") or {})
    if calendar_context:
        print(
            "calendar_context: "
            f"vacation={bool(calendar_context.get('is_vacation_active', False))}, "
            f"wfh={bool(calendar_context.get('is_wfh_today', False))}, "
            f"office={bool(calendar_context.get('is_office_today', False))}"
        )

    discovery_examples = list(data.get("pending_discovery_examples") or [])
    if discovery_examples:
        print("pending_discovery_examples:")
        for item in discovery_examples:
            print(
                f"  {item.get('room_id') or '-'} | {item.get('primary_signal_name') or '-'} | "
                f"{item.get('confidence')} | {item.get('label') or '-'}"
            )


def _print_security_presence_summary(data: dict[str, Any]) -> None:
    print(f"configured_total: {data.get('configured_total', 0)}")
    print(f"active_tonight_total: {data.get('active_tonight_total', 0)}")
    print(f"blocked_total: {data.get('blocked_total', 0)}")

    configured_by_room = dict(data.get("configured_by_room") or {})
    if configured_by_room:
        print(
            "configured_by_room: "
            + ", ".join(f"{key}={value}" for key, value in sorted(configured_by_room.items()))
        )

    source_room_counts = dict(data.get("source_room_counts") or {})
    if source_room_counts:
        print(
            "source_room_counts: "
            + ", ".join(f"{key}={value}" for key, value in sorted(source_room_counts.items()))
        )

    blocked_by_reason = dict(data.get("blocked_by_reason") or {})
    if blocked_by_reason:
        print(
            "blocked_by_reason: "
            + ", ".join(f"{key}={value}" for key, value in sorted(blocked_by_reason.items()))
        )

    examples = list(data.get("examples") or [])
    if examples:
        print("examples:")
        for item in examples:
            print(
                f"  {item.get('reaction_id') or '-'} | active={bool(item.get('active_tonight', False))} | "
                f"plan={item.get('tonight_plan_count', 0)} | blocked={item.get('blocked_reason') or '-'} | "
                f"next={item.get('next_planned_activation') or '-'}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima diagnostics")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument(
        "--section",
        choices=["all", "engine", "house_state", "house_state_summary", "events", "event_store", "proposals", "scheduler", "calendar", "plugins", "learning", "reactions", "lighting", "composite", "security_presence"],
        default="all",
        help="Sezione da mostrare (default: all)",
    )
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    diag = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    runtime = diag.get("data", {}).get("runtime", {})

    sections = {
        "event_store": runtime.get("event_store"),
        "proposals": runtime.get("proposals"),
        "calendar": runtime.get("plugins", {}).get("calendar_summary")
        or runtime.get("engine", {}).get("calendar"),
        "house_state_summary": runtime.get("plugins", {}).get("house_state_summary")
        or runtime.get("engine", {}).get("house_state"),
        "house_state": runtime.get("engine", {}).get("house_state"),
        "events": runtime.get("engine", {}).get("events"),
        "engine": {k: v for k, v in runtime.get("engine", {}).items() if k != "calendar"},
        "scheduler": runtime.get("scheduler"),
        "plugins": runtime.get("plugins"),
        "learning": runtime.get("plugins", {}).get("learning_summary"),
        "reactions": runtime.get("plugins", {}).get("configured_reaction_summary"),
        "lighting": runtime.get("plugins", {}).get("lighting_summary"),
        "composite": runtime.get("plugins", {}).get("composite_summary"),
        "security_presence": runtime.get("plugins", {}).get("security_presence_summary"),
    }

    to_print = sections if args.section == "all" else {args.section: sections[args.section]}

    for name, data in to_print.items():
        if data is None:
            continue
        print(f"\n=== {name.upper()} ===")
        if name == "learning" and isinstance(data, dict):
            _print_learning_summary(data)
            print()
        if name == "reactions" and isinstance(data, dict):
            _print_reaction_summary(data)
            print()
        if name == "lighting" and isinstance(data, dict):
            _print_lighting_summary(data)
            print()
        if name == "composite" and isinstance(data, dict):
            _print_composite_summary(data)
            print()
        if name == "calendar" and isinstance(data, dict):
            _print_calendar_summary(data)
            print()
        if name == "house_state_summary" and isinstance(data, dict):
            _print_house_state_summary(data)
            print()
        if name == "security_presence" and isinstance(data, dict):
            _print_security_presence_summary(data)
            print()
        print(json.dumps(data, indent=2))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
