#!/usr/bin/env python3
"""Bump the minor version in manifest.json. Resets patch to 0."""
import json
from pathlib import Path

manifest_path = Path("custom_components/heima/manifest.json")
data = json.loads(manifest_path.read_text())

major, minor, patch = data["version"].split(".")
data["version"] = f"{major}.{int(minor) + 1}.0"

manifest_path.write_text(json.dumps(data, indent=2) + "\n")
print(f"Version bumped to {data['version']}")
