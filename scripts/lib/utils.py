# lib/utils.py
import re
from typing import Any, Dict, List, Optional, Set, Tuple

def domain(entity_id: str) -> str:
    """Estrae il dominio da un entity_id (es. 'sensor' da 'sensor.temperature')."""
    return entity_id.split(".", 1)[0] if "." in entity_id else ""

def object_id(entity_id: str) -> str:
    """Estrae l'object_id da un entity_id (es. 'temperature' da 'sensor.temperature')."""
    return entity_id.split(".", 1)[1] if "." in entity_id else entity_id

def slug(value: str) -> str:
    """Converte un valore in uno slug (es. 'Soggiorno' -> 'soggiorno')."""
    text = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    return re.sub(r"_+", "_", text).strip("_")

def friendly_name(state: Dict[str, Any]) -> str:
    """Restituisce il friendly_name di un'entità o l'entity_id se non disponibile."""
    attrs = state.get("attributes")
    if isinstance(attrs, dict):
        name = str(attrs.get("friendly_name") or "").strip()
        if name:
            return name
    return str(state.get("entity_id") or "")


def _state_map(states: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Converte una lista di stati in un dizionario entity_id -> state."""
    return {str(state.get("entity_id")): state for state in states if state.get("entity_id")}


def _existing(candidates: List[str], state_by_id: Dict[str, Dict[str, Any]]) -> List[str]:
    """Filtra i candidati, restituendo solo quelli presenti in state_by_id."""
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
    """Restituisce tutte le entità Heima da state_by_id."""
    return [
        entity_id for entity_id in state_by_id
        if any(entity_id.startswith(prefix) for prefix in HEIMA_ENTITY_PREFIXES)
    ]