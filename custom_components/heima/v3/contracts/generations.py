"""Configuration history record shapes; construction never proves activation."""

from dataclasses import dataclass
from typing import Literal, get_args

from .canonical_json import canonical_json_bytes
from .instants import EvidenceInstant, parse_instant

type ConfigurationLayer = Literal["layer2", "layer3", "layer4", "layer5", "layer6"]
_LAYER_ORDER = get_args(ConfigurationLayer.__value__)


def _text(value: str) -> None:
    if type(value) is not str:
        raise TypeError("Generation metadata requires primitive strings")
    canonical_json_bytes(value)


@dataclass(frozen=True, slots=True)
class LayerGenerationRef:
    layer: ConfigurationLayer
    generation_id: str
    definition_fingerprint: str

    def __post_init__(self) -> None:
        _text(self.layer)
        if self.layer not in _LAYER_ORDER:
            raise ValueError("Unknown configuration layer")
        _text(self.generation_id)
        _text(self.definition_fingerprint)


@dataclass(frozen=True, slots=True)
class ComposedGenerationManifest:
    composed_generation_id: str
    previous_composed_generation_id: str | None
    layers: tuple[LayerGenerationRef, ...]
    impact_fingerprint: str
    invalidated_dependents: tuple[str, ...]
    actor_ref: str
    effective_at: EvidenceInstant

    def __post_init__(self) -> None:
        _text(self.composed_generation_id)
        if self.previous_composed_generation_id is not None:
            _text(self.previous_composed_generation_id)
        if type(self.layers) is not tuple:
            raise TypeError("Layer generations require an immutable tuple")
        for ref in self.layers:
            if type(ref) is not LayerGenerationRef:
                raise TypeError("Layer generations require concrete references")
            LayerGenerationRef.__post_init__(ref)
        if tuple(ref.layer for ref in self.layers) != _LAYER_ORDER:
            raise ValueError("Manifest requires every layer once in canonical order")
        _text(self.impact_fingerprint)
        if type(self.invalidated_dependents) is not tuple:
            raise TypeError("Invalidated dependents require an immutable tuple")
        for dependent in self.invalidated_dependents:
            _text(dependent)
        _text(self.actor_ref)
        parse_instant(self.effective_at)
