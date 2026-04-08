"""Helpers for standardized learning diagnostics payloads."""

from __future__ import annotations

from typing import Any


def build_learning_diagnostics(
    *,
    pattern_id: str,
    analyzer_id: str,
    reaction_type: str,
    plugin_family: str,
    **fields: Any,
) -> dict[str, Any]:
    """Build a filtered learning diagnostics payload with common metadata."""
    diagnostics: dict[str, Any] = {
        "pattern_id": pattern_id,
        "analyzer_id": analyzer_id,
        "reaction_type": reaction_type,
        "plugin_family": plugin_family,
    }
    diagnostics.update(fields)
    return {key: value for key, value in diagnostics.items() if value not in (None, "", [])}
