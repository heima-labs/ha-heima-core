"""Tests for config entry diagnostics plugin metadata."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.const import DOMAIN
from custom_components.heima.diagnostics import async_get_config_entry_diagnostics
from custom_components.heima.runtime.analyzers import create_builtin_learning_plugin_registry
from custom_components.heima.runtime.domains.calendar import CalendarEvent, CalendarResult


class _CoordinatorStub:
    def __init__(self) -> None:
        self.data = {"health": "ok"}
        self.engine = SimpleNamespace(diagnostics=lambda: {"engine": "ok"})
        self.scheduler = SimpleNamespace(diagnostics=lambda: {"scheduler": "ok"})
        self._event_store = SimpleNamespace(diagnostics=lambda: {"total_events": 1})
        self._proposal_engine = SimpleNamespace(diagnostics=lambda: {"total": 0})
        self.learning_plugin_registry = create_builtin_learning_plugin_registry()


def _reaction_state(payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        get_sensor=lambda key: len(payload) if key == "heima_reactions_active" else None,
        get_sensor_attributes=lambda key: (
            {
                "reactions": payload,
                "total": len(payload),
                "muted_total": sum(
                    1 for raw in payload.values() if isinstance(raw, dict) and raw.get("muted")
                ),
            }
            if key == "heima_reactions_active"
            else None
        ),
    )


async def test_config_entry_diagnostics_includes_learning_and_reaction_plugins():
    coordinator = _CoordinatorStub()
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    plugins = diagnostics["runtime"]["plugins"]

    learning = plugins["learning_pattern_plugins"]
    reactions = plugins["reaction_plugins"]

    assert any(item["plugin_id"] == "builtin.lighting_routines" for item in learning)
    assert any(item["plugin_id"] == "builtin.composite_room_assist" for item in learning)
    assert any(
        item["plugin_id"] == "builtin.lighting_routines"
        and item["supports_admin_authored"] is False
        and item["admin_authored_templates"] == []
        for item in learning
    )
    assert any(item["reaction_type"] == "room_signal_assist" for item in reactions)
    assert any(item["reaction_type"] == "room_darkness_lighting_assist" for item in reactions)
    assert any(item["reaction_type"] == "scheduled_routine" for item in reactions)


async def test_config_entry_diagnostics_exposes_canonical_signals_summary():
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {
            "behaviors": {
                "event_canonicalizer": {
                    "tracked_entities": {
                        "sensor.studio_temperature": {
                            "room_id": "studio",
                            "signal_name": "room_temperature",
                            "device_class": "temperature",
                            "buckets": [],
                            "burst_threshold": 1.5,
                        }
                    },
                    "bucket_state": {"studio:room_temperature": "warm"},
                    "burst_baseline": {
                        "studio:room_temperature": {
                            "value": 26.0,
                            "ts": "2026-04-13T10:00:00+00:00",
                        }
                    },
                    "last_burst_ts": {"studio:room_temperature": "2026-04-13T10:05:00+00:00"},
                }
            }
        }
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["canonical_signals_summary"]

    assert summary["tracked_signal_count"] == 1
    assert summary["tracked_signal_entities"] == ["sensor.studio_temperature"]
    assert summary["signals_with_burst"] == ["sensor.studio_temperature"]
    assert summary["signals_with_burst_count"] == 1
    assert summary["bucket_state"] == {"studio:room_temperature": "warm"}
    assert summary["last_burst_ts"] == {"studio:room_temperature": "2026-04-13T10:05:00+00:00"}


async def test_config_entry_diagnostics_exposes_heating_observed_provenance():
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {
            "heating": {
                "observed_source": "heima",
                "observed_provenance": {
                    "source": "reaction:heat_pref_test",
                    "origin_reaction_id": "heat_pref_test",
                    "origin_reaction_type": "heating_preference",
                    "expected_domains": ["climate"],
                    "expected_subject_ids": ["climate.test_thermostat"],
                },
            }
        }
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]

    assert diagnostics["runtime"]["engine"]["heating"]["observed_source"] == "heima"
    assert diagnostics["runtime"]["engine"]["heating"]["observed_provenance"] == {
        "source": "reaction:heat_pref_test",
        "origin_reaction_id": "heat_pref_test",
        "origin_reaction_type": "heating_preference",
        "expected_domains": ["climate"],
        "expected_subject_ids": ["climate.test_thermostat"],
    }


async def test_config_entry_diagnostics_exposes_learning_summary() -> None:
    coordinator = _CoordinatorStub()
    coordinator._proposal_engine = SimpleNamespace(
        diagnostics=lambda: {
            "total": 3,
            "pending": 2,
            "pending_stale": 1,
            "proposals": [
                {
                    "id": "p1",
                    "type": "context_conditioned_lighting_scene",
                    "status": "pending",
                    "confidence": 0.95,
                    "description": "Living lights",
                    "is_stale": False,
                    "updated_at": "2026-03-26T10:00:00+00:00",
                },
                {
                    "id": "p2",
                    "type": "room_signal_assist",
                    "status": "pending",
                    "confidence": 0.85,
                    "description": "Bathroom assist",
                    "is_stale": True,
                    "updated_at": "2026-03-26T09:00:00+00:00",
                },
                {
                    "id": "p3",
                    "type": "heating_preference",
                    "status": "accepted",
                    "confidence": 0.75,
                    "description": "Heating home",
                    "is_stale": False,
                    "updated_at": "2026-03-26T08:00:00+00:00",
                },
            ],
        }
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["learning_summary"]

    assert summary["plugin_count"] >= 4
    assert summary["family_count"] >= 4
    assert summary["proposal_total"] == 3
    assert summary["pending_total"] == 2
    assert summary["pending_stale_total"] == 1
    assert summary["config_source"] == "learning.enabled_plugin_families"
    assert "lighting" in summary["enabled_plugin_families"]
    assert summary["disabled_plugin_families"] == []

    lighting = summary["families"]["lighting"]
    assert lighting["pending"] == 1
    assert "context_conditioned_lighting_scene" in lighting["proposal_types"]
    assert "lighting_scene_schedule" not in lighting["proposal_types"]
    assert lighting["admin_authorable"] is False
    assert lighting["admin_authored_templates"] == []
    assert lighting["implemented_admin_authored_templates"] == []
    assert lighting["unimplemented_admin_authored_templates"] == []

    composite = summary["plugins"]["builtin.composite_room_assist"]
    assert composite["pending"] == 1
    assert composite["stale_pending"] == 1
    assert composite["supports_admin_authored"] is True
    assert composite["admin_authored_templates"] == [
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
        "room.contextual_lighting_assist.basic",
        "room.vacancy_lighting_off.basic",
    ]
    assert composite["implemented_admin_authored_templates"] == [
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
        "room.contextual_lighting_assist.basic",
        "room.vacancy_lighting_off.basic",
    ]
    assert composite["unimplemented_admin_authored_templates"] == []

    heating = summary["plugins"]["builtin.heating_preferences"]
    assert heating["accepted"] == 1
    assert heating["supports_admin_authored"] is False


async def test_config_entry_diagnostics_exposes_disabled_learning_families() -> None:
    coordinator = _CoordinatorStub()
    coordinator.learning_plugin_registry = create_builtin_learning_plugin_registry(
        enabled_families={"presence", "lighting"}
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["learning_summary"]

    assert summary["enabled_plugin_families"] == ["lighting", "presence"]
    assert summary["disabled_plugin_families"] == [
        "composite_room_assist",
        "heating",
        "security_presence_simulation",
    ]


async def test_config_entry_diagnostics_exposes_configured_reaction_summary() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=_reaction_state(
            {
                "r1": {"origin": "learned", "author_kind": "heima"},
                "r2": {
                    "origin": "admin_authored",
                    "author_kind": "admin",
                    "source_template_id": "room.signal_assist.basic",
                    "source_proposal_identity_key": "room_signal_assist|room=bathroom",
                },
            }
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["configured_reaction_summary"]
    lighting = diagnostics["runtime"]["plugins"]["lighting_summary"]
    composite = diagnostics["runtime"]["plugins"]["composite_summary"]

    assert summary["total"] == 2
    assert summary["by_origin"] == {"admin_authored": 1, "learned": 1}
    assert summary["by_author_kind"] == {"admin": 1, "heima": 1}
    assert summary["by_template_id"] == {
        "room.signal_assist.basic": 1,
        "unspecified": 1,
    }
    assert summary["identity_collisions"] == {}
    assert summary["lighting_slot_collisions"] == {}
    assert summary["reaction_ids"] == ["r1", "r2"]
    assert lighting == {
        "configured_total": 0,
        "configured_by_room": {},
        "configured_by_slot": {},
        "pending_total": 0,
        "pending_tuning_total": 0,
        "pending_discovery_total": 0,
        "pending_by_room": {},
        "pending_tuning_examples": [],
        "pending_discovery_examples": [],
        "slot_collisions": {},
    }
    assert composite == {
        "configured_total": 1,
        "configured_by_room": {"bathroom": 1},
        "configured_by_type": {},
        "configured_by_primary_signal": {},
        "pending_total": 0,
        "pending_tuning_total": 0,
        "pending_discovery_total": 0,
        "pending_by_room": {},
        "pending_by_type": {},
        "pending_by_primary_signal": {},
        "pending_tuning_examples": [],
        "pending_discovery_examples": [],
    }


async def test_config_entry_diagnostics_supports_legacy_reaction_sensor_state_json() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=SimpleNamespace(
            get_sensor=lambda key: (
                '{"r1":{"origin":"learned","author_kind":"heima"}}'
                if key == "heima_reactions_active"
                else None
            )
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["configured_reaction_summary"]

    assert summary["total"] == 1
    assert summary["by_origin"] == {"learned": 1}
    assert summary["reaction_ids"] == ["r1"]


async def test_config_entry_diagnostics_exposes_configured_reaction_identity_collisions() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=_reaction_state(
            {
                "r1": {
                    "origin": "admin_authored",
                    "author_kind": "admin",
                    "source_template_id": "lighting.scene_schedule.basic",
                    "source_proposal_identity_key": (
                        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200|scene=a"
                    ),
                },
                "r2": {
                    "origin": "learned",
                    "author_kind": "heima",
                    "source_proposal_identity_key": (
                        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200|scene=b"
                    ),
                },
            }
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["configured_reaction_summary"]
    lighting = diagnostics["runtime"]["plugins"]["lighting_summary"]
    composite = diagnostics["runtime"]["plugins"]["composite_summary"]

    assert summary["identity_collisions"] == {}
    assert summary["lighting_slot_collisions"] == {
        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200": ["r1", "r2"]
    }
    assert lighting["configured_total"] == 2
    assert lighting["configured_by_room"] == {"living": 2}
    assert lighting["configured_by_slot"] == {
        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200": 2
    }
    assert lighting["slot_collisions"] == {
        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200": ["r1", "r2"]
    }


async def test_config_entry_diagnostics_exposes_exact_identity_collisions() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=_reaction_state(
            {
                "r1": {
                    "origin": "admin_authored",
                    "author_kind": "admin",
                    "source_template_id": "lighting.scene_schedule.basic",
                    "source_proposal_identity_key": (
                        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200|scene=a"
                    ),
                },
                "r2": {
                    "origin": "learned",
                    "author_kind": "heima",
                    "source_proposal_identity_key": (
                        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200|scene=a"
                    ),
                },
            }
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["configured_reaction_summary"]
    lighting = diagnostics["runtime"]["plugins"]["lighting_summary"]

    assert summary["identity_collisions"] == {
        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200|scene=a": ["r1", "r2"]
    }
    assert summary["lighting_slot_collisions"] == {
        "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200": ["r1", "r2"]
    }
    assert lighting["configured_total"] == 2


async def test_config_entry_diagnostics_exposes_calendar_summary() -> None:
    coordinator = _CoordinatorStub()
    next_vacation = CalendarEvent(
        summary="Ferie agosto",
        start=SimpleNamespace(isoformat=lambda: "2026-08-10T00:00:00+00:00"),
        end=SimpleNamespace(isoformat=lambda: "2026-08-20T00:00:00+00:00"),
        all_day=True,
        category="vacation",
        calendar_entity="calendar.personal",
    )
    coordinator._entry = SimpleNamespace(
        options={
            "calendar": {
                "calendar_entities": ["calendar.personal", "calendar.work"],
            }
        }
    )
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {
            "calendar": {
                "cache_ts": "2026-04-03T10:00:00+00:00",
                "cached_events_count": 4,
            }
        },
        _state=SimpleNamespace(
            get_sensor=lambda _key: None,
            calendar_result=CalendarResult(
                current_events=[object()],
                upcoming_events=[object(), object(), object(), object()],
                is_vacation_active=False,
                is_wfh_today=True,
                is_office_today=False,
                next_vacation=next_vacation,
            ),
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["calendar_summary"]

    assert summary == {
        "configured_entities": ["calendar.personal", "calendar.work"],
        "current_events_count": 1,
        "upcoming_events_count": 4,
        "cache_ts": "2026-04-03T10:00:00+00:00",
        "cached_events_count": 4,
        "is_vacation_active": False,
        "is_wfh_today": True,
        "is_office_today": False,
        "next_vacation": {
            "summary": "Ferie agosto",
            "start": "2026-08-10T00:00:00+00:00",
            "calendar_entity": "calendar.personal",
        },
    }


async def test_config_entry_diagnostics_exposes_house_state_summary() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {
            "house_state": {
                "resolution_trace": {
                    "resolution_path": "home_substate",
                    "winning_reason": "work_candidate_confirmed",
                    "sticky_retention": False,
                    "active_candidates": ["work_candidate", "wake_candidate"],
                    "decision": {
                        "action": "pending",
                        "source_candidate": "work_candidate",
                        "pending_remaining_s": 42.0,
                    },
                }
            }
        },
        _state=SimpleNamespace(
            get_sensor=lambda key: (
                "working"
                if key == "heima_house_state"
                else "work_candidate_confirmed"
                if key == "heima_house_state_reason"
                else None
            ),
            calendar_result=CalendarResult(
                is_vacation_active=False,
                is_wfh_today=True,
                is_office_today=False,
            ),
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["house_state_summary"]

    assert summary == {
        "state": "working",
        "reason": "work_candidate_confirmed",
        "resolution_path": "home_substate",
        "winning_reason": "work_candidate_confirmed",
        "sticky_retention": False,
        "active_candidates": ["work_candidate", "wake_candidate"],
        "pending_candidate": "work_candidate",
        "pending_remaining_s": 42.0,
        "calendar_context": {
            "is_vacation_active": False,
            "is_wfh_today": True,
            "is_office_today": False,
        },
    }


async def test_config_entry_diagnostics_exposes_security_presence_summary() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=_reaction_state(
            {
                "sec1": {
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "reaction_type": "vacation_presence_simulation",
                    "allowed_rooms": ["living"],
                    "source_rooms": ["living", "kitchen"],
                    "active_tonight": True,
                    "operational_state": "ready_tonight",
                    "blocked_reason": "",
                    "tonight_plan_count": 2,
                    "next_planned_activation": "2026-04-04T20:30:00+02:00",
                    "source_profile_kind": "learned_source_profiles",
                    "selected_source_trace": [
                        {
                            "reaction_id": "src1",
                            "room_id": "living",
                            "selection_reason": "top_ranked_seed",
                            "score": 203.0,
                        }
                    ],
                    "excluded_source_trace": [
                        {
                            "reaction_id": "src3",
                            "room_id": "kitchen",
                            "exclusion_reason": "not_selected_within_budget",
                            "score": 150.0,
                        }
                    ],
                    "tonight_plan_preview": [
                        {
                            "room_id": "living",
                            "due_local": "2026-04-04T20:30:00+02:00",
                            "jitter_min": 0,
                            "selection_reason": "top_ranked_seed",
                        }
                    ],
                },
                "sec2": {
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "reaction_type": "vacation_presence_simulation",
                    "allowed_rooms": ["studio"],
                    "source_rooms": ["studio"],
                    "active_tonight": False,
                    "operational_state": "waiting_for_darkness",
                    "blocked_reason": "outside_not_dark",
                    "tonight_plan_count": 0,
                    "source_profile_kind": "accepted_lighting_reactions",
                    "selected_source_trace": [
                        {
                            "reaction_id": "src2",
                            "room_id": "studio",
                            "selection_reason": "top_ranked_seed",
                            "score": 140.0,
                        }
                    ],
                    "excluded_source_trace": [
                        {
                            "reaction_id": "src4",
                            "room_id": "studio",
                            "exclusion_reason": "outside_not_dark",
                            "score": 120.0,
                        }
                    ],
                },
            }
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1", title="Heima", version=1, minor_version=0, options={}
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["security_presence_summary"]

    assert summary["configured_total"] == 2
    assert summary["active_tonight_total"] == 1
    assert summary["blocked_total"] == 1
    assert summary["ready_tonight_total"] == 1
    assert summary["waiting_for_darkness_total"] == 1
    assert summary["insufficient_evidence_total"] == 0
    assert summary["muted_total"] == 0
    assert summary["configured_by_room"] == {"living": 1, "studio": 1}
    assert summary["source_room_counts"] == {"kitchen": 1, "living": 1, "studio": 1}
    assert summary["blocked_by_class"] == {"context_block": 1}
    assert summary["blocked_by_reason"] == {"outside_not_dark": 1}
    assert summary["operational_state_counts"] == {
        "ready_tonight": 1,
        "waiting_for_darkness": 1,
    }
    assert summary["source_profile_kind_counts"] == {
        "accepted_lighting_reactions": 1,
        "learned_source_profiles": 1,
    }
    assert len(summary["examples"]) == 2
    assert summary["examples"][0]["operational_state"] == "ready_tonight"
    assert len(summary["ready_examples"]) == 1
    assert summary["ready_examples"][0]["operational_state"] == "ready_tonight"
    assert summary["ready_examples"][0]["selected_sources"][0]["room_id"] == "living"
    assert summary["ready_examples"][0]["tonight_plan_preview"][0]["room_id"] == "living"
    assert summary["ready_examples"][0]["excluded_sources"][0]["room_id"] == "kitchen"
    assert len(summary["waiting_for_darkness_examples"]) == 1
    assert (
        summary["waiting_for_darkness_examples"][0]["operational_state"] == "waiting_for_darkness"
    )
    assert summary["waiting_for_darkness_examples"][0]["selected_sources"][0]["room_id"] == "studio"
    assert summary["waiting_for_darkness_examples"][0]["excluded_sources"][0]["room_id"] == "studio"
    assert summary["insufficient_evidence_examples"] == []


async def test_config_entry_diagnostics_exposes_muted_security_presence_summary() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=_reaction_state(
            {
                "sec-muted": {
                    "reaction_class": "VacationPresenceSimulationReaction",
                    "reaction_type": "vacation_presence_simulation",
                    "allowed_rooms": ["living"],
                    "source_rooms": ["living"],
                    "active_tonight": False,
                    "muted": True,
                    "blocked_reason": "",
                    "tonight_plan_count": 1,
                    "source_profile_kind": "learned_source_profiles",
                    "selected_source_trace": [
                        {
                            "reaction_id": "src1",
                            "room_id": "living",
                            "selection_reason": "top_ranked_seed",
                            "score": 203.0,
                        }
                    ],
                }
            }
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1", title="Heima", version=1, minor_version=0, options={}
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["security_presence_summary"]

    assert summary["configured_total"] == 1
    assert summary["muted_total"] == 1
    assert summary["operational_state_counts"] == {"muted": 1}
    assert summary["examples"][0]["muted"] is True
    assert summary["examples"][0]["operational_state"] == "muted"


async def test_config_entry_diagnostics_exposes_security_camera_evidence_summary() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {
            "security_camera_evidence": {
                "configured_sources": [
                    {
                        "id": "front_door_cam",
                        "display_name": "Front Door",
                        "role": "entry",
                        "status": "active",
                        "active_kinds": ["person"],
                        "unavailable_kinds": [],
                        "contact_active": False,
                        "last_seen_ts": "2026-04-07T20:10:00+00:00",
                    },
                    {
                        "id": "garage_cam",
                        "display_name": "Garage",
                        "role": "garage",
                        "status": "partial",
                        "active_kinds": ["vehicle"],
                        "unavailable_kinds": ["person"],
                        "contact_active": True,
                        "last_seen_ts": "2026-04-07T20:12:00+00:00",
                    },
                ],
                "active_evidence": [
                    {"source_id": "front_door_cam", "role": "entry", "kind": "person"},
                    {"source_id": "garage_cam", "role": "garage", "kind": "vehicle"},
                ],
                "unavailable_sources": [
                    {"source_id": "garage_cam", "role": "garage", "kind": "person"}
                ],
                "source_status_counts": {"active": 1, "partial": 1},
            },
            "security": {
                "camera_evidence_trace": {
                    "return_home_hint": True,
                    "return_home_hint_reasons": [
                        {
                            "source_id": "front_door_cam",
                            "role": "entry",
                            "reason": "entry_person_detected",
                            "contact_active": False,
                        }
                    ],
                    "breach_candidates": [
                        {
                            "rule": "armed_away_entry_person",
                            "severity": "suspicious",
                            "source_id": "front_door_cam",
                            "role": "entry",
                            "evidence_kinds": ["person"],
                            "contact_active": False,
                            "reason": "entry_person_detected_while_armed_away",
                        }
                    ],
                }
            },
        },
        _state=SimpleNamespace(get_sensor=lambda key: None),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1", title="Heima", version=1, minor_version=0, options={}
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["security_camera_evidence_summary"]

    assert summary["configured_total"] == 2
    assert summary["active_evidence_total"] == 2
    assert summary["unavailable_total"] == 1
    assert summary["breach_candidate_total"] == 1
    assert summary["return_home_hint_active"] is True
    assert summary["configured_by_role"] == {"entry": 1, "garage": 1}
    assert summary["active_by_role"] == {"entry": 1, "garage": 1}
    assert summary["active_by_kind"] == {"person": 1, "vehicle": 1}
    assert summary["source_status_counts"] == {"active": 1, "partial": 1}
    assert summary["breach_by_rule"] == {"armed_away_entry_person": 1}
    assert summary["examples"][0]["source_id"] == "front_door_cam"
    assert summary["breach_candidates"][0]["source_id"] == "front_door_cam"
    assert summary["return_home_hint_reasons"][0]["reason"] == "entry_person_detected"


async def test_config_entry_diagnostics_marks_tuning_followups_for_matching_identity() -> None:
    coordinator = _CoordinatorStub()
    coordinator._proposal_engine = SimpleNamespace(
        diagnostics=lambda: {
            "total": 1,
            "pending": 1,
            "pending_stale": 0,
            "proposals": [
                {
                    "id": "p1",
                    "type": "context_conditioned_lighting_scene",
                    "status": "pending",
                    "confidence": 0.91,
                    "description": "Living tuned lights",
                    "origin": "learned",
                    "followup_kind": "discovery",
                    "identity_key": "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200|scene=tuned",
                    "is_stale": False,
                    "updated_at": "2026-03-30T12:00:00+00:00",
                }
            ],
        }
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={
            "reactions": {
                "configured": {
                    "r-existing": {
                        "reaction_class": "ContextConditionedLightingReaction",
                        "origin": "admin_authored",
                        "source_template_id": "lighting.scene_schedule.basic",
                        "source_proposal_identity_key": (
                            "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200|scene=base"
                        ),
                    }
                }
            }
        },
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    proposals = diagnostics["runtime"]["proposals"]
    lighting = diagnostics["runtime"]["plugins"]["lighting_summary"]
    composite = diagnostics["runtime"]["plugins"]["composite_summary"]

    assert proposals["tuning_pending"] == 1
    item = proposals["proposals"][0]
    assert item["followup_kind"] == "tuning_suggestion"
    assert item["target_reaction_id"] == "r-existing"
    assert item["target_reaction_origin"] == "admin_authored"
    assert item["target_template_id"] == "lighting.scene_schedule.basic"
    assert lighting["pending_total"] == 1
    assert lighting["pending_tuning_total"] == 1
    assert lighting["pending_discovery_total"] == 0
    assert lighting["pending_by_room"] == {}
    assert lighting["pending_tuning_examples"] == [
        {
            "id": "p1",
            "label": "Living tuned lights",
            "room_id": "",
            "slot_key": "context_conditioned_lighting_scene|room=living|weekday=0|bucket=1200",
            "confidence": 0.91,
        }
    ]
    assert lighting["pending_discovery_examples"] == []
    assert composite == {
        "configured_total": 0,
        "configured_by_room": {},
        "configured_by_type": {},
        "configured_by_primary_signal": {},
        "pending_total": 0,
        "pending_tuning_total": 0,
        "pending_discovery_total": 0,
        "pending_by_room": {},
        "pending_by_type": {},
        "pending_by_primary_signal": {},
        "pending_tuning_examples": [],
        "pending_discovery_examples": [],
    }


async def test_config_entry_diagnostics_exposes_composite_summary_examples() -> None:
    coordinator = _CoordinatorStub()
    coordinator._proposal_engine = SimpleNamespace(
        diagnostics=lambda: {
            "total": 2,
            "pending": 2,
            "pending_stale": 0,
            "proposals": [
                {
                    "id": "p1",
                    "type": "room_signal_assist",
                    "status": "pending",
                    "confidence": 0.88,
                    "description": "Bathroom humidity assist",
                    "origin": "learned",
                    "followup_kind": "tuning_suggestion",
                    "config_summary": {
                        "room_id": "bathroom",
                        "primary_signal_name": "room_humidity",
                    },
                },
                {
                    "id": "p2",
                    "type": "room_darkness_lighting_assist",
                    "status": "pending",
                    "confidence": 0.83,
                    "description": "Living darkness lighting assist",
                    "origin": "learned",
                    "followup_kind": "discovery",
                    "config_summary": {
                        "room_id": "living",
                        "primary_signal_name": "room_lux",
                    },
                },
            ],
        }
    )
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=_reaction_state(
            {
                "r1": {
                    "reaction_type": "room_signal_assist",
                    "reaction_class": "RoomSignalAssistReaction",
                    "room_id": "bathroom",
                    "primary_signal_name": "room_humidity",
                },
                "r2": {
                    "reaction_class": "RoomLightingAssistReaction",
                    "source_proposal_identity_key": (
                        "room_darkness_lighting_assist|room=living|primary=room_lux"
                    ),
                },
            }
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1", title="Heima", version=1, minor_version=0, options={}
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    composite = diagnostics["runtime"]["plugins"]["composite_summary"]

    assert composite["configured_total"] == 2
    assert composite["configured_by_room"] == {"bathroom": 1, "living": 1}
    assert composite["configured_by_type"] == {
        "room_darkness_lighting_assist": 1,
        "room_signal_assist": 1,
    }
    assert composite["configured_by_primary_signal"] == {"room_humidity": 1, "room_lux": 1}
    assert composite["pending_total"] == 2
    assert composite["pending_tuning_total"] == 1
    assert composite["pending_discovery_total"] == 1
    assert composite["pending_by_room"] == {"bathroom": 1, "living": 1}
    assert composite["pending_by_type"] == {
        "room_darkness_lighting_assist": 1,
        "room_signal_assist": 1,
    }
    assert composite["pending_by_primary_signal"] == {"room_humidity": 1, "room_lux": 1}
    assert composite["pending_tuning_examples"] == [
        {
            "id": "p1",
            "type": "room_signal_assist",
            "label": "Assist bathroom · humidity",
            "room_id": "bathroom",
            "primary_signal_name": "room_humidity",
            "confidence": 0.88,
        }
    ]
    assert composite["pending_discovery_examples"] == [
        {
            "id": "p2",
            "type": "room_darkness_lighting_assist",
            "label": "Luci living · room_lux",
            "room_id": "living",
            "primary_signal_name": "room_lux",
            "confidence": 0.83,
        }
    ]


async def test_config_entry_diagnostics_exposes_ha_backed_room_inventory_summary(
    monkeypatch,
) -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=SimpleNamespace(get_sensor=lambda _key: None),
    )
    coordinator._proposal_engine = SimpleNamespace(
        diagnostics=lambda: {"total": 0, "pending": 0, "pending_stale": 0, "proposals": []}
    )
    entity_registry = SimpleNamespace(
        entities={
            "e1": SimpleNamespace(
                entity_id="binary_sensor.studio_motion", area_id="studio", device_id=None
            ),
            "e2": SimpleNamespace(entity_id="sensor.studio_lux", area_id="studio", device_id=None),
            "e3": SimpleNamespace(entity_id="light.studio_main", area_id="", device_id="device-1"),
        }
    )
    device_registry = SimpleNamespace(devices={"device-1": SimpleNamespace(area_id="studio")})
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get",
        lambda _hass: entity_registry,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get",
        lambda _hass: device_registry,
    )

    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Heima",
        version=1,
        minor_version=0,
        options={
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "area_id": "studio",
                    "occupancy_sources": ["binary_sensor.studio_motion"],
                    "learning_sources": [],
                }
            ]
        },
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["ha_backed_room_inventory_summary"]

    assert summary["total_rooms"] == 1
    room = summary["rooms"][0]
    assert room["room_id"] == "studio"
    assert room["inventory_entity_total"] == 3
    assert room["suggested_occupancy_sources"] == ["binary_sensor.studio_motion"]
    assert room["suggested_learning_sources"] == ["sensor.studio_lux"]
    assert room["suggested_lighting_entities"] == ["light.studio_main"]
