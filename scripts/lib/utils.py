# lib/utils.py
import re
from typing import Any, Dict, List, Optional, Set, Tuple

def domain(entity_id: str) -> str:
    """Extract the domain from an entity_id (e.g. 'sensor' from 'sensor.temperature')."""
    return entity_id.split(".", 1)[0] if "." in entity_id else ""

def object_id(entity_id: str) -> str:
    """Extract the object_id from an entity_id (e.g. 'temperature' from 'sensor.temperature')."""
    return entity_id.split(".", 1)[1] if "." in entity_id else entity_id

def slug(value: str) -> str:
    """Convert a value into a slug (e.g. 'Living Room' -> 'living_room')."""
    text = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    return re.sub(r"_+", "_", text).strip("_")

def friendly_name(state: Dict[str, Any]) -> str:
    """Return an entity's friendly_name, or the entity_id if unavailable."""
    attrs = state.get("attributes")
    if isinstance(attrs, dict):
        name = str(attrs.get("friendly_name") or "").strip()
        if name:
            return name
    return str(state.get("entity_id") or "")


def _state_map(states: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Convert a list of states into an entity_id -> state dictionary."""
    return {str(state.get("entity_id")): state for state in states if state.get("entity_id")}


def _existing(candidates: List[str], state_by_id: Dict[str, Dict[str, Any]]) -> List[str]:
    """Filter candidates, returning only those present in state_by_id."""
    return [e for e in candidates if e in state_by_id]


HEIMA_ENTITY_PREFIXES = (
    "sensor.heima_",
    "binary_sensor.heima_",
    "button.heima_",
    "select.heima_",
    "switch.heima_",
    "number.heima_",
)


def _heima_entities(state_by_id: Dict[str, Dict[str, Any]]) -> List[str]:
    """Return all Heima entities from state_by_id."""
    return [
        entity_id for entity_id in state_by_id
        if any(entity_id.startswith(prefix) for prefix in HEIMA_ENTITY_PREFIXES)
    ]