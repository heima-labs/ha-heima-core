from __future__ import annotations

import importlib.util
from pathlib import Path

from scripts.runtime_state_replay import _expand_paths, load_sectioned_text_file, validate_payload


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
    nested_dir = tmp_path / "snapshot"
    nested_dir.mkdir()
    nested = nested_dir / "ops_snapshot.json"
    ignored = tmp_path / "ignored.txt"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    nested.write_text("{}", encoding="utf-8")
    ignored.write_text("{}", encoding="utf-8")

    assert _expand_paths([str(tmp_path)]) == [first, nested, second]
    assert _expand_paths([str(tmp_path / "*.json")]) == [first, second]


def test_replay_loads_sectioned_diagnostics_text(tmp_path) -> None:
    diagnostics = tmp_path / "diagnostics_all.txt"
    diagnostics.write_text(
        """
=== EVENT_STORE ===
{"total_events": 1}

=== ENGINE ===
{
  "snapshot": {"security_state": "disarmed"},
  "invariants": {"unresolved_check_ids": []},
  "manual_hold": {
    "active_holds": [],
    "pending_applies": {"total": 0, "by_domain": {}, "items": []}
  }
}
""",
        encoding="utf-8",
    )

    payload = load_sectioned_text_file(diagnostics)

    assert payload["runtime"]["engine"]["snapshot"]["security_state"] == "disarmed"
    assert validate_payload(payload) == []


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
    payload = replay_live._combined_health_runtime_payload(health, diagnostics, {})  # noqa: SLF001

    assert [item.code for item in validate_payload(payload)] == [
        "stale_security_presence_mismatch",
        "resolved_invariant_still_degrades_health",
    ]


def test_replay_flags_manual_hold_inconsistencies() -> None:
    payload = {
        "runtime": {
            "engine": {
                "manual_hold": {
                    "active_holds": [
                        {
                            "scope": "light:entity:light.desk",
                            "reason": "helper_on",
                            "source_entity": "input_boolean.desk_hold",
                            "expires_in_s": -1,
                        }
                    ],
                    "pending_applies": {
                        "total": 3,
                        "by_domain": {"light": 2},
                        "items": [
                            {
                                "entity_id": "light.desk",
                                "expires_in_s": -5,
                            }
                        ],
                    },
                }
            }
        },
        "entity_states": {
            "input_boolean.desk_hold": {"state": "off"},
        },
    }

    assert [item.code for item in validate_payload(payload)] == [
        "manual_hold_pending_total_mismatch",
        "manual_hold_pending_domain_total_mismatch",
        "expired_manual_hold_active",
        "manual_hold_helper_off_still_active",
        "expired_manual_hold_pending_apply",
    ]


def test_replay_accepts_consistent_manual_hold_state() -> None:
    payload = {
        "runtime": {
            "engine": {
                "manual_hold": {
                    "active_holds": [
                        {
                            "scope": "light:entity:light.desk",
                            "reason": "helper_on",
                            "source_entity": "input_boolean.desk_hold",
                            "expires_in_s": 120,
                        }
                    ],
                    "pending_applies": {
                        "total": 1,
                        "by_domain": {"light": 1},
                        "items": [
                            {
                                "entity_id": "light.desk",
                                "expires_in_s": 10,
                            }
                        ],
                    },
                }
            }
        },
        "entity_states": {
            "input_boolean.desk_hold": {"state": "on"},
        },
    }

    assert validate_payload(payload) == []


def test_replay_flags_camera_privacy_policy_runtime_inconsistencies() -> None:
    payload = {
        "entry": {
            "options": {
                "reactions": {
                    "configured": {
                        "camera_policy": {
                            "enabled": True,
                            "source_template_id": "security.camera_privacy_policy",
                            "alarm_states": ["armed_night"],
                            "camera_privacy_policy": {
                                "privacy_entity": "switch.camera_privacy",
                                "privacy_action": "turn_off",
                            },
                            "steps": [
                                {
                                    "action": "switch.turn_on",
                                    "target": "switch.other_privacy",
                                    "params": {"entity_id": "switch.wrong_privacy"},
                                }
                            ],
                        }
                    }
                }
            }
        },
        "runtime": {
            "engine": {
                "snapshot": {"security_state": "armed_night"},
                "manual_hold": {"active_holds": []},
                "reactions": {},
            }
        },
        "entity_states": {
            "switch.camera_privacy": {"state": "on"},
        },
    }

    assert [item.code for item in validate_payload(payload)] == [
        "camera_privacy_policy_missing_runtime_reaction",
        "camera_privacy_policy_step_target_mismatch",
        "camera_privacy_policy_step_entity_mismatch",
        "camera_privacy_policy_step_action_mismatch",
    ]


