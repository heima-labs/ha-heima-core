#!/usr/bin/env python3
"""Readable learning audit summary for Heima."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.ha_client import HAClient


def _print_header(title: str) -> None:
    print(f"\n== {title} ==")


def _proposal_label(example: dict[str, Any]) -> str:
    return (
        f"{example.get('type')} "
        f"[{example.get('status')}] "
        f"{example.get('confidence')} "
        f"{str(example.get('description') or '').strip()}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima learning audit")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    diag = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    runtime = dict(diag.get("data", {}).get("runtime", {}) or {})
    summary = dict(runtime.get("plugins", {}).get("learning_summary", {}) or {})
    reaction_summary = dict(runtime.get("plugins", {}).get("configured_reaction_summary", {}) or {})
    lighting_summary = dict(runtime.get("plugins", {}).get("lighting_summary", {}) or {})
    composite_summary = dict(runtime.get("plugins", {}).get("composite_summary", {}) or {})

    _print_header("Learning Audit")
    print(f"entry_id: {entry_id}")
    print(f"plugins: {summary.get('plugin_count', 0)}")
    print(f"families: {summary.get('family_count', 0)}")
    print(f"proposals total: {summary.get('proposal_total', 0)}")
    print(f"pending: {summary.get('pending_total', 0)}")
    print(f"stale pending: {summary.get('pending_stale_total', 0)}")
    print(f"config source: {summary.get('config_source', 'n/a')}")

    enabled_families = list(summary.get("enabled_plugin_families") or [])
    disabled_families = list(summary.get("disabled_plugin_families") or [])
    if enabled_families:
        print("enabled families: " + ", ".join(enabled_families))
    if disabled_families:
        print("disabled families: " + ", ".join(disabled_families))

    if reaction_summary:
        _print_header("Configured Reactions")
        print(f"total: {reaction_summary.get('total', 0)}")
        by_origin = dict(reaction_summary.get("by_origin") or {})
        if by_origin:
            print(
                "by origin: "
                + ", ".join(f"{key}={value}" for key, value in sorted(by_origin.items()))
            )
        by_author_kind = dict(reaction_summary.get("by_author_kind") or {})
        if by_author_kind:
            print(
                "by author_kind: "
                + ", ".join(
                    f"{key}={value}" for key, value in sorted(by_author_kind.items())
                )
            )
        by_template_id = dict(reaction_summary.get("by_template_id") or {})
        if by_template_id:
            print(
                "by template_id: "
                + ", ".join(
                    f"{key}={value}" for key, value in sorted(by_template_id.items())
                )
            )
        identity_collisions = dict(reaction_summary.get("identity_collisions") or {})
        if identity_collisions:
            print("identity collisions:")
            for identity_key, reaction_ids in sorted(identity_collisions.items()):
                print(f"  {identity_key}: {', '.join(str(item) for item in reaction_ids)}")
        lighting_slot_collisions = dict(reaction_summary.get("lighting_slot_collisions") or {})
        if lighting_slot_collisions:
            print("lighting slot collisions:")
            for slot_key, reaction_ids in sorted(lighting_slot_collisions.items()):
                print(f"  {slot_key}: {', '.join(str(item) for item in reaction_ids)}")

    if lighting_summary:
        _print_header("Lighting")
        print(f"configured total: {lighting_summary.get('configured_total', 0)}")
        print(f"pending total: {lighting_summary.get('pending_total', 0)}")
        print(f"pending tuning: {lighting_summary.get('pending_tuning_total', 0)}")
        print(f"pending discovery: {lighting_summary.get('pending_discovery_total', 0)}")
        configured_by_room = dict(lighting_summary.get("configured_by_room") or {})
        if configured_by_room:
            print(
                "configured by room: "
                + ", ".join(f"{key}={value}" for key, value in sorted(configured_by_room.items()))
            )
        pending_by_room = dict(lighting_summary.get("pending_by_room") or {})
        if pending_by_room:
            print(
                "pending by room: "
                + ", ".join(f"{key}={value}" for key, value in sorted(pending_by_room.items()))
            )
        configured_by_slot = dict(lighting_summary.get("configured_by_slot") or {})
        if configured_by_slot:
            print("configured by slot:")
            for slot_key, total in sorted(configured_by_slot.items()):
                print(f"  {slot_key}: {total}")
        tuning_examples = list(lighting_summary.get("pending_tuning_examples") or [])
        if tuning_examples:
            print("pending tuning examples:")
            for item in tuning_examples:
                print(
                    "  "
                    f"{item.get('room_id') or '-'} | "
                    f"{item.get('slot_key') or '-'} | "
                    f"{item.get('confidence')} | "
                    f"{item.get('label') or '-'}"
                )
        discovery_examples = list(lighting_summary.get("pending_discovery_examples") or [])
        if discovery_examples:
            print("pending discovery examples:")
            for item in discovery_examples:
                print(
                    "  "
                    f"{item.get('room_id') or '-'} | "
                    f"{item.get('slot_key') or '-'} | "
                    f"{item.get('confidence')} | "
                    f"{item.get('label') or '-'}"
                )

    if composite_summary:
        _print_header("Composite")
        print(f"configured total: {composite_summary.get('configured_total', 0)}")
        print(f"pending total: {composite_summary.get('pending_total', 0)}")
        print(f"pending tuning: {composite_summary.get('pending_tuning_total', 0)}")
        print(f"pending discovery: {composite_summary.get('pending_discovery_total', 0)}")
        configured_by_room = dict(composite_summary.get("configured_by_room") or {})
        if configured_by_room:
            print(
                "configured by room: "
                + ", ".join(f"{key}={value}" for key, value in sorted(configured_by_room.items()))
            )
        configured_by_type = dict(composite_summary.get("configured_by_type") or {})
        if configured_by_type:
            print(
                "configured by type: "
                + ", ".join(f"{key}={value}" for key, value in sorted(configured_by_type.items()))
            )
        pending_by_room = dict(composite_summary.get("pending_by_room") or {})
        if pending_by_room:
            print(
                "pending by room: "
                + ", ".join(f"{key}={value}" for key, value in sorted(pending_by_room.items()))
            )
        pending_by_type = dict(composite_summary.get("pending_by_type") or {})
        if pending_by_type:
            print(
                "pending by type: "
                + ", ".join(f"{key}={value}" for key, value in sorted(pending_by_type.items()))
            )
        tuning_examples = list(composite_summary.get("pending_tuning_examples") or [])
        if tuning_examples:
            print("pending tuning examples:")
            for item in tuning_examples:
                print(
                    "  "
                    f"{item.get('room_id') or '-'} | "
                    f"{item.get('primary_signal_name') or '-'} | "
                    f"{item.get('confidence')} | "
                    f"{item.get('label') or '-'}"
                )
        discovery_examples = list(composite_summary.get("pending_discovery_examples") or [])
        if discovery_examples:
            print("pending discovery examples:")
            for item in discovery_examples:
                print(
                    "  "
                    f"{item.get('room_id') or '-'} | "
                    f"{item.get('primary_signal_name') or '-'} | "
                    f"{item.get('confidence')} | "
                    f"{item.get('label') or '-'}"
                )

    families = dict(summary.get("families") or {})
    if families:
        _print_header("By Family")
        for family in sorted(families):
            item = dict(families[family] or {})
            print(
                f"- {family}: total={item.get('total', 0)} "
                f"pending={item.get('pending', 0)} "
                f"accepted={item.get('accepted', 0)} "
                f"rejected={item.get('rejected', 0)} "
                f"stale_pending={item.get('stale_pending', 0)}"
            )
            proposal_types = list(item.get("proposal_types") or [])
            if proposal_types:
                print(f"  proposal_types: {', '.join(proposal_types)}")
            implemented_templates = list(item.get("implemented_admin_authored_templates") or [])
            unimplemented_templates = list(item.get("unimplemented_admin_authored_templates") or [])
            if implemented_templates:
                print("  implemented templates: " + ", ".join(implemented_templates))
            if unimplemented_templates:
                print("  declared-only templates: " + ", ".join(unimplemented_templates))
            examples = list(item.get("top_examples") or [])
            for example in examples:
                print(f"  top: {_proposal_label(example)}")

    plugins = dict(summary.get("plugins") or {})
    if plugins:
        _print_header("By Plugin")
        for plugin_id in sorted(plugins):
            item = dict(plugins[plugin_id] or {})
            print(
                f"- {plugin_id}: total={item.get('total', 0)} "
                f"pending={item.get('pending', 0)} "
                f"accepted={item.get('accepted', 0)} "
                f"rejected={item.get('rejected', 0)} "
                f"stale_pending={item.get('stale_pending', 0)}"
            )
            implemented_templates = list(item.get("implemented_admin_authored_templates") or [])
            unimplemented_templates = list(item.get("unimplemented_admin_authored_templates") or [])
            if implemented_templates:
                print("  implemented templates: " + ", ".join(implemented_templates))
            if unimplemented_templates:
                print("  declared-only templates: " + ", ".join(unimplemented_templates))

    unclaimed = list(summary.get("unclaimed_proposal_types") or [])
    if unclaimed:
        _print_header("Warnings")
        print("unclaimed proposal types: " + ", ".join(unclaimed))
    identity_collisions = dict(reaction_summary.get("identity_collisions") or {})
    lighting_slot_collisions = dict(reaction_summary.get("lighting_slot_collisions") or {})
    if identity_collisions:
        if not unclaimed:
            _print_header("Warnings")
        print("configured reaction identity collisions detected")
    if lighting_slot_collisions:
        if not unclaimed and not identity_collisions:
            _print_header("Warnings")
        print("configured reaction lighting slot collisions detected")

    print("\nPASS: learning audit generated")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
