from __future__ import annotations

import importlib.util
from pathlib import Path

from scripts.runtime_state_replay import _expand_paths, validate_payload


def test_replay_flags_stale_security_presence_mismatch() -> None:
    payload = {
        "health": {
            "status": "degraded",
            "reason": "invariant_violation",
            "last_invariant_violation": {
                "context": {"check_id": "security_presence_mismatch"},
            },
        },
        "runtime": {
            "snapshot": {"security_state": "disarmed"},
            "engine": {
                "invariants": {
                    "active_check_ids": [],
                    "unresolved_check_ids": [],
                }
            },
        },
    }

    findings = validate_payload(payload)

    assert [item.code for item in findings] == [
        "stale_security_presence_mismatch",
        "resolved_invariant_still_degrades_health",
    ]


def test_replay_accepts_active_security_presence_mismatch() -> None:
    payload = {
        "health": {
            "status": "degraded",
            "reason": "invariant_violation",
            "last_invariant_violation": {
                "context": {"check_id": "security_presence_mismatch"},
            },
        },
        "runtime": {
            "snapshot": {"security_state": "armed_away"},
            "engine": {
                "invariants": {
                    "active_check_ids": ["security_presence_mismatch"],
                    "unresolved_check_ids": ["security_presence_mismatch"],
                }
            },
        },
    }

    assert validate_payload(payload) == []


def test_replay_warns_for_critical_non_invariant_anomaly() -> None:
    payload = {
        "state": "degraded",
        "attributes": {
            "health_reason": "anomaly",
            "last_anomaly": {
                "type": "anomaly.stove_on_unattended",
                "severity": "critical",
                "context": {"anomaly_type": "stove_on_unattended"},
            },
        },
    }

    findings = validate_payload(payload)

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].code == "critical_non_invariant_anomaly_without_resolver"


def test_replay_expands_directories_and_globs(tmp_path) -> None:
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    ignored = tmp_path / "ignored.txt"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    ignored.write_text("{}", encoding="utf-8")

    assert _expand_paths([str(tmp_path)]) == [first, second]
    assert _expand_paths([str(tmp_path / "*.json")]) == [first, second]


def test_live_replay_combines_health_sensor_with_runtime_diagnostics() -> None:
    health = {
        "state": "degraded",
        "attributes": {
            "health_reason": "invariant_violation",
            "last_invariant_violation": {
                "context": {"check_id": "security_presence_mismatch"},
            },
        },
    }
    diagnostics = {
        "runtime": {
            "engine": {
                "snapshot": {"security_state": "disarmed"},
                "invariants": {"unresolved_check_ids": []},
            }
        }
    }

    replay_live = _load_live_replay_module()
    payload = replay_live._combined_health_runtime_payload(health, diagnostics)  # noqa: SLF001

    assert [item.code for item in validate_payload(payload)] == [
        "stale_security_presence_mismatch",
        "resolved_invariant_still_degrades_health",
    ]


def _load_live_replay_module():
    path = Path(__file__).resolve().parent.parent / "scripts/live_tests/082_runtime_state_replay_live.py"
    spec = importlib.util.spec_from_file_location("heima_live_082_runtime_state_replay", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
