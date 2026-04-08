#!/usr/bin/env python3
"""Remove Heima entity-registry entries from the fake-house storage."""

from __future__ import annotations

import json
from pathlib import Path


ENTITY_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/examples/ha_test_instance/docker/ha_config/.storage/core.entity_registry"
)


def _is_heima_entity(entry: dict) -> bool:
    return str(entry.get("platform") or "") == "heima"


def main() -> int:
    if not ENTITY_REGISTRY_PATH.exists():
        print(f"skip: entity registry not found at {ENTITY_REGISTRY_PATH}")
        return 0

    payload = json.loads(ENTITY_REGISTRY_PATH.read_text())
    data = dict(payload.get("data") or {})
    entities = list(data.get("entities") or [])
    deleted_entities = list(data.get("deleted_entities") or [])

    kept_entities = [entry for entry in entities if not _is_heima_entity(entry)]
    kept_deleted = [entry for entry in deleted_entities if not _is_heima_entity(entry)]
    removed_total = (len(entities) - len(kept_entities)) + (len(deleted_entities) - len(kept_deleted))

    if removed_total == 0:
        print("heima entity-registry scrub: nothing to remove")
        return 0

    payload["data"] = {
        **data,
        "entities": kept_entities,
        "deleted_entities": kept_deleted,
    }
    ENTITY_REGISTRY_PATH.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"heima entity-registry scrub: removed {removed_total} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
