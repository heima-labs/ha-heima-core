"""Tests for Heima admin observability."""

from __future__ import annotations

import asyncio
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
from custom_components.heima.runtime.observability import RuntimeObservabilityBuffer
from custom_components.heima.websocket_api import (
    _WHY_NOT_NOW_CALLS,
    WS_TYPE_OBSERVABILITY_ACTION,
    WS_TYPE_OBSERVABILITY_SNAPSHOT,
    WS_TYPE_OBSERVABILITY_WHY_NOT_NOW,
    websocket_observability_action,
    websocket_observability_snapshot,
    websocket_observability_why_not_now,
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


class _FakeHass:
    def __init__(self, coordinator: Any | None = None) -> None:
        self.tasks: list[asyncio.Task[Any]] = []
        self.data = (
            {DOMAIN: {"entry-1": {"coordinator": coordinator}}} if coordinator else {DOMAIN: {}}
        )

    def async_create_task(self, task: Any) -> asyncio.Task[Any]:
        created = asyncio.create_task(task)
        self.tasks.append(created)
        return created

    async def drain(self) -> None:
        if self.tasks:
            await asyncio.gather(*self.tasks)


class _FakeEngine:
    health = SimpleNamespace(ok=True, reason="ok")

    def __init__(self) -> None:
        self._observability = RuntimeObservabilityBuffer()
        self.cleared_manual_holds: list[tuple[str, str, str]] = []

    def clear_manual_hold(self, *, domain: str, subject_type: str, subject_id: str) -> None:
        self.cleared_manual_holds.append((domain, subject_type, subject_id))

    def diagnostics(self) -> dict[str, Any]:
        observability = self._observability.diagnostics()
        if not observability["recent_events"]:
            observability["recent_events"] = [
                {
                    "event_id": "event.one",
                    "timestamp": "2026-07-17T10:00:00+00:00",
                    "category": "reaction",
                    "severity": "info",
                    "summary": "Reaction applied.",
                    "reason_code": "applied",
                    "object_links": [{"kind": "reaction", "id": "reaction.one"}],
                }
            ]
        observability["decision_traces"] = [
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
                        "blocked_by": "manual_hold:light:entity:light.studio:external_off",
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
                        "blocked_by": "manual_hold:light:entity:light.studio:external_off",
                        "depends_on": [],
                    }
                ],
                "links": [{"kind": "reaction", "id": "reaction.one"}],
            }
        ]
        return {
            "snapshot": {"house_state": "home"},
            "reactions": {
                "reaction.one": {
                    "fire_count": 1,
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
            "apply_plan": {
                "plan_id": "plan.one",
                "steps": [
                    {
                        "domain": "light",
                        "target": "light.studio",
                        "action": "light.turn_on",
                        "blocked_by": "recovery:power_recovery",
                    }
                ],
            },
            "recovery": {
                "state": "power_recovery",
                "reason": "critical_entities_unavailable",
                "active": True,
                "started_at_monotonic": 100.0,
                "settling_started_at_monotonic": None,
                "parent_state": "power_recovery",
                "unavailable_ratio": 0.5,
                "unavailable_count": 1,
                "critical_entity_count": 2,
                "stabilization_deadline_monotonic": 160.0,
                "stable_snapshot_available": False,
                "reconciliation_pending": False,
                "critical_entities": [
                    {
                        "entity_id": "light.studio",
                        "domain": "light",
                        "state": "unavailable",
                        "available": False,
                    },
                    {
                        "entity_id": "switch.interna_privacy",
                        "domain": "switch",
                        "state": "on",
                        "available": True,
                    },
                ],
                "checkpoint": {
                    "available": True,
                    "usable": True,
                    "stale": False,
                    "checkpoint_id": "checkpoint.one",
                    "age_s": 45.0,
                    "reason": "usable",
                    "difference_count": 1,
                    "differences": [
                        {
                            "entity_id": "light.studio",
                            "domain": "light",
                            "checkpoint_state": "off",
                            "current_state": "unavailable",
                            "kind": "unknown_during_downtime",
                        }
                    ],
                },
            },
            "runtime_context": {"runtime.recovery.state": "power_recovery"},
            "runtime_checkpoint": {
                "storage_key": "heima_runtime_checkpoints",
                "loaded": True,
                "entry_count": 1,
                "load_errors": 0,
                "checkpoints": {"entry-1": {"checkpoint_id": "checkpoint.one"}},
            },
            "runtime_checkpoint_status": {
                "pending_write_reason": "scheduled",
                "write_job_id": "recovery.checkpoint.write",
            },
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
            "house_state": {
                "candidate_trace": {
                    "work_candidate": {
                        "state": True,
                        "reason": "anyone_home+work_window+work_activity",
                        "inputs": {
                            "anyone_home": True,
                            "work_window": True,
                            "work_activity_active": True,
                        },
                    }
                },
                "candidate_summary": {
                    "work_candidate": {
                        "status": "confirmed",
                        "since": "2026-07-17T09:55:00+00:00",
                    }
                },
                "resolution_trace": {
                    "active_candidates": ["work_candidate"],
                    "resolution_path": "home_substate",
                    "winning_reason": "work_candidate_confirmed",
                    "decision": {
                        "action": "enter",
                        "entered_state": "working",
                        "source_candidate": "work_candidate",
                    },
                },
                "house_signals_trace": {
                    "work_window": {"state": True},
                },
                "timers": {"work_enter_min": 5},
                "config": {"work_enter_min": 5},
                "override": {"house_state_override_active": False},
            },
            "observability": observability,
            "events": {
                "notification_delivery_policy": {
                    "name": "Notification Delivery Policy",
                    "decision_counts": {"observability_only": 1},
                    "recent_decisions": [
                        {
                            "outcome": "observability_only",
                            "reason": "policy_observability_only",
                            "event_family": "people",
                            "push_policy": "observability",
                            "target_roles": [],
                            "route_targets": [],
                            "audience": "observability",
                            "security_critical": False,
                            "diagnostics": {"event_type": "people.arrive"},
                        }
                    ],
                    "persistence": {"pending_count": 0, "delivered_count": 0},
                    "aggregation": {"buckets": {}},
                    "burst": {"recent_delivery_count": 0},
                }
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
                    "proposal_ids": ["proposal.visible", "proposal.hidden"],
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
                    "target_reaction_id": "reaction.one",
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
            "analyzer_output_errors": 2,
            "lifecycle_monitoring": {"record_count": 2},
        }


class _FakeRuntimeConfirmation:
    def diagnostics(self) -> dict[str, Any]:
        return {
            "pending": 1,
            "recent_completed": 1,
            "pending_requests": [{"request_id": "request.one", "reaction_id": "reaction.one"}],
            "recent_completed_requests": [
                {"request_id": "request.done", "reaction_id": "reaction.one", "status": "approved"}
            ],
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
        self._health_status_value = "ok"
        self._health_reason_value = "ok"
        self._last_anomaly: dict[str, Any] | None = None
        self._last_invariant_violation: dict[str, Any] | None = None
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
                    "recipient_groups": {
                        "admins": ["stefano"],
                        "residents": ["stefano", "tablet"],
                    },
                    "route_targets": ["residents", "missing"],
                    "audience_targets": {"admins": ["admins"], "residents": ["missing"]},
                    "routes": {"runtime_confirmation": {"target_groups": ["residents"]}},
                    "notification_service_capabilities": {
                        "mobile_app_iphone_stefano": {"supports_actions": True},
                        "persistent_notification": {"supports_actions": False},
                    },
                },
                "security": {
                    "camera_evidence_sources": [
                        {
                            "id": "interna",
                            "role": "entry",
                            "privacy_entity": "switch.interna_privacy",
                            "motion_entity": "binary_sensor.interna_motion",
                        }
                    ]
                },
                "reactions": {
                    "configured": {
                        "reaction.one": {
                            "reaction_type": "context_conditioned_lighting_scene",
                            "origin": "learning_accepted",
                            "author_kind": "admin",
                            "source_template_id": "lighting.context_conditioned",
                            "api_token": "super-secret-token",
                        }
                    },
                    "labels": {"reaction.one": "Evening scene"},
                },
            },
        )
        self.evaluation_reasons: list[str] = []
        self.hass = SimpleNamespace(data={}, async_create_task=self._create_task)
        self.engine = _FakeEngine()
        self.reviewed_promotions: list[tuple[str, str]] = []
        self.reset_promotions: list[str] = []
        self.reviewed_proposals: list[tuple[str, str, str]] = []
        self.reviewed_proposal_batches: list[tuple[tuple[str, ...], str, str, bool]] = []
        self.proposal_engine = _FakeProposalEngine()
        self._runtime_confirmation = _FakeRuntimeConfirmation()
        self.data = SimpleNamespace(
            house_state="home",
            house_state_reason="learned",
            last_decision="evaluation_requested:test",
            last_action="",
        )

    def _health_status(self) -> str:
        return self._health_status_value

    def _health_reason(self) -> str:
        return self._health_reason_value

    def _validation_report(self) -> SimpleNamespace:
        return SimpleNamespace(as_dict=lambda: {"ok": True, "issues": []})

    def _create_task(self, task: Any) -> None:
        if hasattr(task, "close"):
            task.close()

    async def async_request_evaluation(self, *, reason: str) -> None:
        self.evaluation_reasons.append(reason)

    async def async_review_runtime_promotion(self, reaction_id: str, action: str) -> bool:
        self.reviewed_promotions.append((reaction_id, action))
        return reaction_id == "reaction.one"

    async def async_reset_runtime_confirmation_promotion_state(self, reaction_id: str) -> bool:
        self.reset_promotions.append(reaction_id)
        return reaction_id == "reaction.one"

    async def async_review_proposal(
        self,
        proposal_id: str,
        *,
        decision: str,
        approved_by: str,
    ) -> bool:
        self.reviewed_proposals.append((proposal_id, decision, approved_by))
        return proposal_id == "proposal.visible"

    async def async_review_house_state_proposal_batch(
        self,
        proposal_ids: list[str] | tuple[str, ...],
        *,
        decision: str,
        approved_by: str,
        dismiss_similar: bool = False,
    ) -> SimpleNamespace:
        self.reviewed_proposal_batches.append(
            (tuple(proposal_ids), decision, approved_by, dismiss_similar)
        )
        if "stale" in proposal_ids:
            return SimpleNamespace(ok=False, applied_ids=())
        return SimpleNamespace(ok=True, applied_ids=tuple(proposal_ids), ineligible_ids=())


def test_observability_snapshot_has_versioned_minimal_sections() -> None:
    snapshot = build_observability_snapshot(_FakeCoordinator())

    assert snapshot["meta"]["schema_version"] == OBSERVABILITY_SCHEMA_VERSION
    assert snapshot["meta"]["entry_id"] == "entry-1"
    assert snapshot["meta"]["is_partial"] is False
    assert snapshot["runtime"]["house_state"] == "home"
    assert snapshot["reactions"][0]["reaction_id"] == "reaction.one"
    assert snapshot["reactions"][0]["reaction_type"] == "context_conditioned_lighting_scene"
    assert snapshot["reactions"][0]["label"] == "Evening scene"
    assert snapshot["reactions"][0]["origin"] == "learning_accepted"
    assert snapshot["reactions"][0]["author_kind"] == "admin"
    assert snapshot["reactions"][0]["source_template_id"] == "lighting.context_conditioned"
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
    assert snapshot["runtime_confirmations"]["pending_count"] == 1
    assert snapshot["runtime_confirmations"]["recent_completed"][0]["request_id"] == "request.done"
    assert snapshot["runtime_confirmations"]["recent_completed_count"] == 1
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
    assert snapshot["notifications"]["audience_resolution"] == [
        {
            "role": "admins",
            "target": "admins",
            "target_type": "group",
            "routes": ["mobile_app_iphone_stefano"],
            "unresolved": False,
            "actionable_routes": ["mobile_app_iphone_stefano"],
            "text_only_routes": [],
        },
        {
            "role": "residents",
            "target": "missing",
            "target_type": "missing",
            "routes": [],
            "unresolved": True,
            "actionable_routes": [],
            "text_only_routes": [],
        },
    ]
    delivery_policy = snapshot["notifications"]["delivery_policy"]
    assert delivery_policy["effective"]["audience_policy"]["people"]["push"] == "observability"
    assert delivery_policy["health"]["status"] == "warning"
    assert delivery_policy["health"]["issue_count"] == 3
    assert delivery_policy["health"]["issues"] == [
        {"severity": "warning", "reason": "unresolved_fallback_targets"},
        {"severity": "warning", "reason": "unresolved_audience_targets"},
        {"severity": "warning", "reason": "residents_audience_not_group_backed"},
    ]
    assert delivery_policy["unresolved_audience_targets"] == [
        {"role": "residents", "target": "missing"}
    ]
    assert delivery_policy["runtime"]["decision_counts"] == {"observability_only": 1}
    assert delivery_policy["runtime"]["recent_decisions"][0]["reason"] == (
        "policy_observability_only"
    )
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
    assert snapshot["learning"]["analyzer_output_errors"] == {"total": 2}
    assert snapshot["house_state"]["winning_reason"] == "work_candidate_confirmed"
    assert snapshot["house_state"]["resolution_path"] == "home_substate"
    assert snapshot["house_state"]["decision_action"] == "enter"
    assert snapshot["house_state"]["decision_target_state"] == "working"
    assert snapshot["house_state"]["active_candidates"] == ["work_candidate"]
    assert snapshot["house_state"]["candidate_trace"]["work_candidate"]["state"] is True
    assert snapshot["house_state"]["candidate_summary"]["work_candidate"]["status"] == "confirmed"
    assert snapshot["details"]["house_state"]["resolution_trace"]["decision"]["action"] == "enter"
    assert snapshot["recent_events"][0]["event_id"] == "event.one"
    assert snapshot["decision_traces"][0]["trace_id"] == "trace.one"
    assert snapshot["meta"]["retention"]["description"] == "history_since_last_restart"
    reaction_detail = snapshot["details"]["reactions"]["by_id"]["reaction.one"]
    assert reaction_detail["summary"]["reaction_id"] == "reaction.one"
    assert reaction_detail["configured_metadata"]["reaction_type"] == (
        "context_conditioned_lighting_scene"
    )
    assert reaction_detail["configured_metadata"]["api_token"] == "**REDACTED**"
    assert reaction_detail["runtime_diagnostics"] == {"fire_count": 1}
    assert reaction_detail["execution_policy"]["mode"] == "ask_residents"
    assert reaction_detail["latest_trace"]["trace_id"] == "trace.one"
    assert reaction_detail["linked_manual_holds"][0]["scope"] == "light:entity:light.studio"
    assert reaction_detail["linked_runtime_confirmations"][0]["request_id"] == "request.one"
    assert reaction_detail["linked_promotion_reviews"][0]["review_id"] == "review.one"
    assert reaction_detail["linked_proposals"][0]["id"] == "proposal.visible"
    hold_detail = snapshot["details"]["manual_holds"]["by_scope"]["light:entity:light.studio"]
    assert hold_detail["affected_reaction_ids"] == ["reaction.one"]
    request_detail = snapshot["details"]["runtime_confirmations"]["by_request_id"]["request.one"]
    assert request_detail["status_bucket"] == "pending"
    proposal_detail = snapshot["details"]["proposals"]["by_id"]["proposal.visible"]
    assert proposal_detail["linked_reaction_ids"] == ["reaction.one"]
    review_detail = snapshot["details"]["proposals"]["review_rows_by_id"]["bundle.one"]
    assert review_detail["proposal_ids"] == ["proposal.visible", "proposal.hidden"]
    assert snapshot["entity_impact"]["by_domain"] == {
        "binary_sensor": 1,
        "light": 1,
        "switch": 1,
    }
    entities = snapshot["details"]["entities"]["by_id"]
    assert entities["light.studio"]["reaction_ids"] == ["reaction.one"]
    assert entities["light.studio"]["hold_scopes"] == ["light:entity:light.studio"]
    assert entities["light.studio"]["trace_ids"] == ["trace.one"]
    assert entities["switch.interna_privacy"]["source_metadata"] == [
        {
            "camera_source_id": "interna",
            "kind": "security_camera_privacy_source",
            "role": "entry",
        },
        {
            "camera_source_id": "interna",
            "field": "privacy_entity",
            "kind": "security_camera_evidence_source",
        },
    ]
    assert "notify.mobile_app_iphone_stefano" not in entities


def test_observability_notification_health_warns_when_residents_group_is_missing() -> None:
    coordinator = _FakeCoordinator()
    notifications = coordinator.entry.options["notifications"]
    notifications["recipient_groups"] = {"admins": ["stefano"]}
    notifications["route_targets"] = ["admins"]
    notifications["audience_targets"] = {"admins": ["admins"], "residents": ["stefano"]}

    snapshot = build_observability_snapshot(coordinator)

    health = snapshot["notifications"]["delivery_policy"]["health"]
    assert health["status"] == "warning"
    assert {"severity": "warning", "reason": "missing_residents_group"} in health["issues"]
    assert {
        "severity": "warning",
        "reason": "residents_audience_not_group_backed",
    } in health["issues"]
    assert snapshot["notifications"]["delivery_policy"]["unresolved_audience_targets"] == []


def test_observability_snapshot_exposes_recovery_state() -> None:
    snapshot = build_observability_snapshot(_FakeCoordinator())

    recovery = snapshot["recovery"]
    assert recovery["state"] == "power_recovery"
    assert recovery["active"] is True
    assert recovery["critical_entities"]["total"] == 2
    assert recovery["critical_entities"]["unavailable"] == 1
    assert recovery["critical_entities"]["unavailable_items"][0]["entity_id"] == "light.studio"
    assert recovery["checkpoint"]["checkpoint_id"] == "checkpoint.one"
    assert recovery["checkpoint"]["pending_write_reason"] == "scheduled"
    assert recovery["blocked_apply_steps"]["total"] == 1
    assert recovery["blocked_apply_steps"]["examples"][0]["blocked_by"] == (
        "recovery:power_recovery"
    )
    assert snapshot["details"]["recovery"]["checkpoint"]["checkpoint_id"] == "checkpoint.one"


def test_observability_health_exports_invariant_violation_details() -> None:
    coordinator = _FakeCoordinator()
    coordinator._health_status_value = "degraded"
    coordinator._health_reason_value = "invariant_violation"
    coordinator._last_anomaly = {
        "type": "anomaly.presence_without_occupancy",
        "key": "anomaly.presence_without_occupancy",
        "severity": "warning",
        "title": "Invariant violation",
        "message": "Presence says someone is home, but no derived room is occupied.",
        "context": {
            "check_id": "presence_without_occupancy",
            "anomaly_type": "presence_without_occupancy",
            "people_count": 2,
            "occupied_rooms": [],
        },
        "event_id": "event.presence",
        "ts": "2026-07-23T08:27:33+00:00",
    }
    coordinator._last_invariant_violation = dict(coordinator._last_anomaly)

    snapshot = build_observability_snapshot(coordinator)

    health = snapshot["health"]
    assert health["status"] == "degraded"
    assert health["reason"] == "invariant_violation"
    assert health["last_anomaly"]["type"] == "anomaly.presence_without_occupancy"
    assert health["last_invariant_violation"]["context"]["check_id"] == (
        "presence_without_occupancy"
    )
    finding = snapshot["health_findings"][0]
    assert finding["summary"] == ("Presence says someone is home, but no derived room is occupied.")
    assert finding["suggested_action"] == (
        "Inspect invariant check 'presence_without_occupancy' in the Health section."
    )
    assert finding["details"]["event_id"] == "event.presence"


def test_observability_health_finding_handles_missing_context() -> None:
    coordinator = _FakeCoordinator()
    coordinator._health_status_value = "degraded"
    coordinator._health_reason_value = "invariant_violation"
    coordinator._last_invariant_violation = {
        "type": "anomaly.presence_without_occupancy",
        "severity": "warning",
        "title": "Invariant violation",
        "message": "Presence says someone is home, but no derived room is occupied.",
        "context": None,
    }

    snapshot = build_observability_snapshot(coordinator)

    finding = snapshot["health_findings"][0]
    assert finding["suggested_action"] == "Open the Health section for details."


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


def test_observability_why_not_now_requires_admin() -> None:
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": _FakeCoordinator()}}})
    connection = _FakeConnection(is_admin=False)

    with pytest.raises(Unauthorized):
        websocket_observability_why_not_now(
            hass,
            connection,
            {
                "id": 1,
                "type": WS_TYPE_OBSERVABILITY_WHY_NOT_NOW,
                "entry_id": "entry-1",
                "reaction_id": "reaction.one",
            },
        )

    assert connection.results == []
    assert connection.errors == []


def test_observability_why_not_now_returns_not_evaluable_for_supported_contract() -> None:
    _WHY_NOT_NOW_CALLS.clear()
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": _FakeCoordinator()}}})
    connection = _FakeConnection(is_admin=True)

    websocket_observability_why_not_now(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_WHY_NOT_NOW,
            "entry_id": "entry-1",
            "reaction_id": "reaction.one",
        },
    )

    assert connection.errors == []
    result = connection.results[0][1]
    assert result["reaction_id"] == "reaction.one"
    assert result["outcome"] == "not_evaluable"
    assert result["reason_codes"] == ["focused_evaluation_not_supported"]
    assert result["input_summary"]["reaction_type"] == "context_conditioned_lighting_scene"
    assert result["guard_results"][0]["reason_code"] == "manual_hold_active"
    assert result["apply_steps"][0]["target"] == "light.studio"
    assert {"kind": "reaction", "id": "reaction.one"} in result["links"]


