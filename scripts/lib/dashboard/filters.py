# lib/dashboard/filters.py
from typing import List, Dict, Any, Set, Tuple, Optional
from ..utils import domain, object_id, slug

# Patterns to categorize entities
LEARNING_PATTERNS = ("learning", "proposal", "reaction", "event_store", "last_event")
ANOMALY_PATTERNS = ("anomaly", "invariant", "alert")
OCCUPANCY_PATTERNS = ("occupancy", "anonymous_presence", "anyone_home", "people_", "person_")
HEATING_PATTERNS = ("heating",)
SECURITY_PATTERNS = ("security",)

# Domain priority (higher = more important)
DOMAIN_PRIORITY = {
    "binary_sensor": 4,  # State (e.g. presence)
    "sensor": 3,         # Data (e.g. temperature)
    "switch": 2,         # Control
    "light": 2,
    "climate": 2,
    "button": 1,
    "select": 1,
    "number": 1,
}

# Pattern priority (higher = more important)
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
    """Compute an entity's priority based on domain and pattern."""
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
    """Sort entities by priority and name, and truncate to max_entities."""
    # Assign priority and sort
    entities_with_priority = [
        (entity_id, get_entity_priority(entity_id))
        for entity_id in entity_ids
    ]
    entities_with_priority.sort(key=lambda x: (-x[1], x[0]))  # Sort by priority (desc) and name (asc)

    # Extract the sorted IDs
    sorted_entities = [e[0] for e in entities_with_priority]
    return sorted_entities[:max_entities]

def filter_entities_by_patterns(
    entity_ids: List[str],
    patterns: Tuple[str, ...],
    *,
    exclude: Optional[Set[str]] = None,
) -> List[str]:
    """Filter entities based on patterns in their object_id."""
    excluded = exclude or set()
    result = []
    for entity_id in entity_ids:
        if entity_id in excluded:
            continue
        haystack = object_id(entity_id)
        if any(pattern in haystack for pattern in patterns):
            result.append(entity_id)
    return sorted(result)