from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.runtime_confirmation import (
    FAILURE_ALL_STEPS_BLOCKED,
    SKIP_DEPENDENCY_BLOCKED,
    SKIP_DEPENDENCY_CYCLE,
    SKIP_DEPENDENCY_MISSING,
    ConfirmationPolicy,
    ExecutionPolicy,
    RuntimeActionRequest,
    RuntimeActionRequestRegistry,
    RuntimeApplyResult,
    evaluate_step_dependencies,
    fail_if_zero_applied,
    resolve_runtime_request,
)


def test_execution_policy_defaults_to_auto_apply() -> None:
    policy = ExecutionPolicy.from_mapping(None)

    assert policy.mode == "auto_apply"
    assert policy.confirmation is None
    assert policy.promotion == {}


def test_execution_policy_parses_ask_residents_confirmation() -> None:
    policy = ExecutionPolicy.from_mapping(
        {
            "mode": "ask_residents",
            "confirmation": {
                "target_recipients": ["stefano"],
                "target_groups": ["residents"],
                "use_default_route_targets": False,
                "expires_in_minutes": 15,
                "on_timeout": "apply",
                "require_context_revalidation": True,
            },
            "promotion": {"enabled": True},
        }
    )

    assert policy.mode == "ask_residents"
    assert policy.confirmation == ConfirmationPolicy(
        target_recipients=("stefano",),
        target_groups=("residents",),
        use_default_route_targets=False,
        expires_in_minutes=15,
        on_timeout="apply",
        require_context_revalidation=True,
    )
    assert policy.promotion == {"enabled": True}


def test_resolve_runtime_request_is_first_writer_wins() -> None:
    request = _request()

    approved = resolve_runtime_request(request, status="approved")
    dismissed_late = resolve_runtime_request(approved, status="dismissed")

    assert approved.status == "approved"
    assert dismissed_late is approved


def test_runtime_request_registry_deduplicates_pending_occurrence() -> None:
    registry = RuntimeActionRequestRegistry()
    first = _request(request_id="request-1")
    duplicate = _request(request_id="request-2")

    assert registry.add(first) == first
    assert registry.add(duplicate) == first

    diagnostics = registry.diagnostics()
    assert diagnostics.pending == 1
    assert diagnostics.duplicate_occurrences == 1


def test_runtime_request_registry_resolves_and_counts_stale_responses() -> None:
    registry = RuntimeActionRequestRegistry()
    request = registry.add(_request(request_id="request-1"))

    resolved = registry.resolve(request.request_id, status="dismissed")
    stale = registry.resolve(request.request_id, status="approved")

    assert resolved is not None
    assert resolved.status == "dismissed"
    assert stale is None
    diagnostics = registry.diagnostics()
    assert diagnostics.pending == 0
    assert diagnostics.recent_completed == 1
    assert diagnostics.stale_responses == 1
    assert diagnostics.completed_by_status == {"dismissed": 1}


def test_runtime_request_registry_expires_due_requests() -> None:
    registry = RuntimeActionRequestRegistry()
    now = datetime.now(timezone.utc)
    due = _request(request_id="due", created_at=now, expires_at=now)
    later = _request(
        request_id="later",
        occurrence_key="occurrence-2",
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    registry.add(due)
    registry.add(later)

    expired = registry.expire_due(now)

    assert expired == (due,)
    assert registry.get("due") is None
    assert registry.get("later") == later
    assert registry.diagnostics().pending == 1


def test_failed_resolution_gets_default_failure_reason() -> None:
    failed = resolve_runtime_request(_request(), status="failed")

    assert failed.status == "failed"
    assert failed.failure_reason == "validation_failed"


def test_zero_applied_after_apply_trigger_becomes_failed() -> None:
    result = RuntimeApplyResult(blocked_steps=2, blocked_reasons={"manual_hold_active": 2})

    resolved = fail_if_zero_applied(_request(), status="approved", apply_result=result)

    assert resolved.status == "failed"
    assert resolved.apply_result == result
    assert resolved.failure_reason == FAILURE_ALL_STEPS_BLOCKED


def test_nonzero_apply_keeps_trigger_status() -> None:
    result = RuntimeApplyResult(applied_steps=1, blocked_steps=1)

    resolved = fail_if_zero_applied(_request(), status="timeout_applied", apply_result=result)

    assert resolved.status == "timeout_applied"
    assert resolved.apply_result == result
    assert resolved.failure_reason is None


def test_dependency_evaluation_skips_dependent_step_when_dependency_blocked() -> None:
    prepare = ApplyStep(
        domain="scene",
        target="scene.studio_prepare",
        action="scene.turn_on",
        step_id="prepare",
        blocked_by="manual_hold:lighting:room:studio:helper_on",
    )
    dim = ApplyStep(
        domain="light",
        target="light.studio_desk",
        action="light.turn_on",
        step_id="dim",
        depends_on=("prepare",),
    )
    unrelated = ApplyStep(
        domain="switch",
        target="switch.fan",
        action="switch.turn_on",
        step_id="fan",
    )

    result = evaluate_step_dependencies([prepare, dim, unrelated])

    assert result.steps == (prepare, unrelated)
    assert result.skipped_step_ids == ("dim",)
    assert result.skipped_reasons == {SKIP_DEPENDENCY_BLOCKED: 1}


def test_dependency_evaluation_skips_missing_dependency() -> None:
    step = ApplyStep(
        domain="light",
        target="light.studio",
        action="light.turn_on",
        step_id="dim",
        depends_on=("prepare",),
    )

    result = evaluate_step_dependencies([step])

    assert result.steps == ()
    assert result.skipped_step_ids == ("dim",)
    assert result.skipped_reasons == {SKIP_DEPENDENCY_MISSING: 1}


def test_dependency_evaluation_detects_cycle() -> None:
    first = ApplyStep(
        domain="light",
        target="light.first",
        action="light.turn_on",
        step_id="first",
        depends_on=("second",),
    )
    second = ApplyStep(
        domain="light",
        target="light.second",
        action="light.turn_on",
        step_id="second",
        depends_on=("first",),
    )

    result = evaluate_step_dependencies([first, second])

    assert result.steps == ()
    assert set(result.skipped_step_ids) == {"first", "second"}
    assert result.skipped_reasons == {SKIP_DEPENDENCY_CYCLE: 2}


def _request(
    *,
    request_id: str = "request-1",
    occurrence_key: str = "occurrence-1",
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> RuntimeActionRequest:
    now = created_at or datetime.now(timezone.utc)
    return RuntimeActionRequest(
        reaction_id="reaction-1",
        reaction_type="context_conditioned_lighting_scene",
        occurrence_key=occurrence_key,
        title="Apply scene?",
        message="Apply the stored scene.",
        apply_steps=(ApplyStep(domain="light", target="light.studio", action="light.turn_on"),),
        created_at=now,
        expires_at=expires_at or now + timedelta(minutes=10),
        request_id=request_id,
    )
