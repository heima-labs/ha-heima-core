#!/usr/bin/env python3
"""Live check: Heima options flow must be admin-only."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


class HAFlowClient(HAClient):
    def options_flow_init_raw(self, entry_id: str) -> tuple[int, Any]:
        return self.request(
            "POST",
            "/api/config/config_entries/options/flow",
            {"handler": entry_id},
            accept_error=True,
        )


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def scenario_admin_allowed(client: HAFlowClient, entry_id: str) -> None:
    print("== Scenario A: admin can open Heima options flow ==")
    status, data = client.options_flow_init_raw(entry_id)
    _assert(status == 200, f"expected HTTP 200, got {status}")
    _assert(isinstance(data, dict), f"invalid admin flow payload type: {type(data)}")
    _assert(str(data.get("step_id") or "") == "init", f"expected step_id=init, got {data.get('step_id')!r}")
    print("PASS scenario A")


def scenario_non_admin_denied(client: HAFlowClient, entry_id: str) -> None:
    print("== Scenario B: non-admin is denied Heima options flow ==")
    status, data = client.options_flow_init_raw(entry_id)
    if status in {401, 403}:
        print(f"PASS scenario B (blocked by HA API with HTTP {status})")
        return

    _assert(status == 200, f"expected HTTP 200 abort payload or HTTP 401/403, got {status}")
    _assert(isinstance(data, dict), f"invalid non-admin flow payload type: {type(data)}")
    _assert(str(data.get("type") or "") == "abort", f"expected abort payload, got type={data.get('type')!r}")
    _assert(
        str(data.get("reason") or "") == "admin_required",
        f"expected reason=admin_required, got {data.get('reason')!r}",
    )
    print("PASS scenario B")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima admin-only options flow live check")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True, help="Admin Home Assistant token")
    parser.add_argument(
        "--ha-non-admin-token",
        default="",
        help="Optional non-admin Home Assistant token used to verify denial",
    )
    args = parser.parse_args()

    admin_client = HAFlowClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    entry_id = admin_client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    scenario_admin_allowed(admin_client, entry_id)

    if not str(args.ha_non_admin_token or "").strip():
        print("SKIP scenario B (missing --ha-non-admin-token)")
        print("PASS: admin-only options flow checks passed with partial coverage")
        return 0

    non_admin_client = HAFlowClient(
        base_url=args.ha_url,
        token=args.ha_non_admin_token,
        timeout_s=20,
    )
    scenario_non_admin_denied(non_admin_client, entry_id)

    print("PASS: admin-only options flow checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, HAApiError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: unexpected error: {exc}", file=sys.stderr)
        raise SystemExit(1)
