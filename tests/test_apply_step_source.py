from __future__ import annotations

from custom_components.heima.runtime.contracts import (
    ApplyStep,
    ApplyStepSource,
    admin_command_step_source,
    domain_step_source,
    is_authoritative_source,
    reaction_id_from_step_source,
    reaction_step_source,
    redact_actor_id,
    resident_response_step_source,
    sanitize_apply_step_source,
    step_source_actor_type,
    step_source_id,
    step_source_kind,
    step_source_legacy_key,
    step_source_type,
    timeout_step_source,
)


def test_legacy_reaction_source_helpers_remain_compatible() -> None:
    step = ApplyStep(
        domain="light",
        target="light.studio",
        action="light.turn_on",
        source="reaction:studio_scene",
    )

    assert step_source_kind(step) == "legacy"
    assert step_source_id(step) == "studio_scene"
    assert step_source_type(step) is None
    assert step_source_actor_type(step) == "unknown"
    assert step_source_legacy_key(step) == "reaction:studio_scene"
    assert reaction_id_from_step_source(step) == "studio_scene"
    assert not is_authoritative_source(step)
    assert not is_authoritative_source(step, kind="reaction")


def test_structured_reaction_source_helpers() -> None:
    source = reaction_step_source(
        "camera_privacy_policy",
        reaction_type="alarm_state_action",
        correlation_id="corr-1",
    )

    assert step_source_kind(source) == "reaction"
    assert step_source_id(source) == "camera_privacy_policy"
    assert step_source_type(source) == "alarm_state_action"
    assert step_source_actor_type(source) == "heima"
    assert step_source_legacy_key(source) == "reaction:camera_privacy_policy"
    assert reaction_id_from_step_source(source) == "camera_privacy_policy"
    assert is_authoritative_source(source)
    assert is_authoritative_source(source, kind="reaction")
    assert not is_authoritative_source(source, kind="admin_command")


def test_structured_domain_admin_resident_and_timeout_sources() -> None:
    domain = domain_step_source("lighting", source_type="smart_lighting")
    admin = admin_command_step_source(
        "clear_hold",
        command_type="manual_hold.clear",
        actor_id="ha-user-1",
        correlation_id="admin-corr",
    )
    resident = resident_response_step_source(
        "request-1",
        actor_id="recipient-stefano",
        correlation_id="resident-corr",
    )
    timeout = timeout_step_source("request-2", correlation_id="timeout-corr")

    assert step_source_kind(domain) == "domain"
    assert step_source_type(domain) == "smart_lighting"
    assert step_source_actor_type(admin) == "ha_admin"
    assert step_source_legacy_key(admin) == "admin_command:clear_hold"
    assert is_authoritative_source(admin, kind="admin_command")
    assert step_source_actor_type(resident) == "resident"
    assert step_source_legacy_key(resident) == "resident_response:request-1"
    assert is_authoritative_source(resident, kind="resident_response")
    assert step_source_actor_type(timeout) == "scheduler"
    assert step_source_legacy_key(timeout) == "timeout:request-2"
    assert is_authoritative_source(timeout, kind="timeout")


def test_forged_mapping_source_is_sanitized_to_non_authoritative_legacy() -> None:
    forged = {
        "kind": "admin_command",
        "source_id": "clear_hold",
        "actor_type": "ha_admin",
        "actor_id": "raw-ha-user-id",
    }

    source = sanitize_apply_step_source(forged)

    assert isinstance(source, ApplyStepSource)
    assert step_source_kind(source) == "legacy"
    assert step_source_id(source) == "clear_hold"
    assert step_source_legacy_key(source) == "clear_hold"
    assert step_source_actor_type(source) == "unknown"
    assert not is_authoritative_source(source)
    assert not is_authoritative_source(source, kind="admin_command")


def test_actor_redaction_is_stable_and_omits_raw_actor_id() -> None:
    source = resident_response_step_source(
        "request-1",
        actor_id="recipient-stefano",
        correlation_id="corr-1",
    )

    redacted = source.as_redacted_dict()

    assert redacted["actor_id_hash"] == redact_actor_id("recipient-stefano")
    assert redacted["actor_id_hash"] == redact_actor_id("recipient-stefano")
    assert redacted["actor_id_hash"] != "recipient-stefano"
    assert "actor_id" not in redacted
    assert redacted["legacy_key"] == "resident_response:request-1"
