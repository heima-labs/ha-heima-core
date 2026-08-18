"""Core runtime contracts for planning and events."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

EventSeverity = Literal["debug", "info", "warning", "error", "critical"]
RecoveryApplyPolicy = Literal["block", "allow_when_inputs_stable", "allow_admin_command"]
EVENT_SEVERITY_VALUES: tuple[EventSeverity, ...] = (
    "debug",
    "info",
    "warning",
    "error",
    "critical",
)


def coerce_event_severity(value: str) -> EventSeverity:
    """Normalize and validate a public event severity value."""
    normalized = str(value or "").strip().lower()
    if normalized not in EVENT_SEVERITY_VALUES:
        raise ValueError(f"Unsupported event severity '{value}'")
    return normalized


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
    source: str = ""  # e.g. "reaction:MyReaction"; empty = domain pipeline
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
    source: str = ""
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
        return raw
