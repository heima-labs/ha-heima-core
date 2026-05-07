"""Rule-based Home Assistant entity discovery for installer review."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DiscoveredBindingCandidate:
    """One installer-reviewable binding suggestion."""

    candidate_id: str
    entity_id: str
    domain: str
    device_class: str
    suggested_binding: str
    category: str
    reason: str
    confidence: float
    area_id: str | None = None
    area_name: str | None = None
    ambiguous: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiscoveryReport:
    """Grouped discovery output."""

    candidates: tuple[DiscoveredBindingCandidate, ...]

    def as_dict(self) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for candidate in self.candidates:
            grouped.setdefault(candidate.category, []).append(candidate.as_dict())
        return {
            "total": len(self.candidates),
            "by_category": {key: len(value) for key, value in sorted(grouped.items())},
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "groups": grouped,
        }


def discover_binding_candidates(
    *,
    entity_entries: list[Any],
    device_entries: dict[str, Any] | None = None,
    area_entries: dict[str, Any] | None = None,
    state_by_entity: dict[str, Any] | None = None,
) -> DiscoveryReport:
    """Return rule-based binding candidates from HA registry-like objects."""
    device_entries = device_entries or {}
    area_entries = area_entries or {}
    state_by_entity = state_by_entity or {}
    candidates: list[DiscoveredBindingCandidate] = []
    seen: set[str] = set()
    for entry in entity_entries:
        candidate = _candidate_from_entry(
            entry,
            device_entries=device_entries,
            area_entries=area_entries,
            state_by_entity=state_by_entity,
        )
        if candidate is None or candidate.candidate_id in seen:
            continue
        seen.add(candidate.candidate_id)
        candidates.append(candidate)
    return DiscoveryReport(candidates=tuple(sorted(candidates, key=_candidate_sort_key)))


def candidate_label(candidate: DiscoveredBindingCandidate) -> str:
    """Return a compact review label with reason."""
    area = (
        f" [{candidate.area_name or candidate.area_id}]"
        if candidate.area_name or candidate.area_id
        else ""
    )
    marker = " (installer choice required)" if candidate.ambiguous else ""
    return (
        f"{candidate.entity_id}{area} -> {candidate.suggested_binding}{marker}: {candidate.reason}"
    )


def candidate_by_id(
    report: DiscoveryReport, candidate_id: str
) -> DiscoveredBindingCandidate | None:
    for candidate in report.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    return None


def _candidate_from_entry(
    entry: Any,
    *,
    device_entries: dict[str, Any],
    area_entries: dict[str, Any],
    state_by_entity: dict[str, Any],
) -> DiscoveredBindingCandidate | None:
    entity_id = str(getattr(entry, "entity_id", "") or "").strip()
    if "." not in entity_id:
        return None
    domain, _, _ = entity_id.partition(".")
    device_class = _device_class(entry, state_by_entity.get(entity_id))
    area_id = _entry_area_id(entry, device_entries)
    area_name = _area_name(area_id, area_entries)
    if domain in {"person", "device_tracker"}:
        return _candidate(
            entity_id=entity_id,
            domain=domain,
            device_class=device_class,
            suggested_binding="presence_source",
            category="presence",
            reason=f"{domain} entities indicate household presence.",
            confidence=0.9,
            area_id=area_id,
            area_name=area_name,
        )
    if domain == "binary_sensor" and device_class in {"motion", "occupancy", "presence"}:
        return _candidate(
            entity_id=entity_id,
            domain=domain,
            device_class=device_class,
            suggested_binding="room_occupancy_source",
            category="presence",
            reason=f"Binary sensor device_class '{device_class}' can drive room occupancy.",
            confidence=0.85,
            area_id=area_id,
            area_name=area_name,
        )
    if domain == "binary_sensor" and device_class in {"door", "window", "opening", "garage_door"}:
        return _candidate(
            entity_id=entity_id,
            domain=domain,
            device_class=device_class,
            suggested_binding="security_contact",
            category="security",
            reason=f"Binary sensor device_class '{device_class}' can provide door/window evidence.",
            confidence=0.75,
            area_id=area_id,
            area_name=area_name,
            ambiguous=True,
        )
    if domain == "sensor" and device_class == "humidity":
        return _candidate(
            entity_id=entity_id,
            domain=domain,
            device_class=device_class,
            suggested_binding="activity_shower_humidity",
            category="activity",
            reason="Humidity sensors can support shower_running detection after installer review.",
            confidence=0.7,
            area_id=area_id,
            area_name=area_name,
        )
    if domain == "sensor" and device_class in {"power", "energy"}:
        return _candidate(
            entity_id=entity_id,
            domain=domain,
            device_class=device_class,
            suggested_binding="activity_power_candidate",
            category="activity",
            reason="Power/energy sensors may indicate appliance activity; installer must choose the activity type.",
            confidence=0.55,
            area_id=area_id,
            area_name=area_name,
            ambiguous=True,
        )
    if domain == "media_player":
        return _candidate(
            entity_id=entity_id,
            domain=domain,
            device_class=device_class,
            suggested_binding="activity_media_candidate",
            category="activity",
            reason="Media players may indicate TV or media activity after installer review.",
            confidence=0.55,
            area_id=area_id,
            area_name=area_name,
            ambiguous=True,
        )
    return None


def _candidate(
    *,
    entity_id: str,
    domain: str,
    device_class: str,
    suggested_binding: str,
    category: str,
    reason: str,
    confidence: float,
    area_id: str | None,
    area_name: str | None,
    ambiguous: bool = False,
) -> DiscoveredBindingCandidate:
    candidate_id = f"{suggested_binding}:{entity_id}"
    return DiscoveredBindingCandidate(
        candidate_id=candidate_id,
        entity_id=entity_id,
        domain=domain,
        device_class=device_class,
        suggested_binding=suggested_binding,
        category=category,
        reason=reason,
        confidence=confidence,
        area_id=area_id,
        area_name=area_name,
        ambiguous=ambiguous,
    )


def _device_class(entry: Any, state: Any) -> str:
    for source in (entry, state):
        attrs = getattr(source, "attributes", {}) if source is not None else {}
        for key in ("device_class", "original_device_class"):
            value = getattr(source, key, None) if source is not None else None
            if not value and isinstance(attrs, dict):
                value = attrs.get(key)
            clean = str(value or "").strip().lower()
            if clean:
                return clean
    return ""


def _entry_area_id(entry: Any, device_entries: dict[str, Any]) -> str | None:
    area_id = str(getattr(entry, "area_id", "") or "").strip()
    if area_id:
        return area_id
    device_id = str(getattr(entry, "device_id", "") or "").strip()
    if not device_id:
        return None
    device = device_entries.get(device_id)
    area_id = str(getattr(device, "area_id", "") or "").strip()
    return area_id or None


def _area_name(area_id: str | None, area_entries: dict[str, Any]) -> str | None:
    if not area_id:
        return None
    area = area_entries.get(area_id)
    return str(getattr(area, "name", "") or "").strip() or None


def _candidate_sort_key(candidate: DiscoveredBindingCandidate) -> tuple[str, str, str]:
    return (candidate.category, candidate.suggested_binding, candidate.entity_id)
