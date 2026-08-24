"""Tests for the actuator registry's pure data model and validation core (AU1)."""

from __future__ import annotations

from custom_components.heima.actuators import (
    Actuator,
    apply_actuator_delete,
    apply_actuator_upsert,
    is_opening_referenced_by_actuator,
    parse_actuators,
    validate_actuators,
)
from custom_components.heima.const import OPT_ROOM_ACTUATORS, OPT_ROOM_OPENINGS, OPT_ROOMS


def _room(room_id: str, **overrides) -> dict:
    room = {"room_id": room_id, "display_name": room_id}
    room.update(overrides)
    return room


def _opening(opening_id: str, room_id: str, opening_type: str = "window", **overrides) -> dict:
    opening = {"opening_id": opening_id, "room_id": room_id, "type": opening_type}
    opening.update(overrides)
    return opening


def _actuator(actuator_id: str, entity_id: str, room_id: str, **overrides) -> dict:
    actuator = {"actuator_id": actuator_id, "entity_id": entity_id, "room_id": room_id}
    actuator.update(overrides)
    return actuator


def _issue_keys(issues) -> set[str]:
    return {issue.key for issue in issues}


def _base_options(**extra) -> dict:
    options = {
        OPT_ROOMS: [_room("kitchen"), _room("garage")],
        OPT_ROOM_OPENINGS: [_opening("op1", "kitchen", "window", orientation="south")],
        OPT_ROOM_ACTUATORS: [],
    }
    options.update(extra)
    return options


# --- parse_actuators --------------------------------------------------------------


def test_parse_actuators_returns_empty_tuple_when_absent():
    assert parse_actuators({}) == ()


def test_parse_actuators_parses_valid_entry():
    options = _base_options(
        **{
            OPT_ROOM_ACTUATORS: [
                _actuator("a1", "cover.kitchen_shutter", "kitchen", opening_id="op1")
            ]
        }
    )
    actuators = parse_actuators(options)
    assert actuators == (
        Actuator(
            actuator_id="a1",
            entity_id="cover.kitchen_shutter",
            room_id="kitchen",
            opening_id="op1",
            display_name=None,
        ),
    )


def test_parse_actuators_skips_malformed_entries():
    options = {
        OPT_ROOM_ACTUATORS: [
            {"actuator_id": "", "entity_id": "cover.x", "room_id": "kitchen"},  # missing id
            {"actuator_id": "a1", "entity_id": "", "room_id": "kitchen"},  # missing entity_id
            {"actuator_id": "a2", "entity_id": "cover.x"},  # missing room_id
            "not_a_dict",
            _actuator("a3", "cover.y", "kitchen"),
        ]
    }
    actuators = parse_actuators(options)
    assert [a.actuator_id for a in actuators] == ["a3"]


def test_parse_actuators_deduplicates_by_actuator_id():
    options = {
        OPT_ROOM_ACTUATORS: [
            _actuator("a1", "cover.x", "kitchen"),
            _actuator("a1", "cover.y", "kitchen"),
        ]
    }
    actuators = parse_actuators(options)
    assert len(actuators) == 1


def test_parse_actuators_opening_id_and_display_name_default_to_none():
    options = {OPT_ROOM_ACTUATORS: [_actuator("a1", "fan.x", "kitchen")]}
    actuator = parse_actuators(options)[0]
    assert actuator.opening_id is None
    assert actuator.display_name is None


# --- is_opening_referenced_by_actuator ----------------------------------------


def test_is_opening_referenced_by_actuator_true_when_referenced():
    options = _base_options(
        **{
            OPT_ROOM_ACTUATORS: [
                _actuator("a1", "cover.kitchen_shutter", "kitchen", opening_id="op1")
            ]
        }
    )
    assert is_opening_referenced_by_actuator(options, "op1") is True


def test_is_opening_referenced_by_actuator_false_when_not_referenced():
    options = _base_options(**{OPT_ROOM_ACTUATORS: [_actuator("a1", "fan.kitchen", "kitchen")]})
    assert is_opening_referenced_by_actuator(options, "op1") is False


def test_is_opening_referenced_by_actuator_false_for_empty_opening_id():
    assert is_opening_referenced_by_actuator({}, "") is False


# --- validate_actuators ---------------------------------------------------------


def test_validate_actuators_no_issues_for_clean_configuration():
    options = _base_options(
        **{
            OPT_ROOM_ACTUATORS: [
                _actuator("a1", "cover.kitchen_shutter", "kitchen", opening_id="op1"),
                _actuator("a2", "fan.garage", "garage"),
            ]
        }
    )
    assert validate_actuators(options) == ()


