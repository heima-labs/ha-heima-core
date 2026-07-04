# lib/dashboard/sections.py
from typing import List, Dict, Any
from .cards import entity_card, markdown_card, button_card, history_card
from .formatting import format_entity_name, format_entity_value
from .filters import sort_entities, filter_entities_by_patterns
from .translations import translate
from ..utils import domain

def generate_runtime_section(
    inventory: Dict[str, Any],
    state_by_id: Dict[str, Dict[str, Any]],
    lang: str = "it",
) -> List[str]:
    """Generate the 'Runtime' section."""
    common = inventory["common_entities"]
    occupancy = inventory["occupancy_entities"]
    diagnostics_markdown = _generate_diagnostics_markdown(inventory, lang)

    cards = [
        markdown_card("Runtime Diagnostics", diagnostics_markdown, lang),
        entity_card("Core Runtime Entities", common, state_by_id, lang),
        history_card(
            "Runtime Trend",
            [e for e in common if domain(e) in {"sensor", "binary_sensor"}],
            state_by_id,
            lang,
        ),
        entity_card("Occupancy And People", occupancy[:30], state_by_id, lang),
    ]
    return cards

def generate_learning_section(
    inventory: Dict[str, Any],
    state_by_id: Dict[str, Dict[str, Any]],
    lang: str = "it",
) -> List[str]:
    """Generate the 'Learning And Events' section."""
    learning = inventory["learning_entities"]
    anomalies = inventory["anomaly_entities"]
    heating = inventory["heating_entities"]
    security = inventory["security_entities"]

    cards = [
        entity_card("Learning, Events, Proposals", learning[:30], state_by_id, lang),
        entity_card("Anomalies And Alerts", anomalies[:30], state_by_id, lang),
        entity_card("Heating", heating[:30], state_by_id, lang),
        entity_card("Security", security[:30], state_by_id, lang),
    ]
    return cards

def generate_reactions_section(
    inventory: Dict[str, Any],
    lang: str = "it",
) -> List[str]:
    """Generate the 'Runtime Reactions' section."""
    runtime_reactions_markdown = _generate_runtime_reactions_markdown(inventory, lang)
    reactions_markdown = _generate_reactions_markdown(inventory, lang)
    lighting_markdown = _generate_lighting_markdown(inventory, lang)

    cards = [
        markdown_card("Active Runtime Reactions", runtime_reactions_markdown, lang),
        markdown_card("Configured Reactions", reactions_markdown, lang),
        markdown_card("Lighting Runtime", lighting_markdown, lang),
    ]
    return cards

def generate_room_section(
    room: Dict[str, Any],
    state_by_id: Dict[str, Dict[str, Any]],
    lang: str = "it",
) -> List[str]:
    """Generate the section for a single room."""
    room_markdown = _generate_room_markdown(room, lang)
    entities = sort_entities(room["entities"], state_by_id)

    cards = [
        markdown_card(f"Room: {room['display_name']}", room_markdown, lang),
        entity_card(f"{room['display_name']} Entities", entities, state_by_id, lang),
        history_card(
            f"{room['display_name']} Trend",
            [e for e in entities if domain(e) in {"sensor", "binary_sensor", "light"}],
            state_by_id,
            lang,
            hours=8,
        ),
    ]
    return cards

def generate_actions_section(
    inventory: Dict[str, Any],
    lang: str = "it",
) -> List[str]:
    """Generate the 'Developer Actions' or 'Test Lab' section."""
    action_cards = []
    actions = inventory["actions"]

    if actions.get("heima_command"):
        action_cards.append(
            button_card(
                "Recompute Now",
                "mdi:refresh",
                "heima.command",
                {"command": "recompute_now"},
                lang,
            )
        )
        action_cards.append(
            button_card(
                "Reload Heima Entry",
                "mdi:reload",
                "heima.command",
                {"command": "dev_reload"},
                lang,
            )
        )
    if actions.get("test_reset"):
        action_cards.append(
            button_card("Reset Test Lab", "mdi:restore", "script.test_heima_reset", lang=lang)
        )

    if inventory["mode"] == "test-lab":
        test_lab_entities = inventory["test_lab_entities"]
        return [
            entity_card("Test Lab Entities", test_lab_entities[:80], inventory["state_by_id"], lang),
            *action_cards,
        ]
    elif action_cards:
        return action_cards
    return []

