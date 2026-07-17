"""Admin observability snapshot support for Heima."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

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
    validation = _safe_section(
        "installation_validation",
        partial_reasons,
        lambda: coordinator._validation_report().as_dict(),  # noqa: SLF001
        {},
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
        "recent_events": list(runtime_observability.get("recent_events") or []),
        "decision_traces": list(runtime_observability.get("decision_traces") or []),
        "reactions": _reaction_summaries(engine_diag),
        "manual_holds": _manual_hold_summary(engine_diag),
        "runtime_confirmations": _runtime_confirmation_summary(runtime_confirmation),
        "notifications": _notification_summary(entry),
        "learning": _learning_summary(engine_diag, proposal_diag),
        "proposals": _proposal_summary(proposal_diag),
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
        findings.append(
            {
                "finding_id": f"health:{health_status}:{health_reason or 'unknown'}",
                "severity": "error" if health_status == "error" else "warning",
                "reason_code": health_reason or health_status,
                "summary": f"Heima health is {health_status}.",
                "affected_object_ids": [],
                "suggested_action": "Open the Health section for details.",
                "links": [{"kind": "health", "id": health_reason or health_status}],
                "first_seen_at": generated_at,
                "last_seen_at": generated_at,
                "acknowledged": False,
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


def _validation_issues(validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("issues", "findings", "problems"):
        raw = validation.get(key)
        if isinstance(raw, list):
            return [dict(item) for item in raw if isinstance(item, Mapping)]
    return []


def _reaction_summaries(engine_diag: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_reactions = engine_diag.get("reactions") if isinstance(engine_diag, Mapping) else {}
    reactions = raw_reactions if isinstance(raw_reactions, Mapping) else {}
    policies = engine_diag.get("reaction_execution_policies")
    policies = policies if isinstance(policies, Mapping) else {}
    muted = set(engine_diag.get("muted_reactions") or [])
    rows: list[dict[str, Any]] = []
    for reaction_id, diagnostics in sorted(reactions.items(), key=lambda item: str(item[0])):
        diag = dict(diagnostics) if isinstance(diagnostics, Mapping) else {}
        policy = policies.get(reaction_id)
        policy = dict(policy) if isinstance(policy, Mapping) else {}
        rows.append(
            {
                "reaction_id": str(reaction_id),
                "reaction_type": str(diag.get("reaction_type") or diag.get("type") or "unknown"),
                "label": str(diag.get("label") or diag.get("title") or reaction_id),
                "enabled": diag.get("enabled", True) is not False,
                "muted": reaction_id in muted,
                "origin": str(diag.get("origin") or diag.get("author_kind") or "unspecified"),
                "execution_policy": policy,
                "last_outcome": str(diag.get("last_outcome") or "unknown"),
                "latest_trace_id": None,
                "diagnostics": diag,
            }
        )
    return rows


def _manual_hold_summary(engine_diag: Mapping[str, Any]) -> dict[str, Any]:
    raw = engine_diag.get("manual_hold") if isinstance(engine_diag, Mapping) else {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _runtime_confirmation_summary(runtime_confirmation: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(runtime_confirmation) if isinstance(runtime_confirmation, Mapping) else {}
    return {
        "pending": list(data.get("pending") or []),
        "recent_completed": list(data.get("recent_completed") or []),
        "stale_responses": int(data.get("stale_responses") or 0),
        "promotion_reviews": _promotion_reviews(data),
        "raw": data,
    }


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


def _notification_summary(entry: Any) -> dict[str, Any]:
    options = dict(getattr(entry, "options", {}) or {})
    notifications = options.get("notifications")
    notifications = dict(notifications) if isinstance(notifications, Mapping) else {}
    recipients = notifications.get("recipients")
    groups = notifications.get("groups")
    routes = notifications.get("routes")
    services = notifications.get("notification_service_capabilities")
    return {
        "recipient_count": len(recipients) if isinstance(recipients, Mapping) else 0,
        "group_count": len(groups) if isinstance(groups, Mapping) else 0,
        "route_count": len(routes) if isinstance(routes, Mapping) else 0,
        "service_count": len(services) if isinstance(services, Mapping) else 0,
        "recipients": dict(recipients) if isinstance(recipients, Mapping) else {},
        "groups": dict(groups) if isinstance(groups, Mapping) else {},
        "routes": dict(routes) if isinstance(routes, Mapping) else {},
        "notification_service_capabilities": (
            dict(services) if isinstance(services, Mapping) else {}
        ),
    }


def _learning_summary(
    engine_diag: Mapping[str, Any],
    proposal_diag: Mapping[str, Any],
) -> dict[str, Any]:
    modules = engine_diag.get("learning_modules") if isinstance(engine_diag, Mapping) else []
    return {
        "learning_modules": list(modules) if isinstance(modules, list) else [],
        "proposal_pending_count": int(proposal_diag.get("pending") or 0),
        "proposal_total_count": int(proposal_diag.get("total") or 0),
    }


def _proposal_summary(proposal_diag: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(proposal_diag) if isinstance(proposal_diag, Mapping) else {}
    return {
        "total": data.get("total"),
        "pending": data.get("pending"),
        "accepted": data.get("accepted"),
        "rejected": data.get("rejected"),
        "review_row_count": data.get("review_row_count"),
        "temporal_bundle_count": data.get("temporal_bundle_count"),
        "suppressed_by_review_group": data.get("suppressed_by_review_group"),
        "raw": data,
    }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
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
