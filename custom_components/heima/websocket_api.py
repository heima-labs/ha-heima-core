"""Websocket API for Heima admin observability."""

from __future__ import annotations

import time
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized

from .const import DOMAIN
from .observability import build_observability_snapshot

WS_TYPE_OBSERVABILITY_SNAPSHOT = "heima/observability/snapshot"
WS_TYPE_OBSERVABILITY_ACTION = "heima/observability/action"
WS_TYPE_OBSERVABILITY_WHY_NOT_NOW = "heima/observability/why_not_now"
WHY_NOT_NOW_RATE_LIMIT = 2
WHY_NOT_NOW_RATE_WINDOW_S = 60.0
ACTION_CLEAR_MANUAL_HOLD = "clear_manual_hold"
ACTION_REVIEW_RUNTIME_PROMOTION = "review_runtime_promotion"
ACTION_RESET_RUNTIME_CONFIRMATION_PROMOTION_STATE = "reset_runtime_confirmation_promotion_state"
ACTION_REVIEW_PROPOSAL = "review_proposal"
ACTION_REVIEW_PROPOSAL_BATCH = "review_proposal_batch"
PROMOTION_ACTION_APPROVE_AUTO_APPLY = "heima.promotion.approve_auto_apply"
PROMOTION_ACTION_DISMISS_NOT_NOW = "heima.promotion.dismiss_not_now"
PROMOTION_ACTION_DISABLE_FUTURE_PROMPTS = "heima.promotion.disable_future_prompts"
PROMOTION_ACTIONS = {
    PROMOTION_ACTION_APPROVE_AUTO_APPLY,
    PROMOTION_ACTION_DISMISS_NOT_NOW,
    PROMOTION_ACTION_DISABLE_FUTURE_PROMPTS,
}
_WHY_NOT_NOW_CALLS: dict[str, list[float]] = {}


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register Heima websocket commands."""
    websocket_api.async_register_command(hass, websocket_observability_snapshot)
    websocket_api.async_register_command(hass, websocket_observability_action)
    websocket_api.async_register_command(hass, websocket_observability_why_not_now)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_OBSERVABILITY_SNAPSHOT,
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_observability_snapshot(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the read-only admin observability snapshot."""
    coordinator = _coordinator_for_message(hass, msg)
    if coordinator is None:
        connection.send_error(
            msg["id"],
            "not_found",
            "No active Heima config entry found for the requested observability snapshot.",
        )
        return
    connection.send_result(msg["id"], build_observability_snapshot(coordinator))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_OBSERVABILITY_WHY_NOT_NOW,
        vol.Optional("entry_id"): str,
        vol.Required("reaction_id"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_observability_why_not_now(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return focused read-only reasoning for one reaction."""
    coordinator = _coordinator_for_message(hass, msg)
    if coordinator is None:
        connection.send_error(
            msg["id"],
            "not_found",
            "No active Heima config entry found for the requested focused inspection.",
        )
        return
    entry_id = _coordinator_entry_id(coordinator)
    if not _why_not_now_rate_allowed(entry_id):
        connection.send_error(
            msg["id"],
            "rate_limited",
            "Focused observability inspection is rate limited.",
        )
        return
    result = _why_not_now_result(coordinator, str(msg.get("reaction_id") or ""))
    if result.get("outcome") != "not_found":
        _record_admin_action(
            coordinator,
            summary=f"Admin ran focused inspection for reaction '{result['reaction_id']}'.",
            reason_code="why_not_now_inspection",
            object_links=({"kind": "reaction", "id": str(result["reaction_id"])},),
        )
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_OBSERVABILITY_ACTION,
        vol.Optional("entry_id"): str,
        vol.Required("action"): vol.In(
            [
                ACTION_CLEAR_MANUAL_HOLD,
                ACTION_REVIEW_RUNTIME_PROMOTION,
                ACTION_RESET_RUNTIME_CONFIRMATION_PROMOTION_STATE,
                ACTION_REVIEW_PROPOSAL,
                ACTION_REVIEW_PROPOSAL_BATCH,
            ]
        ),
        vol.Optional("payload", default={}): dict,
    }
)
@callback
def websocket_observability_action(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run one allowlisted admin observability action."""
    if not connection.user or not connection.user.is_admin:
        raise Unauthorized()
    coordinator = _coordinator_for_message(hass, msg)
    if coordinator is None:
        connection.send_error(
            msg["id"],
            "not_found",
            "No active Heima config entry found for the requested observability action.",
        )
        return

    hass.async_create_task(_async_handle_observability_action(coordinator, connection, msg))


async def _async_handle_observability_action(
    coordinator: Any,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle one allowlisted admin action and send its websocket response."""
    action = str(msg.get("action") or "").strip()
    payload = dict(msg.get("payload") or {})
    if action == ACTION_CLEAR_MANUAL_HOLD:
        error = await _clear_manual_hold(coordinator, payload)
        if error is not None:
            connection.send_error(msg["id"], "invalid_payload", error)
            return
        connection.send_result(
            msg["id"],
            {
                "ok": True,
                "action": action,
                "snapshot": build_observability_snapshot(coordinator),
            },
        )
        return

    if action == ACTION_REVIEW_RUNTIME_PROMOTION:
        error = await _review_runtime_promotion(coordinator, payload)
        if error is not None:
            connection.send_error(msg["id"], "not_available", error)
            return
        connection.send_result(
            msg["id"],
            {
                "ok": True,
                "action": action,
                "snapshot": build_observability_snapshot(coordinator),
            },
        )
        return

    if action == ACTION_RESET_RUNTIME_CONFIRMATION_PROMOTION_STATE:
        error = await _reset_runtime_confirmation_promotion_state(coordinator, payload)
        if error is not None:
            connection.send_error(msg["id"], "not_available", error)
            return
        connection.send_result(
            msg["id"],
            {
                "ok": True,
                "action": action,
                "snapshot": build_observability_snapshot(coordinator),
            },
        )
        return

    if action == ACTION_REVIEW_PROPOSAL:
        error = await _review_proposal(coordinator, payload)
        if error is not None:
            connection.send_error(msg["id"], "not_available", error)
            return
        connection.send_result(
            msg["id"],
            {
                "ok": True,
                "action": action,
                "snapshot": build_observability_snapshot(coordinator),
            },
        )
        return

    if action == ACTION_REVIEW_PROPOSAL_BATCH:
        error = await _review_proposal_batch(coordinator, payload)
        if error is not None:
            connection.send_error(msg["id"], "not_available", error)
            return
        connection.send_result(
            msg["id"],
            {
                "ok": True,
                "action": action,
                "snapshot": build_observability_snapshot(coordinator),
            },
        )
        return

    connection.send_error(msg["id"], "unsupported_action", f"Unsupported action '{action}'.")


async def _clear_manual_hold(coordinator: Any, payload: dict[str, Any]) -> str | None:
    domain = str(payload.get("domain") or "").strip()
    subject_type = str(payload.get("subject_type") or "").strip()
    subject_id = str(payload.get("subject_id") or "").strip()
    if not domain or not subject_type or not subject_id:
        return "clear_manual_hold requires domain, subject_type, and subject_id."

    coordinator.engine.clear_manual_hold(
        domain=domain,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    runtime_observability = getattr(coordinator.engine, "_observability", None)
    if runtime_observability is not None and hasattr(runtime_observability, "record_admin_action"):
        runtime_observability.record_admin_action(
            summary=f"Admin cleared manual hold '{domain}:{subject_type}:{subject_id}'.",
            reason_code="clear_manual_hold",
            object_links=({"kind": "manual_hold", "id": f"{domain}:{subject_type}:{subject_id}"},),
        )
    request_evaluation = getattr(coordinator, "async_request_evaluation", None)
    if request_evaluation is not None:
        await request_evaluation(
            reason=f"admin_observability:clear_manual_hold:{domain}:{subject_type}:{subject_id}"
        )
    return None


async def _review_runtime_promotion(coordinator: Any, payload: dict[str, Any]) -> str | None:
    reaction_id = str(payload.get("reaction_id") or "").strip()
    promotion_action = str(payload.get("promotion_action") or "").strip()
    if not reaction_id or promotion_action not in PROMOTION_ACTIONS:
        return "review_runtime_promotion requires reaction_id and a supported promotion_action."
    reviewer = getattr(coordinator, "async_review_runtime_promotion", None)
    if reviewer is None:
        return "Runtime promotion review is not available for this config entry."
    accepted = await reviewer(reaction_id, promotion_action)
    if not accepted:
        return f"Runtime promotion review for reaction '{reaction_id}' is not available."
    _record_admin_action(
        coordinator,
        summary=f"Admin reviewed runtime promotion for reaction '{reaction_id}'.",
        reason_code="review_runtime_promotion",
        object_links=({"kind": "reaction", "id": reaction_id},),
    )
    return None


async def _reset_runtime_confirmation_promotion_state(
    coordinator: Any,
    payload: dict[str, Any],
) -> str | None:
    reaction_id = str(payload.get("reaction_id") or "").strip()
    if not reaction_id:
        return "reset_runtime_confirmation_promotion_state requires reaction_id."
    resetter = getattr(coordinator, "async_reset_runtime_confirmation_promotion_state", None)
    if resetter is None:
        return "Runtime confirmation promotion reset is not available for this config entry."
    accepted = await resetter(reaction_id)
    if not accepted:
        return (
            f"Runtime confirmation promotion state for reaction '{reaction_id}' is not available."
        )
    _record_admin_action(
        coordinator,
        summary=f"Admin reset runtime confirmation promotion state for reaction '{reaction_id}'.",
        reason_code="reset_runtime_confirmation_promotion_state",
        object_links=({"kind": "reaction", "id": reaction_id},),
    )
    return None


async def _review_proposal(coordinator: Any, payload: dict[str, Any]) -> str | None:
    proposal_id = str(payload.get("proposal_id") or "").strip()
    decision = _proposal_decision(payload.get("decision"))
    if not proposal_id or decision is None:
        return "review_proposal requires proposal_id and decision."
    reviewer = getattr(coordinator, "async_review_proposal", None)
    if reviewer is None:
        return "Proposal review is not available for this config entry."
    accepted = await reviewer(proposal_id, decision=decision, approved_by="installer")
    if not accepted:
        return f"Proposal '{proposal_id}' is not available for review."
    _record_admin_action(
        coordinator,
        summary=f"Admin {decision} proposal '{proposal_id}'.",
        reason_code="review_proposal",
        object_links=({"kind": "proposal", "id": proposal_id},),
    )
    return None


async def _review_proposal_batch(coordinator: Any, payload: dict[str, Any]) -> str | None:
    raw_ids = payload.get("proposal_ids") or []
    if not isinstance(raw_ids, (list, tuple)):
        return "review_proposal_batch requires proposal_ids to be a list."
    proposal_ids = [str(item).strip() for item in list(raw_ids) if str(item or "").strip()]
    decision = _proposal_decision(payload.get("decision"))
    dismiss_similar = bool(payload.get("dismiss_similar", False))
    if not proposal_ids or decision is None:
        return "review_proposal_batch requires proposal_ids and decision."
    reviewer = getattr(coordinator, "async_review_house_state_proposal_batch", None)
    if reviewer is None:
        return "House-state proposal batch review is not available for this config entry."
    result = await reviewer(
        proposal_ids,
        decision=decision,
        approved_by="installer",
        dismiss_similar=dismiss_similar,
    )
    if not getattr(result, "ok", False):
        return "Proposal batch is stale or no longer available for review."
    applied_ids = tuple(getattr(result, "applied_ids", ()) or ())
    _record_admin_action(
        coordinator,
        summary=f"Admin {decision} proposal batch with {len(applied_ids)} applied proposal(s).",
        reason_code="review_proposal_batch",
        object_links=tuple({"kind": "proposal", "id": proposal_id} for proposal_id in applied_ids),
    )
    return None


def _proposal_decision(value: Any) -> str | None:
    normalized = str(value or "").strip()
    if normalized in {"approved", "rejected"}:
        return normalized
    if normalized == "accept":
        return "approved"
    if normalized == "reject":
        return "rejected"
    return None


def _record_admin_action(
    coordinator: Any,
    *,
    summary: str,
    reason_code: str,
    object_links: tuple[dict[str, str], ...],
) -> None:
    engine = getattr(coordinator, "engine", None)
    runtime_observability = getattr(engine, "_observability", None)
    if runtime_observability is not None and hasattr(runtime_observability, "record_admin_action"):
        runtime_observability.record_admin_action(
            summary=summary,
            reason_code=reason_code,
            object_links=object_links,
        )


def _why_not_now_result(coordinator: Any, reaction_id: str) -> dict[str, Any]:
    normalized = str(reaction_id or "").strip()
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    snapshot = build_observability_snapshot(coordinator)
    reactions = snapshot.get("details", {}).get("reactions", {}).get("by_id", {})
    if normalized not in reactions:
        return {
            "reaction_id": normalized,
            "generated_at": generated_at,
            "outcome": "not_found",
            "reason_codes": ["reaction_not_found"],
            "input_summary": {},
            "condition_results": [],
            "guard_results": [],
            "policy_result": {},
            "apply_steps": [],
            "links": [],
        }
    detail = dict(reactions.get(normalized) or {})
    raw_latest_trace = detail.get("latest_trace")
    latest_trace = dict(raw_latest_trace) if isinstance(raw_latest_trace, dict) else {}
    summary = dict(detail.get("summary") or {})
    return {
        "reaction_id": normalized,
        "generated_at": generated_at,
        "outcome": "not_evaluable",
        "reason_codes": ["focused_evaluation_not_supported"],
        "input_summary": {
            "reaction_type": summary.get("reaction_type"),
            "last_outcome": summary.get("last_outcome"),
            "latest_trace_id": summary.get("latest_trace_id"),
        },
        "condition_results": [],
        "guard_results": list(latest_trace.get("guard_results") or []),
        "policy_result": dict(detail.get("execution_policy") or {}),
        "apply_steps": list(latest_trace.get("apply_steps") or []),
        "links": [
            {"kind": "reaction", "id": normalized},
            *list(latest_trace.get("links") or []),
        ],
    }


def _why_not_now_rate_allowed(entry_id: str) -> bool:
    now = time.monotonic()
    key = entry_id or "default"
    recent = [
        timestamp
        for timestamp in _WHY_NOT_NOW_CALLS.get(key, [])
        if now - timestamp < WHY_NOT_NOW_RATE_WINDOW_S
    ]
    if len(recent) >= WHY_NOT_NOW_RATE_LIMIT:
        _WHY_NOT_NOW_CALLS[key] = recent
        return False
    recent.append(now)
    _WHY_NOT_NOW_CALLS[key] = recent
    return True


def _coordinator_entry_id(coordinator: Any) -> str:
    entry = getattr(coordinator, "entry", None)
    return str(getattr(entry, "entry_id", "") or "")


def _coordinator_for_message(hass: HomeAssistant, msg: dict[str, Any]) -> Any | None:
    domain_data = hass.data.get(DOMAIN, {})
    entry_id = str(msg.get("entry_id") or "").strip()
    if entry_id:
        data = domain_data.get(entry_id)
        return data.get("coordinator") if isinstance(data, dict) else None
    for data in domain_data.values():
        if isinstance(data, dict) and data.get("coordinator") is not None:
            return data["coordinator"]
    return None
