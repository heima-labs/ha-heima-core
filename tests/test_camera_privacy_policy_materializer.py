"""Tests for camera privacy policy materialization."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.heima.config_flow._camera_privacy_policy import (
    CAMERA_PRIVACY_POLICY_TYPE,
    CameraPrivacyPolicyRow,
    apply_camera_privacy_policy_rows_to_options,
    materialize_camera_privacy_policy_row,
)
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.reactions import create_builtin_reaction_plugin_registry
from custom_components.heima.runtime.reactions.alarm_policy import AlarmStateActionReaction


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
                "old-camera-policy": {
                    "reaction_type": "alarm_state_action",
                    "source_template_id": CAMERA_PRIVACY_POLICY_TYPE,
                    "camera_privacy_policy": {"camera_source_id": "interna"},
                },
                "unrelated": {
                    "reaction_type": "scheduled_routine",
                    "weekday": 1,
                },
            },
            "labels": {
                "old-camera-policy": "Old camera policy",
                "unrelated": "Unrelated",
            },
            "muted": ["unrelated"],
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
    )

    assert updated["security"] == options["security"]
    assert "old-camera-policy" not in updated["reactions"]["configured"]
    assert "old-camera-policy" not in updated["reactions"]["labels"]
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
