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
        and item["supports_admin_authored"] is True
        and item["admin_authored_templates"][0]["template_id"]
        == "lighting.scene_schedule.basic"
        and item["admin_authored_templates"][0]["implemented"] is True
        for item in learning
    )
    assert any(item["reaction_class"] == "RoomSignalAssistReaction" for item in reactions)
    assert any(item["reaction_class"] == "RoomLightingAssistReaction" for item in reactions)


async def test_config_entry_diagnostics_exposes_heating_observed_provenance():
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {
            "heating": {
                "observed_source": "heima",
                "observed_provenance": {
                    "source": "reaction:heat_pref_test",
                    "origin_reaction_id": "heat_pref_test",
                    "origin_reaction_class": "HeatingPreferenceReaction",
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
        "origin_reaction_class": "HeatingPreferenceReaction",
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
                    "type": "lighting_scene_schedule",
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
    assert "lighting_scene_schedule" in lighting["proposal_types"]
    assert lighting["admin_authorable"] is True
    assert lighting["admin_authored_templates"] == ["lighting.scene_schedule.basic"]
    assert lighting["implemented_admin_authored_templates"] == ["lighting.scene_schedule.basic"]
    assert lighting["unimplemented_admin_authored_templates"] == []

    composite = summary["plugins"]["builtin.composite_room_assist"]
    assert composite["pending"] == 1
    assert composite["stale_pending"] == 1
    assert composite["supports_admin_authored"] is True
    assert composite["admin_authored_templates"] == [
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
    ]
    assert composite["implemented_admin_authored_templates"] == [
        "room.signal_assist.basic",
        "room.darkness_lighting_assist.basic",
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
        _state=SimpleNamespace(
            get_sensor=lambda key: (
                '{"r1":{"origin":"learned","author_kind":"heima"},'
                '"r2":{"origin":"admin_authored","author_kind":"admin",'
                '"source_template_id":"room.signal_assist.basic",'
                '"source_proposal_identity_key":"room_signal_assist|room=bathroom"}}'
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


async def test_config_entry_diagnostics_exposes_configured_reaction_identity_collisions() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=SimpleNamespace(
            get_sensor=lambda key: (
                '{"r1":{"origin":"admin_authored","author_kind":"admin",'
                '"source_template_id":"lighting.scene_schedule.basic",'
                '"source_proposal_identity_key":"lighting_scene_schedule|room=living|weekday=0|bucket=1200|scene=a"},'
                '"r2":{"origin":"learned","author_kind":"heima",'
                '"source_proposal_identity_key":"lighting_scene_schedule|room=living|weekday=0|bucket=1200|scene=b"}}'
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
    lighting = diagnostics["runtime"]["plugins"]["lighting_summary"]
    composite = diagnostics["runtime"]["plugins"]["composite_summary"]

    assert summary["identity_collisions"] == {}
    assert summary["lighting_slot_collisions"] == {
        "lighting_scene_schedule|room=living|weekday=0|bucket=1200": ["r1", "r2"]
    }
    assert lighting["configured_total"] == 2
    assert lighting["configured_by_room"] == {"living": 2}
    assert lighting["configured_by_slot"] == {
        "lighting_scene_schedule|room=living|weekday=0|bucket=1200": 2
    }
    assert lighting["slot_collisions"] == {
        "lighting_scene_schedule|room=living|weekday=0|bucket=1200": ["r1", "r2"]
    }


async def test_config_entry_diagnostics_exposes_exact_identity_collisions() -> None:
    coordinator = _CoordinatorStub()
    coordinator.engine = SimpleNamespace(
        diagnostics=lambda: {"engine": "ok"},
        _state=SimpleNamespace(
            get_sensor=lambda key: (
                '{"r1":{"origin":"admin_authored","author_kind":"admin",'
                '"source_template_id":"lighting.scene_schedule.basic",'
                '"source_proposal_identity_key":"lighting_scene_schedule|room=living|weekday=0|bucket=1200|scene=a"},'
                '"r2":{"origin":"learned","author_kind":"heima",'
                '"source_proposal_identity_key":"lighting_scene_schedule|room=living|weekday=0|bucket=1200|scene=a"}}'
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
    lighting = diagnostics["runtime"]["plugins"]["lighting_summary"]

    assert summary["identity_collisions"] == {
        "lighting_scene_schedule|room=living|weekday=0|bucket=1200|scene=a": ["r1", "r2"]
    }
    assert summary["lighting_slot_collisions"] == {
        "lighting_scene_schedule|room=living|weekday=0|bucket=1200": ["r1", "r2"]
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
        _state=SimpleNamespace(
            get_sensor=lambda key: (
                '{"sec1":{"reaction_class":"VacationPresenceSimulationReaction","reaction_type":"vacation_presence_simulation","allowed_rooms":["living"],"source_rooms":["living","kitchen"],"active_tonight":true,"operational_state":"ready_tonight","blocked_reason":"","tonight_plan_count":2,"next_planned_activation":"2026-04-04T20:30:00+02:00","source_profile_kind":"learned_source_profiles","selected_source_trace":[{"reaction_id":"src1","room_id":"living","selection_reason":"top_ranked_seed","score":203.0}]},'
                '"sec2":{"reaction_class":"VacationPresenceSimulationReaction","reaction_type":"vacation_presence_simulation","allowed_rooms":["studio"],"source_rooms":["studio"],"active_tonight":false,"operational_state":"waiting_for_darkness","blocked_reason":"outside_not_dark","tonight_plan_count":0,"source_profile_kind":"accepted_lighting_reactions","selected_source_trace":[{"reaction_id":"src2","room_id":"studio","selection_reason":"top_ranked_seed","score":140.0}]}}'
                if key == "heima_reactions_active"
                else None
            )
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(entry_id="entry-1", title="Heima", version=1, minor_version=0, options={})

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    summary = diagnostics["runtime"]["plugins"]["security_presence_summary"]

    assert summary["configured_total"] == 2
    assert summary["active_tonight_total"] == 1
    assert summary["blocked_total"] == 1
    assert summary["ready_tonight_total"] == 1
    assert summary["waiting_for_darkness_total"] == 1
    assert summary["insufficient_evidence_total"] == 0
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
    assert len(summary["waiting_for_darkness_examples"]) == 1
    assert summary["waiting_for_darkness_examples"][0]["operational_state"] == "waiting_for_darkness"
    assert summary["waiting_for_darkness_examples"][0]["selected_sources"][0]["room_id"] == "studio"
    assert summary["insufficient_evidence_examples"] == []


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
                    "type": "lighting_scene_schedule",
                    "status": "pending",
                    "confidence": 0.91,
                    "description": "Living tuned lights",
                    "origin": "learned",
                    "followup_kind": "discovery",
                    "identity_key": "lighting_scene_schedule|room=living|weekday=0|bucket=1200|scene=tuned",
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
                        "reaction_class": "LightingScheduleReaction",
                        "origin": "admin_authored",
                        "source_template_id": "lighting.scene_schedule.basic",
                        "source_proposal_identity_key": (
                            "lighting_scene_schedule|room=living|weekday=0|bucket=1200|scene=base"
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
            "slot_key": "lighting_scene_schedule|room=living|weekday=0|bucket=1200",
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
                        "primary_signal_name": "humidity",
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
        _state=SimpleNamespace(
            get_sensor=lambda key: (
                '{"r1":{"reaction_type":"room_signal_assist","reaction_class":"RoomSignalAssistReaction","room_id":"bathroom","primary_signal_name":"humidity"},'
                '"r2":{"reaction_class":"RoomLightingAssistReaction","source_proposal_identity_key":"room_darkness_lighting_assist|room=living|primary=room_lux"}}'
                if key == "heima_reactions_active"
                else None
            )
        ),
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": {"coordinator": coordinator}}})
    entry = SimpleNamespace(entry_id="entry-1", title="Heima", version=1, minor_version=0, options={})

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]
    composite = diagnostics["runtime"]["plugins"]["composite_summary"]

    assert composite["configured_total"] == 2
    assert composite["configured_by_room"] == {"bathroom": 1, "living": 1}
    assert composite["configured_by_type"] == {"room_signal_assist": 1}
    assert composite["configured_by_primary_signal"] == {"humidity": 1, "room_lux": 1}
    assert composite["pending_total"] == 2
    assert composite["pending_tuning_total"] == 1
    assert composite["pending_discovery_total"] == 1
    assert composite["pending_by_room"] == {"bathroom": 1, "living": 1}
    assert composite["pending_by_type"] == {
        "room_darkness_lighting_assist": 1,
        "room_signal_assist": 1,
    }
    assert composite["pending_by_primary_signal"] == {"humidity": 1, "room_lux": 1}
    assert composite["pending_tuning_examples"] == [
        {
            "id": "p1",
            "type": "room_signal_assist",
            "label": "Assist bathroom · humidity",
            "room_id": "bathroom",
            "primary_signal_name": "humidity",
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
