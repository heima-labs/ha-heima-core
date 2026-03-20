#!/usr/bin/env python3
"""Diagnostic assert for Heima learning proposals sensor."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAClient


def _to_int(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return 0
    return int(float(raw))


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima learning proposals diagnostics")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--entity-id", default="sensor.heima_reaction_proposals")
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--require-type", default="", help="e.g. presence_preheat")
    parser.add_argument("--require-status", default="pending", help="e.g. pending/accepted/rejected")
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token)
    state = client.get_state(args.entity_id)
    sensor_count = _to_int(state.get("state"))
    attrs = dict(state.get("attributes") or {})
    proposals = [p for p in attrs.values() if isinstance(p, dict)]

    if args.require_status:
        matching = [p for p in proposals if str(p.get("status", "")) == args.require_status]
    else:
        matching = list(proposals)

    print(f"Entity: {args.entity_id}")
    print(f"Sensor pending count: {sensor_count}")
    print(f"Attributes proposals: {len(proposals)}")
    if args.require_status:
        print(f"Matching status '{args.require_status}': {len(matching)}")

    if proposals:
        print("Proposals:")
        for pid, proposal in attrs.items():
            if not isinstance(proposal, dict):
                continue
            ptype = str(proposal.get("type", ""))
            status = str(proposal.get("status", ""))
            conf = proposal.get("confidence", "")
            desc = str(proposal.get("description", "")).strip()
            print(f"- id={pid} type={ptype} status={status} confidence={conf} desc={desc}")

    if len(matching) < args.min_count:
        raise RuntimeError(
            f"Expected at least {args.min_count} proposals"
            f"{f' with status={args.require_status!r}' if args.require_status else ''},"
            f" got {len(matching)}"
        )

    if args.require_type:
        matched = False
        for proposal in matching:
            if str(proposal.get("type", "")) != args.require_type:
                continue
            matched = True
            break
        if not matched:
            raise RuntimeError(
                f"No proposal found with type='{args.require_type}' status='{args.require_status}'"
            )

    print("PASS: learning proposals diagnostic checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