def test_replay_flags_camera_privacy_switch_mismatch_after_fire() -> None:
    payload = {
        "entry": {
            "options": {
                "reactions": {
                    "configured": {
                        "camera_policy": {
                            "enabled": True,
                            "source_template_id": "security.camera_privacy_policy",
                            "alarm_states": ["armed_night"],
                            "camera_privacy_policy": {
                                "privacy_entity": "switch.camera_privacy",
                                "privacy_action": "turn_off",
                            },
                            "steps": [
                                {
                                    "action": "switch.turn_off",
                                    "target": "switch.camera_privacy",
                                    "params": {"entity_id": "switch.camera_privacy"},
                                }
                            ],
                        }
                    }
                }
            }
        },
        "runtime": {
            "engine": {
                "snapshot": {"security_state": "armed_night"},
                "manual_hold": {"active_holds": []},
                "reactions": {"camera_policy": {"last_fired_state": "armed_night"}},
            }
        },
        "entity_states": {
            "switch.camera_privacy": {"state": "on"},
        },
    }

    assert [item.code for item in validate_payload(payload)] == [
        "camera_privacy_runtime_switch_state_mismatch"
    ]


def test_replay_accepts_camera_privacy_switch_mismatch_when_held() -> None:
    payload = {
        "entry": {
            "options": {
                "reactions": {
                    "configured": {
                        "camera_policy": {
                            "enabled": True,
                            "source_template_id": "security.camera_privacy_policy",
                            "alarm_states": ["armed_night"],
                            "camera_privacy_policy": {
                                "privacy_entity": "switch.camera_privacy",
                                "privacy_action": "turn_off",
                            },
                            "steps": [
                                {
                                    "action": "switch.turn_off",
                                    "target": "switch.camera_privacy",
                                    "params": {"entity_id": "switch.camera_privacy"},
                                }
                            ],
                        }
                    }
                }
            }
        },
        "runtime": {
            "engine": {
                "snapshot": {"security_state": "armed_night"},
                "manual_hold": {
                    "active_holds": [
                        {"scope": "switch:entity:switch.camera_privacy", "reason": "external_on"}
                    ]
                },
                "reactions": {"camera_policy": {"last_fired_state": "armed_night"}},
            }
        },
        "entity_states": {
            "switch.camera_privacy": {"state": "on"},
        },
    }

    assert validate_payload(payload) == []


def test_replay_flags_runtime_confirmation_inconsistencies() -> None:
    payload = {
        "generated_at": "2026-07-21T10:00:00+00:00",
        "runtime": {
            "runtime_confirmation": {
                "pending": 2,
                "pending_requests": [
                    {
                        "request_id": "request-a",
                        "status": "pending",
                        "expires_at": "2026-07-21T09:59:00+00:00",
                    }
                ],
                "scheduled_timeouts": ["request-b"],
                "recent_completed": 3,
                "completed_by_status": {"approved": 1, "cancelled": 1},
            }
        },
    }

    assert [item.code for item in validate_payload(payload)] == [
        "runtime_confirmation_pending_count_mismatch",
        "runtime_confirmation_pending_timeout_not_scheduled",
        "runtime_confirmation_orphan_timeout_handle",
        "runtime_confirmation_expired_pending_request",
        "runtime_confirmation_completed_count_mismatch",
    ]


def test_replay_accepts_consistent_runtime_confirmation_state() -> None:
    payload = {
        "generated_at": "2026-07-21T10:00:00+00:00",
        "runtime": {
            "runtime_confirmation": {
                "pending": 1,
                "pending_requests": [
                    {
                        "request_id": "request-a",
                        "status": "pending",
                        "expires_at": "2026-07-21T10:05:00+00:00",
                    }
                ],
                "scheduled_timeouts": ["request-a"],
                "recent_completed": 2,
                "completed_by_status": {"approved": 1, "cancelled": 1},
            }
        },
    }

    assert validate_payload(payload) == []


def _load_live_replay_module():
    path = (
        Path(__file__).resolve().parent.parent
        / "scripts/live_tests/082_runtime_state_replay_live.py"
    )
    spec = importlib.util.spec_from_file_location("heima_live_082_runtime_state_replay", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
