#!/usr/bin/env python3
"""Generate a Heima developer dashboard from a live Home Assistant instance."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.ha_client import HAApiError, HAClient
from lib.dashboard.layout import get_grid_layout
from lib.dashboard.sections import (
    generate_runtime_section,
    generate_learning_section,
    generate_reactions_section,
    generate_room_section,
    generate_actions_section,
)
from lib.dashboard.filters import sort_entities, filter_entities_by_patterns
from lib.dashboard.cards import entity_card
from lib.dashboard.translations import translate
from lib.utils import slug, domain, object_id, friendly_name, _state_map, _existing, _heima_entities

HEIMA_ENTITY_PREFIXES = (
    "sensor.heima_",
    "binary_sensor.heima_",
    "button.heima_",
    "select.heima_",
    "switch.heima_",
    "number.heima_",
)

ROOM_SIGNAL_DOMAINS = {
    "binary_sensor",
    "sensor",
    "light",
    "switch",
    "fan",
    "media_player",
    "climate",
    "cover",
}

CORE_RUNTIME_ENTITIES = [
    "sensor.heima_house_state",
    "sensor.heima_house_state_reason",
    "sensor.heima_house_state_path",
    "binary_sensor.heima_anyone_home",
    "sensor.heima_people_count",
    "sensor.heima_people_home_list",
    "sensor.heima_security_state",
    "sensor.heima_security_reason",
    "sensor.heima_last_event",
    "sensor.heima_event_stats",
    "sensor.heima_event_store",
    "sensor.heima_reaction_proposals",
    "sensor.heima_reactions_active",
]

LEARNING_ENTITY_PATTERNS = ("learning", "proposal", "reaction", "event_store", "last_event")
ANOMALY_ENTITY_PATTERNS = ("anomaly", "invariant", "alert")
OCCUPANCY_ENTITY_PATTERNS = ("occupancy", "anonymous_presence", "anyone_home", "people_", "person_")
HEATING_ENTITY_PATTERNS = ("heating",)
SECURITY_ENTITY_PATTERNS = ("security",)

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL", ""))
    parser.add_argument("--ha-token", default=os.environ.get("HA_TOKEN", ""))
    parser.add_argument("--out", required=True, help="Output Lovelace YAML path.")
    parser.add_argument("--dump-inventory", help="Optional JSON path for the discovered dashboard inventory.")
    parser.add_argument(
        "--mode",
        choices=["generic", "test-lab"],
        default="generic",
        help="Dashboard flavor. test-lab adds lab fixture controls when present.",
    )
    parser.add_argument("--max-room-entities", type=int, default=24)
    parser.add_argument("--max-reactions", type=int, default=40)
    parser.add_argument(
        "--lang",
        choices=["it", "en"],
        default="it",
        help="Language for the dashboard.",
    )
    return parser.parse_args()

def discover_inventory(
    client: HAClient,
    *,
    mode: str,
    max_room_entities: int,
    max_reactions: int,
) -> Dict[str, Any]:
    """Discover entities and information for the dashboard."""
    entry_id = client.find_heima_entry_id()
    entry = client.get_entry(entry_id)
    states = client.all_states()
    state_by_id = _state_map(states)

    diagnostics = _diagnostics_root(client, entry_id)
    diagnostics_entry = diagnostics.get("entry", {})
    diagnostics_options = (
        diagnostics_entry.get("options", {}) if isinstance(diagnostics_entry, dict) else {}
    )
    options = (
        dict(diagnostics_options)
        if isinstance(diagnostics_options, dict) and diagnostics_options
        else dict(entry.get("options") or {})
    )

    heima_entities = _heima_entities(state_by_id)
    configured = _configured_reactions(options)
    rooms = _rooms(options)
    canonical_by_room = _event_canonicalizer_entities(diagnostics)
    reactions_by_room = _reaction_room_map(configured)

    room_cards = []
    for room in rooms:
        room_id = room["room_id"]
        entity_ids = set(canonical_by_room.get(room_id, []))
        entity_ids.update(_room_entities_from_config(room, state_by_id))
        entity_ids.update(_room_entities_from_heuristics(room, state_by_id))
        heima_room_candidates = [
            f"binary_sensor.heima_occupancy_{slug(room_id)}",
            f"sensor.heima_occupancy_{slug(room_id)}_source",
            f"sensor.heima_occupancy_{slug(room_id)}_last_change",
            f"binary_sensor.heima_lighting_hold_{slug(room_id)}",
            f"sensor.heima_room_{slug(room_id)}_view",
        ]
        entity_ids.update(_existing(heima_room_candidates, state_by_id))
        sorted_entities = sort_entities(list(entity_ids), state_by_id, max_room_entities)
        room_cards.append(
            {
                **{key: room[key] for key in ("room_id", "display_name", "area_id", "occupancy_mode")},
                "entities": sorted_entities,
                "entity_count": len(sorted_entities),
                "reactions": reactions_by_room.get(room_id, [])[:max_reactions],
                "reaction_count": len(reactions_by_room.get(room_id, [])),
            }
        )

    runtime = diagnostics.get("runtime", {}) if isinstance(diagnostics.get("runtime"), dict) else {}
    engine = runtime.get("engine", {}) if isinstance(runtime.get("engine"), dict) else {}
    plugins = runtime.get("plugins", {}) if isinstance(runtime.get("plugins"), dict) else {}
    learning_modules = engine.get("learning_modules", [])

    services = _services(client)
    common_entities = _existing(CORE_RUNTIME_ENTITIES, state_by_id)
    learning_entities = filter_entities_by_patterns(
        heima_entities,
        LEARNING_ENTITY_PATTERNS,
        exclude=set(common_entities),
    )
    anomaly_entities = filter_entities_by_patterns(heima_entities, ANOMALY_ENTITY_PATTERNS)
    occupancy_entities = filter_entities_by_patterns(heima_entities, OCCUPANCY_ENTITY_PATTERNS)
    heating_entities = filter_entities_by_patterns(heima_entities, HEATING_ENTITY_PATTERNS)
    security_entities = filter_entities_by_patterns(heima_entities, SECURITY_ENTITY_PATTERNS)
    active_reactions = _compact_runtime_reactions(
        engine.get("reactions", {}),
        configured,
        max_reactions=max_reactions,
    )

    test_lab_entities: List[str] = []
    if mode == "test-lab":
        test_lab_entities = sorted(
            entity_id
            for entity_id in state_by_id
            if entity_id.startswith(
                (
                    "input_boolean.test_heima_",
                    "input_number.test_heima_",
                    "binary_sensor.test_heima_",
                    "sensor.test_heima_",
                    "light.test_heima_",
                    "switch.test_heima_",
                    "script.test_heima_",
                )
            )
        )

    return {
        "entry_id": entry_id,
        "mode": mode,
        "generated_from": str(client.base_url).rstrip("/"),
        "rooms": room_cards,
        "heima_entities": heima_entities,
        "common_entities": common_entities,
        "learning_entities": learning_entities,
        "anomaly_entities": anomaly_entities,
        "occupancy_entities": occupancy_entities,
        "heating_entities": heating_entities,
        "security_entities": security_entities,
        "test_lab_entities": test_lab_entities,
        "configured_reactions": [
            {
                "reaction_id": reaction_id,
                "reaction_type": str(cfg.get("reaction_type") or cfg.get("reaction_class") or ""),
                "room_id": str(cfg.get("room_id") or ""),
                "enabled": cfg.get("enabled", True),
                "source_request": str(cfg.get("source_request") or ""),
            }
            for reaction_id, cfg in sorted(configured.items())
        ][:max_reactions],
        "reaction_count": len(configured),
        "diagnostics_summary": {
            "snapshot": _compact_snapshot(engine.get("snapshot", {})),
            "apply_plan_steps": len(engine.get("apply_plan", {}).get("steps", []))
            if isinstance(engine.get("apply_plan"), dict)
            else 0,
            "active_reactions": len(active_reactions),
            "active_reaction_rows": active_reactions,
            "muted_reactions": len(engine.get("muted_reactions", []))
            if isinstance(engine.get("muted_reactions"), list)
            else 0,
            "learning_modules": _compact_learning_modules(learning_modules),
            "lighting": _compact_lighting(engine.get("lighting", {})),
            "configured_reaction_summary": plugins.get("configured_reaction_summary", {}),
        },
        "actions": {
            "heima_command": "heima.command" in services,
            "test_reset": "script.test_heima_reset" in state_by_id,
        },
        "state_by_id": state_by_id,  # Added to pass it to the modules
    }

# Helper functions (moved here for now, could be moved to utils.py)
def _diagnostics_root(client: HAClient, entry_id: str) -> Dict[str, Any]:
    try:
        raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    except HAApiError:
        return {}
    if not isinstance(raw, dict):
        return {}
    data = raw.get("data")
    return dict(data) if isinstance(data, dict) else {}

def _configured_reactions(options: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    reactions = options.get("reactions")
    if not isinstance(reactions, dict):
        return {}
    configured = reactions.get("configured")
    if not isinstance(configured, dict):
        return {}
    return {
        str(reaction_id): dict(cfg)
        for reaction_id, cfg in configured.items()
        if isinstance(cfg, dict)
    }

def _rooms(options: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = options.get("rooms")
    if not isinstance(raw, list):
        return []
    rooms = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        room_id = str(item.get("room_id") or "").strip()
        if not room_id:
            continue
        rooms.append(
            {
                "room_id": room_id,
                "display_name": str(item.get("display_name") or room_id).strip(),
                "area_id": str(item.get("area_id") or "").strip(),
                "occupancy_mode": _room_occupancy_mode(item),
                "raw": dict(item),
            }
        )
    return rooms

def _room_occupancy_mode(room_cfg: Dict[str, Any]) -> str:
    explicit = str(room_cfg.get("occupancy_mode") or "").strip()
    if explicit:
        return explicit
    occupancy = room_cfg.get("occupancy")
    if isinstance(occupancy, dict):
        explicit = str(occupancy.get("mode") or "").strip()
        if explicit:
            return explicit
    return "unknown"

def _configured_entity_refs(value: Any) -> Set[str]:
    refs: Set[str] = set()
    if isinstance(value, str):
        if "." in value:
            refs.add(value)
        return refs
    if isinstance(value, list):
        for item in value:
            refs.update(_configured_entity_refs(item))
        return refs
    if isinstance(value, dict):
        for item in value.values():
            refs.update(_configured_entity_refs(item))
    return refs

def _room_entities_from_config(room: Dict[str, Any], state_by_id: Dict[str, Dict[str, Any]]) -> Set[str]:
    refs = _configured_entity_refs(room.get("raw", {}))
    return {entity_id for entity_id in refs if entity_id in state_by_id}

def _room_entities_from_heuristics(
    room: Dict[str, Any],
    state_by_id: Dict[str, Dict[str, Any]],
) -> Set[str]:
    room_id = slug(room["room_id"])
    display = slug(room["display_name"])
    tokens = {token for token in {room_id, display} if token}
    result: Set[str] = set()
    for entity_id, state in state_by_id.items():
        if domain(entity_id) not in ROOM_SIGNAL_DOMAINS:
            continue
        object_id_part = slug(object_id(entity_id))
        friendly = slug(friendly_name(state))
        if any(token and (token in object_id_part or token in friendly) for token in tokens):
            result.add(entity_id)
    return result

def _event_canonicalizer_entities(diagnostics: Dict[str, Any]) -> Dict[str, List[str]]:
    tracked = (
        diagnostics.get("runtime", {})
        .get("engine", {})
        .get("behaviors", {})
        .get("event_canonicalizer", {})
        .get("tracked_entities", {})
    )
    if not isinstance(tracked, dict):
        return {}
    by_room: Dict[str, List[str]] = {}
    for entity_id, payload in tracked.items():
        if not isinstance(payload, dict):
            continue
        room_id = str(payload.get("room_id") or "").strip()
        if room_id and "." in str(entity_id):
            by_room.setdefault(room_id, []).append(str(entity_id))
    return {room: sorted(set(entities)) for room, entities in by_room.items()}

def _reaction_room_map(configured: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for reaction_id, cfg in configured.items():
        room_id = str(cfg.get("room_id") or "").strip()
        if not room_id:
            continue
        result.setdefault(room_id, []).append(
            {
                "reaction_id": reaction_id,
                "reaction_type": str(cfg.get("reaction_type") or cfg.get("reaction_class") or ""),
                "enabled": cfg.get("enabled", True),
                "source_request": str(cfg.get("source_request") or ""),
            }
        )
    return result

def _services(client: HAClient) -> Set[str]:
    try:
        payload = client.get("/api/services")
    except HAApiError:
        return set()
    if not isinstance(payload, list):
        return set()
    result: Set[str] = set()
    for domain_payload in payload:
        if not isinstance(domain_payload, dict):
            continue
        domain_name = str(domain_payload.get("domain") or "")
        services = domain_payload.get("services")
        if not isinstance(services, dict):
            continue
        for service in services:
            result.add(f"{domain_name}.{service}")
    return result

def _compact_snapshot(snapshot: Any) -> Dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {}
    keys = [
        "house_state",
        "anyone_home",
        "people_count",
        "occupied_rooms",
        "security_state",
        "notes",
    ]
    return {key: snapshot.get(key) for key in keys if key in snapshot}

def _compact_learning_modules(modules: Any) -> List[Dict[str, Any]]:
    if not isinstance(modules, list):
        return []
    result = []
    for item in modules:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "module_id": item.get("module_id"),
                "ready": item.get("ready"),
                "min_support": item.get("min_support"),
                "analyzed_snapshots": item.get("analyzed_snapshots"),
                "slot_count": item.get("slot_count"),
                "pattern_count": item.get("pattern_count"),
                "approved_patterns": item.get("approved_patterns"),
            }
        )
    return result

def _compact_runtime_reactions(
    reactions: Any,
    configured: Dict[str, Dict[str, Any]],
    *,
    max_reactions: int,
) -> List[Dict[str, Any]]:
    if not isinstance(reactions, dict):
        return []
    rows = []
    for reaction_id, diagnostics in sorted(reactions.items()):
        diag = diagnostics if isinstance(diagnostics, dict) else {}
        cfg = configured.get(str(reaction_id), {})
        rows.append(
            {
                "reaction_id": str(reaction_id),
                "reaction_type": str(cfg.get("reaction_type") or cfg.get("reaction_class") or ""),
                "room_id": str(diag.get("room_id") or cfg.get("room_id") or ""),
                "fire_count": diag.get("fire_count", ""),
                "suppressed_count": diag.get("suppressed_count", ""),
                "last_fired_iso": diag.get("last_fired_iso") or "",
                "state": _runtime_reaction_state(diag),
            }
        )
    return rows[:max_reactions]

def _runtime_reaction_state(diag: Dict[str, Any]) -> str:
    for key in (
        "blocked_reason",
        "operational_state",
        "state",
        "selected_profile",
        "current_indoor_bucket",
    ):
        value = str(diag.get(key) or "").strip()
        if value:
            return value
    if diag.get("manual_override_active"):
        return "manual_override"
    if diag.get("manual_on_hold"):
        return "manual_on_hold"
    return "-"

def _compact_lighting(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    recent = payload.get("recent_entity_applies", {})
    return {
        "last_scene_by_room": payload.get("last_scene_by_room", {}),
        "last_apply_ts_by_room": payload.get("last_apply_ts_by_room", {}),
        "hold_seen_state_by_room": payload.get("hold_seen_state_by_room", {}),
        "recent_entity_applies": recent if isinstance(recent, dict) else {},
        "conflicts_last_eval": payload.get("conflicts_last_eval", []),
    }

def generate_dashboard_yaml(inventory: Dict[str, Any], lang: str = "it") -> str:
    """Generate the dashboard YAML."""
    title = translate("Heima Developer Debug", lang)
    state_by_id = inventory["state_by_id"]

    sections = [
        _section("Runtime", generate_runtime_section(inventory, state_by_id, lang), lang),
        _section("Learning And Events", generate_learning_section(inventory, state_by_id, lang), lang),
        _section("Runtime Reactions", generate_reactions_section(inventory, lang), lang),
    ]

    for room in inventory["rooms"]:
        sections.append(
            _section(
                f"Room {room['room_id']}",
                generate_room_section(room, state_by_id, lang),
                lang,
            )
        )

    action_cards = generate_actions_section(inventory, lang)
    if action_cards:
        if inventory["mode"] == "test-lab":
            sections.append(_section("Test Lab", action_cards, lang))
        else:
            sections.append(_section("Developer Actions", action_cards, lang))

    uncategorized = [
        entity_id
        for entity_id in inventory["heima_entities"]
        if entity_id not in set(inventory["common_entities"])
        | set(inventory["learning_entities"])
        | set(inventory["anomaly_entities"])
    ]
    if uncategorized:
        sections.append(
            _section(
                "All Heima Entities",
                [entity_card("Uncategorized Heima Entities", uncategorized[:80], state_by_id, lang)],
                lang,
            )
        )

    return "\n".join(
        [
            "# Generated by scripts/generate_debug_dashboard.py",
            f"title: {yaml_scalar(title)}",
            "path: heima-dev-debug",
            "icon: mdi:developer-board",
            "type: sections",
            "max_columns: 4",
            "sections:",
            *sections,
            "",
        ]
    )

def _section(title: str, cards: List[str], lang: str = "it") -> str:
    """Generate a dashboard section."""
    if not cards:
        return ""
    return get_grid_layout(cards)

def yaml_scalar(value: str) -> str:
    """Escape a value for YAML (duplicated from cards.py to avoid circular imports)."""
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'

def main() -> int:
    args = _parse_args()
    if not args.ha_url or not args.ha_token:
        print("ERROR: --ha-url and --ha-token are required, or source scripts/.env.", file=sys.stderr)
        return 2

    client = HAClient(args.ha_url, args.ha_token, timeout_s=30)
    inventory = discover_inventory(
        client,
        mode=args.mode,
        max_room_entities=max(1, args.max_room_entities),
        max_reactions=max(1, args.max_reactions),
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(generate_dashboard_yaml(inventory, args.lang), encoding="utf-8")

    if args.dump_inventory:
        inventory_path = Path(args.dump_inventory)
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(f"Generated dashboard: {out}", file=sys.stderr)
    if args.dump_inventory:
        print(f"Generated inventory: {args.dump_inventory}", file=sys.stderr)
    print(
        f"Rooms={len(inventory['rooms'])} Heima entities={len(inventory['heima_entities'])} "
        f"Reactions={inventory['reaction_count']}",
        file=sys.stderr,
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())