"""Tests for Phase 7 R5: heima_reactions_active sensor, mute/unmute commands."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from custom_components.heima.runtime.contracts import ApplyStep
from custom_components.heima.runtime.reactions.builtin import ConsecutiveStateReaction
from custom_components.heima.runtime.snapshot import DecisionSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step() -> ApplyStep:
    return ApplyStep(domain="heating", target="climate.test", action="climate.set_temperature")


def _snap(anyone_home: bool = False) -> DecisionSnapshot:
    base = DecisionSnapshot.empty()
    from dataclasses import replace

    ts = datetime.now(timezone.utc).isoformat()
    return replace(base, anyone_home=anyone_home, ts=ts)


def _make_engine():
    """Create a minimal HeimaEngine with mocked HA dependencies."""
    from unittest.mock import patch

    from custom_components.heima.runtime.engine import HeimaEngine

    hass = MagicMock()
    hass.states.get.return_value = None
    entry = MagicMock()
    entry.options = {}
    entry.entry_id = "test_entry"

    with patch.object(HeimaEngine, "_build_default_state"):
        engine = HeimaEngine.__new__(HeimaEngine)
        engine._hass = hass
        engine._entry = entry
        engine._behaviors = []
        engine._reactions = []
        engine._muted_reactions = set()
        from custom_components.heima.runtime.snapshot_buffer import SnapshotBuffer

        engine._snapshot_buffer = SnapshotBuffer()
        from custom_components.heima.runtime.state_store import CanonicalState

        engine._state = CanonicalState()
        engine._state.sensors = {"heima_reactions_active": 0}
        engine._state.sensor_attributes = {
            "heima_reactions_active": {"reactions": {}, "total": 0, "muted_total": 0}
        }
        from custom_components.heima.runtime.domains.events import EventsDomain

        engine._events_domain = EventsDomain(hass)

    return engine


# ---------------------------------------------------------------------------
# _sync_reactions_sensor
# ---------------------------------------------------------------------------


def test_sync_reactions_sensor_empty():
    engine = _make_engine()
    engine._sync_reactions_sensor()
    assert engine._state.get_sensor("heima_reactions_active") == 0
    assert engine._state.get_sensor_attributes("heima_reactions_active") == {
        "reactions": {},
        "total": 0,
        "muted_total": 0,
    }


def test_sync_reactions_sensor_shows_registered_reactions():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: not s.anyone_home,
        consecutive_n=2,
        steps=[_step()],
        reaction_id="eco_heating",
    )
    engine._reactions.append(r)
    engine._sync_reactions_sensor()
    assert engine._state.get_sensor("heima_reactions_active") == 1
    val = engine._state.get_sensor_attributes("heima_reactions_active")["reactions"]
    assert "eco_heating" in val
    assert val["eco_heating"]["muted"] is False
    assert val["eco_heating"]["fire_count"] == 0


def test_sync_reactions_sensor_shows_muted_true():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: not s.anyone_home,
        consecutive_n=1,
        steps=[_step()],
        reaction_id="my_reaction",
    )
    engine._reactions.append(r)
    engine._muted_reactions.add("my_reaction")
    engine._sync_reactions_sensor()
    val = engine._state.get_sensor_attributes("heima_reactions_active")["reactions"]
    assert val["my_reaction"]["muted"] is True
    assert engine._state.get_sensor_attributes("heima_reactions_active")["muted_total"] == 1


def test_sync_reactions_sensor_exposes_configured_reaction_provenance():
    engine = _make_engine()
    engine._entry.options = {
        "reactions": {
            "configured": {
                "my_reaction": {
                    "reaction_class": "LightingScheduleReaction",
                    "reaction_type": "lighting_scene_schedule",
                    "origin": "admin_authored",
                    "author_kind": "admin",
                    "source_request": "template:lighting.scene_schedule.basic",
                    "source_template_id": "lighting.scene_schedule.basic",
                    "source_proposal_id": "proposal-admin",
                    "source_proposal_identity_key": "lighting_scene_schedule|room=living|weekday=0|bucket=1200",
                    "created_at": "2026-03-30T10:00:00+00:00",
                    "last_tuned_at": None,
                }
            }
        }
    }
    r = ConsecutiveStateReaction(
        predicate=lambda s: True, consecutive_n=1, steps=[], reaction_id="my_reaction"
    )
    engine._reactions.append(r)

    engine._sync_reactions_sensor()
    val = engine._state.get_sensor_attributes("heima_reactions_active")["reactions"]
    assert val["my_reaction"]["origin"] == "admin_authored"
    assert val["my_reaction"]["author_kind"] == "admin"
    assert val["my_reaction"]["reaction_type"] == "lighting_scene_schedule"
    assert val["my_reaction"]["source_request"] == "template:lighting.scene_schedule.basic"
    assert val["my_reaction"]["source_template_id"] == "lighting.scene_schedule.basic"
    assert val["my_reaction"]["source_proposal_id"] == "proposal-admin"


def test_sync_reactions_sensor_keeps_state_compact_for_large_payload():
    engine = _make_engine()
    engine._entry.options = {
        "reactions": {
            "configured": {
                f"reaction_{index}": {
                    "reaction_class": "RoomLightingAssistReaction",
                    "reaction_type": "room_darkness_lighting_assist",
                    "origin": "admin_authored",
                    "author_kind": "admin",
                    "source_proposal_identity_key": (
                        f"room_darkness_lighting_assist|room=studio|primary=room_lux_{index}"
                    ),
                }
                for index in range(20)
            }
        }
    }
    for index in range(20):
        engine._reactions.append(
            ConsecutiveStateReaction(
                predicate=lambda s: True,
                consecutive_n=1,
                steps=[],
                reaction_id=f"reaction_{index}",
            )
        )

    engine._sync_reactions_sensor()

    state_value = engine._state.get_sensor("heima_reactions_active")
    attrs = engine._state.get_sensor_attributes("heima_reactions_active")

    assert state_value == 20
    assert isinstance(state_value, int)
    assert len(str(state_value)) < 255
    assert attrs is not None
    assert attrs["total"] == 20
    assert len(attrs["reactions"]) == 20


# ---------------------------------------------------------------------------
# mute_reaction / unmute_reaction
# ---------------------------------------------------------------------------


def test_mute_reaction_returns_true_for_known_reaction():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True, consecutive_n=1, steps=[], reaction_id="r1"
    )
    engine._reactions.append(r)
    assert engine.mute_reaction("r1") is True


def test_mute_reaction_returns_false_for_unknown():
    engine = _make_engine()
    assert engine.mute_reaction("nonexistent") is False


def test_mute_adds_to_muted_set():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True, consecutive_n=1, steps=[], reaction_id="r1"
    )
    engine._reactions.append(r)
    engine.mute_reaction("r1")
    assert "r1" in engine._muted_reactions


def test_unmute_reaction_returns_true_for_known_reaction():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True, consecutive_n=1, steps=[], reaction_id="r1"
    )
    engine._reactions.append(r)
    engine._muted_reactions.add("r1")
    assert engine.unmute_reaction("r1") is True


def test_unmute_removes_from_muted_set():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True, consecutive_n=1, steps=[], reaction_id="r1"
    )
    engine._reactions.append(r)
    engine._muted_reactions.add("r1")
    engine.unmute_reaction("r1")
    assert "r1" not in engine._muted_reactions


def test_unmute_reaction_returns_false_for_unknown():
    engine = _make_engine()
    assert engine.unmute_reaction("nonexistent") is False


def test_mute_reactions_by_type_returns_matching_ids():
    engine = _make_engine()
    engine._entry.options = {
        "reactions": {
            "configured": {
                "sec1": {"reaction_type": "vacation_presence_simulation"},
                "sec2": {"reaction_type": "vacation_presence_simulation"},
                "light1": {"reaction_type": "lighting_scene_schedule"},
            }
        }
    }
    for reaction_id in ("sec1", "sec2", "light1"):
        r = ConsecutiveStateReaction(
            predicate=lambda s: True, consecutive_n=1, steps=[], reaction_id=reaction_id
        )
        engine._reactions.append(r)

    matched = engine.mute_reactions_by_type("vacation_presence_simulation")

    assert matched == ["sec1", "sec2"]
    assert engine._muted_reactions == {"sec1", "sec2"}


def test_unmute_reactions_by_type_returns_matching_ids():
    engine = _make_engine()
    engine._entry.options = {
        "reactions": {
            "configured": {
                "sec1": {"reaction_type": "vacation_presence_simulation"},
                "sec2": {"reaction_type": "vacation_presence_simulation"},
                "light1": {"reaction_type": "lighting_scene_schedule"},
            }
        }
    }
    for reaction_id in ("sec1", "sec2", "light1"):
        r = ConsecutiveStateReaction(
            predicate=lambda s: True, consecutive_n=1, steps=[], reaction_id=reaction_id
        )
        engine._reactions.append(r)
    engine._muted_reactions = {"sec1", "sec2", "light1"}

    matched = engine.unmute_reactions_by_type("vacation_presence_simulation")

    assert matched == ["sec1", "sec2"]
    assert engine._muted_reactions == {"light1"}


# ---------------------------------------------------------------------------
# _dispatch_reactions — mute skipping
# ---------------------------------------------------------------------------


def test_dispatch_skips_muted_reaction():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True,
        consecutive_n=1,
        steps=[_step()],
        reaction_id="r1",
    )
    engine._reactions.append(r)
    engine._muted_reactions.add("r1")
    history = [_snap(False)]
    result = engine._dispatch_reactions(history)
    assert result == []


def test_dispatch_fires_unmuted_reaction():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True,
        consecutive_n=1,
        steps=[_step()],
        reaction_id="r1",
    )
    engine._reactions.append(r)
    history = [_snap(False)]
    result = engine._dispatch_reactions(history)
    assert len(result) == 1
    assert result[0].source == "reaction:r1"


def test_dispatch_tags_source_with_reaction_id():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True,
        consecutive_n=1,
        steps=[_step()],
        reaction_id="presence_preheat",
    )
    engine._reactions.append(r)
    result = engine._dispatch_reactions([_snap()])
    assert all(s.source == "reaction:presence_preheat" for s in result)


# ---------------------------------------------------------------------------
# reaction.fired event
# ---------------------------------------------------------------------------


def test_dispatch_queues_reaction_fired_event_when_steps_produced():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True,
        consecutive_n=1,
        steps=[_step()],
        reaction_id="r_fire",
    )
    engine._reactions.append(r)
    engine._dispatch_reactions([_snap()])
    queued = engine._events_domain._pending_events
    assert any(e.type == "reaction.fired" for e in queued)


def test_dispatch_does_not_queue_event_when_no_steps():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: False,  # never matches
        consecutive_n=1,
        steps=[_step()],
        reaction_id="r_no_fire",
    )
    engine._reactions.append(r)
    engine._dispatch_reactions([_snap()])
    queued = engine._events_domain._pending_events
    assert not any(e.type == "reaction.fired" for e in queued)


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------


def test_diagnostics_includes_muted_reactions():
    engine = _make_engine()
    # Patch minimal diagnostics dependencies
    engine._snapshot = DecisionSnapshot.empty()
    engine._active_constraints = set()
    from custom_components.heima.runtime.contracts import ApplyPlan

    engine._apply_plan = ApplyPlan.empty()
    engine._lighting_domain = MagicMock()
    engine._lighting_domain.diagnostics.return_value = {}
    engine._heating_domain = MagicMock()
    engine._heating_domain.diagnostics.return_value = {}
    engine._security_domain = MagicMock()
    engine._security_domain.diagnostics.return_value = {}
    engine._house_state_domain = MagicMock()
    engine._house_state_domain.diagnostics.return_value = {}
    engine._people_domain = MagicMock()
    engine._people_domain.diagnostics.return_value = {}
    engine._occupancy_domain = MagicMock()
    engine._occupancy_domain.diagnostics.return_value = {}
    engine._calendar_domain = MagicMock()
    engine._calendar_domain.diagnostics.return_value = {}
    engine._events_domain = MagicMock()
    engine._events_domain.diagnostics.return_value = {}
    engine._normalizer = MagicMock()
    engine._normalizer.diagnostics.return_value = {}

    engine._muted_reactions = {"r_muted"}
    diag = engine.diagnostics()
    assert "muted_reactions" in diag
    assert "r_muted" in diag["muted_reactions"]


# ---------------------------------------------------------------------------
# Persisted mute restoration from options (CF3)
# ---------------------------------------------------------------------------


def test_options_reload_restores_persisted_mute():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True, consecutive_n=1, steps=[], reaction_id="r1"
    )
    engine._reactions.append(r)

    # Simulate on_options_reloaded logic: engine reads options["reactions"]["muted"]
    options = {"reactions": {"muted": ["r1"]}}
    persisted_muted = set(options.get("reactions", {}).get("muted", []))
    known_ids = {rx.reaction_id for rx in engine._reactions}
    engine._muted_reactions = persisted_muted & known_ids

    assert "r1" in engine._muted_reactions


def test_options_reload_ignores_unknown_reaction_ids():
    engine = _make_engine()
    options = {"reactions": {"muted": ["nonexistent"]}}
    persisted_muted = set(options.get("reactions", {}).get("muted", []))
    known_ids = {rx.reaction_id for rx in engine._reactions}
    engine._muted_reactions = persisted_muted & known_ids

    assert len(engine._muted_reactions) == 0


def test_options_reload_clears_mute_when_not_in_options():
    engine = _make_engine()
    r = ConsecutiveStateReaction(
        predicate=lambda s: True, consecutive_n=1, steps=[], reaction_id="r1"
    )
    engine._reactions.append(r)
    engine._muted_reactions.add("r1")  # previously muted at runtime

    # Options without reactions key → muted cleared
    options: dict = {}
    persisted_muted = set(options.get("reactions", {}).get("muted", []))
    known_ids = {rx.reaction_id for rx in engine._reactions}
    engine._muted_reactions = persisted_muted & known_ids

    assert "r1" not in engine._muted_reactions
