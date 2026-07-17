"""Bounded runtime observability buffers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .contracts import ApplyPlan, ApplyStep

DEFAULT_EVENT_LIMIT = 500
DEFAULT_TRACE_LIMIT = 100


@dataclass(frozen=True)
class RuntimeActivityEvent:
    """One bounded runtime activity event for admin observability."""

    category: str
    summary: str
    reason_code: str
    severity: str = "info"
    object_links: tuple[dict[str, str], ...] = ()
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "category": self.category,
            "severity": self.severity,
            "summary": self.summary,
            "reason_code": self.reason_code,
            "object_links": [dict(item) for item in self.object_links],
        }


@dataclass(frozen=True)
class DecisionTrace:
    """One bounded decision trace for admin observability."""

    reaction_id: str
    occurrence_key: str
    outcome: str
    reason_codes: tuple[str, ...]
    input_summary: dict[str, Any] = field(default_factory=dict)
    condition_results: tuple[dict[str, Any], ...] = ()
    guard_results: tuple[dict[str, Any], ...] = ()
    apply_steps: tuple[dict[str, Any], ...] = ()
    links: tuple[dict[str, str], ...] = ()
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "reaction_id": self.reaction_id,
            "occurrence_key": self.occurrence_key,
            "timestamp": self.timestamp,
            "outcome": self.outcome,
            "reason_codes": list(self.reason_codes),
            "input_summary": dict(self.input_summary),
            "condition_results": [dict(item) for item in self.condition_results],
            "guard_results": [dict(item) for item in self.guard_results],
            "apply_steps": [dict(item) for item in self.apply_steps],
            "links": [dict(item) for item in self.links],
        }


class RuntimeObservabilityBuffer:
    """Bounded in-memory event and decision trace buffer."""

    def __init__(
        self,
        *,
        event_limit: int = DEFAULT_EVENT_LIMIT,
        trace_limit: int = DEFAULT_TRACE_LIMIT,
    ) -> None:
        self._events: deque[RuntimeActivityEvent] = deque(maxlen=max(1, int(event_limit)))
        self._traces: deque[DecisionTrace] = deque(maxlen=max(1, int(trace_limit)))
        self._started_at = datetime.now(UTC).isoformat()

    def record_event(self, event: RuntimeActivityEvent) -> None:
        """Append one runtime activity event."""
        self._events.append(event)

    def record_trace(self, trace: DecisionTrace) -> None:
        """Append one decision trace."""
        self._traces.append(trace)

    def record_apply_plan(
        self,
        *,
        reason: str,
        plan: ApplyPlan,
        engine_enabled: bool,
    ) -> None:
        """Record aggregate decision traces for one filtered apply plan."""
        grouped = _group_steps(plan.steps)
        if not grouped:
            self.record_event(
                RuntimeActivityEvent(
                    category="reaction",
                    severity="debug",
                    summary=f"Evaluation '{reason}' produced no apply steps.",
                    reason_code="no_apply_steps",
                )
            )
            return

        for group_id, steps in grouped.items():
            executable = [step for step in steps if not step.blocked_by]
            blocked = [step for step in steps if step.blocked_by]
            if executable and engine_enabled:
                outcome = "applied"
                reason_codes = ["matched", "apply_plan_ready"]
                if blocked:
                    reason_codes.append("partial_blocked")
            elif executable:
                outcome = "skipped"
                reason_codes = ["engine_disabled"]
            else:
                outcome = "blocked"
                reason_codes = sorted(
                    {_reason_code_from_blocker(step.blocked_by) for step in blocked}
                )

            trace = DecisionTrace(
                reaction_id=group_id,
                occurrence_key=f"evaluation:{reason}:{plan.plan_id}:{group_id}",
                outcome=outcome,
                reason_codes=tuple(reason_codes),
                input_summary={"evaluation_reason": reason, "plan_id": plan.plan_id},
                guard_results=tuple(_guard_result(step) for step in blocked),
                apply_steps=tuple(_step_summary(step) for step in steps),
                links=tuple(_links_for_group(group_id, steps)),
            )
            self.record_trace(trace)
            self.record_event(
                RuntimeActivityEvent(
                    category="reaction",
                    severity="info" if outcome == "applied" else "warning",
                    summary=_event_summary(group_id, outcome, executable, blocked),
                    reason_code=outcome,
                    object_links=tuple(_links_for_group(group_id, steps)),
                )
            )

    def record_runtime_confirmation_waiting(
        self,
        *,
        reaction_id: str,
        reaction_type: str,
        occurrence_key: str,
        steps: list[ApplyStep] | tuple[ApplyStep, ...],
    ) -> None:
        """Record a reaction occurrence waiting for resident confirmation."""
        trace = DecisionTrace(
            reaction_id=reaction_id,
            occurrence_key=occurrence_key,
            outcome="waiting",
            reason_codes=("matched", "waiting_for_resident_confirmation"),
            input_summary={"reaction_type": reaction_type},
            apply_steps=tuple(_step_summary(step) for step in steps),
            links=({"kind": "reaction", "id": reaction_id},),
        )
        self.record_trace(trace)
        self.record_event(
            RuntimeActivityEvent(
                category="notification",
                summary=f"Reaction '{reaction_id}' is waiting for resident confirmation.",
                reason_code="waiting_for_resident_confirmation",
                object_links=({"kind": "reaction", "id": reaction_id},),
            )
        )

    def record_runtime_confirmation_apply(
        self,
        *,
        reaction_id: str,
        request_id: str,
        status: str,
        apply_steps: list[ApplyStep] | tuple[ApplyStep, ...],
        applied_steps: int,
        blocked_reasons: dict[str, int],
        skipped_reasons: dict[str, int],
    ) -> None:
        """Record the result of applying a runtime-confirmation request."""
        if applied_steps > 0:
            outcome = "applied"
        elif blocked_reasons:
            outcome = "blocked"
        elif skipped_reasons:
            outcome = "skipped"
        else:
            outcome = "failed"
        reason_codes = [status, outcome]
        reason_codes.extend(sorted(blocked_reasons))
        reason_codes.extend(sorted(skipped_reasons))
        trace = DecisionTrace(
            reaction_id=reaction_id,
            occurrence_key=f"runtime_confirmation:{request_id}",
            outcome=outcome,
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            input_summary={
                "request_id": request_id,
                "runtime_confirmation_status": status,
            },
            guard_results=tuple(
                {"result": "blocked", "reason_code": reason, "count": count}
                for reason, count in sorted(blocked_reasons.items())
            ),
            apply_steps=tuple(_step_summary(step) for step in apply_steps),
            links=(
                {"kind": "reaction", "id": reaction_id},
                {"kind": "runtime_confirmation", "id": request_id},
            ),
        )
        self.record_trace(trace)
        self.record_event(
            RuntimeActivityEvent(
                category="notification",
                severity="info" if outcome == "applied" else "warning",
                summary=(
                    f"Runtime confirmation '{request_id}' for reaction '{reaction_id}' "
                    f"finished as {outcome}."
                ),
                reason_code=outcome,
                object_links=(
                    {"kind": "reaction", "id": reaction_id},
                    {"kind": "runtime_confirmation", "id": request_id},
                ),
            )
        )

    def record_admin_action(
        self,
        *,
        summary: str,
        reason_code: str,
        object_links: tuple[dict[str, str], ...] = (),
    ) -> None:
        """Record an explicit HA-admin action."""
        self.record_event(
            RuntimeActivityEvent(
                category="admin_action",
                severity="info",
                summary=summary,
                reason_code=reason_code,
                object_links=object_links,
            )
        )

    def diagnostics(self) -> dict[str, Any]:
        """Return serializable observability diagnostics."""
        return {
            "retention": {
                "mode": "in_memory",
                "description": "history_since_last_restart",
                "started_at": self._started_at,
                "event_limit": self._events.maxlen,
                "trace_limit": self._traces.maxlen,
            },
            "recent_events": [event.as_dict() for event in self._events],
            "decision_traces": [trace.as_dict() for trace in self._traces],
        }


def _group_steps(steps: list[ApplyStep]) -> dict[str, list[ApplyStep]]:
    grouped: dict[str, list[ApplyStep]] = {}
    for step in steps:
        group_id = _reaction_id_from_source(step.source) or f"domain:{step.domain}"
        grouped.setdefault(group_id, []).append(step)
    return grouped


def _reaction_id_from_source(source: str) -> str:
    token = str(source or "").strip()
    if token.startswith("reaction:"):
        return token.split(":", 1)[1]
    return ""


def _reason_code_from_blocker(blocked_by: str) -> str:
    reason = str(blocked_by or "").strip()
    if reason.startswith("manual_hold:"):
        return "manual_hold_active"
    if reason.startswith("constraint:"):
        return "constraint_active"
    return reason or "blocked"


def _guard_result(step: ApplyStep) -> dict[str, Any]:
    return {
        "result": "blocked",
        "reason_code": _reason_code_from_blocker(step.blocked_by),
        "blocked_by": step.blocked_by,
        "step_id": step.step_id,
        "target": step.target,
    }


def _step_summary(step: ApplyStep) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "domain": step.domain,
        "target": step.target,
        "action": step.action,
        "reason": step.reason,
        "source": step.source,
        "blocked_by": step.blocked_by,
        "depends_on": list(step.depends_on),
    }


def _links_for_group(group_id: str, steps: list[ApplyStep]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    if not group_id.startswith("domain:"):
        links.append({"kind": "reaction", "id": group_id})
    for step in steps:
        entity_id = str(step.params.get("entity_id") or step.target or "").strip()
        if entity_id:
            links.append({"kind": "entity", "id": entity_id})
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        key = (link["kind"], link["id"])
        if key not in seen:
            unique.append(link)
            seen.add(key)
    return unique


def _event_summary(
    group_id: str,
    outcome: str,
    executable: list[ApplyStep],
    blocked: list[ApplyStep],
) -> str:
    if outcome == "applied":
        return (
            f"'{group_id}' produced {len(executable)} executable step(s)"
            f" and {len(blocked)} blocked step(s)."
        )
    if outcome == "blocked":
        return f"'{group_id}' was blocked for {len(blocked)} step(s)."
    return f"'{group_id}' was skipped with {len(executable)} executable step(s)."
