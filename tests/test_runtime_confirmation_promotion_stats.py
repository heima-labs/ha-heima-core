from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.runtime_confirmation import RuntimeActionRequest


class _FakeConfigEntries:
    def async_update_entry(self, entry, *, options):
        entry.options = dict(options)


def _coordinator(options: dict) -> HeimaCoordinator:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(options=dict(options))
    coordinator.hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    return coordinator


def _request(reaction_id: str = "r1") -> RuntimeActionRequest:
    now = datetime.now(timezone.utc)
    return RuntimeActionRequest(
        reaction_id=reaction_id,
        reaction_type="context_conditioned_lighting_scene",
        occurrence_key="occurrence-1",
        title="Apply?",
        message="Apply stored steps?",
        apply_steps=(ApplyStep(domain="light", target="light.studio", action="light.turn_on"),),
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )


def test_runtime_confirmation_outcomes_persist_stats() -> None:
    coordinator = _coordinator(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "context_conditioned_lighting_scene",
                        "execution_policy": {"mode": "ask_residents"},
                    }
                }
            }
        }
    )
    request = _request()

    coordinator._record_runtime_confirmation_outcome(request, "pending")
    coordinator._record_runtime_confirmation_outcome(request, "approved")

    stats = coordinator.entry.options["reactions"]["confirmation_stats"]["r1"]
    assert stats["requested"] == 1
    assert stats["approved"] == 1
    assert stats["first_requested_at"]
    assert stats["last_requested_at"]
    assert stats["last_approved_at"]
    assert len(stats["approved_dates"]) == 1


def test_runtime_confirmation_promotion_review_created_from_explicit_evidence() -> None:
    coordinator = _coordinator(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "context_conditioned_lighting_scene",
                        "execution_policy": {
                            "mode": "ask_residents",
                            "promotion": {
                                "min_samples": 2,
                                "min_approval_rate": 0.5,
                                "min_distinct_days": 1,
                            },
                        },
                    }
                }
            }
        }
    )
    request = _request()

    coordinator._record_runtime_confirmation_outcome(request, "approved")
    coordinator._record_runtime_confirmation_outcome(request, "dismissed")

    review = coordinator.entry.options["reactions"]["promotion_reviews"]["r1"]
    assert review["status"] == "pending_admin_review"
    assert review["target_mode"] == "auto_apply"
    assert review["next_reminder_after"]
    assert review["reminder_due"] is False


def test_timeout_outcomes_do_not_create_promotion_review() -> None:
    coordinator = _coordinator(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "context_conditioned_lighting_scene",
                        "execution_policy": {
                            "mode": "ask_residents",
                            "promotion": {
                                "min_samples": 1,
                                "min_approval_rate": 0.0,
                                "min_distinct_days": 0,
                            },
                        },
                    }
                }
            }
        }
    )
    request = _request()

    coordinator._record_runtime_confirmation_outcome(request, "timeout_applied")
    coordinator._record_runtime_confirmation_outcome(request, "timeout_skipped")

    assert (
        coordinator.entry.options["reactions"]["confirmation_stats"]["r1"]["timeout_applied"] == 1
    )
    assert (
        coordinator.entry.options["reactions"]["confirmation_stats"]["r1"]["timeout_skipped"] == 1
    )
    assert coordinator.entry.options["reactions"].get("promotion_reviews", {}) == {}


def test_pending_promotion_review_is_revoked_when_new_evidence_fails_threshold() -> None:
    coordinator = _coordinator(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "context_conditioned_lighting_scene",
                        "execution_policy": {
                            "mode": "ask_residents",
                            "promotion": {
                                "min_samples": 2,
                                "min_approval_rate": 0.75,
                                "min_distinct_days": 1,
                            },
                        },
                    }
                },
                "promotion_reviews": {
                    "r1": {
                        "reaction_id": "r1",
                        "status": "pending_admin_review",
                        "target_mode": "auto_apply",
                    }
                },
                "confirmation_stats": {
                    "r1": {
                        "approved": 2,
                        "dismissed": 0,
                        "approved_dates": ["2026-07-14"],
                    }
                },
            }
        }
    )

    coordinator._record_runtime_confirmation_outcome(_request(), "dismissed")

    review = coordinator.entry.options["reactions"]["promotion_reviews"]["r1"]
    assert review["status"] == "revoked"
    assert review["failure_reason"] == "approval_rate_below_threshold"