def _generate_diagnostics_markdown(inventory: Dict[str, Any], lang: str) -> str:
    """Generate the markdown for diagnostics."""
    summary = inventory["diagnostics_summary"]
    snapshot = summary.get("snapshot", {})

    lines = [
        f"Generato da `{inventory['generated_from']}`.",
        "",
        "### Snapshot",
        _generate_table(["Campo", "Valore"], [[translate(k, lang), _format_snapshot_value(v)] for k, v in snapshot.items()], lang),
        "",
        "### Contatori Runtime",
        _generate_table(
            ["Metrica", "Valore"],
            [
                ["Reazioni configurate", inventory["reaction_count"]],
                ["Reazioni attive", summary.get("active_reactions", 0)],
                ["Reazioni silenziate", summary.get("muted_reactions", 0)],
                ["Passaggi piano applicazione", summary.get("apply_plan_steps", 0)],
            ],
            lang,
        ),
    ]

    modules = summary.get("learning_modules", [])
    if modules:
        lines.extend(
            [
                "",
                "### Moduli di Apprendimento",
                _generate_table(
                    ["Modulo", "Pronto", "Supporto", "Snapshot", "Slot/Pattern"],
                    [
                        [
                            item.get("module_id", ""),
                            "✅" if item.get("ready") else "❌",
                            item.get("min_support", ""),
                            item.get("analyzed_snapshots", ""),
                            item.get("slot_count") or item.get("pattern_count") or item.get("approved_patterns", ""),
                        ]
                        for item in modules
                    ],
                    lang,
                ),
            ]
        )
    return "\n".join(lines)

def _generate_table(headers: List[str], rows: List[List[Any]], lang: str) -> str:
    """Generate a markdown table with translated headers."""
    translated_headers = [translate(h, lang) for h in headers]
    header = "| " + " | ".join(translated_headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(_md_cell(value) for value in row) + " |")
    return "\n".join([header, sep, *body])

def _md_cell(value: Any) -> str:
    """Format a cell for markdown."""
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")

def _format_snapshot_value(value: Any) -> str:
    """Format a snapshot value."""
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)

def _generate_runtime_reactions_markdown(inventory: Dict[str, Any], lang: str) -> str:
    """Generate the markdown for active runtime reactions."""
    rows = [
        [
            item["reaction_id"],
            item["reaction_type"] or "-",
            item["room_id"] or "-",
            item["fire_count"],
            item["suppressed_count"],
            item["state"],
        ]
        for item in inventory["diagnostics_summary"].get("active_reaction_rows", [])
    ]
    headers = ["ID", "Tipo", "Stanza", "Attivazioni", "Soppressioni", "Stato"]
    return _generate_table(headers, rows, lang)

def _generate_reactions_markdown(inventory: Dict[str, Any], lang: str) -> str:
    """Generate the markdown for configured reactions."""
    rows = [
        [
            item["reaction_id"],
            item["reaction_type"],
            item["room_id"] or "-",
            "✅" if item["enabled"] else "❌",
            item["source_request"] or "-",
        ]
        for item in inventory["configured_reactions"]
    ]
    headers = ["ID", "Tipo", "Stanza", "Attiva", "Sorgente"]
    return _generate_table(headers, rows, lang)

def _generate_lighting_markdown(inventory: Dict[str, Any], lang: str) -> str:
    """Generate the markdown for the lighting runtime."""
    lighting = inventory["diagnostics_summary"].get("lighting", {})
    rows = []
    for room_id, value in sorted(dict(lighting.get("last_scene_by_room") or {}).items()):
        rows.append([f"Ultima scena {room_id}", value])
    for room_id, value in sorted(dict(lighting.get("hold_seen_state_by_room") or {}).items()):
        rows.append([f"Stato hold {room_id}", value])
    recent = lighting.get("recent_entity_applies", {})
    if isinstance(recent, dict):
        for entity_id, payload in sorted(recent.items()):
            item = payload if isinstance(payload, dict) else {}
            rows.append(
                [
                    f"Applicazione recente {entity_id}",
                    f"{item.get('action', '-')}, stanza={item.get('room_id', '-')}",
                ]
            )
    conflicts = lighting.get("conflicts_last_eval", [])
    if isinstance(conflicts, list):
        rows.append(["Conflitti", len(conflicts)])
    headers = ["Metrica", "Valore"]
    return _generate_table(headers, rows, lang)

def _generate_room_markdown(room: Dict[str, Any], lang: str) -> str:
    """Generate the markdown for a room."""
    rows = [
        ["Stanza", room["room_id"]],
        ["Nome visualizzato", room["display_name"]],
        ["Area", room["area_id"] or "-"],
        ["Modalità presenza", room["occupancy_mode"]],
        ["Entità rilevate", room["entity_count"]],
        ["Reazioni configurate", room["reaction_count"]],
    ]
    if room["reactions"]:
        rows.extend(
            [
                [f"Reazione {index}", f"{item['reaction_type']} `{item['reaction_id']}`"]
                for index, item in enumerate(room["reactions"], start=1)
            ]
        )
    headers = ["Campo", "Valore"]
    return _generate_table(headers, rows, lang)