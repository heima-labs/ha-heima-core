"""Declarative catalog for room-scoped composite learning patterns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .composite import CompositePatternSpec


DescriptionBuilder = Callable[[str, int, int], str]
SuggestedConfigBuilder = Callable[[str, list[Any]], dict[str, Any]]
ConfidenceBuilder = Callable[[list[Any]], float]
DiagnosticsBuilder = Callable[[str, list[Any], list[Any], CompositePatternSpec], dict[str, Any]]


@dataclass(frozen=True)
class CompositeLearningPatternDefinition:
    """Declarative contract for one reviewable room-scoped composite pattern."""

    pattern_id: str
    analyzer_id: str
    reaction_type: str
    fingerprint_key: str
    matcher_spec: CompositePatternSpec
    min_occurrences: int
    min_weeks: int
    description_builder: DescriptionBuilder
    suggested_config_builder: SuggestedConfigBuilder
    confidence_builder: ConfidenceBuilder
    diagnostics_builder: DiagnosticsBuilder | None = None