def test_validate_actuators_dangling_room_is_warning():
    options = _base_options(**{OPT_ROOM_ACTUATORS: [_actuator("a1", "cover.x", "attic")]})
    issues = validate_actuators(options)
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].key == "actuators.actuator.a1.dangling_room"


def test_validate_actuators_dangling_opening_is_warning():
    options = _base_options(
        **{OPT_ROOM_ACTUATORS: [_actuator("a1", "cover.x", "kitchen", opening_id="missing")]}
    )
    issues = validate_actuators(options)
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].key == "actuators.actuator.a1.dangling_opening"


def test_validate_actuators_opening_in_different_room_is_error():
    options = _base_options(
        **{OPT_ROOM_ACTUATORS: [_actuator("a1", "cover.x", "garage", opening_id="op1")]}
    )
    issues = validate_actuators(options)
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].key == "actuators.actuator.a1.opening_room_mismatch"


def test_validate_actuators_shared_entity_id_is_warning():
    options = _base_options(
        **{
            OPT_ROOM_ACTUATORS: [
                _actuator("a1", "cover.shared", "kitchen"),
                _actuator("a2", "cover.shared", "garage"),
            ]
        }
    )
    issues = validate_actuators(options)
    assert _issue_keys(issues) == {"actuators.entity.cover.shared.shared"}
    assert issues[0].severity == "warning"


def test_validate_actuators_unique_entity_ids_produce_no_shared_warning():
    options = _base_options(
        **{
            OPT_ROOM_ACTUATORS: [
                _actuator("a1", "cover.a", "kitchen"),
                _actuator("a2", "cover.b", "garage"),
            ]
        }
    )
    assert validate_actuators(options) == ()


# --- apply_actuator_upsert ------------------------------------------------------


def test_apply_actuator_upsert_generates_id_when_absent():
    options = _base_options()
    new_options, issues = apply_actuator_upsert(
        options, actuator_id=None, entity_id="cover.x", room_id="kitchen"
    )
    assert issues == ()
    assert new_options is not None
    actuators = new_options[OPT_ROOM_ACTUATORS]
    assert len(actuators) == 1
    assert actuators[0]["actuator_id"]
    assert actuators[0]["entity_id"] == "cover.x"


def test_apply_actuator_upsert_rejects_missing_entity_id():
    options = _base_options()
    new_options, issues = apply_actuator_upsert(
        options, actuator_id=None, entity_id="", room_id="kitchen"
    )
    assert new_options is None
    assert issues == ()


def test_apply_actuator_upsert_rejects_missing_room_id():
    options = _base_options()
    new_options, issues = apply_actuator_upsert(
        options, actuator_id=None, entity_id="cover.x", room_id=""
    )
    assert new_options is None
    assert issues == ()


def test_apply_actuator_upsert_with_existing_id_edits_in_place():
    options = _base_options(**{OPT_ROOM_ACTUATORS: [_actuator("a1", "cover.old", "kitchen")]})
    new_options, issues = apply_actuator_upsert(
        options, actuator_id="a1", entity_id="cover.new", room_id="kitchen"
    )
    assert issues == ()
    actuators = new_options[OPT_ROOM_ACTUATORS]
    assert len(actuators) == 1
    assert actuators[0]["entity_id"] == "cover.new"


def test_apply_actuator_upsert_blocked_by_opening_room_mismatch():
    options = _base_options()
    new_options, issues = apply_actuator_upsert(
        options, actuator_id=None, entity_id="cover.x", room_id="garage", opening_id="op1"
    )
    assert new_options is None
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].key.endswith(".opening_room_mismatch")


def test_apply_actuator_upsert_not_blocked_by_dangling_room_warning():
    # Warnings never block a save; only error-severity issues do.
    options = _base_options()
    new_options, issues = apply_actuator_upsert(
        options, actuator_id=None, entity_id="cover.x", room_id="attic"
    )
    assert issues == ()
    assert new_options is not None


# --- apply_actuator_delete -------------------------------------------------------


def test_apply_actuator_delete_removes_existing():
    options = _base_options(**{OPT_ROOM_ACTUATORS: [_actuator("a1", "cover.x", "kitchen")]})
    new_options, issues = apply_actuator_delete(options, actuator_id="a1")
    assert issues == ()
    assert new_options[OPT_ROOM_ACTUATORS] == []


def test_apply_actuator_delete_is_noop_for_unknown_id():
    options = _base_options(**{OPT_ROOM_ACTUATORS: [_actuator("a1", "cover.x", "kitchen")]})
    new_options, issues = apply_actuator_delete(options, actuator_id="does_not_exist")
    assert new_options is None
    assert issues == ()


def test_apply_actuator_delete_rejects_empty_id():
    new_options, issues = apply_actuator_delete(_base_options(), actuator_id="")
    assert new_options is None
    assert issues == ()