def test_observability_why_not_now_returns_not_found_for_unknown_reaction() -> None:
    _WHY_NOT_NOW_CALLS.clear()
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": _FakeCoordinator()}}})
    connection = _FakeConnection(is_admin=True)

    websocket_observability_why_not_now(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_WHY_NOT_NOW,
            "entry_id": "entry-1",
            "reaction_id": "missing",
        },
    )

    assert connection.errors == []
    assert connection.results[0][1]["outcome"] == "not_found"
    assert connection.results[0][1]["reason_codes"] == ["reaction_not_found"]


def test_observability_why_not_now_rate_limits_per_entry() -> None:
    _WHY_NOT_NOW_CALLS.clear()
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": _FakeCoordinator()}}})
    connection = _FakeConnection(is_admin=True)

    for msg_id in (1, 2, 3):
        websocket_observability_why_not_now(
            hass,
            connection,
            {
                "id": msg_id,
                "type": WS_TYPE_OBSERVABILITY_WHY_NOT_NOW,
                "entry_id": "entry-1",
                "reaction_id": "reaction.one",
            },
        )

    assert [result[0] for result in connection.results] == [1, 2]
    assert connection.errors[0][0] == 3
    assert connection.errors[0][1] == "rate_limited"


@pytest.mark.asyncio
async def test_observability_action_requires_admin() -> None:
    hass = _FakeHass(_FakeCoordinator())
    connection = _FakeConnection(is_admin=False)

    with pytest.raises(Unauthorized):
        websocket_observability_action(
            hass,
            connection,
            {
                "id": 1,
                "type": WS_TYPE_OBSERVABILITY_ACTION,
                "entry_id": "entry-1",
                "action": "clear_manual_hold",
                "payload": {
                    "domain": "light",
                    "subject_type": "entity",
                    "subject_id": "light.studio",
                },
            },
        )

    assert connection.results == []
    assert connection.errors == []


