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
                        "guard_results": [],
                        "apply_steps": [],
                        "links": [{"kind": "reaction", "id": "reaction.one"}],
                    }
                ],
            },
            "learning_modules": [{"module_id": "house_state_inference"}],
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
        }


class _FakeRuntimeConfirmation:
    def diagnostics(self) -> dict[str, Any]:
        return {
            "pending": [{"request_id": "request.one"}],
            "recent_completed": [],
            "stale_responses": 1,
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
                        }
                    },
                    "groups": {"residents": {"members": ["stefano"]}},
                    "routes": {"runtime_confirmation": {"target_groups": ["residents"]}},
                    "notification_service_capabilities": {
                        "notify.mobile_app_iphone_stefano": {"supports_actions": True}
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
    assert snapshot["manual_holds"]["active_holds"][0]["scope"] == "light:entity:light.studio"
    assert snapshot["runtime_confirmations"]["pending"][0]["request_id"] == "request.one"
    assert snapshot["proposals"]["review_row_count"] == 3
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
