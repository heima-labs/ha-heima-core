# lib/dashboard/filters.py
from typing import List, Dict, Any, Set, Tuple, Optional
from ..utils import domain, object_id, slug

# Pattern per categorizzare le entità
LEARNING_PATTERNS = ("learning", "proposal", "reaction", "event_store", "last_event")
ANOMALY_PATTERNS = ("anomaly", "invariant", "alert")
OCCUPANCY_PATTERNS = ("occupancy", "anonymous_presence", "anyone_home", "people_", "person_")
HEATING_PATTERNS = ("heating",)
SECURITY_PATTERNS = ("security",)

# Priorità dei domini (più alto = più importante)
DOMAIN_PRIORITY = {
    "binary_sensor": 4,  # Stato (es. presenza)
    "sensor": 3,         # Dati (es. temperatura)
    "switch": 2,         # Controllo
    "light": 2,
    "climate": 2,
    "button": 1,
    "select": 1,
    "number": 1,
}

# Priorità dei pattern (più alto = più importante)
PATTERN_PRIORITY = {
    "house_state": 10,
    "security_state": 10,
    "anyone_home": 9,
    "people_count": 9,
    "occupancy": 8,
    "temperature": 7,
    "humidity": 6,
}

def get_entity_priority(entity_id: str) -> int:
    """Calcola la priorità di un'entità in base a dominio e pattern."""
    priority = DOMAIN_PRIORITY.get(domain(entity_id), 0)
    object_id_part = object_id(entity_id)

    for pattern, pattern_priority in PATTERN_PRIORITY.items():
        if pattern in object_id_part:
            priority += pattern_priority
            break

    return priority

def sort_entities(
    entity_ids: List[str],
    state_by_id: Dict[str, Dict[str, Any]],
    max_entities: int = 30,
) -> List[str]:
    """Ordina le entità per priorità e nome, e le troncate a max_entities."""
    # Assegna priorità e ordina
    entities_with_priority = [
        (entity_id, get_entity_priority(entity_id))
        for entity_id in entity_ids
    ]
    entities_with_priority.sort(key=lambda x: (-x[1], x[0]))  # Ordina per priorità (desc) e nome (asc)

    # Estrai gli ID ordinati
    sorted_entities = [e[0] for e in entities_with_priority]
    return sorted_entities[:max_entities]

def filter_entities_by_patterns(
    entity_ids: List[str],
    patterns: Tuple[str, ...],
    *,
    exclude: Optional[Set[str]] = None,
) -> List[str]:
    """Filtra le entità in base a pattern nel loro object_id."""
    excluded = exclude or set()
    result = []
    for entity_id in entity_ids:
        if entity_id in excluded:
            continue
        haystack = object_id(entity_id)
        if any(pattern in haystack for pattern in patterns):
            result.append(entity_id)
    return sorted(result)