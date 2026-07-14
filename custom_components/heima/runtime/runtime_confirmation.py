"""Runtime confirmation contracts and pure helpers."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Callable, Literal
from uuid import uuid4

from .contracts import ApplyStep
from .snapshot import DecisionSnapshot

ExecutionPolicyMode = Literal["auto_apply", "ask_residents"]
TimeoutBehavior = Literal["skip", "apply"]
RuntimeRequestStatus = Literal[
    "pending",
    "approved",
    "dismissed",
    "timeout_skipped",
    "timeout_applied",
    "cancelled",
    "failed",
]

TERMINAL_REQUEST_STATUSES: frozenset[str] = frozenset(
    {
        "approved",
        "dismissed",
        "timeout_skipped",
        "timeout_applied",
        "cancelled",
        "failed",
    }
)

FAILURE_NO_ACTIONABLE_ROUTE = "no_actionable_route"
FAILURE_MANUAL_HOLD_ACTIVE = "manual_hold_active"
FAILURE_TARGET_UNAVAILABLE = "target_unavailable"
FAILURE_CONTEXT_REVALIDATION_FAILED = "context_revalidation_failed"
FAILURE_ALL_STEPS_BLOCKED = "all_steps_blocked"
FAILURE_APPLY_ERROR = "apply_error"
FAILURE_VALIDATION_FAILED = "validation_failed"

SKIP_DEPENDENCY_BLOCKED = "dependency_blocked"
SKIP_DEPENDENCY_FAILED = "dependency_failed"
SKIP_DEPENDENCY_MISSING = "dependency_missing"
SKIP_DEPENDENCY_SKIPPED = "dependency_skipped"
SKIP_DEPENDENCY_CYCLE = "dependency_cycle"


@dataclass(frozen=True)
class ExecutionPolicy:
    """Execution mode for a configured reaction."""

    mode: ExecutionPolicyMode = "auto_apply"
    confirmation: "ConfirmationPolicy | None" = None
    promotion: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Any) -> "ExecutionPolicy":
        """Build a policy from persisted reaction options."""
        if not isinstance(value, dict):
            return cls()
        mode = str(value.get("mode") or "auto_apply").strip()
        if mode not in {"auto_apply", "ask_residents"}:
            mode = "auto_apply"
        confirmation = (
            ConfirmationPolicy.from_mapping(value.get("confirmation"))
            if mode == "ask_residents"
            else None
        )
        promotion = value.get("promotion")
        return cls(
            mode=mode,  # type: ignore[arg-type]
            confirmation=confirmation,
            promotion=dict(promotion) if isinstance(promotion, dict) else {},
        )


@dataclass(frozen=True)
class ConfirmationPolicy:
    """Resident confirmation settings for one reaction."""

    target_recipients: tuple[str, ...] = ()
    target_groups: tuple[str, ...] = ()
    use_default_route_targets: bool = True
    expires_in_minutes: int = 10
    on_timeout: TimeoutBehavior = "skip"
    require_context_revalidation: bool = False

    @classmethod
    def from_mapping(cls, value: Any) -> "ConfirmationPolicy":
        """Build confirmation settings from persisted options."""
        if not isinstance(value, dict):
            return cls()
        on_timeout = str(value.get("on_timeout") or "skip").strip()
        if on_timeout not in {"skip", "apply"}:
            on_timeout = "skip"
        return cls(
            target_recipients=_string_tuple(value.get("target_recipients")),
            target_groups=_string_tuple(value.get("target_groups")),
            use_default_route_targets=bool(value.get("use_default_route_targets", True)),
            expires_in_minutes=max(1, _int_value(value.get("expires_in_minutes"), 10)),
            on_timeout=on_timeout,  # type: ignore[arg-type]
            require_context_revalidation=bool(value.get("require_context_revalidation", False)),
        )


@dataclass(frozen=True)
class RuntimeApplyResult:
    """Summary of what happened when a stored plan was processed."""

    applied_steps: int = 0
    blocked_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    blocked_reasons: dict[str, int] = field(default_factory=dict)
    failed_reasons: dict[str, int] = field(default_factory=dict)
    skipped_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def attempted_steps(self) -> int:
        """Number of steps that were not skipped by dependency handling."""
        return self.applied_steps + self.blocked_steps + self.failed_steps


@dataclass(frozen=True)
class RuntimeActionRequest:
    """Concrete one-shot resident confirmation request."""

    reaction_id: str
    reaction_type: str
    occurrence_key: str
    title: str
    message: str
    apply_steps: tuple[ApplyStep, ...]
    created_at: datetime
    expires_at: datetime
    on_timeout: TimeoutBehavior = "skip"
    status: RuntimeRequestStatus = "pending"
    request_id: str = field(default_factory=lambda: str(uuid4()))
    confirmation_targets: tuple[str, ...] = ()
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    apply_result: RuntimeApplyResult | None = None
    failure_reason: str | None = None

    @property
    def is_terminal(self) -> bool:
        """Return true once the first valid resolution won."""
        return self.status in TERMINAL_REQUEST_STATUSES


@dataclass(frozen=True)
class RuntimeRequestRegistryDiagnostics:
    """Serializable counters for the in-memory request registry."""

    pending: int = 0
    recent_completed: int = 0
    stale_responses: int = 0
    duplicate_occurrences: int = 0
    completed_by_status: dict[str, int] = field(default_factory=dict)
    pending_requests: list[dict[str, Any]] = field(default_factory=list)
    recent_completed_requests: list[dict[str, Any]] = field(default_factory=list)
    completed_step_counts: dict[str, int] = field(default_factory=dict)
    completed_blocked_reasons: dict[str, int] = field(default_factory=dict)
    completed_failed_reasons: dict[str, int] = field(default_factory=dict)
    completed_skipped_reasons: dict[str, int] = field(default_factory=dict)
    failed_request_reasons: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pending": self.pending,
            "recent_completed": self.recent_completed,
            "stale_responses": self.stale_responses,
            "duplicate_occurrences": self.duplicate_occurrences,
            "completed_by_status": dict(self.completed_by_status),
            "pending_requests": list(self.pending_requests),
            "recent_completed_requests": list(self.recent_completed_requests),
            "completed_step_counts": dict(self.completed_step_counts),
            "completed_blocked_reasons": dict(self.completed_blocked_reasons),
            "completed_failed_reasons": dict(self.completed_failed_reasons),
            "completed_skipped_reasons": dict(self.completed_skipped_reasons),
            "failed_request_reasons": dict(self.failed_request_reasons),
        }


class RuntimeActionRequestRegistry:
    """In-memory registry for pending runtime confirmation requests."""

    def __init__(self, *, recent_limit: int = 50) -> None:
        self._pending_by_id: dict[str, RuntimeActionRequest] = {}
        self._pending_by_occurrence: dict[tuple[str, str], str] = {}
        self._recent_completed: list[RuntimeActionRequest] = []
        self._recent_limit = max(1, recent_limit)
        self._stale_responses = 0
        self._duplicate_occurrences = 0

    def add(self, request: RuntimeActionRequest) -> RuntimeActionRequest:
        """Add a pending request, reusing an existing pending occurrence."""
        occurrence = (request.reaction_id, request.occurrence_key)
        existing_id = self._pending_by_occurrence.get(occurrence)
        if existing_id:
            existing = self._pending_by_id.get(existing_id)
            if existing is not None:
                self._duplicate_occurrences += 1
                return existing

        self._pending_by_id[request.request_id] = request
        self._pending_by_occurrence[occurrence] = request.request_id
        return request

    def get(self, request_id: str) -> RuntimeActionRequest | None:
        return self._pending_by_id.get(request_id)

    def resolve(
        self,
        request_id: str,
        *,
        status: RuntimeRequestStatus,
        apply_result: RuntimeApplyResult | None = None,
        failure_reason: str | None = None,
    ) -> RuntimeActionRequest | None:
        request = self._pending_by_id.get(request_id)
        if request is None:
            self._stale_responses += 1
            return None

        resolved = resolve_runtime_request(
            request,
            status=status,
            apply_result=apply_result,
            failure_reason=failure_reason,
        )
        if not resolved.is_terminal:
            self._pending_by_id[request_id] = resolved
            return resolved

        self._remove_pending(request)
        self._append_completed(resolved)
        return resolved

    def expire_due(self, now: datetime) -> tuple[RuntimeActionRequest, ...]:
        """Return and remove pending requests whose timeout has elapsed."""
        due: list[RuntimeActionRequest] = []
        for request in list(self._pending_by_id.values()):
            if request.expires_at > now:
                continue
            due.append(request)
            self._remove_pending(request)
        return tuple(due)

    def mark_completed(self, request: RuntimeActionRequest) -> RuntimeActionRequest:
        """Store an externally processed terminal request in recent history."""
        if not request.is_terminal:
            return request
        self._remove_pending(request)
        self._append_completed(request)
        return request

    def diagnostics(self) -> RuntimeRequestRegistryDiagnostics:
        completed_by_status: dict[str, int] = {}
        completed_step_counts = {
            "applied": 0,
            "blocked": 0,
            "failed": 0,
            "skipped": 0,
        }
        blocked_reasons: dict[str, int] = {}
        failed_reasons: dict[str, int] = {}
        skipped_reasons: dict[str, int] = {}
        failed_request_reasons: dict[str, int] = {}
        for request in self._recent_completed:
            completed_by_status[request.status] = completed_by_status.get(request.status, 0) + 1
            if request.failure_reason:
                failed_request_reasons[request.failure_reason] = (
                    failed_request_reasons.get(request.failure_reason, 0) + 1
                )
            if request.apply_result is None:
                continue
            completed_step_counts["applied"] += request.apply_result.applied_steps
            completed_step_counts["blocked"] += request.apply_result.blocked_steps
            completed_step_counts["failed"] += request.apply_result.failed_steps
            completed_step_counts["skipped"] += request.apply_result.skipped_steps
            _merge_reason_counts(blocked_reasons, request.apply_result.blocked_reasons)
            _merge_reason_counts(failed_reasons, request.apply_result.failed_reasons)
            _merge_reason_counts(skipped_reasons, request.apply_result.skipped_reasons)
        return RuntimeRequestRegistryDiagnostics(
            pending=len(self._pending_by_id),
            recent_completed=len(self._recent_completed),
            stale_responses=self._stale_responses,
            duplicate_occurrences=self._duplicate_occurrences,
            completed_by_status=completed_by_status,
            pending_requests=[
                _request_diagnostics(request) for request in self._pending_by_id.values()
            ],
            recent_completed_requests=[
                _request_diagnostics(request) for request in self._recent_completed
            ],
            completed_step_counts=completed_step_counts,
            completed_blocked_reasons=blocked_reasons,
            completed_failed_reasons=failed_reasons,
            completed_skipped_reasons=skipped_reasons,
            failed_request_reasons=failed_request_reasons,
        )

    def _remove_pending(self, request: RuntimeActionRequest) -> None:
        self._pending_by_id.pop(request.request_id, None)
        self._pending_by_occurrence.pop((request.reaction_id, request.occurrence_key), None)

    def _append_completed(self, request: RuntimeActionRequest) -> None:
        self._recent_completed.append(request)
        if len(self._recent_completed) > self._recent_limit:
            del self._recent_completed[: len(self._recent_completed) - self._recent_limit]


def _request_diagnostics(request: RuntimeActionRequest) -> dict[str, Any]:
    apply_result = request.apply_result
    return {
        "request_id": request.request_id,
        "reaction_id": request.reaction_id,
        "reaction_type": request.reaction_type,
        "occurrence_key": request.occurrence_key,
        "status": request.status,
        "created_at": request.created_at.isoformat(),
        "expires_at": request.expires_at.isoformat(),
        "on_timeout": request.on_timeout,
        "confirmation_targets": list(request.confirmation_targets),
        "failure_reason": request.failure_reason,
        "apply_steps": [_apply_step_diagnostics(step) for step in request.apply_steps],
        "apply_result": (
            {
                "applied_steps": apply_result.applied_steps,
                "blocked_steps": apply_result.blocked_steps,
                "failed_steps": apply_result.failed_steps,
                "skipped_steps": apply_result.skipped_steps,
                "blocked_reasons": dict(apply_result.blocked_reasons),
                "failed_reasons": dict(apply_result.failed_reasons),
                "skipped_reasons": dict(apply_result.skipped_reasons),
            }
            if apply_result is not None
            else None
        ),
    }


def _apply_step_diagnostics(step: ApplyStep) -> dict[str, Any]:
    return {
        "domain": step.domain,
        "target": step.target,
        "action": step.action,
        "step_id": step.step_id,
        "depends_on": list(step.depends_on),
        "blocked_by": step.blocked_by,
        "reason": step.reason,
        "source": step.source,
    }


def _merge_reason_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for reason, count in dict(source or {}).items():
        key = str(reason or "").strip()
        if not key:
            continue
        target[key] = target.get(key, 0) + int(count or 0)


@dataclass(frozen=True)
class RuntimePlanValidationResult:
    """Descriptor or generic validation result."""

    allowed: bool
    failure_reason: str = ""

    @classmethod
    def allow(cls) -> "RuntimePlanValidationResult":
        return cls(allowed=True)

    @classmethod
    def reject(cls, reason: str) -> "RuntimePlanValidationResult":
        return cls(allowed=False, failure_reason=reason or FAILURE_VALIDATION_FAILED)


@dataclass(frozen=True)
class RenderedRuntimeRequest:
    """Text shown to residents for a concrete stored plan."""

    title: str
    message: str


@dataclass(frozen=True)
class RuntimeConfirmationDescriptor:
    """Domain-specific hooks required to support runtime confirmation."""

    reaction_type: str
    occurrence_key: Callable[[Any, DecisionSnapshot, list[ApplyStep]], str]
    render_request: Callable[[Any, list[ApplyStep], str], RenderedRuntimeRequest]
    validate_stored_plan: (
        Callable[[RuntimeActionRequest, DecisionSnapshot], RuntimePlanValidationResult] | None
    ) = None
    validate_context: (
        Callable[[RuntimeActionRequest, DecisionSnapshot], RuntimePlanValidationResult] | None
    ) = None


@dataclass(frozen=True)
class DependencyEvaluation:
    """Result of evaluating explicit step dependencies."""

    steps: tuple[ApplyStep, ...]
    skipped_step_ids: tuple[str, ...] = ()
    skipped_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def skipped_steps(self) -> int:
        return len(self.skipped_step_ids)


def resolve_runtime_request(
    request: RuntimeActionRequest,
    *,
    status: RuntimeRequestStatus,
    apply_result: RuntimeApplyResult | None = None,
    failure_reason: str | None = None,
) -> RuntimeActionRequest:
    """Resolve a request once, preserving first-writer-wins semantics."""
    if request.is_terminal:
        return request
    if status == "pending":
        return request
    if status == "failed" and not failure_reason:
        failure_reason = FAILURE_VALIDATION_FAILED
    return replace(
        request,
        status=status,
        apply_result=apply_result,
        failure_reason=failure_reason if status == "failed" else None,
    )


def fail_if_zero_applied(
    request: RuntimeActionRequest,
    *,
    status: RuntimeRequestStatus,
    apply_result: RuntimeApplyResult,
    failure_reason: str = FAILURE_ALL_STEPS_BLOCKED,
) -> RuntimeActionRequest:
    """Resolve as failed when an apply trigger processed no executable steps."""
    if status not in {"approved", "timeout_applied"}:
        return resolve_runtime_request(
            request,
            status=status,
            apply_result=apply_result,
            failure_reason=failure_reason if status == "failed" else None,
        )
    if apply_result.applied_steps <= 0:
        return resolve_runtime_request(
            request,
            status="failed",
            apply_result=apply_result,
            failure_reason=failure_reason,
        )
    return resolve_runtime_request(request, status=status, apply_result=apply_result)


def evaluate_step_dependencies(
    steps: list[ApplyStep] | tuple[ApplyStep, ...],
    *,
    failed_step_ids: set[str] | None = None,
    skipped_step_ids: set[str] | None = None,
) -> DependencyEvaluation:
    """Skip steps whose explicit dependencies did not run.

    The function is pure and does not mutate step objects. It only considers
    explicit `step_id` / `depends_on` metadata; list order is ignored.
    """
    failed = set(failed_step_ids or set())
    skipped = set(skipped_step_ids or set())
    by_id = {step.step_id: step for step in steps if step.step_id}
    unavailable: dict[str, str] = {}
    for step in steps:
        if not step.step_id:
            continue
        if step.blocked_by:
            unavailable[step.step_id] = SKIP_DEPENDENCY_BLOCKED
        elif step.step_id in failed:
            unavailable[step.step_id] = SKIP_DEPENDENCY_FAILED
        elif step.step_id in skipped:
            unavailable[step.step_id] = SKIP_DEPENDENCY_SKIPPED

    changed = True
    while changed:
        changed = False
        for step in steps:
            if not step.step_id or step.step_id in unavailable:
                continue
            dependency_reason = _dependency_skip_reason(step, by_id, unavailable)
            if dependency_reason:
                unavailable[step.step_id] = dependency_reason
                changed = True

    for step_id in _cyclic_step_ids(steps, by_id, unavailable):
        unavailable.setdefault(step_id, SKIP_DEPENDENCY_CYCLE)

    kept: list[ApplyStep] = []
    skipped_ids: list[str] = []
    skipped_reasons: dict[str, int] = {}
    for step in steps:
        if step.step_id and step.step_id in unavailable and not step.blocked_by:
            skipped_ids.append(step.step_id)
            reason = unavailable[step.step_id]
            skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
            continue
        kept.append(step)

    return DependencyEvaluation(
        steps=tuple(kept),
        skipped_step_ids=tuple(skipped_ids),
        skipped_reasons=skipped_reasons,
    )


def _dependency_skip_reason(
    step: ApplyStep,
    by_id: dict[str, ApplyStep],
    unavailable: dict[str, str],
) -> str:
    for dependency_id in _string_tuple(step.depends_on):
        if dependency_id not in by_id:
            return SKIP_DEPENDENCY_MISSING
        if dependency_id in unavailable:
            reason = unavailable[dependency_id]
            if reason == SKIP_DEPENDENCY_FAILED:
                return SKIP_DEPENDENCY_FAILED
            if reason in {SKIP_DEPENDENCY_SKIPPED, SKIP_DEPENDENCY_MISSING, SKIP_DEPENDENCY_CYCLE}:
                return SKIP_DEPENDENCY_SKIPPED
            return SKIP_DEPENDENCY_BLOCKED
    return ""


def _cyclic_step_ids(
    steps: list[ApplyStep] | tuple[ApplyStep, ...],
    by_id: dict[str, ApplyStep],
    unavailable: dict[str, str],
) -> set[str]:
    cyclic: set[str] = set()
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in unavailable or step_id in visited:
            return
        if step_id in visiting:
            cyclic.update(visiting)
            return
        step = by_id.get(step_id)
        if step is None:
            return
        visiting.add(step_id)
        for dependency_id in _string_tuple(step.depends_on):
            if dependency_id in by_id:
                visit(dependency_id)
        visiting.discard(step_id)
        visited.add(step_id)

    for step in steps:
        if step.step_id:
            visit(step.step_id)
    return cyclic


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, list | tuple | set):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
