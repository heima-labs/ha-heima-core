#!/usr/bin/env python3
"""Replay exported Heima diagnostics and flag stale runtime state."""

from __future__ import annotations

import argparse
import glob
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReplayFinding:
    severity: str
    code: str
    message: str


def validate_payload(payload: dict[str, Any], *, source: str = "<payload>") -> list[ReplayFinding]:
    """Validate one exported Heima diagnostics/observability payload."""
    health = _health(payload)
    runtime = _runtime(payload)
    engine = _engine(payload)
    findings: list[ReplayFinding] = []

    health_status = _str_first(
        health.get("status"),
        payload.get("state"),
        _path(payload, ("attributes", "status")),
    )
    health_reason = _str_first(
        health.get("reason"),
        health.get("health_reason"),
        _path(payload, ("attributes", "health_reason")),
    )
    last_invariant = _dict_first(
        health.get("last_invariant_violation"),
        _path(payload, ("attributes", "last_invariant_violation")),
    )
    last_anomaly = _dict_first(
        health.get("last_anomaly"),
        _path(payload, ("attributes", "last_anomaly")),
    )
    invariant_context = _dict_first(last_invariant.get("context"))
    anomaly_context = _dict_first(last_anomaly.get("context"))
    check_id = _str_first(invariant_context.get("check_id"), anomaly_context.get("check_id"))
    security_state = _str_first(
        _path(runtime, ("snapshot", "security_state")),
        _path(engine, ("snapshot", "security_state")),
        _path(payload, ("attributes", "security_state")),
    )
    unresolved = _string_set(_path(engine, ("invariants", "unresolved_check_ids")))

    degraded = health_status == "degraded" or health_reason == "invariant_violation"
    if degraded and check_id == "security_presence_mismatch" and security_state:
        if security_state != "armed_away":
            findings.append(
                ReplayFinding(
                    "error",
                    "stale_security_presence_mismatch",
                    (
                        f"{source}: health is degraded by security_presence_mismatch, "
                        f"but current security_state is {security_state!r}."
                    ),
                )
            )

    if degraded and check_id and unresolved is not None and check_id not in unresolved:
        findings.append(
            ReplayFinding(
                "error",
                "resolved_invariant_still_degrades_health",
                (
                    f"{source}: health is degraded by invariant {check_id!r}, "
                    "but engine.invariants.unresolved_check_ids does not contain it."
                ),
            )
        )

    anomaly_type = _str_first(last_anomaly.get("type"))
    anomaly_severity = _str_first(last_anomaly.get("severity"))
    if degraded and not check_id and anomaly_severity == "critical" and anomaly_type:
        findings.append(
            ReplayFinding(
                "warning",
                "critical_non_invariant_anomaly_without_resolver",
                (
                    f"{source}: critical non-invariant anomaly {anomaly_type!r} is degrading "
                    "health; no generic replayable resolution model exists yet."
                ),
            )
        )

    findings.extend(_validate_manual_hold(payload, source=source))
    findings.extend(_validate_camera_privacy_runtime(payload, source=source))
    findings.extend(_validate_runtime_confirmations(payload, source=source))
    return findings


