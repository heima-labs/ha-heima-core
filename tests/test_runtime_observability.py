"""Tests for runtime observability buffers."""

from __future__ import annotations

from custom_components.heima.runtime.contracts import ApplyPlan, ApplyStep
from custom_components.heima.runtime.observability import RuntimeObservabilityBuffer


def test_observability_buffer_records_applied_and_blocked_plan_traces() -> None:
    buffer = RuntimeObservabilityBuffer(event_limit=10, trace_limit=10)
    plan = ApplyPlan(
        plan_id="plan-1",
        steps=[
            ApplyStep(
                domain="switch",
                target="switch.interna_privacy",
                action="switch.turn_off",
                params={"entity_id": "switch.interna_privacy"},
                source="reaction:camera_privacy",
            ),
            ApplyStep(
                domain="light",
                target="light.studio",
                action="light.turn_on",
                params={"entity_id": "light.studio"},
                source="reaction:studio_scene",
                blocked_by="manual_hold:light:entity:light.studio:external_off",
            ),
        ],
    )

    buffer.record_apply_plan(reason="state_changed:alarm", plan=plan, engine_enabled=True)

    diagnostics = buffer.diagnostics()
    traces = {item["reaction_id"]: item for item in diagnostics["decision_traces"]}
    assert traces["camera_privacy"]["outcome"] == "applied"
    assert traces["camera_privacy"]["reason_codes"] == ["matched", "apply_plan_ready"]
    assert traces["studio_scene"]["outcome"] == "blocked"
    assert traces["studio_scene"]["reason_codes"] == ["manual_hold_active"]
    assert diagnostics["recent_events"][0]["reason_code"] == "applied"
    assert diagnostics["recent_events"][1]["reason_code"] == "blocked"


def test_observability_buffer_records_engine_disabled_as_skipped() -> None:
    buffer = RuntimeObservabilityBuffer(event_limit=10, trace_limit=10)
    plan = ApplyPlan(
        plan_id="plan-1",
        steps=[
            ApplyStep(
                domain="switch",
                target="switch.interna_privacy",
                action="switch.turn_off",
                params={"entity_id": "switch.interna_privacy"},
                source="reaction:camera_privacy",
            )
        ],
    )

    buffer.record_apply_plan(reason="test", plan=plan, engine_enabled=False)

    trace = buffer.diagnostics()["decision_traces"][0]
    assert trace["outcome"] == "skipped"
    assert trace["reason_codes"] == ["engine_disabled"]


def test_observability_buffer_records_runtime_confirmation_waiting_and_apply() -> None:
    buffer = RuntimeObservabilityBuffer(event_limit=10, trace_limit=10)
    steps = (
        ApplyStep(
            domain="light",
            target="light.studio",
            action="light.turn_on",
            params={"entity_id": "light.studio"},
            source="reaction:studio_scene",
            step_id="main",
        ),
    )

    buffer.record_runtime_confirmation_waiting(
        reaction_id="studio_scene",
        reaction_type="context_conditioned_lighting_scene",
        occurrence_key="occurrence-1",
        steps=steps,
    )
    buffer.record_runtime_confirmation_apply(
        reaction_id="studio_scene",
        request_id="request-1",
        status="approved",
        apply_steps=steps,
        applied_steps=1,
        blocked_reasons={},
        skipped_reasons={},
    )

    diagnostics = buffer.diagnostics()
    assert diagnostics["decision_traces"][0]["outcome"] == "waiting"
    assert diagnostics["decision_traces"][0]["reason_codes"] == [
        "matched",
        "waiting_for_resident_confirmation",
    ]
    assert diagnostics["decision_traces"][1]["outcome"] == "applied"
    assert diagnostics["decision_traces"][1]["reason_codes"] == ["approved", "applied"]


def test_observability_buffer_is_bounded() -> None:
    buffer = RuntimeObservabilityBuffer(event_limit=1, trace_limit=1)
    plan = ApplyPlan(
        plan_id="plan-1",
        steps=[
            ApplyStep(
                domain="switch",
                target="switch.one",
                action="switch.turn_on",
                params={"entity_id": "switch.one"},
                source="reaction:first",
            )
        ],
    )
    buffer.record_apply_plan(reason="first", plan=plan, engine_enabled=True)
    buffer.record_apply_plan(
        reason="second",
        plan=ApplyPlan(
            plan_id="plan-2",
            steps=[
                ApplyStep(
                    domain="switch",
                    target="switch.two",
                    action="switch.turn_on",
                    params={"entity_id": "switch.two"},
                    source="reaction:second",
                )
            ],
        ),
        engine_enabled=True,
    )

    diagnostics = buffer.diagnostics()
    assert len(diagnostics["recent_events"]) == 1
    assert len(diagnostics["decision_traces"]) == 1
    assert diagnostics["decision_traces"][0]["reaction_id"] == "second"


def test_observability_buffer_records_admin_action_events() -> None:
    buffer = RuntimeObservabilityBuffer(event_limit=10, trace_limit=10)

    buffer.record_admin_action(
        summary="Admin cleared manual hold 'light:entity:light.studio'.",
        reason_code="clear_manual_hold",
        object_links=({"kind": "manual_hold", "id": "light:entity:light.studio"},),
    )

    event = buffer.diagnostics()["recent_events"][0]
    assert event["category"] == "admin_action"
    assert event["severity"] == "info"
    assert event["reason_code"] == "clear_manual_hold"
    assert event["object_links"] == [{"kind": "manual_hold", "id": "light:entity:light.studio"}]
