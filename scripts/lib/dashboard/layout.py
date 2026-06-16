# lib/dashboard/layout.py
from typing import List, Dict, Any

def calculate_max_columns(entities: List[str], min_width_per_entity: int = 20) -> int:
    """
    Calcola il numero massimo di colonne in base alla lunghezza media dei nomi delle entità.
    Regola empirica: se la media supera `min_width_per_entity * 2`, riduci le colonne.
    """
    avg_length = sum(len(e) for e in entities) / len(entities) if entities else 0
    if avg_length > min_width_per_entity * 2:
        return max(1, 4 - int(avg_length // min_width_per_entity))
    return 4

def get_grid_layout(cards: List[str], max_columns: int = 4) -> str:
    """Genera la struttura YAML per un grid layout."""
    lines = [
        "  - type: grid",
        f"    columns: {max_columns}",
        "    cards:",
    ]
    for card in cards:
        lines.extend("      " + line if line else "" for line in card.splitlines())
    return "\n".join(lines)