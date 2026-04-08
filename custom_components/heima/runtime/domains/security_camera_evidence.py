"""Security-owned camera evidence provider for the runtime DAG."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from ..normalization.service import InputNormalizer


@dataclass(frozen=True)
class CameraEvidenceRecord:
    """Single normalized camera-derived evidence item."""

    source_id: str
    display_name: str
    role: str
    kind: str
    source_entities: list[str]
    active: bool
    confidence: int
    reason: str
    last_seen_ts: str | None
    security_priority: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SecurityCameraEvidenceResult:
    """Structured output of the camera evidence provider."""

    configured_sources: list[dict[str, Any]] = field(default_factory=list)
    active_evidence: list[CameraEvidenceRecord] = field(default_factory=list)
    unavailable_sources: list[dict[str, Any]] = field(default_factory=list)
    return_home_hint: bool = False
    return_home_hint_reasons: list[dict[str, Any]] = field(default_factory=list)
    security_breach_candidates: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        active_by_role: dict[str, int] = {}
        active_by_kind: dict[str, int] = {}
        source_status_counts: dict[str, int] = {}
        for item in self.active_evidence:
            active_by_role[item.role] = active_by_role.get(item.role, 0) + 1
            active_by_kind[item.kind] = active_by_kind.get(item.kind, 0) + 1
        for source in self.configured_sources:
            status = str(source.get("status") or "unknown")
            source_status_counts[status] = source_status_counts.get(status, 0) + 1
        return {
            "configured_sources": [dict(item) for item in self.configured_sources],
            "active_evidence": [item.as_dict() for item in self.active_evidence],
            "unavailable_sources": [dict(item) for item in self.unavailable_sources],
            "return_home_hint": self.return_home_hint,
            "return_home_hint_reasons": [dict(item) for item in self.return_home_hint_reasons],
            "security_breach_candidates": [dict(item) for item in self.security_breach_candidates],
            "configured_source_count": len(self.configured_sources),
            "active_evidence_count": len(self.active_evidence),
            "unavailable_source_count": len(self.unavailable_sources),
            "active_by_role": active_by_role,
            "active_by_kind": active_by_kind,
            "source_status_counts": source_status_counts,
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
        return_home_hint_reasons: list[dict[str, Any]] = []

        for raw in raw_sources:
            if not isinstance(raw, dict):
                continue
            source = self._normalize_source(raw)
            if not source["enabled"]:
                continue
            source_bound_kinds: list[str] = []
            source_active_kinds: list[str] = []
            source_unavailable_kinds: list[str] = []
            source_last_seen_ts: str | None = None
            for kind, field_name in self._SUPPORTED_EVIDENCE_FIELDS:
                entity_id = str(source.get(field_name) or "").strip()
                if not entity_id:
                    continue
                source_bound_kinds.append(kind)
                observation = self._normalizer.boolean_signal(entity_id)
                evidence_last_seen_ts = self._entity_last_seen_ts(entity_id) or observation.ts
                if not observation.available:
                    source_unavailable_kinds.append(kind)
                    unavailable_sources.append(
                        {
                            "source_id": source["id"],
                            "display_name": source["display_name"],
                            "role": source["role"],
                            "kind": kind,
                            "entity_id": entity_id,
                            "reason": observation.reason,
                        }
                    )
                    continue
                if observation.state != "on":
                    continue
                source_active_kinds.append(kind)
                source_last_seen_ts = self._max_ts(source_last_seen_ts, evidence_last_seen_ts)
                active_evidence.append(
                    CameraEvidenceRecord(
                        source_id=source["id"],
                        display_name=source["display_name"] or source["id"],
                        role=source["role"],
                        kind=kind,
                        source_entities=[entity_id],
                        active=True,
                        confidence=int(observation.confidence),
                        reason=str(observation.reason or "state_match_on"),
                        last_seen_ts=evidence_last_seen_ts,
                        security_priority=str(source["security_priority"]),
                    )
                )
            contact_entity = str(source.get("contact_entity") or "").strip()
            contact_active = False
            contact_last_seen_ts: str | None = None
            if contact_entity:
                contact_observation = self._normalizer.boolean_signal(contact_entity)
                if contact_observation.available and contact_observation.state == "on":
                    contact_active = True
                    contact_last_seen_ts = self._entity_last_seen_ts(contact_entity) or contact_observation.ts
                elif not contact_observation.available:
                    unavailable_sources.append(
                        {
                            "source_id": source["id"],
                            "display_name": source["display_name"],
                            "role": source["role"],
                            "kind": "contact",
                            "entity_id": contact_entity,
                            "reason": contact_observation.reason,
                        }
                    )
            source_summary = {
                **source,
                "bound_kinds": source_bound_kinds,
                "active_kinds": source_active_kinds,
                "unavailable_kinds": source_unavailable_kinds,
                "status": self._source_status(
                    bound_kinds=source_bound_kinds,
                    active_kinds=source_active_kinds,
                    unavailable_kinds=source_unavailable_kinds,
                ),
                "last_seen_ts": source_last_seen_ts,
                "source_entities": {
                    field_name.removesuffix("_entity"): str(source.get(field_name) or "").strip()
                    for _, field_name in self._SUPPORTED_EVIDENCE_FIELDS
                    if str(source.get(field_name) or "").strip()
                },
                "contact_entity": contact_entity,
                "contact_active": contact_active,
                "contact_last_seen_ts": contact_last_seen_ts,
            }
            configured_sources.append(source_summary)
            return_home_reason = self._return_home_reason(source_summary)
            if return_home_reason is not None:
                return_home_hint_reasons.append(return_home_reason)

        self._last_result = SecurityCameraEvidenceResult(
            configured_sources=configured_sources,
            active_evidence=active_evidence,
            unavailable_sources=unavailable_sources,
            return_home_hint=bool(return_home_hint_reasons),
            return_home_hint_reasons=return_home_hint_reasons,
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

    @staticmethod
    def _source_status(
        *,
        bound_kinds: list[str],
        active_kinds: list[str],
        unavailable_kinds: list[str],
    ) -> str:
        if not bound_kinds:
            return "misconfigured"
        if active_kinds:
            return "active"
        if unavailable_kinds and len(unavailable_kinds) == len(bound_kinds):
            return "unavailable"
        if unavailable_kinds:
            return "partial"
        return "idle"

    def _entity_last_seen_ts(self, entity_id: str) -> str | None:
        state_obj = self._hass.states.get(entity_id)
        if state_obj is None:
            return None
        for attr_name in ("last_changed", "last_updated"):
            value = getattr(state_obj, attr_name, None)
            if value is None:
                continue
            if isinstance(value, datetime):
                return value.isoformat()
            text = str(value).strip()
            if text:
                return text
        return None

    @staticmethod
    def _max_ts(current: str | None, candidate: str | None) -> str | None:
        if not candidate:
            return current
        if not current:
            return candidate
        return max(current, candidate)

    @staticmethod
    def _return_home_reason(source_summary: dict[str, Any]) -> dict[str, Any] | None:
        if not bool(source_summary.get("return_home_contributor")):
            return None
        role = str(source_summary.get("role") or "")
        active_kinds = set(source_summary.get("active_kinds", []))
        contact_active = bool(source_summary.get("contact_active"))
        if role == "entry" and "person" in active_kinds:
            return {
                "source_id": source_summary.get("id"),
                "role": role,
                "reason": "entry_person_detected",
                "contact_active": contact_active,
            }
        if role == "garage" and ({"person", "vehicle"} & active_kinds):
            return {
                "source_id": source_summary.get("id"),
                "role": role,
                "reason": "garage_person_or_vehicle_detected",
                "contact_active": contact_active,
            }
        return None
