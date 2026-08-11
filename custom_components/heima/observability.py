"""Admin observability snapshot support for Heima."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from .const import OPT_REACTIONS, OPT_SECURITY
from .runtime.notifications import (
    AUDIENCE_TARGET_ADMINS,
    AUDIENCE_TARGET_RESIDENTS,
    normalize_notification_policy_config,
    notification_delivery_policy_fields,
)

OBSERVABILITY_SCHEMA_VERSION = 1

_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "auth",
    "auth_header",
    "authorization",
    "bearer",
    "client_secret",
    "code",
    "headers",
    "password",
    "refresh_token",
    "secret",
    "token",
}


def build_observability_snapshot(coordinator: Any) -> dict[str, Any]:
    """Build a redacted, admin-oriented observability snapshot."""
    partial_reasons: list[str] = []
    generated_at = datetime.now(UTC).isoformat()
    entry = getattr(coordinator, "entry", None)
    entry_id = str(getattr(entry, "entry_id", "") or "")

    engine_diag = _safe_section(
        "engine",
        partial_reasons,
        lambda: coordinator.engine.diagnostics(),
        {},
    )
    proposal_diag = _safe_section(
        "proposal_engine",
        partial_reasons,
        lambda: coordinator.proposal_engine.diagnostics(),
        {},
    )
    runtime_confirmation = _safe_section(
        "runtime_confirmation",
        partial_reasons,
        lambda: coordinator._runtime_confirmation.diagnostics(),  # noqa: SLF001
        {},
    )
    runtime_observability = _runtime_observability(engine_diag)
    recent_events = list(runtime_observability.get("recent_events") or [])
    decision_traces = list(runtime_observability.get("decision_traces") or [])
    validation = _safe_section(
        "installation_validation",
        partial_reasons,
        lambda: coordinator._validation_report().as_dict(),  # noqa: SLF001
        {},
    )
    reactions = _reaction_summaries(
        engine_diag,
        entry=entry,
        decision_traces=decision_traces,
    )
    manual_holds = _manual_hold_summary(engine_diag, runtime_observability)
    runtime_confirmations = _runtime_confirmation_summary(runtime_confirmation)
    notifications = _notification_summary(entry, engine_diag=engine_diag)
    learning = _learning_summary(engine_diag, proposal_diag)
    proposals = _proposal_summary(proposal_diag)
    house_state = _house_state_diagnostics(engine_diag)
    entity_impact = _entity_impact_index(
        entry=entry,
        reactions=reactions,
        manual_holds=manual_holds,
        runtime_confirmations=runtime_confirmations,
        decision_traces=decision_traces,
    )

    snapshot = {
        "meta": {
            "schema_version": OBSERVABILITY_SCHEMA_VERSION,
            "generated_at": generated_at,
            "entry_id": entry_id,
            "engine_version": _engine_version(coordinator),
            "is_partial": bool(partial_reasons),
            "partial_reasons": partial_reasons,
            "retention": runtime_observability.get(
                "retention",
                {
                    "mode": "in_memory",
                    "description": "history_since_last_restart",
                },
            ),
        },
        "health": _health_summary(coordinator, validation),
        "runtime": _runtime_summary(coordinator, engine_diag),
        "health_findings": _health_findings(coordinator, validation, generated_at),
        "recent_events": recent_events,
        "decision_traces": decision_traces,
        "reactions": reactions,
        "manual_holds": manual_holds,
        "runtime_confirmations": runtime_confirmations,
        "notifications": notifications,
        "learning": learning,
        "proposals": proposals,
        "house_state": house_state,
        "entity_impact": entity_impact,
        "details": _detail_projections(
            engine_diag=engine_diag,
            entry=entry,
            reactions=reactions,
            manual_holds=manual_holds,
            runtime_confirmations=runtime_confirmations,
            proposals=proposals,
            house_state=house_state,
            decision_traces=decision_traces,
            entity_impact=entity_impact,
        ),
    }
    return redact_observability_data(snapshot)


def redact_observability_data(value: Any) -> Any:
    """Redact secrets while preserving admin-useful local identifiers."""
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                redacted[key_text] = "**REDACTED**"
            else:
                redacted[key_text] = redact_observability_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_observability_data(item) for item in value]
    if isinstance(value, tuple):
        return [redact_observability_data(item) for item in value]
    if isinstance(value, str) and _looks_sensitive_string(value):
        return "**REDACTED**"
    return deepcopy(value)


def _safe_section(
    name: str,
    partial_reasons: list[str],
    builder: Callable[[], Any],
    default: Any,
) -> Any:
    try:
        value = builder()
    except Exception as err:  # noqa: BLE001
        partial_reasons.append(f"{name}:{type(err).__name__}")
        return default
    return value if value is not None else default


def _engine_version(coordinator: Any) -> str:
    manifest = getattr(getattr(coordinator, "hass", None), "data", {}).get("manifest", {})
    if isinstance(manifest, Mapping):
        version = manifest.get("version")
        if version:
            return str(version)
    return "unknown"


def _health_summary(coordinator: Any, validation: Mapping[str, Any]) -> dict[str, Any]:
    health_status = getattr(coordinator, "_health_status", lambda: "unknown")()
    health_reason = getattr(coordinator, "_health_reason", lambda: "")()
    return {
        "status": str(health_status or "unknown"),
        "reason": str(health_reason or ""),
        "last_anomaly": _health_event_detail(getattr(coordinator, "_last_anomaly", None)),
        "last_invariant_violation": _health_event_detail(
            getattr(coordinator, "_last_invariant_violation", None)
        ),
        "validation": dict(validation),
    }


def _runtime_summary(coordinator: Any, engine_diag: Mapping[str, Any]) -> dict[str, Any]:
    data = getattr(coordinator, "data", None)
    snapshot = engine_diag.get("snapshot") if isinstance(engine_diag, Mapping) else {}
    snapshot = dict(snapshot) if isinstance(snapshot, Mapping) else {}
    return {
        "house_state": getattr(data, "house_state", snapshot.get("house_state", "unknown")),
        "house_state_reason": getattr(data, "house_state_reason", ""),
        "last_decision": getattr(data, "last_decision", ""),
        "last_action": getattr(data, "last_action", ""),
        "snapshot": snapshot,
    }


def _runtime_observability(engine_diag: Mapping[str, Any]) -> dict[str, Any]:
    raw = engine_diag.get("observability") if isinstance(engine_diag, Mapping) else {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _health_findings(
    coordinator: Any,
    validation: Mapping[str, Any],
    generated_at: str,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    health_status = str(getattr(coordinator, "_health_status", lambda: "unknown")())
    health_reason = str(getattr(coordinator, "_health_reason", lambda: "")())
    if health_status not in {"ok", "unknown"}:
        active_health_event = _active_health_event(coordinator, health_reason)
        findings.append(
            {
                "finding_id": f"health:{health_status}:{health_reason or 'unknown'}",
                "severity": "error" if health_status == "error" else "warning",
                "reason_code": health_reason or health_status,
                "summary": _health_finding_summary(health_status, active_health_event),
                "affected_object_ids": [],
                "suggested_action": _health_finding_suggested_action(active_health_event),
                "links": [{"kind": "health", "id": health_reason or health_status}],
                "first_seen_at": generated_at,
                "last_seen_at": generated_at,
                "acknowledged": False,
                "details": active_health_event,
            }
        )

    for item in _validation_issues(validation):
        reason = str(item.get("reason_code") or item.get("code") or item.get("id") or "validation")
        severity = str(item.get("severity") or "warning")
        findings.append(
            {
                "finding_id": f"validation:{reason}",
                "severity": severity,
                "reason_code": reason,
                "summary": str(item.get("summary") or item.get("message") or reason),
                "affected_object_ids": _string_list(item.get("affected_object_ids")),
                "suggested_action": str(item.get("suggested_action") or ""),
                "links": list(item.get("links") or []),
                "first_seen_at": generated_at,
                "last_seen_at": generated_at,
                "acknowledged": False,
            }
        )
    return findings


def _active_health_event(coordinator: Any, health_reason: str) -> dict[str, Any]:
    if health_reason == "invariant_violation":
        return _health_event_detail(getattr(coordinator, "_last_invariant_violation", None))
    if health_reason == "anomaly":
        return _health_event_detail(getattr(coordinator, "_last_anomaly", None))
    return {}


def _health_event_detail(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _health_finding_summary(health_status: str, event: Mapping[str, Any]) -> str:
    message = str(event.get("message") or "").strip()
    title = str(event.get("title") or "").strip()
    event_type = str(event.get("type") or "").strip()
    if message:
        return message
    if title and event_type:
        return f"{title}: {event_type}"
    if event_type:
        return event_type
    return f"Heima health is {health_status}."


def _health_finding_suggested_action(event: Mapping[str, Any]) -> str:
    context = event.get("context") if isinstance(event.get("context"), Mapping) else {}
    check_id = str(context.get("check_id") or "").strip()
    if check_id:
        return f"Inspect invariant check '{check_id}' in the Health section."
    return "Open the Health section for details."


def _validation_issues(validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("issues", "findings", "problems"):
        raw = validation.get(key)
        if isinstance(raw, list):
            return [dict(item) for item in raw if isinstance(item, Mapping)]
    return []


def _reaction_summaries(
    engine_diag: Mapping[str, Any],
    *,
    entry: Any,
    decision_traces: list[Any],
) -> list[dict[str, Any]]:
    raw_reactions = engine_diag.get("reactions") if isinstance(engine_diag, Mapping) else {}
    reactions = raw_reactions if isinstance(raw_reactions, Mapping) else {}
    policies = engine_diag.get("reaction_execution_policies")
    policies = policies if isinstance(policies, Mapping) else {}
    muted = set(engine_diag.get("muted_reactions") or [])
    configured, labels = _configured_reaction_metadata(entry)
    latest_trace_by_reaction = _latest_trace_by_reaction(decision_traces)
    manual_hold_scopes = _manual_hold_scopes_by_reaction(engine_diag, decision_traces)
    rows: list[dict[str, Any]] = []
    for reaction_id, diagnostics in sorted(reactions.items(), key=lambda item: str(item[0])):
        diag = dict(diagnostics) if isinstance(diagnostics, Mapping) else {}
        cfg = configured.get(str(reaction_id), {})
        policy = policies.get(reaction_id)
        policy = dict(policy) if isinstance(policy, Mapping) else {}
        latest_trace = latest_trace_by_reaction.get(str(reaction_id))
        rows.append(
            {
                "reaction_id": str(reaction_id),
                "reaction_type": str(
                    diag.get("reaction_type")
                    or cfg.get("reaction_type")
                    or diag.get("type")
                    or "unknown"
                ),
                "label": str(
                    diag.get("label")
                    or labels.get(str(reaction_id))
                    or cfg.get("label")
                    or cfg.get("title")
                    or diag.get("title")
                    or reaction_id
                ),
                "enabled": diag.get("enabled", True) is not False,
                "muted": reaction_id in muted,
                "origin": str(
                    diag.get("origin")
                    or cfg.get("origin")
                    or cfg.get("author_kind")
                    or diag.get("author_kind")
                    or "unspecified"
                ),
                "author_kind": str(
                    diag.get("author_kind") or cfg.get("author_kind") or "unspecified"
                ),
                "source_template_id": str(
                    cfg.get("source_template_id") or cfg.get("admin_authored_template_id") or ""
                ),
                "source_request": str(cfg.get("source_request") or ""),
                "execution_policy": policy,
                "last_outcome": str(
                    latest_trace.get("outcome")
                    if latest_trace
                    else diag.get("last_outcome") or "unknown"
                ),
                "latest_trace_id": latest_trace.get("trace_id") if latest_trace else None,
                "linked_manual_hold_scopes": manual_hold_scopes.get(str(reaction_id), []),
                "diagnostics": {**cfg, **diag},
            }
        )
    return rows


def _configured_reaction_metadata(entry: Any) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    options = getattr(entry, "options", {})
    options = dict(options) if isinstance(options, Mapping) else {}
    reactions = options.get(OPT_REACTIONS)
    reactions = dict(reactions) if isinstance(reactions, Mapping) else {}
    configured = reactions.get("configured")
    labels = reactions.get("labels")
    configured_rows = {
        str(reaction_id): dict(cfg)
        for reaction_id, cfg in dict(configured or {}).items()
        if isinstance(cfg, Mapping)
    }
    label_rows = {
        str(reaction_id): str(label)
        for reaction_id, label in dict(labels or {}).items()
        if str(label or "").strip()
    }
    return configured_rows, label_rows


def _manual_hold_summary(
    engine_diag: Mapping[str, Any],
    runtime_observability: Mapping[str, Any],
) -> dict[str, Any]:
    raw = engine_diag.get("manual_hold") if isinstance(engine_diag, Mapping) else {}
    data = dict(raw) if isinstance(raw, Mapping) else {}
    data["active_holds"] = _manual_hold_rows_with_links(
        data.get("active_holds"),
        runtime_observability,
    )
    return data


def _runtime_confirmation_summary(runtime_confirmation: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(runtime_confirmation) if isinstance(runtime_confirmation, Mapping) else {}
    pending_rows = _request_rows(
        data.get("pending_requests"),
        fallback=data.get("pending"),
    )
    recent_completed_rows = _request_rows(
        data.get("recent_completed_requests"),
        fallback=data.get("recent_completed"),
    )
    return {
        "pending": pending_rows,
        "pending_count": _count_value(data.get("pending"), fallback=len(pending_rows)),
        "recent_completed": recent_completed_rows,
        "recent_completed_count": _count_value(
            data.get("recent_completed"),
            fallback=len(recent_completed_rows),
        ),
        "stale_responses": int(data.get("stale_responses") or 0),
        "duplicate_occurrences": int(data.get("duplicate_occurrences") or 0),
        "completed_by_status": dict(data.get("completed_by_status") or {}),
        "completed_step_counts": dict(data.get("completed_step_counts") or {}),
        "completed_blocked_reasons": dict(data.get("completed_blocked_reasons") or {}),
        "completed_failed_reasons": dict(data.get("completed_failed_reasons") or {}),
        "completed_skipped_reasons": dict(data.get("completed_skipped_reasons") or {}),
        "failed_request_reasons": dict(data.get("failed_request_reasons") or {}),
        "scheduled_timeouts": list(data.get("scheduled_timeouts") or []),
        "action_event_subscription_active": bool(
            data.get("action_event_subscription_active", False)
        ),
        "promotion_reviews": _promotion_reviews(data),
        "raw": data,
    }


def _request_rows(value: Any, *, fallback: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(fallback, list):
        return list(fallback)
    return []


def _count_value(value: Any, *, fallback: int) -> int:
    if isinstance(value, bool):
        return int(fallback)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(fallback))


def _latest_trace_by_reaction(decision_traces: list[Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in decision_traces:
        if not isinstance(item, Mapping):
            continue
        reaction_id = str(item.get("reaction_id") or "").strip()
        if not reaction_id or reaction_id.startswith("domain:"):
            continue
        latest[reaction_id] = dict(item)
    return latest


def _manual_hold_scopes_by_reaction(
    engine_diag: Mapping[str, Any],
    decision_traces: list[Any],
) -> dict[str, list[str]]:
    active_scopes = {
        str(item.get("scope") or "")
        for item in _manual_hold_active_rows(engine_diag)
        if str(item.get("scope") or "")
    }
    by_reaction: dict[str, set[str]] = {}
    for item in decision_traces:
        if not isinstance(item, Mapping):
            continue
        reaction_id = str(item.get("reaction_id") or "").strip()
        if not reaction_id or reaction_id.startswith("domain:"):
            continue
        for step in item.get("apply_steps") or []:
            if not isinstance(step, Mapping):
                continue
            blocked_by = str(step.get("blocked_by") or "")
            scope = _manual_hold_scope_from_blocked_by(blocked_by)
            if scope and (not active_scopes or scope in active_scopes):
                by_reaction.setdefault(reaction_id, set()).add(scope)
    return {reaction_id: sorted(scopes) for reaction_id, scopes in by_reaction.items()}


def _manual_hold_rows_with_links(
    rows: Any,
    runtime_observability: Mapping[str, Any],
) -> list[dict[str, Any]]:
    active_rows = [dict(item) for item in rows or [] if isinstance(item, Mapping)]
    reactions_by_scope: dict[str, set[str]] = {}
    for trace in runtime_observability.get("decision_traces") or []:
        if not isinstance(trace, Mapping):
            continue
        reaction_id = str(trace.get("reaction_id") or "").strip()
        if not reaction_id or reaction_id.startswith("domain:"):
            continue
        for step in trace.get("apply_steps") or []:
            if not isinstance(step, Mapping):
                continue
            scope = _manual_hold_scope_from_blocked_by(str(step.get("blocked_by") or ""))
            if scope:
                reactions_by_scope.setdefault(scope, set()).add(reaction_id)

    for row in active_rows:
        scope = str(row.get("scope") or "").strip()
        row["affected_reaction_ids"] = sorted(reactions_by_scope.get(scope, set()))
        row["links"] = [
            {"kind": "reaction", "id": reaction_id} for reaction_id in row["affected_reaction_ids"]
        ]
        source_entity = str(row.get("source_entity") or "").strip()
        if source_entity:
            row["links"].append({"kind": "entity", "id": source_entity})
    return active_rows


def _manual_hold_active_rows(engine_diag: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = engine_diag.get("manual_hold") if isinstance(engine_diag, Mapping) else {}
    if not isinstance(raw, Mapping):
        return []
    return [dict(item) for item in raw.get("active_holds") or [] if isinstance(item, Mapping)]


def _manual_hold_scope_from_blocked_by(blocked_by: str) -> str:
    token = str(blocked_by or "").strip()
    if not token.startswith("manual_hold:"):
        return ""
    remainder = token.removeprefix("manual_hold:")
    parts = remainder.split(":")
    if len(parts) < 4:
        return ""
    return ":".join(parts[:3]) if "." not in parts[2] else ":".join(parts[:3])


def _promotion_reviews(runtime_confirmation: Mapping[str, Any]) -> list[dict[str, Any]]:
    persisted = runtime_confirmation.get("persisted")
    if not isinstance(persisted, Mapping):
        return []
    by_reaction = persisted.get("by_reaction")
    if not isinstance(by_reaction, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for reaction_id, item in sorted(by_reaction.items(), key=lambda row: str(row[0])):
        data = dict(item) if isinstance(item, Mapping) else {}
        review = data.get("promotion_review")
        if isinstance(review, Mapping) and review:
            rows.append({"reaction_id": str(reaction_id), **dict(review)})
    return rows


def _notification_summary(
    entry: Any, engine_diag: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    options = dict(getattr(entry, "options", {}) or {})
    notifications = options.get("notifications")
    notifications = dict(notifications) if isinstance(notifications, Mapping) else {}
    recipients = notifications.get("recipients")
    groups = notifications.get("recipient_groups") or notifications.get("groups")
    route_targets = notifications.get("route_targets")
    services = notifications.get("notification_service_capabilities")
    recipients = dict(recipients) if isinstance(recipients, Mapping) else {}
    groups = dict(groups) if isinstance(groups, Mapping) else {}
    services = dict(services) if isinstance(services, Mapping) else {}
    route_targets = _string_list(route_targets)
    resolved_routes = _resolve_notification_targets(
        recipients=recipients,
        groups=groups,
        route_targets=route_targets,
    )
    actionable_routes = [
        route
        for route in resolved_routes["routes"]
        if _notification_route_supports_actions(route, services)
    ]
    skipped_non_actionable = [
        route for route in resolved_routes["routes"] if route not in set(actionable_routes)
    ]
    effective_policy = notification_delivery_policy_fields(
        normalize_notification_policy_config(notifications)
    )
    policy_runtime = {}
    if isinstance(engine_diag, Mapping):
        events_diag = engine_diag.get("events")
        if isinstance(events_diag, Mapping):
            runtime_policy = events_diag.get("notification_delivery_policy")
            if isinstance(runtime_policy, Mapping):
                policy_runtime = dict(runtime_policy)
    return {
        "recipient_count": len(recipients),
        "group_count": len(groups),
        "route_count": len(route_targets),
        "service_count": len(services),
        "recipients": recipients,
        "groups": groups,
        "route_targets": route_targets,
        "resolved_routes": resolved_routes["routes"],
        "unresolved_targets": resolved_routes["unresolved_targets"],
        "actionable_routes": actionable_routes,
        "skipped_non_actionable_routes": skipped_non_actionable,
        "notification_service_capabilities": services,
        "audience_resolution": _notification_audience_resolution(
            recipients=recipients,
            groups=groups,
            services=services,
            audience_targets=effective_policy.get("audience_targets"),
        ),
        "delivery_policy": {
            "effective": effective_policy,
            "unresolved_audience_targets": _unresolved_audience_targets(
                recipients=recipients,
                groups=groups,
                audience_targets=effective_policy.get("audience_targets"),
            ),
            "health": _notification_delivery_policy_health(
                recipients=recipients,
                groups=groups,
                route_targets=route_targets,
                resolved_routes=resolved_routes["routes"],
                unresolved_route_targets=resolved_routes["unresolved_targets"],
                actionable_routes=actionable_routes,
                effective_policy=effective_policy,
            ),
            "runtime": policy_runtime,
        },
    }


def _notification_audience_resolution(
    *,
    recipients: Mapping[str, Any],
    groups: Mapping[str, Any],
    services: Mapping[str, Any],
    audience_targets: Any,
) -> list[dict[str, Any]]:
    if not isinstance(audience_targets, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for role, targets in sorted(audience_targets.items(), key=lambda item: str(item[0])):
        for target in _string_list(targets):
            resolved = _resolve_notification_targets(
                recipients=recipients,
                groups=groups,
                route_targets=[target],
            )
            routes = resolved["routes"]
            rows.append(
                {
                    "role": str(role),
                    "target": target,
                    "target_type": _notification_target_type(
                        target, recipients=recipients, groups=groups
                    ),
                    "routes": routes,
                    "unresolved": bool(resolved["unresolved_targets"]),
                    "actionable_routes": [
                        route
                        for route in routes
                        if _notification_route_supports_actions(route, services)
                    ],
                    "text_only_routes": [
                        route
                        for route in routes
                        if not _notification_route_supports_actions(route, services)
                    ],
                }
            )
    return rows


def _notification_target_type(
    target: str,
    *,
    recipients: Mapping[str, Any],
    groups: Mapping[str, Any],
) -> str:
    if target in recipients:
        return "recipient"
    if target in groups:
        return "group"
    return "missing"


def _notification_delivery_policy_health(
    *,
    recipients: Mapping[str, Any],
    groups: Mapping[str, Any],
    route_targets: list[str],
    resolved_routes: list[str],
    unresolved_route_targets: list[str],
    actionable_routes: list[str],
    effective_policy: Mapping[str, Any],
) -> dict[str, Any]:
    audience_targets = effective_policy.get("audience_targets")
    unresolved_audience = _unresolved_audience_targets(
        recipients=recipients,
        groups=groups,
        audience_targets=audience_targets,
    )
    issues: list[dict[str, str]] = []
    if not recipients:
        issues.append({"severity": "warning", "reason": "no_recipients"})
    if not route_targets:
        issues.append({"severity": "warning", "reason": "no_fallback_targets"})
    if unresolved_route_targets:
        issues.append({"severity": "warning", "reason": "unresolved_fallback_targets"})
    if unresolved_audience:
        issues.append({"severity": "warning", "reason": "unresolved_audience_targets"})
    if route_targets and not resolved_routes:
        issues.append({"severity": "warning", "reason": "fallback_targets_resolve_no_routes"})
    if resolved_routes and not actionable_routes:
        issues.append({"severity": "warning", "reason": "no_actionable_routes"})

    if isinstance(audience_targets, Mapping):
        for role in (AUDIENCE_TARGET_ADMINS, AUDIENCE_TARGET_RESIDENTS):
            configured = [target for target in _string_list(audience_targets.get(role))]
            if not configured:
                issues.append({"severity": "warning", "reason": f"empty_{role}_audience"})
            if _notification_policy_uses_audience(effective_policy, role):
                if role not in groups:
                    issues.append({"severity": "warning", "reason": f"missing_{role}_group"})
                if role not in configured:
                    issues.append(
                        {
                            "severity": "warning",
                            "reason": f"{role}_audience_not_group_backed",
                        }
                    )

    status = "ok" if not issues else "warning"
    return {
        "status": status,
        "issue_count": len(issues),
        "issues": issues,
    }


def _notification_policy_uses_audience(effective_policy: Mapping[str, Any], role: str) -> bool:
    audience_policy = effective_policy.get("audience_policy")
    if not isinstance(audience_policy, Mapping):
        return False
    for raw_policy in audience_policy.values():
        policy = ""
        if isinstance(raw_policy, Mapping):
            policy = str(raw_policy.get("push") or "").strip()
        elif raw_policy is not None:
            policy = str(raw_policy).strip()
        if _notification_push_policy_uses_audience(policy, role):
            return True
    return False


def _notification_push_policy_uses_audience(push_policy: str, role: str) -> bool:
    if role == AUDIENCE_TARGET_ADMINS:
        return "admins" in push_policy
    if role == AUDIENCE_TARGET_RESIDENTS:
        return "residents" in push_policy
    return False


def _unresolved_audience_targets(
    *,
    recipients: Mapping[str, Any],
    groups: Mapping[str, Any],
    audience_targets: Any,
) -> list[dict[str, str]]:
    if not isinstance(audience_targets, Mapping):
        return []
    available = set(str(key) for key in recipients) | set(str(key) for key in groups)
    unresolved: list[dict[str, str]] = []
    for role, values in audience_targets.items():
        for target in _string_list(values):
            if target not in available:
                unresolved.append({"role": str(role), "target": target})
    return unresolved


def _learning_summary(
    engine_diag: Mapping[str, Any],
    proposal_diag: Mapping[str, Any],
) -> dict[str, Any]:
    modules = engine_diag.get("learning_modules") if isinstance(engine_diag, Mapping) else []
    if not isinstance(modules, list):
        modules = []
    module_rows = [dict(item) for item in modules if isinstance(item, Mapping)]
    return {
        "learning_modules": module_rows,
        "module_count": len(module_rows),
        "ready_module_count": sum(1 for item in module_rows if item.get("ready") is True),
        "proposal_pending_count": int(proposal_diag.get("pending") or 0),
        "proposal_total_count": int(proposal_diag.get("total") or 0),
        "analyzer_failures": _mapping_or_count(
            proposal_diag.get("analyzer_failures"),
            count_key="total",
        ),
        "analyzer_output_errors": _mapping_or_count(
            proposal_diag.get("analyzer_output_errors"),
            count_key="total",
        ),
        "lifecycle_monitoring": _mapping_or_count(
            proposal_diag.get("lifecycle_monitoring"),
            count_key="record_count",
        ),
    }


def _proposal_summary(proposal_diag: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(proposal_diag) if isinstance(proposal_diag, Mapping) else {}
    proposals = [dict(item) for item in data.get("proposals") or [] if isinstance(item, Mapping)]
    pending_all = [item for item in proposals if item.get("status") == "pending"]
    pending_visible = [item for item in pending_all if not item.get("suppressed_by_review_group")]
    pending_suppressed = [item for item in pending_all if item.get("suppressed_by_review_group")]
    return {
        "total": data.get("total"),
        "pending": data.get("pending"),
        "accepted": data.get("accepted"),
        "rejected": data.get("rejected"),
        "real_pending_count": len(pending_all),
        "visible_pending_count": len(pending_visible),
        "suppressed_pending_count": len(pending_suppressed),
        "suppressed_in_review_count": data.get("suppressed_in_review_count"),
        "pending_stale": data.get("pending_stale"),
        "review_row_count": data.get("review_row_count"),
        "review_rows": _list_or_empty(data.get("review_rows")),
        "review_groups": _mapping_or_count(data.get("review_groups"), count_key="total"),
        "temporal_bundle_count": data.get("temporal_bundle_count"),
        "temporal_bundle_member_count": data.get("temporal_bundle_member_count"),
        "temporal_bundles": _list_or_empty(data.get("temporal_bundles")),
        "pending_by_type": _counter_by(proposals, "type", status="pending"),
        "visible_pending_by_type": _counter_by(pending_visible, "type"),
        "suppressed_pending_by_type": _counter_by(pending_suppressed, "type"),
        "pending_by_followup_kind": _counter_by(pending_all, "followup_kind"),
        "visible_examples": pending_visible[:10],
        "suppressed_examples": pending_suppressed[:10],
        "suppressed_by_review_group": data.get("suppressed_by_review_group"),
        "raw": data,
    }


def _house_state_diagnostics(engine_diag: Mapping[str, Any]) -> dict[str, Any]:
    raw = engine_diag.get("house_state") if isinstance(engine_diag, Mapping) else {}
    data = dict(raw) if isinstance(raw, Mapping) else {}
    resolution_trace = _mapping_or_empty(data.get("resolution_trace"))
    candidate_summary = _mapping_or_empty(data.get("candidate_summary"))
    candidate_trace = _mapping_or_empty(data.get("candidate_trace"))
    decision = _mapping_or_empty(resolution_trace.get("decision"))
    active_candidates = _string_list(resolution_trace.get("active_candidates"))
    pending_candidate = ""
    pending_remaining_s = None
    if str(decision.get("action") or "") == "pending":
        pending_candidate = str(decision.get("source_candidate") or "")
        pending_remaining_s = decision.get("pending_remaining_s")
    return {
        "winning_reason": str(
            resolution_trace.get("winning_reason")
            or resolution_trace.get("reason")
            or decision.get("reason")
            or ""
        ),
        "resolution_path": str(
            resolution_trace.get("resolution_path") or resolution_trace.get("path") or ""
        ),
        "decision_action": str(decision.get("action") or ""),
        "decision_target_state": str(
            decision.get("target_state")
            or decision.get("entered_state")
            or decision.get("state")
            or ""
        ),
        "pending_candidate": pending_candidate,
        "pending_remaining_s": pending_remaining_s,
        "active_candidates": active_candidates,
        "candidate_summary": candidate_summary,
        "candidate_trace": candidate_trace,
        "resolution_trace": resolution_trace,
        "house_signals_trace": _mapping_or_empty(data.get("house_signals_trace")),
        "timers": _mapping_or_empty(data.get("timers")),
        "config": _mapping_or_empty(data.get("config")),
        "override": _mapping_or_empty(data.get("override")),
        "raw": data,
    }


def _detail_projections(
    *,
    engine_diag: Mapping[str, Any],
    entry: Any,
    reactions: list[dict[str, Any]],
    manual_holds: Mapping[str, Any],
    runtime_confirmations: Mapping[str, Any],
    proposals: Mapping[str, Any],
    house_state: Mapping[str, Any],
    decision_traces: list[Any],
    entity_impact: Mapping[str, Any],
) -> dict[str, Any]:
    configured, labels = _configured_reaction_metadata(entry)
    raw_reactions = engine_diag.get("reactions") if isinstance(engine_diag, Mapping) else {}
    raw_reactions = raw_reactions if isinstance(raw_reactions, Mapping) else {}
    policies = engine_diag.get("reaction_execution_policies")
    policies = policies if isinstance(policies, Mapping) else {}
    active_holds = [dict(item) for item in manual_holds.get("active_holds") or []]
    pending_requests = [dict(item) for item in runtime_confirmations.get("pending") or []]
    completed_requests = [
        dict(item) for item in runtime_confirmations.get("recent_completed") or []
    ]
    promotion_reviews = [
        dict(item) for item in runtime_confirmations.get("promotion_reviews") or []
    ]
    proposal_rows = [dict(item) for item in proposals.get("raw", {}).get("proposals") or []]
    review_rows = [dict(item) for item in proposals.get("review_rows") or []]

    traces_by_reaction = _traces_by_reaction(decision_traces)
    holds_by_scope = {str(item.get("scope") or ""): item for item in active_holds}
    requests_by_reaction = _requests_by_reaction(pending_requests + completed_requests)
    promotion_reviews_by_reaction = _rows_by_key(promotion_reviews, "reaction_id")
    proposals_by_reaction = _proposals_by_reaction(proposal_rows)

    reaction_details: dict[str, dict[str, Any]] = {}
    for row in reactions:
        reaction_id = str(row.get("reaction_id") or "").strip()
        if not reaction_id:
            continue
        cfg = configured.get(reaction_id, {})
        diag = raw_reactions.get(reaction_id)
        diag = dict(diag) if isinstance(diag, Mapping) else {}
        linked_hold_scopes = _string_list(row.get("linked_manual_hold_scopes"))
        traces = traces_by_reaction.get(reaction_id, [])
        reaction_details[reaction_id] = {
            "summary": dict(row),
            "configured_metadata": cfg,
            "runtime_diagnostics": diag,
            "label_metadata": {"label": labels.get(reaction_id, "")},
            "execution_policy": dict(policies.get(reaction_id) or {}),
            "latest_trace": traces[-1] if traces else None,
            "recent_traces": traces[-10:],
            "linked_manual_holds": [
                holds_by_scope[scope] for scope in linked_hold_scopes if scope in holds_by_scope
            ],
            "linked_runtime_confirmations": requests_by_reaction.get(reaction_id, []),
            "linked_promotion_reviews": promotion_reviews_by_reaction.get(reaction_id, []),
            "linked_proposals": proposals_by_reaction.get(reaction_id, []),
        }

    return {
        "reactions": {"by_id": reaction_details},
        "manual_holds": {"by_scope": _manual_hold_details_by_scope(active_holds)},
        "runtime_confirmations": {
            "by_request_id": _runtime_confirmation_details_by_request_id(
                pending_requests=pending_requests,
                completed_requests=completed_requests,
            )
        },
        "proposals": {
            "by_id": _proposal_details_by_id(proposal_rows),
            "review_rows_by_id": _review_row_details_by_id(review_rows),
        },
        "house_state": dict(house_state),
        "entities": {
            "by_id": {
                str(row.get("entity_id")): row
                for row in entity_impact.get("entities", [])
                if str(row.get("entity_id") or "")
            }
        },
    }


def _traces_by_reaction(decision_traces: list[Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in decision_traces:
        if not isinstance(item, Mapping):
            continue
        reaction_id = str(item.get("reaction_id") or "").strip()
        if not reaction_id or reaction_id.startswith("domain:"):
            continue
        grouped.setdefault(reaction_id, []).append(dict(item))
    return grouped


def _requests_by_reaction(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        reaction_id = str(row.get("reaction_id") or "").strip()
        if reaction_id:
            grouped.setdefault(reaction_id, []).append(row)
    return grouped


def _rows_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = str(row.get(key) or "").strip()
        if value:
            grouped.setdefault(value, []).append(row)
    return grouped


def _proposals_by_reaction(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        reaction_ids = _proposal_linked_reaction_ids(row)
        for reaction_id in reaction_ids:
            grouped.setdefault(reaction_id, []).append(row)
    return grouped


def _proposal_linked_reaction_ids(row: Mapping[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in (
        "reaction_id",
        "target_reaction_id",
        "source_reaction_id",
        "accepted_reaction_id",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            candidates.append(value)
    return sorted(set(candidates))


def _manual_hold_details_by_scope(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for row in rows:
        scope = str(row.get("scope") or "").strip()
        if not scope:
            continue
        details[scope] = {
            "summary": row,
            "affected_reaction_ids": _string_list(row.get("affected_reaction_ids")),
            "links": list(row.get("links") or []),
        }
    return details


def _runtime_confirmation_details_by_request_id(
    *,
    pending_requests: list[dict[str, Any]],
    completed_requests: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for status, rows in (
        ("pending", pending_requests),
        ("completed", completed_requests),
    ):
        for row in rows:
            request_id = str(row.get("request_id") or "").strip()
            if not request_id:
                continue
            details[request_id] = {
                "summary": row,
                "status_bucket": status,
                "reaction_id": str(row.get("reaction_id") or ""),
            }
    return details


def _proposal_details_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for row in rows:
        proposal_id = str(row.get("id") or row.get("proposal_id") or "").strip()
        if not proposal_id:
            continue
        details[proposal_id] = {
            "summary": row,
            "linked_reaction_ids": _proposal_linked_reaction_ids(row),
        }
    return details


def _review_row_details_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        row_id = str(
            row.get("review_row_id")
            or row.get("bundle_id")
            or row.get("proposal_id")
            or f"row:{index}"
        )
        details[row_id] = {
            "summary": row,
            "proposal_ids": _string_list(row.get("proposal_ids"))
            or _string_list(row.get("proposal_id")),
        }
    return details


_ENTITY_DOMAINS = {
    "alarm_control_panel",
    "automation",
    "binary_sensor",
    "button",
    "calendar",
    "camera",
    "climate",
    "cover",
    "device_tracker",
    "fan",
    "group",
    "humidifier",
    "input_boolean",
    "input_number",
    "input_select",
    "light",
    "lock",
    "media_player",
    "number",
    "person",
    "scene",
    "script",
    "select",
    "sensor",
    "switch",
    "vacuum",
    "weather",
}


def _entity_impact_index(
    *,
    entry: Any,
    reactions: list[dict[str, Any]],
    manual_holds: Mapping[str, Any],
    runtime_confirmations: Mapping[str, Any],
    decision_traces: list[Any],
) -> dict[str, Any]:
    builder: dict[str, dict[str, Any]] = {}
    configured, _labels = _configured_reaction_metadata(entry)

    for reaction in reactions:
        reaction_id = str(reaction.get("reaction_id") or "").strip()
        cfg = configured.get(reaction_id, {})
        for entity_id in _entity_ids_from_value(cfg):
            _entity_link(builder, entity_id, "reaction_ids", reaction_id)
            _entity_link(
                builder, entity_id, "policy_ids", str(reaction.get("source_template_id") or "")
            )

    for trace in decision_traces:
        if not isinstance(trace, Mapping):
            continue
        reaction_id = str(trace.get("reaction_id") or "").strip()
        trace_id = str(trace.get("trace_id") or "").strip()
        for step in trace.get("apply_steps") or []:
            if not isinstance(step, Mapping):
                continue
            for entity_id in _entity_ids_from_apply_step(step):
                _entity_link(builder, entity_id, "reaction_ids", reaction_id)
                _entity_link(builder, entity_id, "trace_ids", trace_id)
                _entity_append(builder, entity_id, "apply_steps", dict(step))
        for link in trace.get("links") or []:
            if isinstance(link, Mapping) and link.get("kind") == "entity":
                entity_id = str(link.get("id") or "").strip()
                if _is_entity_id(entity_id):
                    _entity_link(builder, entity_id, "reaction_ids", reaction_id)
                    _entity_link(builder, entity_id, "trace_ids", trace_id)

    for hold in manual_holds.get("active_holds") or []:
        if not isinstance(hold, Mapping):
            continue
        scope = str(hold.get("scope") or "").strip()
        for entity_id in _entity_ids_from_manual_hold(hold):
            _entity_link(builder, entity_id, "hold_scopes", scope)
            for reaction_id in _string_list(hold.get("affected_reaction_ids")):
                _entity_link(builder, entity_id, "reaction_ids", reaction_id)

    pending_applies = manual_holds.get("pending_applies")
    if isinstance(pending_applies, Mapping):
        for item in pending_applies.get("items") or []:
            if not isinstance(item, Mapping):
                continue
            for entity_id in _entity_ids_from_value(item):
                _entity_append(builder, entity_id, "pending_applies", dict(item))

    request_rows = [
        *[
            dict(item)
            for item in runtime_confirmations.get("pending") or []
            if isinstance(item, Mapping)
        ],
        *[
            dict(item)
            for item in runtime_confirmations.get("recent_completed") or []
            if isinstance(item, Mapping)
        ],
    ]
    for request in request_rows:
        request_id = str(request.get("request_id") or "").strip()
        reaction_id = str(request.get("reaction_id") or "").strip()
        for entity_id in _entity_ids_from_value(request):
            _entity_link(builder, entity_id, "request_ids", request_id)
            _entity_link(builder, entity_id, "reaction_ids", reaction_id)

    for source in _camera_privacy_sources(entry):
        privacy_entity = str(source.get("privacy_entity") or "").strip()
        if not _is_entity_id(privacy_entity):
            continue
        _entity_append(
            builder,
            privacy_entity,
            "source_metadata",
            {
                "kind": "security_camera_privacy_source",
                "camera_source_id": str(source.get("id") or ""),
                "role": str(source.get("role") or ""),
            },
        )
        for key, value in source.items():
            if key.endswith("_entity") and _is_entity_id(str(value or "")):
                _entity_append(
                    builder,
                    str(value),
                    "source_metadata",
                    {
                        "kind": "security_camera_evidence_source",
                        "camera_source_id": str(source.get("id") or ""),
                        "field": key,
                    },
                )

    rows = [_finalize_entity_row(entity_id, data) for entity_id, data in sorted(builder.items())]
    return {
        "entity_count": len(rows),
        "entities": rows,
        "by_domain": _counter_by_entity_domain(rows),
    }


def _entity_ids_from_apply_step(step: Mapping[str, Any]) -> list[str]:
    candidates = []
    target = str(step.get("target") or "").strip()
    if _is_entity_id(target):
        candidates.append(target)
    params = step.get("params")
    if isinstance(params, Mapping):
        candidates.extend(_entity_ids_from_value(params.get("entity_id")))
    candidates.extend(_entity_ids_from_value(step.get("entity_id")))
    return sorted(set(candidates))


def _entity_ids_from_manual_hold(hold: Mapping[str, Any]) -> list[str]:
    candidates = _entity_ids_from_value(hold.get("source_entity"))
    scope = str(hold.get("scope") or "")
    parts = scope.split(":")
    if len(parts) >= 3 and _is_entity_id(parts[2]):
        candidates.append(parts[2])
    return sorted(set(candidates))


def _entity_ids_from_value(value: Any) -> list[str]:
    found: set[str] = set()
    if isinstance(value, str):
        for token in value.replace(",", " ").split():
            cleaned = token.strip("[](){}'\"")
            if _is_entity_id(cleaned):
                found.add(cleaned)
    elif isinstance(value, Mapping):
        for item in value.values():
            found.update(_entity_ids_from_value(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.update(_entity_ids_from_value(item))
    return sorted(found)


def _is_entity_id(value: str) -> bool:
    if "." not in value or " " in value:
        return False
    domain, object_id = value.split(".", 1)
    return bool(domain in _ENTITY_DOMAINS and object_id)


def _camera_privacy_sources(entry: Any) -> list[dict[str, Any]]:
    options = dict(getattr(entry, "options", {}) or {})
    security = options.get(OPT_SECURITY)
    security = dict(security) if isinstance(security, Mapping) else {}
    return [
        dict(item)
        for item in security.get("camera_evidence_sources") or []
        if isinstance(item, Mapping)
    ]


def _entity_link(
    builder: dict[str, dict[str, Any]],
    entity_id: str,
    key: str,
    value: str,
) -> None:
    if not _is_entity_id(entity_id) or not value:
        return
    row = builder.setdefault(entity_id, {})
    row.setdefault(key, set()).add(value)


def _entity_append(
    builder: dict[str, dict[str, Any]],
    entity_id: str,
    key: str,
    value: dict[str, Any],
) -> None:
    if not _is_entity_id(entity_id):
        return
    row = builder.setdefault(entity_id, {})
    row.setdefault(key, []).append(value)


def _finalize_entity_row(entity_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "domain": entity_id.split(".", 1)[0],
        "reaction_ids": sorted(data.get("reaction_ids") or []),
        "trace_ids": sorted(data.get("trace_ids") or []),
        "hold_scopes": sorted(data.get("hold_scopes") or []),
        "request_ids": sorted(data.get("request_ids") or []),
        "policy_ids": sorted(data.get("policy_ids") or []),
        "apply_steps": list(data.get("apply_steps") or []),
        "pending_applies": list(data.get("pending_applies") or []),
        "source_metadata": list(data.get("source_metadata") or []),
    }


def _counter_by_entity_domain(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        domain = str(row.get("domain") or "unknown")
        counts[domain] = counts.get(domain, 0) + 1
    return dict(sorted(counts.items()))


def _mapping_or_count(value: Any, *, count_key: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, bool) or value is None:
        return {}
    try:
        return {count_key: max(0, int(value))}
    except (TypeError, ValueError):
        return {}


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _counter_by(
    rows: list[dict[str, Any]],
    key: str,
    *,
    status: str | None = None,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if status is not None and row.get("status") != status:
            continue
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _resolve_notification_targets(
    *,
    recipients: Mapping[str, Any],
    groups: Mapping[str, Any],
    route_targets: list[str],
) -> dict[str, list[str]]:
    resolved: list[str] = []
    unresolved: list[str] = []
    seen: set[str] = set()

    def add_route(route: Any) -> None:
        normalized = _normalize_notify_service_name(route)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        resolved.append(normalized)

    for target in route_targets:
        if target in recipients:
            for route in _recipient_routes(recipients.get(target)):
                add_route(route)
            continue
        if target in groups:
            for recipient_id in _string_list(groups.get(target)):
                for route in _recipient_routes(recipients.get(recipient_id)):
                    add_route(route)
            continue
        unresolved.append(target)

    return {
        "routes": resolved,
        "unresolved_targets": unresolved,
    }


def _notification_route_supports_actions(
    route: str,
    capabilities: Mapping[str, Any],
) -> bool:
    raw = capabilities.get(_normalize_notify_service_name(route))
    return isinstance(raw, Mapping) and bool(raw.get("supports_actions", False))


def _recipient_routes(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return _string_list(value.get("notify_services"))
    return _string_list(value)


def _normalize_notify_service_name(route: Any) -> str:
    normalized = str(route or "").strip()
    if normalized.startswith("notify."):
        normalized = normalized.split(".", 1)[1]
    return normalized


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    return normalized in _SENSITIVE_KEYS or any(
        token in normalized for token in ("password", "secret", "token", "authorization")
    )


def _looks_sensitive_string(value: str) -> bool:
    stripped = value.strip()
    lower = stripped.lower()
    return lower.startswith("bearer ") or lower.startswith("basic ")
