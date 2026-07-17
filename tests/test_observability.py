"""Tests for Heima admin observability."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.exceptions import Unauthorized

from custom_components.heima.const import DOMAIN
from custom_components.heima.observability import (
    OBSERVABILITY_SCHEMA_VERSION,
    build_observability_snapshot,
    redact_observability_data,
)
from custom_components.heima.websocket_api import (
    WS_TYPE_OBSERVABILITY_SNAPSHOT,
    websocket_observability_snapshot,
)


class _FakeConnection:
    def __init__(self, *, is_admin: bool) -> None:
        self.user = SimpleNamespace(is_admin=is_admin)
        self.results: list[tuple[int, Any]] = []
        self.errors: list[tuple[int, str, str]] = []

    def send_result(self, msg_id: int, result: Any | None = None) -> None:
        self.results.append((msg_id, result))

    def send_error(self, msg_id: int, code: str, message: str, *args: Any) -> None:
        self.errors.append((msg_id, code, message))


class _FakeEngine:
    health = SimpleNamespace(ok=True, reason="ok")

    def diagnostics(self) -> dict[str, Any]:
        return {
            "snapshot": {"house_state": "home"},
            "reactions": {
                "reaction.one": {
                    "reaction_type": "context_conditioned_lighting_scene",
                    "label": "Evening scene",
                    "origin": "learning_accepted",
                }
            },
            "reaction_execution_policies": {
                "reaction.one": {
                    "source": "profile",
                    "mode": "ask_residents",
                    "profile_id": "residents",
                }
            },
            "muted_reactions": [],
            "manual_hold": {
                "active_holds": [
                    {
                        "scope": "light:entity:light.studio",
                        "reason": "external_off",
                        "source_entity": "light.studio",
                    }
                ],
                "pending_applies": {"total": 0, "by_domain": {}, "items": []},
            },
            "observability": {
                "retention": {
                    "mode": "in_memory",
                    "description": "history_since_last_restart",
                    "event_limit": 500,
                    "trace_limit": 100,
                },
                "recent_events": [
                    {
                        "event_id": "event.one",
                        "timestamp": "2026-07-17T10:00:00+00:00",
                        "category": "reaction",
                        "severity": "info",
                        "summary": "Reaction applied.",
                        "reason_code": "applied",
                        "object_links": [{"kind": "reaction", "id": "reaction.one"}],
                    }
                ],
                "decision_traces": [
                    {
                        "trace_id": "trace.one",
                        "reaction_id": "reaction.one",
                        "occurrence_key": "occurrence.one",
                        "timestamp": "2026-07-17T10:00:00+00:00",
                        "outcome": "applied",
                        "reason_codes": ["matched", "apply_plan_ready"],
                        "input_summary": {},
                        "condition_results": [],
                        "guard_results": [
                            {
                                "result": "blocked",
                                "reason_code": "manual_hold_active",
                                "blocked_by": (
                                    "manual_hold:light:entity:light.studio:external_off"
                                ),
                            }
                        ],
                        "apply_steps": [
                            {
                                "step_id": "main",
                                "domain": "light",
                                "target": "light.studio",
                                "action": "light.turn_on",
                                "reason": "test",
                                "source": "reaction:reaction.one",
                                "blocked_by": (
                                    "manual_hold:light:entity:light.studio:external_off"
                                ),
                                "depends_on": [],
                            }
                        ],
                        "links": [{"kind": "reaction", "id": "reaction.one"}],
                    }
                ],
            },
            "learning_modules": [
                {"module_id": "house_state_inference", "ready": True},
                {"module_id": "lighting_pattern", "ready": False},
            ],
        }


class _FakeProposalEngine:
    def diagnostics(self) -> dict[str, Any]:
        return {
            "total": 10,
            "pending": 7,
            "accepted": 2,
            "rejected": 1,
            "review_row_count": 3,
            "suppressed_by_review_group": 4,
            "suppressed_in_review_count": 1,
            "pending_stale": 1,
            "review_rows": [
                {
                    "row_type": "temporal_bundle",
                    "bundle_id": "bundle.one",
                    "member_count": 2,
                    "predicted_state": "home",
                },
                {
                    "row_type": "proposal",
                    "proposal_id": "proposal.visible",
                    "type": "house_state_learned_context",
                },
            ],
            "review_groups": {"group.one": {"visible": "proposal.visible"}},
            "temporal_bundle_count": 1,
            "temporal_bundle_member_count": 2,
            "temporal_bundles": [
                {
                    "bundle_id": "bundle.one",
                    "member_count": 2,
                    "predicted_state": "home",
                }
            ],
            "proposals": [
                {
                    "id": "proposal.visible",
                    "type": "house_state_learned_context",
                    "status": "pending",
                    "followup_kind": "discovery",
                    "suppressed_by_review_group": False,
                    "is_stale": False,
                },
                {
                    "id": "proposal.hidden",
                    "type": "house_state_learned_context",
                    "status": "pending",
                    "followup_kind": "discovery",
                    "suppressed_by_review_group": True,
                    "is_stale": True,
                },
                {
                    "id": "proposal.accepted",
                    "type": "activity_discovered",
                    "status": "accepted",
                    "followup_kind": "discovery",
                    "suppressed_by_review_group": False,
                    "is_stale": False,
                },
            ],
            "analyzer_failures": {"house_state_inference": 1},
            "analyzer_output_errors": {},
            "lifecycle_monitoring": {"record_count": 2},
        }


class _FakeRuntimeConfirmation:
    def diagnostics(self) -> dict[str, Any]:
        return {
            "pending": [{"request_id": "request.one"}],
            "recent_completed": [{"request_id": "request.done", "status": "approved"}],
            "stale_responses": 1,
            "duplicate_occurrences": 2,
            "completed_by_status": {"approved": 1},
            "completed_step_counts": {"applied": 1, "blocked": 0, "failed": 0, "skipped": 0},
            "completed_blocked_reasons": {},
            "completed_failed_reasons": {},
            "completed_skipped_reasons": {},
            "failed_request_reasons": {},
            "scheduled_timeouts": ["request.one"],
            "action_event_subscription_active": True,
            "persisted": {
                "by_reaction": {
                    "reaction.one": {
                        "promotion_review": {
                            "status": "pending_admin_review",
                            "review_id": "review.one",
                        }
                    }
                }
            },
        }


class _FakeCoordinator:
    def __init__(self) -> None:
        self.entry = SimpleNamespace(
            entry_id="entry-1",
            options={
                "notifications": {
                    "recipients": {
                        "stefano": {
                            "notify_services": ["notify.mobile_app_iphone_stefano"],
                            "token": "secret-token",
                        },
                        "tablet": ["persistent_notification"],
                    },
                    "groups": {"residents": {"members": ["stefano"]}},
                    "recipient_groups": {"residents": ["stefano", "tablet"]},
                    "route_targets": ["residents", "missing"],
                    "routes": {"runtime_confirmation": {"target_groups": ["residents"]}},
                    "notification_service_capabilities": {
                        "mobile_app_iphone_stefano": {"supports_actions": True},
                        "persistent_notification": {"supports_actions": False},
                    },
                }
            },
        )
        self.hass = SimpleNamespace(data={})
        self.engine = _FakeEngine()
        self.proposal_engine = _FakeProposalEngine()
        self._runtime_confirmation = _FakeRuntimeConfirmation()
        self.data = SimpleNamespace(
            house_state="home",
            house_state_reason="learned",
            last_decision="evaluation_requested:test",
            last_action="",
        )

    def _health_status(self) -> str:
        return "ok"

    def _health_reason(self) -> str:
        return "ok"

    def _validation_report(self) -> SimpleNamespace:
        return SimpleNamespace(as_dict=lambda: {"ok": True, "issues": []})


def test_observability_snapshot_has_versioned_minimal_sections() -> None:
    snapshot = build_observability_snapshot(_FakeCoordinator())

    assert snapshot["meta"]["schema_version"] == OBSERVABILITY_SCHEMA_VERSION
    assert snapshot["meta"]["entry_id"] == "entry-1"
    assert snapshot["meta"]["is_partial"] is False
    assert snapshot["runtime"]["house_state"] == "home"
    assert snapshot["reactions"][0]["reaction_id"] == "reaction.one"
    assert snapshot["reactions"][0]["latest_trace_id"] == "trace.one"
    assert snapshot["reactions"][0]["last_outcome"] == "applied"
    assert snapshot["reactions"][0]["linked_manual_hold_scopes"] == ["light:entity:light.studio"]
    assert snapshot["manual_holds"]["active_holds"][0]["scope"] == "light:entity:light.studio"
    assert snapshot["manual_holds"]["active_holds"][0]["affected_reaction_ids"] == ["reaction.one"]
    assert snapshot["manual_holds"]["active_holds"][0]["links"] == [
        {"kind": "reaction", "id": "reaction.one"},
        {"kind": "entity", "id": "light.studio"},
    ]
    assert snapshot["runtime_confirmations"]["pending"][0]["request_id"] == "request.one"
    assert snapshot["runtime_confirmations"]["recent_completed"][0]["request_id"] == "request.done"
    assert snapshot["runtime_confirmations"]["completed_by_status"] == {"approved": 1}
    assert snapshot["runtime_confirmations"]["scheduled_timeouts"] == ["request.one"]
    assert snapshot["runtime_confirmations"]["action_event_subscription_active"] is True
    assert snapshot["notifications"]["resolved_routes"] == [
        "mobile_app_iphone_stefano",
        "persistent_notification",
    ]
    assert snapshot["notifications"]["unresolved_targets"] == ["missing"]
    assert snapshot["notifications"]["actionable_routes"] == ["mobile_app_iphone_stefano"]
    assert snapshot["notifications"]["skipped_non_actionable_routes"] == ["persistent_notification"]
    assert snapshot["proposals"]["review_row_count"] == 3
    assert snapshot["proposals"]["real_pending_count"] == 2
    assert snapshot["proposals"]["visible_pending_count"] == 1
    assert snapshot["proposals"]["suppressed_pending_count"] == 1
    assert snapshot["proposals"]["pending_by_type"] == {"house_state_learned_context": 2}
    assert snapshot["proposals"]["review_rows"][0]["row_type"] == "temporal_bundle"
    assert snapshot["proposals"]["temporal_bundles"][0]["bundle_id"] == "bundle.one"
    assert snapshot["learning"]["module_count"] == 2
    assert snapshot["learning"]["ready_module_count"] == 1
    assert snapshot["learning"]["analyzer_failures"] == {"house_state_inference": 1}
    assert snapshot["recent_events"][0]["event_id"] == "event.one"
    assert snapshot["decision_traces"][0]["trace_id"] == "trace.one"
    assert snapshot["meta"]["retention"]["description"] == "history_since_last_restart"


def test_observability_redacts_secrets_but_preserves_entity_ids() -> None:
    redacted = redact_observability_data(
        {
            "entity_id": "switch.interna_privacy",
            "access_token": "abc",
            "nested": {"Authorization": "Bearer abc"},
            "plain": "Bearer abc",
        }
    )

    assert redacted["entity_id"] == "switch.interna_privacy"
    assert redacted["access_token"] == "**REDACTED**"
    assert redacted["nested"]["Authorization"] == "**REDACTED**"
    assert redacted["plain"] == "**REDACTED**"


def test_observability_snapshot_marks_partial_sections() -> None:
    coordinator = _FakeCoordinator()
    coordinator.engine = SimpleNamespace(diagnostics=lambda: (_ for _ in ()).throw(RuntimeError()))

    snapshot = build_observability_snapshot(coordinator)

    assert snapshot["meta"]["is_partial"] is True
    assert snapshot["meta"]["partial_reasons"] == ["engine:RuntimeError"]


def test_observability_websocket_requires_admin() -> None:
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": _FakeCoordinator()}}})
    connection = _FakeConnection(is_admin=False)

    with pytest.raises(Unauthorized):
        websocket_observability_snapshot(
            hass,
            connection,
            {"id": 1, "type": WS_TYPE_OBSERVABILITY_SNAPSHOT, "entry_id": "entry-1"},
        )

    assert connection.results == []
    assert connection.errors == []


def test_observability_websocket_returns_snapshot_for_admin() -> None:
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": _FakeCoordinator()}}})
    connection = _FakeConnection(is_admin=True)

    websocket_observability_snapshot(
        hass,
        connection,
        {"id": 1, "type": WS_TYPE_OBSERVABILITY_SNAPSHOT, "entry_id": "entry-1"},
    )

    assert connection.errors == []
    assert connection.results[0][0] == 1
    assert connection.results[0][1]["meta"]["entry_id"] == "entry-1"


def test_observability_websocket_reports_missing_entry_for_admin() -> None:
    hass = SimpleNamespace(data={DOMAIN: {}})
    connection = _FakeConnection(is_admin=True)

    websocket_observability_snapshot(
        hass,
        connection,
        {"id": 1, "type": WS_TYPE_OBSERVABILITY_SNAPSHOT, "entry_id": "missing"},
    )

    assert connection.results == []
    assert connection.errors[0][1] == "not_found"