def test_not_now_cooldown_blocks_reprompt_from_old_evidence() -> None:
    now = datetime.now(timezone.utc).isoformat()
    coordinator = _coordinator(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "context_conditioned_lighting_scene",
                        "execution_policy": {
                            "mode": "ask_residents",
                            "promotion": {
                                "min_samples": 1,
                                "min_approval_rate": 0.8,
                                "min_distinct_days": 1,
                                "cooldown_schedule_days": [14],
                                "min_new_approvals_after_dismissal": 1,
                            },
                        },
                    }
                },
                "promotion_reviews": {
                    "r1": {
                        "reaction_id": "r1",
                        "status": "dismissed_not_now",
                        "promotion_dismiss_count": 1,
                        "last_promotion_dismissed_at": now,
                    }
                },
                "confirmation_stats": {
                    "r1": {
                        "approved": 5,
                        "dismissed": 0,
                        "approved_dates": ["2026-07-14"],
                    }
                },
            }
        }
    )

    coordinator._record_runtime_confirmation_outcome(_request(), "approved")

    review = coordinator.entry.options["reactions"]["promotion_reviews"]["r1"]
    assert review["status"] == "dismissed_not_now"


def test_not_now_requires_new_approval_after_cooldown() -> None:
    old = datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat()
    coordinator = _coordinator(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "context_conditioned_lighting_scene",
                        "execution_policy": {
                            "mode": "ask_residents",
                            "promotion": {
                                "min_samples": 1,
                                "min_approval_rate": 0.8,
                                "min_distinct_days": 1,
                                "cooldown_schedule_days": [1],
                                "min_new_approvals_after_dismissal": 2,
                            },
                        },
                    }
                },
                "promotion_reviews": {
                    "r1": {
                        "reaction_id": "r1",
                        "status": "dismissed_not_now",
                        "promotion_dismiss_count": 1,
                        "last_promotion_dismissed_at": old,
                    }
                },
                "confirmation_stats": {
                    "r1": {
                        "approved": 5,
                        "dismissed": 0,
                        "approved_dates": ["2026-07-14"],
                        "explicit_events": [
                            {"outcome": "approved", "ts": "1999-01-01T00:00:00+00:00"}
                        ],
                    }
                },
            }
        }
    )

    coordinator._record_runtime_confirmation_outcome(_request(), "approved")
    assert (
        coordinator.entry.options["reactions"]["promotion_reviews"]["r1"]["status"]
        == "dismissed_not_now"
    )

    coordinator._record_runtime_confirmation_outcome(_request(), "approved")

    review = coordinator.entry.options["reactions"]["promotion_reviews"]["r1"]
    assert review["status"] == "pending_admin_review"


def test_pending_promotion_review_marks_admin_reminder_due_after_interval() -> None:
    old = datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat()
    coordinator = _coordinator(
        {
            "reactions": {
                "configured": {
                    "r1": {
                        "reaction_type": "context_conditioned_lighting_scene",
                        "execution_policy": {
                            "mode": "ask_residents",
                            "promotion": {
                                "min_samples": 1,
                                "min_approval_rate": 0.8,
                                "min_distinct_days": 1,
                                "reminder_interval_days": 1,
                            },
                        },
                    }
                },
                "promotion_reviews": {
                    "r1": {
                        "reaction_id": "r1",
                        "status": "pending_admin_review",
                        "first_prompted_at": old,
                        "last_prompted_at": old,
                        "target_mode": "auto_apply",
                    }
                },
                "confirmation_stats": {
                    "r1": {
                        "approved": 1,
                        "dismissed": 0,
                        "approved_dates": ["2026-07-14"],
                    }
                },
            }
        }
    )

    coordinator._record_runtime_confirmation_outcome(_request(), "approved")

    review = coordinator.entry.options["reactions"]["promotion_reviews"]["r1"]
    assert review["status"] == "pending_admin_review"
    assert review["reminder_due"] is True
    assert review["next_reminder_after"].startswith("2000-01-02")