@pytest.mark.asyncio
async def test_observability_action_rejects_invalid_clear_manual_hold_payload() -> None:
    hass = _FakeHass(_FakeCoordinator())
    connection = _FakeConnection(is_admin=True)

    websocket_observability_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_ACTION,
            "entry_id": "entry-1",
            "action": "clear_manual_hold",
            "payload": {"domain": "light"},
        },
    )
    await hass.drain()

    assert connection.results == []
    assert connection.errors[0][1] == "invalid_payload"


@pytest.mark.asyncio
async def test_observability_action_clears_manual_hold_and_returns_audited_snapshot() -> None:
    coordinator = _FakeCoordinator()
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    websocket_observability_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_ACTION,
            "entry_id": "entry-1",
            "action": "clear_manual_hold",
            "payload": {
                "domain": "light",
                "subject_type": "entity",
                "subject_id": "light.studio",
            },
        },
    )
    await hass.drain()

    assert connection.errors == []
    assert coordinator.engine.cleared_manual_holds == [("light", "entity", "light.studio")]
    result = connection.results[0][1]
    assert result["ok"] is True
    assert result["action"] == "clear_manual_hold"
    assert result["snapshot"]["recent_events"][0]["category"] == "admin_action"
    assert result["snapshot"]["recent_events"][0]["reason_code"] == "clear_manual_hold"
    assert coordinator.evaluation_reasons == [
        "admin_observability:clear_manual_hold:light:entity:light.studio"
    ]


