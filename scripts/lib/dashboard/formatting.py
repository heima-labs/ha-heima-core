# lib/dashboard/formatting.py
import json
from typing import Any, Dict
from ..utils import domain, object_id, friendly_name
from .translations import translate

# Mapping to shorten entity names
ENTITY_NAME_REPLACEMENTS = {
    "heima_": "",
    "_last_change": " (⏱️)",
    "_source": " (📡)",
    "_count": " (🔢)",
    "_state": " Stato",
    "_reason": " Motivo",
    "_occupancy": " Presenza",
    "_temperature": " Temp.",
    "_humidity": " Umidità",
    "_light": " Luce",
    "_security": " Sicurezza",
    "_people": " Persone",
    "_house": " Casa",
    "_room": " Stanza",
}

# Mapping to format values
VALUE_FORMATTERS = {
    "sensor": {
        "default": lambda v, u: f"{float(v):.1f} {u}" if u else str(v),
        "temperature": lambda v, u: f"{float(v):.1f}°C",
        "humidity": lambda v, u: f"{float(v):.1f}%",
    },
    "binary_sensor": {
        "default": lambda v, u: "ON" if v == "on" else "OFF",
    },
}

def format_entity_name(entity_id: str, state: Dict[str, Any], lang: str = "it") -> str:
    """Format an entity's name in a human-readable way."""
    # Use friendly_name if available
    name = friendly_name(state)
    if name and name != entity_id:
        return name

    # Apply replacements
    name = entity_id
    for pattern, replacement in ENTITY_NAME_REPLACEMENTS.items():
        name = name.replace(pattern, replacement)

    # Translate known parts of the name
    parts = name.split("_")
    translated_parts = []
    for part in parts:
        translated = translate(part.capitalize(), lang)
        if translated != part.capitalize():
            translated_parts.append(translated)
        else:
            translated_parts.append(part)
    name = " ".join(translated_parts).strip()

    # Remove multiple spaces
    return " ".join(name.split())

def format_entity_value(entity_id: str, state: Dict[str, Any], lang: str = "it") -> str:
    """Format an entity's value based on its domain and attributes."""
    domain_name = domain(entity_id)
    state_value = state.get("state")
    attributes = state.get("attributes", {})

    # Domain-specific formatting
    if domain_name in VALUE_FORMATTERS:
        formatter = VALUE_FORMATTERS[domain_name].get(
            object_id(entity_id).split("_")[0],  # E.g. "temperature" from "sensor.temperature_room"
            VALUE_FORMATTERS[domain_name]["default"]
        )
        unit = attributes.get("unit_of_measurement", "")
        try:
            return formatter(state_value, unit)
        except (ValueError, TypeError):
            pass

    # Generic formatting
    if isinstance(state_value, (int, float)):
        return f"{state_value:.1f}"
    elif isinstance(state_value, str):
        if state_value.startswith(("202", "197")):  # ISO date/time
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(state_value.replace("Z", "+00:00"))
                return dt.strftime("%d/%m %H:%M")
            except ValueError:
                pass
        return state_value
    elif isinstance(state_value, dict):
        return json.dumps(state_value, ensure_ascii=False)
    return str(state_value)