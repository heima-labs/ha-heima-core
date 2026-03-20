#!/usr/bin/env python3
"""Compatibility wrapper for the unified lab recovery/setup script.

The canonical setup entrypoint is now `scripts/recover_test_lab_config.py`.
This wrapper is kept only so older local commands do not break.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    target = repo_root / "scripts" / "recover_test_lab_config.py"
    cmd = [sys.executable, str(target), *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
