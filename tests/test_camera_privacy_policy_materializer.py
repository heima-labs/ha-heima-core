"""Tests for camera privacy policy materialization."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.heima.config_flow._camera_privacy_policy import (
    CAMERA_PRIVACY_POLICY_TYPE,
    CameraPrivacyPolicyRow,
    apply_camera_privacy_policy_rows_to_options,
    materialize_camera_privacy_policy_row,
    parse_camera_privacy_policy_rows_from_options,
)
from custom_components.heima.runtime.contracts import ApplyPlan
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.manual_hold import ManualHoldManager
from custom_components.heima.runtime.reactions import create_builtin_reaction_plugin_registry
from custom_components.heima.runtime.reactions.alarm_policy import AlarmStateActionReaction
from custom_components.heima.runtime.snapshot import DecisionSnapshot


def _make_engine(options: dict | None = None) -> HeimaEngine:
    hass = MagicMock()
    hass.states.get.return_value = None
    entry = MagicMock()
    entry.options = options or {}
    entry.entry_id = "test_entry"

    engine = HeimaEngine.__new__(HeimaEngine)
    engine._hass = hass
    engine._entry = entry
    engine._reactions = []
    engine._muted_reactions = set()
    engine._configured_reaction_ids = set()
    engine._reaction_plugin_registry = create_builtin_reaction_plugin_registry()
    engine._events_domain = MagicMock()
    return engine


def test_materialize_camera_privacy_policy_row_generates_alarm_state_action_config() -> None:
    materialized = materialize_camera_privacy_policy_row(
        CameraPrivacyPolicyRow(
            camera_source_id="interna",
            camera_display_name="Corridoio",
            privacy_entity="switch.interna_privacy",
            alarm_states=("armed_night",),
            house_filter_mode="except",
            house_states=("guest",),
            privacy_action="turn_off",
            enabled=False,
        )
    )

    assert materialized.reaction_id == (
        "camera_privacy_policy__interna__armed_night__except_guest__turn_off"
    )
    assert materialized.label == "Corridoio privacy: off when alarm is armed_night except guest"
    assert materialized.config == {
        "reaction_type": "alarm_state_action",
        "enabled": False,
        "origin": "admin_authored",
        "author_kind": "admin",
        "admin_authored_template_id": CAMERA_PRIVACY_POLICY_TYPE,
        "source_template_id": CAMERA_PRIVACY_POLICY_TYPE,
        "source_request": f"template:{CAMERA_PRIVACY_POLICY_TYPE}",
        "alarm_states": ["armed_night"],
        "steps": [
            {
                "domain": "switch",
                "target": "switch.interna_privacy",
                "action": "switch.turn_off",
                "params": {"entity_id": "switch.interna_privacy"},
            }
        ],
        "skip_house_states": ["guest"],
        "only_house_states": [],
        "camera_privacy_policy": {
            "camera_source_id": "interna",
            "privacy_entity": "switch.interna_privacy",
            "house_filter_mode": "except",
            "house_states": ["guest"],
            "privacy_action": "turn_off",
        },
    }


def test_materialize_camera_privacy_policy_row_maps_only_filter_and_enabled_default() -> None:
    materialized = materialize_camera_privacy_policy_row(
        CameraPrivacyPolicyRow(
            camera_source_id="interna",
            privacy_entity="switch.interna_privacy",
            alarm_states=("disarmed", "armed_away"),
            house_filter_mode="only",
            house_states=("home", "guest"),
            privacy_action="turn_on",
        )
    )

    assert materialized.config["enabled"] is True
    assert materialized.config["alarm_states"] == ["disarmed", "armed_away"]
    assert materialized.config["only_house_states"] == ["home", "guest"]
    assert materialized.config["skip_house_states"] == []
    assert materialized.config["steps"][0]["action"] == "switch.turn_on"


def test_apply_camera_privacy_policy_rows_preserves_unrelated_options_and_reactions() -> None:
    old_policy = materialize_camera_privacy_policy_row(
        CameraPrivacyPolicyRow(
            camera_source_id="interna",
            privacy_entity="switch.interna_privacy",
            alarm_states=("disarmed",),
            privacy_action="turn_on",
        )
    )
    options = {
        "security": {
            "camera_evidence_sources": [
                {
                    "id": "interna",
                    "role": "interior",
                    "privacy_entity": "switch.interna_privacy",
                    "manual_hold_entity": "input_boolean.corridoio_privacy_hold",
                    "motion_entity": "binary_sensor.interna_motion",
                }
            ]
        },
        "reactions": {
            "configured": {
                old_policy.reaction_id: old_policy.config,
                "unrelated": {
                    "reaction_type": "scheduled_routine",
                    "weekday": 1,
                },
            },
            "labels": {
                old_policy.reaction_id: "Old camera policy",
                "unrelated": "Unrelated",
            },
            "muted": ["unrelated", old_policy.reaction_id],
        },
    }

    updated = apply_camera_privacy_policy_rows_to_options(
        options,
        [
            CameraPrivacyPolicyRow(
                camera_source_id="interna",
                camera_display_name="Corridoio",
                privacy_entity="switch.interna_privacy",
                alarm_states=("armed_away",),
                privacy_action="turn_off",
            )
        ],
        replace_managed_reaction_ids={old_policy.reaction_id},
    )

    assert updated["security"] == options["security"]
    assert old_policy.reaction_id not in updated["reactions"]["configured"]
    assert old_policy.reaction_id not in updated["reactions"]["labels"]
    assert updated["reactions"]["configured"]["unrelated"] == {
        "reaction_type": "scheduled_routine",
        "weekday": 1,
    }
    assert updated["reactions"]["labels"]["unrelated"] == "Unrelated"
    assert updated["reactions"]["muted"] == ["unrelated"]
    new_id = "camera_privacy_policy__interna__armed_away__any__turn_off"
    assert new_id in updated["reactions"]["configured"]
    assert updated["reactions"]["labels"][new_id] == (
        "Corridoio privacy: off when alarm is armed_away"
    )


def test_apply_camera_privacy_policy_rows_preserves_unparseable_managed_policy() -> None:
    parseable_policy = materialize_camera_privacy_policy_row(
        CameraPrivacyPolicyRow(
            camera_source_id="interna",
            privacy_entity="switch.interna_privacy",
            alarm_states=("disarmed",),
            privacy_action="turn_on",
        )
    )
    stale_policy = {
        "reaction_type": "alarm_state_action",
        "source_template_id": CAMERA_PRIVACY_POLICY_TYPE,
        "camera_privacy_policy": {
            "camera_source_id": "missing_camera",
            "privacy_entity": "switch.missing_privacy",
            "privacy_action": "turn_on",
        },
        "alarm_states": ["disarmed"],
        "steps": [
            {
                "domain": "switch",
                "target": "switch.missing_privacy",
                "action": "switch.turn_on",
                "params": {"entity_id": "switch.missing_privacy"},
            }
        ],
    }
    options = {
        "security": {
            "camera_evidence_sources": [
                {
                    "id": "interna",
                    "role": "interior",
                    "privacy_entity": "switch.interna_privacy",
                }
            ]
        },
        "reactions": {
            "configured": {
                parseable_policy.reaction_id: parseable_policy.config,
                "stale-camera-policy": stale_policy,
            },
            "labels": {
                parseable_policy.reaction_id: "Old parseable",
                "stale-camera-policy": "Stale camera policy",
            },
            "muted": ["stale-camera-policy"],
        },
    }

    updated = apply_camera_privacy_policy_rows_to_options(
        options,
        [
            CameraPrivacyPolicyRow(
                camera_source_id="interna",
                privacy_entity="switch.interna_privacy",
                alarm_states=("armed_away",),
                privacy_action="turn_off",
            )
        ],
        replace_managed_reaction_ids={parseable_policy.reaction_id},
    )

    assert updated["reactions"]["configured"]["stale-camera-policy"] == stale_policy
    assert updated["reactions"]["labels"]["stale-camera-policy"] == "Stale camera policy"
    assert updated["reactions"]["muted"] == ["stale-camera-policy"]


def test_materialize_camera_privacy_policy_row_uses_deterministic_suffix_on_conflict() -> None:
    row = CameraPrivacyPolicyRow(
        camera_source_id="interna",
        privacy_entity="switch.interna_privacy",
        alarm_states=("armed_away",),
        privacy_action="turn_off",
    )
    base = materialize_camera_privacy_policy_row(row)
    conflicted = materialize_camera_privacy_policy_row(
        row,
        existing_configured={base.reaction_id: {"reaction_type": "alarm_state_action"}},
    )
    conflicted_again = materialize_camera_privacy_policy_row(
        row,
        existing_configured={base.reaction_id: {"reaction_type": "alarm_state_action"}},
    )

    assert conflicted.reaction_id.startswith(f"{base.reaction_id}__")
    assert conflicted.reaction_id == conflicted_again.reaction_id


def test_generated_camera_privacy_policy_rebuilds_through_reaction_registry() -> None:
    materialized = materialize_camera_privacy_policy_row(
        CameraPrivacyPolicyRow(
            camera_source_id="interna",
            privacy_entity="switch.interna_privacy",
            alarm_states=("armed_away",),
            privacy_action="turn_off",
        )
    )
    engine = _make_engine(
        {
            "reactions": {
                "configured": {
                    materialized.reaction_id: materialized.config,
                }
            }
        }
    )

    engine._rebuild_configured_reactions()

    assert len(engine._reactions) == 1
    assert isinstance(engine._reactions[0], AlarmStateActionReaction)
    assert engine._reactions[0].reaction_id == materialized.reaction_id


def test_generated_camera_privacy_policy_action_is_blocked_by_manual_hold() -> None:
    materialized = materialize_camera_privacy_policy_row(
        CameraPrivacyPolicyRow(
            camera_source_id="interna",
            privacy_entity="switch.interna_privacy",
            alarm_states=("armed_away",),
            privacy_action="turn_off",
        )
    )
    engine = _make_engine(
        {
            "security": {
                "camera_evidence_sources": [
                    {
                        "id": "interna",
                        "role": "interior",
                        "privacy_entity": "switch.interna_privacy",
                        "manual_hold_entity": "input_boolean.corridoio_privacy_hold",
                    }
                ]
            },
            "reactions": {"configured": {materialized.reaction_id: materialized.config}},
        }
    )
    engine._manual_hold_manager = ManualHoldManager()
    engine._behaviors = []
    engine._state = SimpleNamespace(get_binary=lambda _key: False)
    engine._hass.states.get.side_effect = lambda entity_id: SimpleNamespace(
        state="on" if entity_id == "input_boolean.corridoio_privacy_hold" else "off"
    )
    engine._rebuild_configured_reactions()
    snapshot = replace(DecisionSnapshot.empty(), security_state="armed_away", house_state="home")

    steps = engine._reactions[0].evaluate([snapshot])
    filtered = engine._dispatch_apply_filter(ApplyPlan(steps=steps), snapshot)

    assert len(filtered.steps) == 1
    assert filtered.steps[0].blocked_by == (
        "manual_hold:switch:entity:switch.interna_privacy:helper_on"
    )


def test_parse_camera_privacy_policy_rows_reads_managed_metadata() -> None:
    materialized = materialize_camera_privacy_policy_row(
        CameraPrivacyPolicyRow(
            camera_source_id="interna",
            privacy_entity="switch.interna_privacy",
            alarm_states=("armed_night",),
            house_filter_mode="except",
            house_states=("guest",),
            privacy_action="turn_off",
            enabled=False,
        )
    )
    options = {
        "security": {
            "camera_evidence_sources": [
                {
                    "id": "interna",
                    "display_name": "Corridoio",
                    "role": "interior",
                    "privacy_entity": "switch.interna_privacy",
                }
            ]
        },
        "reactions": {
            "configured": {materialized.reaction_id: materialized.config},
            "labels": {materialized.reaction_id: "Corridoio policy"},
        },
    }

    parsed = parse_camera_privacy_policy_rows_from_options(options)

    assert len(parsed) == 1
    assert parsed[0].reaction_id == materialized.reaction_id
    assert parsed[0].imported is False
    assert parsed[0].label == "Corridoio policy"
    assert parsed[0].row == CameraPrivacyPolicyRow(
        camera_source_id="interna",
        privacy_entity="switch.interna_privacy",
        alarm_states=("armed_night",),
        house_filter_mode="except",
        house_states=("guest",),
        privacy_action="turn_off",
        enabled=False,
        camera_display_name="Corridoio",
    )


def test_parse_camera_privacy_policy_rows_imports_compatible_alarm_state_action() -> None:
    options = {
        "security": {
            "camera_evidence_sources": [
                {
                    "id": "interna",
                    "display_name": "Corridoio",
                    "role": "interior",
                    "privacy_entity": "switch.interna_privacy",
                }
            ]
        },
        "reactions": {
            "configured": {
                "raw-privacy-off": {
                    "reaction_type": "alarm_state_action",
                    "enabled": True,
                    "alarm_states": ["armed_away", "armed_night"],
                    "skip_house_states": ["guest"],
                    "steps": [
                        {
                            "domain": "switch",
                            "target": "switch.interna_privacy",
                            "action": "switch.turn_off",
                            "params": {"entity_id": "switch.interna_privacy"},
                        }
                    ],
                }
            },
            "labels": {"raw-privacy-off": "Raw privacy off"},
        },
    }

    parsed = parse_camera_privacy_policy_rows_from_options(options)

    assert len(parsed) == 1
    assert parsed[0].reaction_id == "raw-privacy-off"
    assert parsed[0].imported is True
    assert parsed[0].label == "Raw privacy off"
    assert parsed[0].row == CameraPrivacyPolicyRow(
        camera_source_id="interna",
        privacy_entity="switch.interna_privacy",
        alarm_states=("armed_away", "armed_night"),
        house_filter_mode="except",
        house_states=("guest",),
        privacy_action="turn_off",
        enabled=True,
        camera_display_name="Corridoio",
    )


def test_parse_camera_privacy_policy_rows_ignores_incompatible_alarm_state_actions() -> None:
    options = {
        "security": {
            "camera_evidence_sources": [
                {
                    "id": "interna",
                    "role": "interior",
                    "privacy_entity": "switch.interna_privacy",
                }
            ]
        },
        "reactions": {
            "configured": {
                "wrong-entity": {
                    "reaction_type": "alarm_state_action",
                    "alarm_states": ["armed_away"],
                    "steps": [
                        {
                            "domain": "switch",
                            "target": "switch.other",
                            "action": "switch.turn_off",
                            "params": {"entity_id": "switch.other"},
                        }
                    ],
                },
                "two-steps": {
                    "reaction_type": "alarm_state_action",
                    "alarm_states": ["armed_away"],
                    "steps": [
                        {
                            "domain": "switch",
                            "target": "switch.interna_privacy",
                            "action": "switch.turn_off",
                            "params": {"entity_id": "switch.interna_privacy"},
                        },
                        {
                            "domain": "switch",
                            "target": "switch.interna_privacy",
                            "action": "switch.turn_on",
                            "params": {"entity_id": "switch.interna_privacy"},
                        },
                    ],
                },
                "target-mismatch": {
                    "reaction_type": "alarm_state_action",
                    "alarm_states": ["armed_away"],
                    "steps": [
                        {
                            "domain": "switch",
                            "target": "switch.interna_privacy",
                            "action": "switch.turn_off",
                            "params": {"entity_id": "switch.other"},
                        }
                    ],
                },
            }
        },
    }

    assert parse_camera_privacy_policy_rows_from_options(options) == []


def test_apply_camera_privacy_policy_rows_can_adopt_imported_reaction_id() -> None:
    options = {
        "security": {
            "camera_evidence_sources": [
                {
                    "id": "interna",
                    "display_name": "Corridoio",
                    "role": "interior",
                    "privacy_entity": "switch.interna_privacy",
                }
            ]
        },
        "reactions": {
            "configured": {
                "raw-privacy-off": {
                    "reaction_type": "alarm_state_action",
                    "alarm_states": ["armed_away"],
                    "steps": [
                        {
                            "domain": "switch",
                            "target": "switch.interna_privacy",
                            "action": "switch.turn_off",
                            "params": {"entity_id": "switch.interna_privacy"},
                        }
                    ],
                },
                "unrelated": {"reaction_type": "scheduled_routine"},
            },
            "labels": {
                "raw-privacy-off": "Raw privacy off",
                "unrelated": "Unrelated",
            },
            "muted": ["raw-privacy-off", "unrelated"],
        },
    }
    imported = parse_camera_privacy_policy_rows_from_options(options)

    updated = apply_camera_privacy_policy_rows_to_options(
        options,
        [imported[0].row],
        replace_reaction_ids={imported[0].reaction_id},
    )

    new_id = "camera_privacy_policy__interna__armed_away__any__turn_off"
    assert "raw-privacy-off" not in updated["reactions"]["configured"]
    assert "raw-privacy-off" not in updated["reactions"]["labels"]
    assert updated["reactions"]["muted"] == ["unrelated"]
    assert new_id in updated["reactions"]["configured"]
    assert updated["reactions"]["configured"][new_id]["camera_privacy_policy"] == {
        "camera_source_id": "interna",
        "privacy_entity": "switch.interna_privacy",
        "house_filter_mode": "always",
        "house_states": [],
        "privacy_action": "turn_off",
    }
    assert updated["reactions"]["configured"]["unrelated"] == {"reaction_type": "scheduled_routine"}
    assert updated["reactions"]["labels"]["unrelated"] == "Unrelated"
