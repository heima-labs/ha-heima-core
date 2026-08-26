"""Installation validation report helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from .const import (
    DEFAULT_ACTIVITY_BINDINGS,
    OPT_ACTIVITY_BINDINGS,
    OPT_PEOPLE_ANON,
    OPT_PEOPLE_NAMED,
    OPT_ROOM_ACTUATORS,
    OPT_ROOM_CONNECTIONS,
    OPT_ROOM_OPENINGS,
    OPT_ROOMS,
    OPT_SECURITY,
)
from .room_sources import room_occupancy_source_entity_ids
from .runtime.activity_detectors.config import normalize_activity_bindings

ValidationSeverity = Literal["ok", "warning", "error"]

_SEVERITY_RANK: dict[ValidationSeverity, int] = {"ok": 0, "warning": 1, "error": 2}
_POWER_ACTIVITY_NAMES = {
    name for name, cfg in DEFAULT_ACTIVITY_BINDINGS.items() if "threshold_w" in cfg
}
_MIN_LEARNING_SNAPSHOTS = 10


@dataclass(frozen=True)
class ValidationIssue:
    """One installation validation finding."""

    key: str
    severity: ValidationSeverity
    title: str
    description: str
    capability: str
    missing: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationSection:
    """Validation findings for one functional area."""

    key: str
    title: str
    severity: ValidationSeverity
    summary: str
    issues: tuple[ValidationIssue, ...] = ()
    available: tuple[str, ...] = ()
    unavailable: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationReport:
    """Serializable installation validation report."""

    severity: ValidationSeverity
    summary: str
    sections: tuple[ValidationSection, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "summary": self.summary,
            "sections": [section.as_dict() for section in self.sections],
            "issue_count": sum(len(section.issues) for section in self.sections),
            "warning_count": sum(
                1
                for section in self.sections
                for issue in section.issues
                if issue.severity == "warning"
            ),
            "error_count": sum(
                1
                for section in self.sections
                for issue in section.issues
                if issue.severity == "error"
            ),
        }


def build_validation_report(
    *,
    options: dict[str, Any],
    snapshot_count: int = 0,
    approval_count: int = 0,
    pending_proposal_count: int = 0,
    known_entity_ids: frozenset[str] | None = None,
) -> ValidationReport:
    """Build a cheap structural installation validation report.

    `known_entity_ids` is optional: callers without HA registry access (e.g. the config-flow
    local fallback) may omit it, in which case the topology section skips its
    entity-still-resolves check but still runs every check that needs only `options`.
    """
    sections = (
        _activity_section(options),
        _invariant_section(options),
        _topology_section(options, known_entity_ids=known_entity_ids),
        _actuators_section(options, known_entity_ids=known_entity_ids),
        _learning_section(
            snapshot_count=snapshot_count,
            approval_count=approval_count,
            pending_proposal_count=pending_proposal_count,
        ),
    )
    severity = _max_severity(section.severity for section in sections)
    warnings = sum(
        1 for section in sections for issue in section.issues if issue.severity == "warning"
    )
    errors = sum(1 for section in sections for issue in section.issues if issue.severity == "error")
    if errors:
        summary = f"Installation has {errors} blocking issue(s) and {warnings} warning(s)."
    elif warnings:
        summary = f"Installation is usable with {warnings} warning(s)."
    else:
        summary = "Installation validation passed."
    return ValidationReport(severity=severity, summary=summary, sections=sections)


def validation_summary_text(report: ValidationReport) -> str:
    """Return a compact human-readable summary for config flow placeholders."""
    lines = [report.summary]
    for section in report.sections:
        lines.append(f"{section.title}: {section.summary}")
        for issue in section.issues:
            lines.append(f"- {issue.title}: {issue.description}")
    return "\n".join(lines)


def _activity_section(options: dict[str, Any]) -> ValidationSection:
    bindings = normalize_activity_bindings(options.get(OPT_ACTIVITY_BINDINGS, {}))
    available: list[str] = []
    unavailable: list[str] = []
    issues: list[ValidationIssue] = []
    for activity_name in sorted(DEFAULT_ACTIVITY_BINDINGS):
        cfg = bindings.get(activity_name, {})
        entity_id = str(cfg.get("entity_id") or "").strip()
        if entity_id:
            available.append(activity_name)
            continue
        unavailable.append(activity_name)
        entity_key = str(DEFAULT_ACTIVITY_BINDINGS[activity_name].get("entity_key") or "entity_id")
        missing = (entity_key,)
        if activity_name == "shower_running":
            description = "Shower detection needs a bathroom humidity sensor binding."
        elif activity_name in _POWER_ACTIVITY_NAMES:
            description = f"{activity_name} needs a power or media entity binding."
        else:
            description = f"{activity_name} needs an entity binding."
        issues.append(
            ValidationIssue(
                key=f"activity.{activity_name}.missing_binding",
                severity="warning",
                title=f"{activity_name} unavailable",
                description=description,
                capability=activity_name,
                missing=missing,
            )
        )
    return _section(
        key="activities",
        title="Activities",
        available=available,
        unavailable=unavailable,
        issues=issues,
    )


def _invariant_section(options: dict[str, Any]) -> ValidationSection:
    rooms = [room for room in options.get(OPT_ROOMS, []) or [] if isinstance(room, dict)]
    sensorized_rooms = [
        str(room.get("room_id") or "") for room in rooms if room_occupancy_source_entity_ids(room)
    ]
    people = options.get(OPT_PEOPLE_NAMED, []) or []
    anonymous = options.get(OPT_PEOPLE_ANON, {}) or {}
    has_presence = any(
        isinstance(person, dict)
        and (str(person.get("person_entity") or "").strip() or person.get("sources"))
        for person in people
    ) or bool(isinstance(anonymous, dict) and anonymous.get("sources"))
    security = options.get(OPT_SECURITY, {})
    security_enabled = bool(isinstance(security, dict) and security.get("enabled"))
    security_entity = (
        str(security.get("security_state_entity") or "").strip()
        if isinstance(security, dict)
        else ""
    )

    available: list[str] = []
    unavailable: list[str] = []
    issues: list[ValidationIssue] = []
    if has_presence and sensorized_rooms:
        available.append("presence_without_occupancy")
    else:
        unavailable.append("presence_without_occupancy")
        missing = []
        if not has_presence:
            missing.append("presence_source")
        if not sensorized_rooms:
            missing.append("room_occupancy_source")
        issues.append(
            ValidationIssue(
                key="invariant.presence_without_occupancy.inactive",
                severity="warning",
                title="Presence invariant inactive",
                description="Presence/occupancy mismatch checks need presence and room occupancy bindings.",
                capability="presence_without_occupancy",
                missing=tuple(missing),
            )
        )

    if security_enabled and security_entity:
        available.append("security_presence_mismatch")
    else:
        unavailable.append("security_presence_mismatch")
        issues.append(
            ValidationIssue(
                key="invariant.security_presence_mismatch.inactive",
                severity="warning",
                title="Security invariant inactive",
                description="Security presence mismatch checks need enabled security config and a security state entity.",
                capability="security_presence_mismatch",
                missing=("security_state_entity",),
            )
        )
    return _section(
        key="invariants",
        title="Invariants",
        available=available,
        unavailable=unavailable,
        issues=issues,
    )


def _learning_section(
    *,
    snapshot_count: int,
    approval_count: int,
    pending_proposal_count: int,
) -> ValidationSection:
    available: list[str] = []
    unavailable: list[str] = []
    issues: list[ValidationIssue] = []
    if snapshot_count >= _MIN_LEARNING_SNAPSHOTS:
        available.append("learning_history")
    else:
        unavailable.append("learning_history")
        issues.append(
            ValidationIssue(
                key="learning.snapshots.insufficient",
                severity="warning",
                title="Learning history limited",
                description=(
                    f"Learning has {snapshot_count} snapshot(s); "
                    f"{_MIN_LEARNING_SNAPSHOTS} are recommended before judging coverage."
                ),
                capability="learning_history",
                missing=("snapshots",),
            )
        )
    if approval_count or pending_proposal_count:
        available.append("approval_feedback")
    else:
        unavailable.append("approval_feedback")
        issues.append(
            ValidationIssue(
                key="learning.approvals.none",
                severity="warning",
                title="No approval feedback yet",
                description="Learned suggestions need resident or installer decisions before they affect runtime.",
                capability="approval_feedback",
                missing=("approval_records",),
            )
        )
    return _section(
        key="learning",
        title="Learning",
        available=available,
        unavailable=unavailable,
        issues=issues,
    )


def _topology_section(
    options: dict[str, Any],
    *,
    known_entity_ids: frozenset[str] | None,
) -> ValidationSection:
    # Local import: room_topology.py imports ValidationIssue from this module, so importing it
    # at module scope here would create a circular import.
    from .room_topology import validate_topology

    issues: list[ValidationIssue] = list(validate_topology(options))

    rooms = [room for room in options.get(OPT_ROOMS, []) or [] if isinstance(room, dict)]
    orphaned_room_ids = {
        str(room.get("room_id") or "")
        for room in rooms
        if str(room.get("ha_sync_status") or "").strip() == "orphaned"
    }
    if orphaned_room_ids:
        for opening in options.get(OPT_ROOM_OPENINGS, []) or []:
            if not isinstance(opening, dict):
                continue
            room_id = str(opening.get("room_id") or "")
            opening_id = str(opening.get("opening_id") or "")
            if not opening_id or room_id not in orphaned_room_ids:
                continue
            issues.append(
                ValidationIssue(
                    key=f"topology.opening.{opening_id}.orphaned_room",
                    severity="warning",
                    title="Opening's room is no longer synced with Home Assistant",
                    description=(
                        f"Opening '{opening_id}' belongs to room '{room_id}', whose Home Assistant "
                        "Area was removed. The room is retained but no longer reconciled with a "
                        "live Area."
                    ),
                    capability="room_topology",
                )
            )
        for connection in options.get(OPT_ROOM_CONNECTIONS, []) or []:
            if not isinstance(connection, dict):
                continue
            room_b = str(connection.get("room_b") or "")
            connection_id = str(connection.get("connection_id") or "")
            if not connection_id or room_b not in orphaned_room_ids:
                continue
            issues.append(
                ValidationIssue(
                    key=f"topology.connection.{connection_id}.orphaned_room",
                    severity="warning",
                    title="Connection's room is no longer synced with Home Assistant",
                    description=(
                        f"Connection '{connection_id}' references room '{room_b}', whose Home "
                        "Assistant Area was removed. The room is retained but no longer "
                        "reconciled with a live Area."
                    ),
                    capability="room_topology",
                )
            )

    if known_entity_ids is not None:
        seen_entity_ids: set[str] = set()
        for opening in options.get(OPT_ROOM_OPENINGS, []) or []:
            if not isinstance(opening, dict):
                continue
            entity_id = str(opening.get("entity_id") or "").strip()
            opening_id = str(opening.get("opening_id") or "").strip()
            if not entity_id or not opening_id or entity_id in seen_entity_ids:
                continue
            if entity_id in known_entity_ids:
                continue
            seen_entity_ids.add(entity_id)
            issues.append(
                ValidationIssue(
                    key=f"topology.entity.{entity_id}.unavailable",
                    severity="warning",
                    title="Opening entity no longer resolves",
                    description=(
                        f"entity_id '{entity_id}' bound to opening '{opening_id}' no longer "
                        "resolves in Home Assistant. The opening is retained as a valid "
                        "geographic reference."
                    ),
                    capability="room_topology",
                    missing=(entity_id,),
                )
            )

    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    if errors:
        summary = f"{errors} blocking issue(s), {warnings} warning(s)."
    elif warnings:
        summary = f"{warnings} warning(s)."
    else:
        summary = "Room topology is valid."
    return ValidationSection(
        key="room_topology",
        title="Room Topology",
        severity=_max_severity(issue.severity for issue in issues) if issues else "ok",
        summary=summary,
        issues=tuple(issues),
    )


def _actuators_section(
    options: dict[str, Any],
    *,
    known_entity_ids: frozenset[str] | None,
) -> ValidationSection:
    # Local import: actuators.py imports ValidationIssue from this module, so importing it
    # at module scope here would create a circular import (same reason as _topology_section).
    from .actuators import validate_actuators

    issues: list[ValidationIssue] = list(validate_actuators(options))

    if known_entity_ids is not None:
        seen_entity_ids: set[str] = set()
        for actuator in options.get(OPT_ROOM_ACTUATORS, []) or []:
            if not isinstance(actuator, dict):
                continue
            entity_id = str(actuator.get("entity_id") or "").strip()
            actuator_id = str(actuator.get("actuator_id") or "").strip()
            if not entity_id or not actuator_id or entity_id in seen_entity_ids:
                continue
            if entity_id in known_entity_ids:
                continue
            seen_entity_ids.add(entity_id)
            issues.append(
                ValidationIssue(
                    key=f"actuators.entity.{entity_id}.unavailable",
                    severity="warning",
                    title="Actuator entity no longer resolves",
                    description=(
                        f"entity_id '{entity_id}' bound to actuator '{actuator_id}' no longer "
                        "resolves in Home Assistant. The actuator is retained as a valid "
                        "placement reference."
                    ),
                    capability="actuator_registry",
                    missing=(entity_id,),
                )
            )

    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    if errors:
        summary = f"{errors} blocking issue(s), {warnings} warning(s)."
    elif warnings:
        summary = f"{warnings} warning(s)."
    else:
        summary = "Actuator registry is valid."
    return ValidationSection(
        key="actuator_registry",
        title="Actuator Registry",
        severity=_max_severity(issue.severity for issue in issues) if issues else "ok",
        summary=summary,
        issues=tuple(issues),
    )


def _section(
    *,
    key: str,
    title: str,
    available: list[str],
    unavailable: list[str],
    issues: list[ValidationIssue],
) -> ValidationSection:
    severity = _max_severity(issue.severity for issue in issues) if issues else "ok"
    if unavailable:
        summary = f"{len(available)} available, {len(unavailable)} unavailable."
    else:
        summary = f"{len(available)} available."
    return ValidationSection(
        key=key,
        title=title,
        severity=severity,
        summary=summary,
        issues=tuple(issues),
        available=tuple(sorted(available)),
        unavailable=tuple(sorted(unavailable)),
    )


def _max_severity(values: Any) -> ValidationSeverity:
    severity: ValidationSeverity = "ok"
    for value in values:
        candidate: ValidationSeverity = value if value in _SEVERITY_RANK else "ok"
        if _SEVERITY_RANK[candidate] > _SEVERITY_RANK[severity]:
            severity = candidate
    return severity
