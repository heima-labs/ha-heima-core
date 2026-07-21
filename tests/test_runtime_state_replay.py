from __future__ import annotations

from scripts.runtime_state_replay import validate_payload


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
