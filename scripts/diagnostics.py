#!/usr/bin/env python3
"""Stampa i diagnostics Heima in modo leggibile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.ha_client import HAClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima diagnostics")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument(
        "--section",
        choices=["all", "engine", "event_store", "proposals", "scheduler", "calendar"],
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
        "calendar": runtime.get("engine", {}).get("calendar"),
        "engine": {k: v for k, v in runtime.get("engine", {}).items() if k != "calendar"},
        "scheduler": runtime.get("scheduler"),
    }

    to_print = sections if args.section == "all" else {args.section: sections[args.section]}

    for name, data in to_print.items():
        if data is None:
            continue
        print(f"\n=== {name.upper()} ===")
        print(json.dumps(data, indent=2))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