def _validate_manual_hold(payload: dict[str, Any], *, source: str) -> list[ReplayFinding]:
    manual_hold = _manual_hold(payload)
    if not manual_hold:
        return []

    findings: list[ReplayFinding] = []
    active_holds = _list_first(manual_hold.get("active_holds"))
    pending_applies = _dict_first(manual_hold.get("pending_applies"))
    pending_items = _list_first(pending_applies.get("items"))
    pending_total = _int_or_none(pending_applies.get("total"))
    if pending_total is not None and pending_items and pending_total != len(pending_items):
        findings.append(
            ReplayFinding(
                "error",
                "manual_hold_pending_total_mismatch",
                (
                    f"{source}: manual_hold.pending_applies.total is {pending_total}, "
                    f"but {len(pending_items)} pending apply item(s) are present."
                ),
            )
        )

    by_domain = _dict_first(pending_applies.get("by_domain"))
    if pending_total is not None and by_domain:
        by_domain_total = sum(_int_or_none(value) or 0 for value in by_domain.values())
        if by_domain_total != pending_total:
            findings.append(
                ReplayFinding(
                    "error",
                    "manual_hold_pending_domain_total_mismatch",
                    (
                        f"{source}: manual_hold.pending_applies.by_domain sums to "
                        f"{by_domain_total}, but total is {pending_total}."
                    ),
                )
            )

    for hold in active_holds:
        if not isinstance(hold, dict):
            continue
        expires_in = _float_or_none(hold.get("expires_in_s"))
        if expires_in is not None and expires_in <= 0:
            findings.append(
                ReplayFinding(
                    "error",
                    "expired_manual_hold_active",
                    (
                        f"{source}: manual hold {hold.get('scope')!r} is still active "
                        f"with expires_in_s={expires_in}."
                    ),
                )
            )
        source_entity = _str_first(hold.get("source_entity"))
        reason = _str_first(hold.get("reason"))
        source_state = _entity_state(payload, source_entity)
        if reason == "helper_on" and source_state and source_state != "on":
            findings.append(
                ReplayFinding(
                    "error",
                    "manual_hold_helper_off_still_active",
                    (
                        f"{source}: helper-backed manual hold {hold.get('scope')!r} "
                        f"is active while {source_entity} is {source_state!r}."
                    ),
                )
            )

    for item in pending_items:
        if not isinstance(item, dict):
            continue
        expires_in = _float_or_none(item.get("expires_in_s"))
        if expires_in is not None and expires_in <= 0:
            findings.append(
                ReplayFinding(
                    "error",
                    "expired_manual_hold_pending_apply",
                    (
                        f"{source}: pending apply for {item.get('entity_id')!r} "
                        f"has expires_in_s={expires_in}."
                    ),
                )
            )
    return findings


def _validate_camera_privacy_runtime(
    payload: dict[str, Any],
    *,
    source: str,
) -> list[ReplayFinding]:
    configured = _configured_reactions(payload)
    if not configured:
        return []

    runtime_reactions = _engine_reactions(payload)
    current_security_state = _current_security_state(payload)
    held_scopes = _manual_hold_scopes(payload)
    findings: list[ReplayFinding] = []

    for reaction_id, raw_cfg in configured.items():
        if not isinstance(raw_cfg, dict):
            continue
        cfg = dict(raw_cfg)
        policy = _dict_first(cfg.get("camera_privacy_policy"))
        source_template_id = _str_first(
            cfg.get("source_template_id"),
            cfg.get("admin_authored_template_id"),
        )
        if not policy and source_template_id != "security.camera_privacy_policy":
            continue
        if cfg.get("enabled") is False:
            continue

        reaction_id = str(reaction_id)
        if reaction_id not in runtime_reactions:
            findings.append(
                ReplayFinding(
                    "error",
                    "camera_privacy_policy_missing_runtime_reaction",
                    f"{source}: enabled camera privacy policy {reaction_id!r} is not loaded.",
                )
            )

        privacy_entity = _str_first(policy.get("privacy_entity"))
        privacy_action = _str_first(policy.get("privacy_action"))
        expected_service = _privacy_action_service(privacy_action)
        if policy and not privacy_entity:
            findings.append(
                ReplayFinding(
                    "error",
                    "camera_privacy_policy_missing_privacy_entity",
                    f"{source}: camera privacy policy {reaction_id!r} has no privacy_entity.",
                )
            )
        if policy and not expected_service:
            findings.append(
                ReplayFinding(
                    "error",
                    "camera_privacy_policy_invalid_action",
                    (
                        f"{source}: camera privacy policy {reaction_id!r} has invalid "
                        f"privacy_action {privacy_action!r}."
                    ),
                )
            )

        steps = _list_first(cfg.get("steps"))
        if policy and not steps:
            findings.append(
                ReplayFinding(
                    "error",
                    "camera_privacy_policy_missing_steps",
                    f"{source}: camera privacy policy {reaction_id!r} has no apply steps.",
                )
            )
        for step in steps:
            if not isinstance(step, dict):
                continue
            target = _str_first(step.get("target"))
            params_entity = _str_first(_dict_first(step.get("params")).get("entity_id"))
            action = _str_first(step.get("action"))
            if privacy_entity and target and target != privacy_entity:
                findings.append(
                    ReplayFinding(
                        "error",
                        "camera_privacy_policy_step_target_mismatch",
                        (
                            f"{source}: camera privacy policy {reaction_id!r} targets "
                            f"{target!r}, but privacy_entity is {privacy_entity!r}."
                        ),
                    )
                )
            if privacy_entity and params_entity and params_entity != privacy_entity:
                findings.append(
                    ReplayFinding(
                        "error",
                        "camera_privacy_policy_step_entity_mismatch",
                        (
                            f"{source}: camera privacy policy {reaction_id!r} params.entity_id "
                            f"is {params_entity!r}, but privacy_entity is {privacy_entity!r}."
                        ),
                    )
                )
            if expected_service and action and action != expected_service:
                findings.append(
                    ReplayFinding(
                        "error",
                        "camera_privacy_policy_step_action_mismatch",
                        (
                            f"{source}: camera privacy policy {reaction_id!r} action "
                            f"is {action!r}, but privacy_action requires {expected_service!r}."
                        ),
                    )
                )

        runtime = _dict_first(runtime_reactions.get(reaction_id))
        last_fired_state = _str_first(runtime.get("last_fired_state"))
        alarm_states = _string_set(cfg.get("alarm_states")) or set()
        expected_state = _privacy_action_state(privacy_action)
        entity_state = _entity_state(payload, privacy_entity)
        is_privacy_held = f"switch:entity:{privacy_entity}" in held_scopes
        if (
            privacy_entity
            and expected_state
            and entity_state
            and last_fired_state
            and last_fired_state in alarm_states
            and current_security_state == last_fired_state
            and not is_privacy_held
            and entity_state != expected_state
        ):
            findings.append(
                ReplayFinding(
                    "error",
                    "camera_privacy_runtime_switch_state_mismatch",
                    (
                        f"{source}: camera privacy policy {reaction_id!r} fired for "
                        f"{last_fired_state!r}, but {privacy_entity} is {entity_state!r} "
                        f"instead of {expected_state!r} and no manual hold is active."
                    ),
                )
            )
    return findings


