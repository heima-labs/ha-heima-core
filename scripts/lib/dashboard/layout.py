# lib/dashboard/layout.py
from typing import List, Dict, Any

def calculate_max_columns(entities: List[str], min_width_per_entity: int = 20) -> int:
    """
    Compute the maximum number of columns based on the average length of entity names.
    Empirical rule: if the average exceeds `min_width_per_entity * 2`, reduce the columns.
    """
    avg_length = sum(len(e) for e in entities) / len(entities) if entities else 0
    if avg_length > min_width_per_entity * 2:
        return max(1, 4 - int(avg_length // min_width_per_entity))
    return 4

def get_grid_layout(cards: List[str], max_columns: int = 4) -> str:
    """Generate the YAML structure for a grid layout."""
    lines = [
        "  - type: grid",
        f"    columns: {max_columns}",
        "    cards:",
    ]
    for card in cards:
        lines.extend("      " + line if line else "" for line in card.splitlines())
    return "\n".join(lines)