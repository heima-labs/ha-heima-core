#!/usr/bin/env python3
"""Live-safe checks for Heima Notification Delivery Policy decisions.

This test reads the live Heima config entry and simulates policy decisions
locally. It never calls notify services and does not require a real phone.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    python = root / ".venv" / "bin" / "python"
    cmd = [
        str(python if python.exists() else Path(sys.executable)),
        str(root / "scripts" / "notification_delivery_policy_diag.py"),
        "--ha-url",
        args.ha_url,
        "--ha-token",
        args.ha_token,
    ]
    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode != 0:
        return result.returncode
    print("PASS: notification delivery policy live-safe simulation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
