#!/usr/bin/env python3
"""Diagnostic assert for Heima learning_summary diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima learning summary diagnostics")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--min-plugin-count", type=int, default=1)
    parser.add_argument("--min-family-count", type=int, default=1)
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = client.find_heima_entry_id()
    diag = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    runtime = dict(diag.get("data", {}).get("runtime", {}) or {})
    plugins = dict(runtime.get("plugins", {}) or {})
    summary = dict(plugins.get("learning_summary", {}) or {})

    plugin_count = int(summary.get("plugin_count") or 0)
    family_count = int(summary.get("family_count") or 0)
    proposal_total = int(summary.get("proposal_total") or 0)
    pending_total = int(summary.get("pending_total") or 0)

    print(f"plugin_count={plugin_count}")
    print(f"family_count={family_count}")
    print(f"proposal_total={proposal_total}")
    print(f"pending_total={pending_total}")

    _assert(plugin_count >= args.min_plugin_count, f"expected plugin_count >= {args.min_plugin_count}, got {plugin_count}")
    _assert(family_count >= args.min_family_count, f"expected family_count >= {args.min_family_count}, got {family_count}")
    _assert(isinstance(summary.get("families"), dict), "learning_summary.families must be a dict")
    _assert(isinstance(summary.get("plugins"), dict), "learning_summary.plugins must be a dict")
    _assert(isinstance(summary.get("unclaimed_proposal_types"), list), "learning_summary.unclaimed_proposal_types must be a list")

    print("PASS: learning summary diagnostic checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