@pytest.mark.asyncio
async def test_observability_action_reviews_runtime_promotion() -> None:
    coordinator = _FakeCoordinator()
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    websocket_observability_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_ACTION,
            "entry_id": "entry-1",
            "action": "review_runtime_promotion",
            "payload": {
                "reaction_id": "reaction.one",
                "promotion_action": "heima.promotion.approve_auto_apply",
            },
        },
    )
    await hass.drain()

    assert connection.errors == []
    assert coordinator.reviewed_promotions == [
        ("reaction.one", "heima.promotion.approve_auto_apply")
    ]
    result = connection.results[0][1]
    assert result["ok"] is True
    assert result["snapshot"]["recent_events"][0]["reason_code"] == "review_runtime_promotion"


@pytest.mark.asyncio
async def test_observability_action_reports_unavailable_runtime_promotion() -> None:
    coordinator = _FakeCoordinator()
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    websocket_observability_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_ACTION,
            "entry_id": "entry-1",
            "action": "review_runtime_promotion",
            "payload": {
                "reaction_id": "missing",
                "promotion_action": "heima.promotion.approve_auto_apply",
            },
        },
    )
    await hass.drain()

    assert connection.results == []
    assert connection.errors[0][1] == "not_available"


@pytest.mark.asyncio
async def test_observability_action_resets_runtime_confirmation_promotion_state() -> None:
    coordinator = _FakeCoordinator()
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    websocket_observability_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_ACTION,
            "entry_id": "entry-1",
            "action": "reset_runtime_confirmation_promotion_state",
            "payload": {"reaction_id": "reaction.one"},
        },
    )
    await hass.drain()

    assert connection.errors == []
    assert coordinator.reset_promotions == ["reaction.one"]
    result = connection.results[0][1]
    assert result["ok"] is True
    assert (
        result["snapshot"]["recent_events"][0]["reason_code"]
        == "reset_runtime_confirmation_promotion_state"
    )


