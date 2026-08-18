"""Core runtime contracts for planning and events."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

EventSeverity = Literal["debug", "info", "warning", "error", "critical"]
RecoveryApplyPolicy = Literal["block", "allow_when_inputs_stable", "allow_admin_command"]
ApplyStepSourceKind = Literal[
    "reaction",
    "domain",
    "admin_command",
    "resident_response",
    "timeout",
    "recovery",
    "system",
    "test",
    "legacy",
]
ApplyStepSourceActorType = Literal[
    "ha_admin",
    "resident",
    "heima",
    "scheduler",
    "service",
    "system",
    "test",
    "unknown",
]
EVENT_SEVERITY_VALUES: tuple[EventSeverity, ...] = (
    "debug",
    "info",
    "warning",
    "error",
    "critical",
)
APPLY_STEP_SOURCE_KIND_VALUES: tuple[ApplyStepSourceKind, ...] = (
    "reaction",
    "domain",
    "admin_command",
    "resident_response",
    "timeout",
    "recovery",
    "system",
    "test",
    "legacy",
)
APPLY_STEP_SOURCE_ACTOR_TYPE_VALUES: tuple[ApplyStepSourceActorType, ...] = (
    "ha_admin",
    "resident",
    "heima",
    "scheduler",
    "service",
    "system",
    "test",
    "unknown",
)


def coerce_event_severity(value: str) -> EventSeverity:
    """Normalize and validate a public event severity value."""
    normalized = str(value or "").strip().lower()
    if normalized not in EVENT_SEVERITY_VALUES:
        raise ValueError(f"Unsupported event severity '{value}'")
    return normalized


@dataclass(frozen=True)
class ApplyStepSource:
    """Structured runtime source assigned by trusted Heima boundaries."""

    kind: ApplyStepSourceKind
    source_id: str
    source_type: str | None = None
    actor_type: ApplyStepSourceActorType = "heima"
    actor_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

    def legacy_key(self) -> str:
        """Return the deterministic compatibility rendering for legacy consumers."""
        source_id = str(self.source_id or "").strip()
        if self.kind == "legacy":
            return source_id
        if not source_id:
            return str(self.kind)
        return f"{self.kind}:{source_id}"

    def as_redacted_dict(self) -> dict[str, Any]:
        """Return a diagnostics-safe source representation."""
        data: dict[str, Any] = {
            "kind": self.kind,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "actor_type": self.actor_type,
            "actor_id_hash": redact_actor_id(self.actor_id),
            "correlation_id": self.correlation_id,
            "legacy_key": self.legacy_key(),
        }
        return {key: value for key, value in data.items() if value not in (None, "")}


ApplyStepSourceValue = ApplyStepSource | str


def redact_actor_id(actor_id: str | None) -> str | None:
    """Return a stable diagnostics-safe actor id hash."""
    raw = str(actor_id or "").strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def reaction_step_source(
    reaction_id: str,
    *,
    reaction_type: str | None = None,
    correlation_id: str | None = None,
) -> ApplyStepSource:
    return ApplyStepSource(
        kind="reaction",
        source_id=str(reaction_id or "").strip(),
        source_type=reaction_type,
        actor_type="heima",
        correlation_id=correlation_id or str(uuid4()),
    )


def domain_step_source(
    domain_id: str,
    *,
    source_type: str | None = None,
    actor_type: ApplyStepSourceActorType = "heima",
    correlation_id: str | None = None,
) -> ApplyStepSource:
    return ApplyStepSource(
        kind="domain",
        source_id=str(domain_id or "").strip(),
        source_type=source_type,
        actor_type=actor_type,
        correlation_id=correlation_id or str(uuid4()),
    )


def admin_command_step_source(
    command_id: str,
    *,
    command_type: str | None = None,
    actor_id: str | None = None,
    correlation_id: str | None = None,
) -> ApplyStepSource:
    return ApplyStepSource(
        kind="admin_command",
        source_id=str(command_id or "").strip(),
        source_type=command_type,
        actor_type="ha_admin",
        actor_id=actor_id,
        correlation_id=correlation_id or str(uuid4()),
    )


def resident_response_step_source(
    request_id: str,
    *,
    actor_id: str | None = None,
    correlation_id: str | None = None,
) -> ApplyStepSource:
    return ApplyStepSource(
        kind="resident_response",
        source_id=str(request_id or "").strip(),
        actor_type="resident",
        actor_id=actor_id,
        correlation_id=correlation_id or str(uuid4()),
    )


def timeout_step_source(
    request_id: str,
    *,
    correlation_id: str | None = None,
) -> ApplyStepSource:
    return ApplyStepSource(
        kind="timeout",
        source_id=str(request_id or "").strip(),
        actor_type="scheduler",
        correlation_id=correlation_id or str(uuid4()),
    )


def recovery_step_source(
    recovery_id: str,
    *,
    recovery_type: str | None = None,
    correlation_id: str | None = None,
) -> ApplyStepSource:
    return ApplyStepSource(
        kind="recovery",
        source_id=str(recovery_id or "").strip(),
        source_type=recovery_type,
        actor_type="system",
        correlation_id=correlation_id or str(uuid4()),
    )


def system_step_source(
    source_id: str,
    *,
    source_type: str | None = None,
    correlation_id: str | None = None,
) -> ApplyStepSource:
    return ApplyStepSource(
        kind="system",
        source_id=str(source_id or "").strip(),
        source_type=source_type,
        actor_type="system",
        correlation_id=correlation_id or str(uuid4()),
    )


def test_step_source(
    source_id: str,
    *,
    source_type: str | None = None,
    correlation_id: str | None = None,
) -> ApplyStepSource:
    return ApplyStepSource(
        kind="test",
        source_id=str(source_id or "").strip(),
        source_type=source_type,
        actor_type="test",
        correlation_id=correlation_id or str(uuid4()),
    )


def legacy_step_source(source: object) -> ApplyStepSource:
    return ApplyStepSource(
        kind="legacy",
        source_id=str(source or "").strip(),
        actor_type="unknown",
    )


def sanitize_apply_step_source(value: object) -> ApplyStepSourceValue:
    """Accept source input from persisted/user-controlled data as non-authoritative."""
    if isinstance(value, ApplyStepSource):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        raw_legacy = value.get("legacy_key") or value.get("source") or value.get("source_id") or ""
        return legacy_step_source(raw_legacy)
    return legacy_step_source(value)


def _source_value(source_or_step: object) -> Any:
    return getattr(source_or_step, "source", source_or_step)


def step_source_kind(source_or_step: object) -> ApplyStepSourceKind:
    source = _source_value(source_or_step)
    if isinstance(source, ApplyStepSource):
        return source.kind
    return "legacy"


def step_source_id(source_or_step: object) -> str:
    source = _source_value(source_or_step)
    if isinstance(source, ApplyStepSource):
        return source.source_id
    raw = str(source or "").strip()
    if ":" in raw:
        return raw.split(":", 1)[1]
    return raw


def step_source_type(source_or_step: object) -> str | None:
    source = _source_value(source_or_step)
    if isinstance(source, ApplyStepSource):
        return source.source_type
    return None


def step_source_actor_type(source_or_step: object) -> ApplyStepSourceActorType:
    source = _source_value(source_or_step)
    if isinstance(source, ApplyStepSource):
        return source.actor_type
    return "unknown"


def step_source_legacy_key(source_or_step: object) -> str:
    source = _source_value(source_or_step)
    if isinstance(source, ApplyStepSource):
        return source.legacy_key()
    return str(source or "").strip()


def step_source_diagnostics(source_or_step: object) -> dict[str, Any] | None:
    source = _source_value(source_or_step)
    if isinstance(source, ApplyStepSource):
        return source.as_redacted_dict()
    return None


def reaction_id_from_step_source(source_or_step: object) -> str | None:
    source = _source_value(source_or_step)
    if isinstance(source, ApplyStepSource):
        return source.source_id if source.kind == "reaction" and source.source_id else None
    raw = str(source or "").strip()
    if raw.startswith("reaction:"):
        return raw.split(":", 1)[1] or None
    return None


def is_authoritative_source(
    source_or_step: object,
    *,
    kind: ApplyStepSourceKind | None = None,
) -> bool:
    source = _source_value(source_or_step)
    if not isinstance(source, ApplyStepSource):
        return False
    if source.kind == "legacy":
        return False
    if kind is not None and source.kind != kind:
        return False
    return bool(str(source.source_id or "").strip())


@dataclass(frozen=True)
class HeimaEvent:
    """Canonical event payload flowing through runtime."""

    type: str
    key: str
    severity: EventSeverity
    title: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        context = data.get("context")
        if isinstance(context, dict):
            data["context"] = {
                key: value for key, value in context.items() if not str(key).startswith("_heima_")
            }
        return data


@dataclass(frozen=True)
class ApplyStep:
    """Single desired apply action."""

    domain: str
    target: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    blocked_by: str = ""  # set by apply_filter; non-empty means step is skipped
    source: ApplyStepSourceValue = ""  # legacy string or structured runtime source
    context_id: str | None = None  # HA Context id to use when executing this step
    step_id: str = ""  # optional id for dependency-aware runtime plans
    depends_on: tuple[str, ...] = ()  # step_id values from the same runtime plan
    recovery_policy: RecoveryApplyPolicy = "block"


@dataclass(frozen=True)
class ApplyPlan:
    """Collection of apply actions for an evaluation cycle."""

    plan_id: str = field(default_factory=lambda: str(uuid4()))
    steps: list[ApplyStep] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "ApplyPlan":
        return cls(steps=[])


@dataclass(frozen=True)
class ScriptApplyBatch:
    """Short-lived provenance batch for one script.turn_on execution.

    This is not a persisted learning event. It is runtime-local provenance used
    by recorder behaviors to avoid misclassifying Heima-caused effects as user
    behavior.
    """

    script_entity: str
    applied_ts: float
    correlation_id: str
    source: ApplyStepSourceValue = ""
    origin_reaction_id: str | None = None
    origin_reaction_type: str | None = None
    room_id: str | None = None
    expected_domains: tuple[str, ...] = ()
    expected_subject_ids: tuple[str, ...] = ()
    expected_entity_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["expected_domains"] = list(self.expected_domains)
        raw["expected_subject_ids"] = list(self.expected_subject_ids)
        raw["expected_entity_ids"] = list(self.expected_entity_ids)
        raw["source"] = step_source_legacy_key(self.source)
        source_details = step_source_diagnostics(self.source)
        if source_details is not None:
            raw["source_details"] = source_details
        return raw
