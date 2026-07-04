# lib/dashboard/cards.py
from typing import List, Dict, Any, Optional
from ..utils import slug, friendly_name, domain
from .formatting import format_entity_name, format_entity_value
from .translations import translate

def yaml_scalar(value: str) -> str:
    """Escape a value for YAML."""
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'

def entity_card(
    title: str,
    entities: List[str],
    state_by_id: Dict[str, Dict[str, Any]],
    lang: str = "it",
    max_columns: int = 4,
) -> str:
    """Generate an 'entities'-type card with formatted names and values."""
    if not entities:
        return markdown_card(title, "_Nessuna entità corrispondente._", lang)

    # Calculate the layout
    max_cols = calculate_max_columns(entities)

    lines = [
        "- type: entities",
        f"  title: {yaml_scalar(translate(title, lang))}",
        "  show_header_toggle: false",
        f"  columns: {max_cols}",
        "  entities:",
    ]
    for entity_id in entities:
        state = state_by_id.get(entity_id, {})
        name = format_entity_name(entity_id, state, lang)
        value = format_entity_value(entity_id, state, lang)
        lines.append(f"    - entity: {entity_id}")
        if name != entity_id:  # If the name was formatted
            lines.append(f"      name: {yaml_scalar(name)}")
        if value:  # Add the value as secondary_info
            lines.append(f"      secondary_info: {yaml_scalar(value)}")
    return "\n".join(lines)

def markdown_card(title: str, content: str, lang: str = "it") -> str:
    """Generate a 'markdown'-type card."""
    translated_title = translate(title, lang)
    body = "\n".join(f"    {line}" if line else "" for line in content.splitlines())
    return "\n".join(
        [
            "- type: markdown",
            f"  title: {yaml_scalar(translated_title)}",
            "  content: |",
            body or "    ",
        ]
    )

def button_card(
    name: str,
    icon: str,
    service: str,
    data: Optional[Dict[str, Any]] = None,
    lang: str = "it",
) -> str:
    """Generate a 'button'-type card."""
    translated_name = translate(name, lang)
    lines = [
        "- type: button",
        f"  name: {yaml_scalar(translated_name)}",
        f"  icon: {icon}",
        "  tap_action:",
        "    action: call-service",
        f"    service: {service}",
    ]
    if data:
        lines.append("    data:")
        for key, value in data.items():
            lines.append(f"      {key}: {yaml_scalar(str(value))}")
    return "\n".join(lines)

def history_card(
    title: str,
    entities: List[str],
    state_by_id: Dict[str, Dict[str, Any]],
    lang: str = "it",
    hours: int = 12,
    max_columns: int = 4,
) -> str:
    """Generate a 'history-graph'-type card."""
    if not entities:
        return markdown_card(title, "_Nessuna entità con storia._", lang)

    # Only keep entities with a domain supported by history-graph
    supported_domains = {"sensor", "binary_sensor", "light"}
    filtered_entities = [
        e for e in entities
        if domain(e) in supported_domains
    ][:8]  # Limit to 8 entities for performance

    lines = [
        "- type: history-graph",
        f"  title: {yaml_scalar(translate(title, lang))}",
        f"  hours_to_show: {hours}",
        "  refresh_interval: 60",
        "  entities:",
    ]
    for entity_id in filtered_entities:
        lines.append(f"    - entity: {entity_id}")
    return "\n".join(lines)

from .layout import calculate_max_columns