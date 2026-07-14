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
