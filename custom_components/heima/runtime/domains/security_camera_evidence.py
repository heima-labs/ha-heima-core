"""Security-owned camera evidence provider for the runtime DAG."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant

from ..normalization.service import InputNormalizer


@dataclass(frozen=True)
class CameraEvidenceRecord:
    """Single normalized camera-derived evidence item."""

    source_id: str
    role: str
    kind: str
    source_entity_id: str
    active: bool
    confidence: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SecurityCameraEvidenceResult:
    """Structured output of the camera evidence provider."""

    configured_sources: list[dict[str, Any]] = field(default_factory=list)
    active_evidence: list[CameraEvidenceRecord] = field(default_factory=list)
    unavailable_sources: list[dict[str, Any]] = field(default_factory=list)
    return_home_hint: bool = False
    security_breach_candidates: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "configured_sources": [dict(item) for item in self.configured_sources],
            "active_evidence": [item.as_dict() for item in self.active_evidence],
            "unavailable_sources": [dict(item) for item in self.unavailable_sources],
            "return_home_hint": self.return_home_hint,
            "security_breach_candidates": [dict(item) for item in self.security_breach_candidates],
            "configured_source_count": len(self.configured_sources),
            "active_evidence_count": len(self.active_evidence),
            "unavailable_source_count": len(self.unavailable_sources),
        }


class SecurityCameraEvidenceProvider:
    """Computes reusable camera-derived evidence for downstream domains."""

    _SUPPORTED_EVIDENCE_FIELDS: tuple[tuple[str, str], ...] = (
        ("motion", "motion_entity"),
        ("person", "person_entity"),
        ("vehicle", "vehicle_entity"),
    )

    def __init__(self, hass: HomeAssistant, normalizer: InputNormalizer) -> None:
        self._hass = hass
        self._normalizer = normalizer
        self._last_result = SecurityCameraEvidenceResult()

    def reset(self) -> None:
        """Clear cached diagnostics on options reload."""
        self._last_result = SecurityCameraEvidenceResult()

    def diagnostics(self) -> dict[str, Any]:
        return self._last_result.as_dict()

    def compute(self, security_cfg: dict[str, Any]) -> SecurityCameraEvidenceResult:
        """Read configured camera sources and normalize basic evidence state."""
        raw_sources = security_cfg.get("camera_evidence_sources", [])
        if not isinstance(raw_sources, list):
            self._last_result = SecurityCameraEvidenceResult()
            return self._last_result

        configured_sources: list[dict[str, Any]] = []
        active_evidence: list[CameraEvidenceRecord] = []
        unavailable_sources: list[dict[str, Any]] = []

        for raw in raw_sources:
            if not isinstance(raw, dict):
                continue
            source = self._normalize_source(raw)
            if not source["enabled"]:
                continue
            configured_sources.append(source)
            for kind, field_name in self._SUPPORTED_EVIDENCE_FIELDS:
                entity_id = str(source.get(field_name) or "").strip()
                if not entity_id:
                    continue
                observation = self._normalizer.boolean_signal(entity_id)
                if not observation.available:
                    unavailable_sources.append(
                        {
                            "source_id": source["id"],
                            "role": source["role"],
                            "kind": kind,
                            "entity_id": entity_id,
                            "reason": observation.reason,
                        }
                    )
                    continue
                if observation.state != "on":
                    continue
                active_evidence.append(
                    CameraEvidenceRecord(
                        source_id=source["id"],
                        role=source["role"],
                        kind=kind,
                        source_entity_id=entity_id,
                        active=True,
                        confidence=int(observation.confidence),
                        reason=str(observation.reason or "state_match_on"),
                    )
                )

        self._last_result = SecurityCameraEvidenceResult(
            configured_sources=configured_sources,
            active_evidence=active_evidence,
            unavailable_sources=unavailable_sources,
            return_home_hint=False,
            security_breach_candidates=[],
        )
        return self._last_result

    @staticmethod
    def _normalize_source(raw: dict[str, Any]) -> dict[str, Any]:
        source_id = str(raw.get("id") or "").strip()
        role = str(raw.get("role") or "").strip()
        return {
            "id": source_id,
            "display_name": str(raw.get("display_name") or "").strip(),
            "enabled": bool(raw.get("enabled", True)),
            "role": role,
            "motion_entity": str(raw.get("motion_entity") or "").strip(),
            "person_entity": str(raw.get("person_entity") or "").strip(),
            "vehicle_entity": str(raw.get("vehicle_entity") or "").strip(),
            "contact_entity": str(raw.get("contact_entity") or "").strip(),
            "return_home_contributor": bool(raw.get("return_home_contributor", False)),
            "security_priority": str(raw.get("security_priority") or "").strip() or "normal",
        }