def _validate_runtime_confirmations(
    payload: dict[str, Any],
    *,
    source: str,
) -> list[ReplayFinding]:
    confirmations = _runtime_confirmation(payload)
    if not confirmations:
        return []

    findings: list[ReplayFinding] = []
    pending_requests = [
        item for item in _list_first(confirmations.get("pending_requests")) if isinstance(item, dict)
    ]
    pending_count = _int_or_none(confirmations.get("pending"))
    if pending_count is not None and pending_count != len(pending_requests):
        findings.append(
            ReplayFinding(
                "error",
                "runtime_confirmation_pending_count_mismatch",
                (
                    f"{source}: runtime_confirmation.pending is {pending_count}, "
                    f"but {len(pending_requests)} pending request(s) are listed."
                ),
            )
        )

    pending_ids = {_str_first(item.get("request_id")) for item in pending_requests}
    pending_ids.discard("")
    scheduled_timeouts = _string_set(confirmations.get("scheduled_timeouts"))
    if scheduled_timeouts is not None:
        missing_timeouts = sorted(pending_ids - scheduled_timeouts)
        orphan_timeouts = sorted(scheduled_timeouts - pending_ids)
        for request_id in missing_timeouts:
            findings.append(
                ReplayFinding(
                    "error",
                    "runtime_confirmation_pending_timeout_not_scheduled",
                    f"{source}: pending runtime confirmation {request_id!r} has no timeout handle.",
                )
            )
        for request_id in orphan_timeouts:
            findings.append(
                ReplayFinding(
                    "error",
                    "runtime_confirmation_orphan_timeout_handle",
                    f"{source}: timeout handle exists for non-pending request {request_id!r}.",
                )
            )

    now = _payload_timestamp(payload)
    if now is not None:
        for item in pending_requests:
            expires_at = _parse_datetime(item.get("expires_at"))
            request_id = _str_first(item.get("request_id")) or "<unknown>"
            if expires_at is not None and expires_at <= now:
                findings.append(
                    ReplayFinding(
                        "error",
                        "runtime_confirmation_expired_pending_request",
                        (
                            f"{source}: pending runtime confirmation {request_id!r} "
                            f"expired at {expires_at.isoformat()}."
                        ),
                    )
                )

    completed_by_status = _dict_first(confirmations.get("completed_by_status"))
    recent_completed = _int_or_none(confirmations.get("recent_completed"))
    if recent_completed is not None and completed_by_status:
        completed_total = sum(_int_or_none(value) or 0 for value in completed_by_status.values())
        if completed_total != recent_completed:
            findings.append(
                ReplayFinding(
                    "error",
                    "runtime_confirmation_completed_count_mismatch",
                    (
                        f"{source}: runtime_confirmation.completed_by_status sums to "
                        f"{completed_total}, but recent_completed is {recent_completed}."
                    ),
                )
            )
    return findings