@pytest.mark.asyncio
async def test_observability_action_reviews_single_proposal() -> None:
    coordinator = _FakeCoordinator()
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    websocket_observability_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_ACTION,
            "entry_id": "entry-1",
            "action": "review_proposal",
            "payload": {"proposal_id": "proposal.visible", "decision": "approved"},
        },
    )
    await hass.drain()

    assert connection.errors == []
    assert coordinator.reviewed_proposals == [("proposal.visible", "approved", "installer")]
    result = connection.results[0][1]
    assert result["ok"] is True
    assert result["snapshot"]["recent_events"][0]["reason_code"] == "review_proposal"


@pytest.mark.asyncio
async def test_observability_action_reviews_proposal_batch() -> None:
    coordinator = _FakeCoordinator()
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    websocket_observability_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_ACTION,
            "entry_id": "entry-1",
            "action": "review_proposal_batch",
            "payload": {
                "proposal_ids": ["proposal.visible", "proposal.hidden"],
                "decision": "rejected",
                "dismiss_similar": True,
            },
        },
    )
    await hass.drain()

    assert connection.errors == []
    assert coordinator.reviewed_proposal_batches == [
        (
            ("proposal.visible", "proposal.hidden"),
            "rejected",
            "installer",
            True,
        )
    ]
    result = connection.results[0][1]
    assert result["ok"] is True
    assert result["snapshot"]["recent_events"][0]["reason_code"] == "review_proposal_batch"


@pytest.mark.asyncio
async def test_observability_action_reports_stale_proposal_batch() -> None:
    coordinator = _FakeCoordinator()
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    websocket_observability_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_ACTION,
            "entry_id": "entry-1",
            "action": "review_proposal_batch",
            "payload": {"proposal_ids": ["stale"], "decision": "approved"},
        },
    )
    await hass.drain()

    assert connection.results == []
    assert connection.errors[0][1] == "not_available"


@pytest.mark.asyncio
async def test_observability_action_rejects_non_list_proposal_batch_payload() -> None:
    coordinator = _FakeCoordinator()
    hass = _FakeHass(coordinator)
    connection = _FakeConnection(is_admin=True)

    websocket_observability_action(
        hass,
        connection,
        {
            "id": 1,
            "type": WS_TYPE_OBSERVABILITY_ACTION,
            "entry_id": "entry-1",
            "action": "review_proposal_batch",
            "payload": {"proposal_ids": "proposal.visible", "decision": "approved"},
        },
    )
    await hass.drain()

    assert connection.results == []
    assert connection.errors[0][1] == "not_available"
    assert coordinator.reviewed_proposal_batches == []
