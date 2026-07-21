#!/usr/bin/env python3
"""Replay exported Heima diagnostics and flag stale runtime state."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
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

    return findings


def load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Diagnostics or observability JSON files")
    args = parser.parse_args()

    findings: list[ReplayFinding] = []
    for raw_path in args.paths:
        path = Path(raw_path)
        payload = load_json_file(path)
        if not isinstance(payload, dict):
            findings.append(
                ReplayFinding("error", "invalid_payload", f"{path}: root JSON value is not an object")
            )
            continue
        findings.extend(validate_payload(payload, source=str(path)))

    if not findings:
        print("PASS: no stale runtime-state findings")
        return 0

    for finding in findings:
        print(f"{finding.severity.upper()} {finding.code}: {finding.message}")
    return 1 if any(item.severity == "error" for item in findings) else 0


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


def _dict_first(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return dict(value)
    return {}


def _str_first(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


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


if __name__ == "__main__":
    raise SystemExit(main())