def load_payload_file(path: Path) -> Any:
    if path.suffix.lower() == ".txt":
        return load_sectioned_text_file(path)
    return load_json_file(path)


def load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_sectioned_text_file(path: Path) -> dict[str, Any]:
    sections = _parse_sectioned_json(path.read_text(encoding="utf-8"))
    engine = _dict_first(sections.get("ENGINE"))
    runtime: dict[str, Any] = {}
    if engine:
        runtime["engine"] = engine
    runtime_confirmation = _dict_first(
        sections.get("RUNTIME_CONFIRMATION"),
        sections.get("RUNTIME_CONFIRMATIONS"),
    )
    if runtime_confirmation:
        runtime["runtime_confirmation"] = runtime_confirmation
    return {
        "source_format": "sectioned_text",
        "sections": sections,
        "runtime": runtime,
        "health": _dict_first(sections.get("HEALTH")),
        "generated_at": _str_first(_path(sections, ("OPS_SNAPSHOT", "generated_at"))),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Diagnostics or observability JSON files")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print checked file and finding counts.",
    )
    args = parser.parse_args()

    findings: list[ReplayFinding] = []
    paths = _expand_paths(args.paths)
    for path in paths:
        payload = load_payload_file(path)
        if not isinstance(payload, dict):
            findings.append(
                ReplayFinding("error", "invalid_payload", f"{path}: root JSON value is not an object")
            )
            continue
        findings.extend(validate_payload(payload, source=str(path)))

    if args.summary:
        errors = sum(1 for item in findings if item.severity == "error")
        warnings = sum(1 for item in findings if item.severity == "warning")
        print(f"Checked files: {len(paths)}")
        print(f"Findings: errors={errors} warnings={warnings}")

    if not paths:
        print("ERROR no_input_files: no diagnostics files matched the requested paths")
        return 1

    if not findings:
        print("PASS: no stale runtime-state findings")
        return 0

    for finding in findings:
        print(f"{finding.severity.upper()} {finding.code}: {finding.message}")
    return 1 if any(item.severity == "error" for item in findings) else 0


