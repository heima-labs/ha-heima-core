#!/usr/bin/env python3
"""Generate the non-admin Heima dashboard from the real Heima config entry."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from lib.ha_client import HAClient  # noqa: E402,I001


ROOM_ICONS: dict[str, str] = {
    "studio": "mdi:desk",
    "office": "mdi:desk",
    "ufficio": "mdi:desk",
    "living": "mdi:sofa-outline",
    "salotto": "mdi:sofa-outline",
    "soggiorno": "mdi:sofa-outline",
    "bathroom": "mdi:shower",
    "bagno": "mdi:shower",
    "bedroom": "mdi:bed-king-outline",
    "camera": "mdi:bed-king-outline",
    "kitchen": "mdi:pot-steam-outline",
    "cucina": "mdi:pot-steam-outline",
    "garage": "mdi:garage-variant",
    "garden": "mdi:flower-outline",
    "giardino": "mdi:flower-outline",
}

TEMPLATE_PATH = Path(__file__).with_name("heima_dashboard_template.yaml")


def _room_icon(room_id: str, display_name: str) -> str:
    haystack = f"{room_id} {display_name}".lower()
    for key, icon in ROOM_ICONS.items():
        if key in haystack:
            return icon
    return "mdi:door-open"


def _pad(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in text.splitlines())


def _slug_to_entity_suffix(room_id: str) -> str:
    clean = re.sub(r"[^a-z0-9_]+", "_", room_id.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean


def discover(client: HAClient, *, max_rooms: int) -> dict[str, Any]:
    entry_id = client.find_heima_entry_id()
    entry = client.get_entry(entry_id)
    options = dict(entry.get("options") or {})

    rooms: list[dict[str, str]] = []
    for item in list(options.get("rooms", [])):
        if not isinstance(item, dict):
            continue
        room_id = str(item.get("room_id") or "").strip()
        if not room_id:
            continue
        display_name = str(item.get("display_name") or room_id).strip()
        rooms.append(
            {
                "room_id": room_id,
                "display_name": display_name,
                "entity_suffix": _slug_to_entity_suffix(room_id),
                "icon": _room_icon(room_id, display_name),
            }
        )
    rooms = rooms[:max_rooms]
    return {"entry_id": entry_id, "rooms": rooms}


def generate_yaml(data: dict[str, Any]) -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL", ""))
    parser.add_argument("--ha-token", default=os.environ.get("HA_TOKEN", ""))
    parser.add_argument("--out", required=True, help="Output dashboard YAML path")
    parser.add_argument("--max-rooms", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not args.ha_url or not args.ha_token:
        print("ERROR: --ha-url e --ha-token obbligatori (o HA_URL/HA_TOKEN env)", file=sys.stderr)
        sys.exit(1)

    client = HAClient(base_url=args.ha_url, token=args.ha_token)
    data = discover(client, max_rooms=max(args.max_rooms, 1))
    yaml_out = generate_yaml(data)
    Path(args.out).write_text(yaml_out, encoding="utf-8")
    print(f"✓ Generated {args.out}", file=sys.stderr)
    print(f"  Rooms: {[room['room_id'] for room in data['rooms']]}", file=sys.stderr)


if __name__ == "__main__":
    main()
