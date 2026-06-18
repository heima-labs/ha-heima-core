#!/usr/bin/env python3
"""Live diagnostics for learning plugin execution modes.

The test is intentionally non-destructive: it only reads config entry
diagnostics and verifies that plugin families are reported according to their
execution role instead of being folded into analyzer enabled/disabled buckets.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    _assert(isinstance(raw, dict), f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    _assert(isinstance(data, dict), "diagnostics payload missing data object")
    return data


def _learning_summary(client: HAClient, entry_id: str) -> dict[str, Any]:
    plugins = _diagnostics_data(client, entry_id).get("runtime", {}).get("plugins", {})
    _assert(isinstance(plugins, dict), "runtime.plugins must be a dict")
    summary = plugins.get("learning_summary", {})
    _assert(isinstance(summary, dict), "plugins.learning_summary must be a dict")
    return summary


def _plugin(summary: dict[str, Any], plugin_id: str) -> dict[str, Any]:
    plugins = summary.get("plugins")
    _assert(isinstance(plugins, dict), "learning_summary.plugins must be a dict")
    plugin = plugins.get(plugin_id)
    _assert(isinstance(plugin, dict), f"missing plugin summary for {plugin_id}")
    return plugin


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima learning plugin execution modes")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    summary = _learning_summary(client, entry_id)

    enabled = set(summary.get("enabled_plugin_families") or [])
    disabled = set(summary.get("disabled_plugin_families") or [])
    lifecycle_only = set(summary.get("lifecycle_only_plugin_families") or [])
    admin_authored_only = set(summary.get("admin_authored_only_plugin_families") or [])

    _assert("house_state" in lifecycle_only, "house_state must be lifecycle-only")
    _assert(
        "scheduled_routine" in admin_authored_only,
        "scheduled_routine must be admin-authored-only",
    )
    _assert("house_state" not in enabled, "house_state leaked into enabled analyzer families")
    _assert("house_state" not in disabled, "house_state leaked into disabled analyzer families")
    _assert(
        "scheduled_routine" not in enabled,
        "scheduled_routine leaked into enabled analyzer families",
    )
    _assert(
        "scheduled_routine" not in disabled,
        "scheduled_routine leaked into disabled analyzer families",
    )

    house_state = _plugin(summary, "builtin.house_state_contexts")
    scheduled_routine = _plugin(summary, "builtin.scheduled_routines")

    _assert(
        house_state.get("execution_mode") == "lifecycle_only",
        f"unexpected house_state execution_mode: {house_state.get('execution_mode')!r}",
    )
    _assert(
        "house_state_learned_context" in set(house_state.get("proposal_types") or []),
        "house_state lifecycle plugin must claim house_state_learned_context",
    )
    _assert(
        scheduled_routine.get("execution_mode") == "admin_authored_only",
        f"unexpected scheduled_routine execution_mode: {scheduled_routine.get('execution_mode')!r}",
    )
    _assert(
        "scheduled_routine.basic" in set(scheduled_routine.get("admin_authored_templates") or []),
        "scheduled_routine admin template missing from diagnostics",
    )

    print(f"enabled_analyzer_families={sorted(enabled)}")
    print(f"disabled_analyzer_families={sorted(disabled)}")
    print(f"lifecycle_only_plugin_families={sorted(lifecycle_only)}")
    print(f"admin_authored_only_plugin_families={sorted(admin_authored_only)}")
    print("PASS: learning plugin execution mode diagnostics are coherent")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