def _expand_paths(raw_paths: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in raw_paths:
        expanded = sorted(glob.glob(raw))
        candidates = expanded if expanded else [raw]
        for candidate in candidates:
            path = Path(candidate)
            if path.is_dir():
                paths.extend(sorted(_diagnostics_files(path)))
            else:
                paths.append(path)
    return paths


def _diagnostics_files(path: Path) -> list[Path]:
    return [
        item
        for item in path.rglob("*")
        if item.is_file()
        and (item.suffix.lower() == ".json" or item.name == "diagnostics_all.txt")
    ]


def _parse_sectioned_json(text: str) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    matches = list(re.finditer(r"^===\s+([A-Z0-9_]+)\s+===$", text, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        name = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = _extract_first_json_value(text[start:end])
        if value is not None:
            sections[name] = value
    return sections


def _extract_first_json_value(text: str) -> Any:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", text):
        try:
            value, _ = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        return value
    return None


def _health(payload: dict[str, Any]) -> dict[str, Any]:
    return _dict_first(payload.get("health"), payload.get("attributes"))


def _runtime(payload: dict[str, Any]) -> dict[str, Any]:
    runtime = _dict_first(payload.get("runtime"))
    if runtime:
        return runtime
    data = _dict_first(payload.get("data"))
    return _dict_first(data.get("runtime"))


def _engine(payload: dict[str, Any]) -> dict[str, Any]:
    runtime = _runtime(payload)
    return _dict_first(runtime.get("engine"))


def _manual_hold(payload: dict[str, Any]) -> dict[str, Any]:
    engine = _engine(payload)
    manual_hold = _dict_first(engine.get("manual_hold"))
    if manual_hold:
        return manual_hold
    runtime = _runtime(payload)
    manual_hold = _dict_first(runtime.get("manual_hold"))
    if manual_hold:
        return manual_hold
    return _dict_first(payload.get("manual_hold"), payload.get("manual_holds"))


def _runtime_confirmation(payload: dict[str, Any]) -> dict[str, Any]:
    runtime = _runtime(payload)
    confirmation = _dict_first(
        runtime.get("runtime_confirmation"),
        runtime.get("runtime_confirmations"),
    )
    if confirmation:
        return confirmation
    return _dict_first(payload.get("runtime_confirmation"), payload.get("runtime_confirmations"))


def _entry_options(payload: dict[str, Any]) -> dict[str, Any]:
    entry = _dict_first(payload.get("entry"), _path(payload, ("data", "entry")))
    options = _dict_first(entry.get("options"))
    if options:
        return options
    return _dict_first(payload.get("options"), _path(payload, ("data", "options")))


def _configured_reactions(payload: dict[str, Any]) -> dict[str, Any]:
    options = _entry_options(payload)
    reactions = _dict_first(options.get("reactions"))
    configured = _dict_first(reactions.get("configured"))
    if configured:
        return configured
    configured = _dict_first(_path(payload, ("reactions", "configured")))
    if configured:
        return configured
    return _dict_first(_path(payload, ("data", "reactions", "configured")))


def _engine_reactions(payload: dict[str, Any]) -> dict[str, Any]:
    reactions = _dict_first(_engine(payload).get("reactions"))
    if reactions:
        return reactions
    rows = payload.get("reactions")
    if isinstance(rows, list):
        return {
            str(item.get("reaction_id") or item.get("id") or ""): dict(item)
            for item in rows
            if isinstance(item, dict)
        }
    return {}


def _manual_hold_scopes(payload: dict[str, Any]) -> set[str]:
    scopes: set[str] = set()
    for hold in _list_first(_manual_hold(payload).get("active_holds")):
        if isinstance(hold, dict):
            scope = _str_first(hold.get("scope"))
            if scope:
                scopes.add(scope)
    return scopes


def _current_security_state(payload: dict[str, Any]) -> str:
    runtime = _runtime(payload)
    engine = _engine(payload)
    return _str_first(
        _path(runtime, ("snapshot", "security_state")),
        _path(engine, ("snapshot", "security_state")),
        _path(payload, ("attributes", "security_state")),
    )


def _privacy_action_service(privacy_action: str) -> str:
    if privacy_action == "turn_on":
        return "switch.turn_on"
    if privacy_action == "turn_off":
        return "switch.turn_off"
    return ""


def _privacy_action_state(privacy_action: str) -> str:
    if privacy_action == "turn_on":
        return "on"
    if privacy_action == "turn_off":
        return "off"
    return ""


def _entity_state(payload: dict[str, Any], entity_id: str) -> str:
    if not entity_id:
        return ""
    states = payload.get("entity_states")
    if isinstance(states, dict):
        state = _dict_first(states.get(entity_id))
        return _str_first(state.get("state"))
    if isinstance(states, list):
        for item in states:
            if isinstance(item, dict) and item.get("entity_id") == entity_id:
                return _str_first(item.get("state"))
    inputs = _dict_first(payload.get("inputs"))
    if entity_id in inputs:
        return _str_first(_dict_first(inputs.get(entity_id)).get("state"))
    return ""


def _dict_first(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return dict(value)
    return {}


def _list_first(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _str_first(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_set(value: Any) -> set[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if str(item)}


def _path(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _payload_timestamp(payload: dict[str, Any]) -> datetime | None:
    for value in (
        payload.get("generated_at"),
        payload.get("created_at"),
        payload.get("ts"),
        _path(payload, ("metadata", "generated_at")),
        _path(payload, ("health", "last_updated")),
        _path(payload, ("attributes", "last_updated")),
        payload.get("last_updated"),
        payload.get("last_reported"),
    ):
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
