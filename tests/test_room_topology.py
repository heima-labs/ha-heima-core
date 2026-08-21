"""Tests for the room topology data model, derivation, and pure validation core (AR1)."""

from __future__ import annotations

from custom_components.heima.const import OPT_ROOM_CONNECTIONS, OPT_ROOM_OPENINGS, OPT_ROOMS
from custom_components.heima.room_topology import (
    Opening,
    build_topology_graph,
    derive_connection_type,
    derive_exposure,
    room_floor_of,
    room_type_of,
    validate_topology,
)


def _room(room_id: str, **overrides) -> dict:
    room = {"room_id": room_id, "display_name": room_id}
    room.update(overrides)
    return room


def _opening(opening_id: str, room_id: str, opening_type: str, **overrides) -> dict:
    opening = {"opening_id": opening_id, "room_id": room_id, "type": opening_type}
    opening.update(overrides)
    return opening


def _connection(connection_id: str, opening_id: str, room_b: str, **overrides) -> dict:
    connection = {"connection_id": connection_id, "opening_id": opening_id, "room_b": room_b}
    connection.update(overrides)
    return connection


def _issue_keys(issues) -> set[str]:
    return {issue.key for issue in issues}


# --- room_type / floor defaults -------------------------------------------------


def test_room_type_defaults_to_indoor_when_absent():
    assert room_type_of({"room_id": "living_room"}) == "indoor"


def test_room_type_defaults_to_indoor_when_invalid():
    assert room_type_of({"room_id": "x", "room_type": "spaceship"}) == "indoor"


def test_room_type_of_respects_explicit_value():
    assert room_type_of({"room_id": "x", "room_type": "garage"}) == "garage"


def test_room_floor_defaults_to_zero():
    assert room_floor_of({"room_id": "x"}) == 0
    assert room_floor_of({"room_id": "x", "floor": "not-a-number"}) == 0


def test_room_floor_of_respects_explicit_value():
    assert room_floor_of({"room_id": "x", "floor": 2}) == 2


# --- connection_type derivation --------------------------------------------------


def test_connection_type_indoor_when_both_sides_indoor_or_transit():
    assert derive_connection_type(room_a_type="indoor", room_b_type="indoor", override=None) == (
        "indoor"
    )
    assert derive_connection_type(room_a_type="indoor", room_b_type="transit", override=None) == (
        "indoor"
    )


def test_connection_type_outdoor_when_either_side_balcony_or_outdoor():
    assert derive_connection_type(room_a_type="indoor", room_b_type="balcony", override=None) == (
        "outdoor"
    )
    assert derive_connection_type(room_a_type="outdoor", room_b_type="indoor", override=None) == (
        "outdoor"
    )


def test_connection_type_separate_when_either_side_garage_or_basement():
    assert derive_connection_type(room_a_type="indoor", room_b_type="garage", override=None) == (
        "separate"
    )
    assert derive_connection_type(room_a_type="basement", room_b_type="indoor", override=None) == (
        "separate"
    )


def test_connection_type_garage_or_basement_priority_over_outdoor():
    # A garage that is also a balcony-adjacent room: separate wins (priority rule order).
    assert derive_connection_type(room_a_type="garage", room_b_type="balcony", override=None) == (
        "separate"
    )


def test_connection_type_separate_when_room_b_is_outside():
    assert derive_connection_type(room_a_type="indoor", room_b_type=None, override=None) == (
        "separate"
    )


def test_connection_type_separate_when_either_side_external():
    assert derive_connection_type(room_a_type="external", room_b_type="indoor", override=None) == (
        "separate"
    )
    assert derive_connection_type(room_a_type="indoor", room_b_type="external", override=None) == (
        "separate"
    )


def test_connection_type_override_wins_unconditionally():
    assert (
        derive_connection_type(room_a_type="garage", room_b_type="indoor", override="indoor")
        == "indoor"
    )
    assert (
        derive_connection_type(room_a_type="indoor", room_b_type="indoor", override="separate")
        == "separate"
    )


def test_connection_type_invalid_override_is_ignored():
    assert (
        derive_connection_type(room_a_type="indoor", room_b_type="indoor", override="not_a_type")
        == "indoor"
    )


# --- exposure derivation ----------------------------------------------------------


def test_exposure_is_union_of_window_orientations():
    openings = (
        Opening("o1", "r1", "window", orientation="north"),
        Opening("o2", "r1", "door_window", orientation="east"),
        Opening("o3", "r1", "door", orientation="south"),  # plain door: excluded
        Opening("o4", "r2", "window", orientation="west"),  # other room: excluded
    )
    assert derive_exposure("r1", openings) == ("east", "north")


def test_exposure_recomputes_as_openings_change():
    openings = (Opening("o1", "r1", "window", orientation="north"),)
    assert derive_exposure("r1", openings) == ("north",)
    openings += (Opening("o2", "r1", "window", orientation="south"),)
    assert derive_exposure("r1", openings) == ("north", "south")


def test_exposure_empty_when_no_windows():
    assert derive_exposure("r1", (Opening("o1", "r1", "door"),)) == ()


# --- build_topology_graph: best-effort, excludes broken entries ------------------


def test_build_topology_graph_resolves_connection_type_and_room_a():
    options = {
        OPT_ROOMS: [_room("kitchen", room_type="indoor"), _room("garage", room_type="garage")],
        OPT_ROOM_OPENINGS: [_opening("op1", "kitchen", "door")],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "op1", "garage")],
    }
    graph = build_topology_graph(options)
    assert len(graph.connections) == 1
    resolved = graph.connections[0]
    assert resolved.room_a == "kitchen"
    assert resolved.connection_type == "separate"


def test_build_topology_graph_supports_outside_room_b():
    options = {
        OPT_ROOMS: [_room("entrance", room_type="indoor")],
        OPT_ROOM_OPENINGS: [_opening("op1", "entrance", "door")],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "op1", "outside")],
    }
    graph = build_topology_graph(options)
    assert graph.connections[0].connection_type == "separate"
    assert graph.connections[0].connection.room_b == "outside"


def test_build_topology_graph_excludes_dangling_connection_without_raising():
    options = {
        OPT_ROOMS: [_room("kitchen")],
        OPT_ROOM_OPENINGS: [],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "missing_opening", "outside")],
    }
    graph = build_topology_graph(options)
    assert graph.connections == ()


def test_build_topology_graph_excludes_connection_on_non_door_opening():
    options = {
        OPT_ROOMS: [_room("kitchen"), _room("garage", room_type="garage")],
        OPT_ROOM_OPENINGS: [_opening("op1", "kitchen", "window")],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "op1", "garage")],
    }
    graph = build_topology_graph(options)
    assert graph.connections == ()


def test_build_topology_graph_excludes_connection_with_dangling_room_b():
    options = {
        OPT_ROOMS: [_room("kitchen")],
        OPT_ROOM_OPENINGS: [_opening("op1", "kitchen", "door")],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "op1", "missing_room")],
    }
    graph = build_topology_graph(options)
    assert graph.connections == ()


def test_build_topology_graph_never_raises_on_malformed_options():
    options = {
        OPT_ROOMS: "not-a-list",
        OPT_ROOM_OPENINGS: [{"opening_id": "op1"}, "not-a-dict", None],
        OPT_ROOM_CONNECTIONS: [{"connection_id": "c1"}],
    }
    graph = build_topology_graph(options)
    assert graph.openings == ()
    assert graph.connections == ()


# --- validate_topology: referential integrity -------------------------------------


def test_validate_topology_flags_opening_with_dangling_room():
    options = {
        OPT_ROOMS: [],
        OPT_ROOM_OPENINGS: [_opening("op1", "missing_room", "door")],
        OPT_ROOM_CONNECTIONS: [],
    }
    issues = validate_topology(options)
    assert any(
        issue.key == "topology.opening.op1.dangling_room" and issue.severity == "error"
        for issue in issues
    )


def test_validate_topology_flags_connection_with_dangling_opening():
    options = {
        OPT_ROOMS: [_room("kitchen")],
        OPT_ROOM_OPENINGS: [],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "missing_opening", "outside")],
    }
    issues = validate_topology(options)
    assert any(
        issue.key == "topology.connection.c1.dangling_opening" and issue.severity == "error"
        for issue in issues
    )


def test_validate_topology_flags_connection_on_non_door_opening_as_error():
    options = {
        OPT_ROOMS: [_room("kitchen")],
        OPT_ROOM_OPENINGS: [_opening("op1", "kitchen", "window")],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "op1", "outside")],
    }
    issues = validate_topology(options)
    assert any(
        issue.key == "topology.connection.c1.invalid_opening_type" and issue.severity == "error"
        for issue in issues
    )


def test_validate_topology_flags_connection_with_dangling_room_b():
    options = {
        OPT_ROOMS: [_room("kitchen")],
        OPT_ROOM_OPENINGS: [_opening("op1", "kitchen", "door")],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "op1", "missing_room")],
    }
    issues = validate_topology(options)
    assert any(
        issue.key == "topology.connection.c1.dangling_room_b" and issue.severity == "error"
        for issue in issues
    )


# --- validate_topology: isolation -------------------------------------------------


def test_validate_topology_skips_isolation_check_when_topology_entirely_unconfigured():
    # Every pre-AR installation: rooms exist, but no Opening/Connection has ever been created
    # (AR4's editor is the only way to create them). Must never warn in this state.
    options = {
        OPT_ROOMS: [_room("living_room", room_type="indoor")],
        OPT_ROOM_OPENINGS: [],
        OPT_ROOM_CONNECTIONS: [],
    }
    issues = validate_topology(options)
    assert not any(key.startswith("topology.room.") for key in _issue_keys(issues))


def test_validate_topology_warns_on_isolated_indoor_room_once_topology_is_in_use():
    options = {
        OPT_ROOMS: [
            _room("living_room", room_type="indoor"),
            _room("hallway", room_type="indoor"),
            _room("kitchen", room_type="indoor"),
        ],
        OPT_ROOM_OPENINGS: [_opening("op1", "hallway", "door")],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "op1", "kitchen")],
    }
    issues = validate_topology(options)
    assert any(
        issue.key == "topology.room.living_room.isolated" and issue.severity == "warning"
        for issue in issues
    )
    assert not any(issue.key == "topology.room.hallway.isolated" for issue in issues)
    assert not any(issue.key == "topology.room.kitchen.isolated" for issue in issues)


def test_validate_topology_does_not_warn_on_isolated_garage_basement_outdoor_external():
    options = {
        OPT_ROOMS: [
            _room("garage", room_type="garage"),
            _room("basement", room_type="basement"),
            _room("patio", room_type="outdoor"),
            _room("guest_house", room_type="external"),
            _room("hallway", room_type="indoor"),
            _room("kitchen", room_type="indoor"),
        ],
        OPT_ROOM_OPENINGS: [_opening("op1", "hallway", "door")],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "op1", "kitchen")],
    }
    issues = validate_topology(options)
    for exempt_room_id in ("garage", "basement", "patio", "guest_house"):
        assert not any(issue.key == f"topology.room.{exempt_room_id}.isolated" for issue in issues)


def test_validate_topology_no_isolation_warning_when_connected():
    options = {
        OPT_ROOMS: [_room("kitchen"), _room("hallway")],
        OPT_ROOM_OPENINGS: [_opening("op1", "kitchen", "door")],
        OPT_ROOM_CONNECTIONS: [_connection("c1", "op1", "hallway")],
    }
    issues = validate_topology(options)
    assert not any(key.startswith("topology.room.") for key in _issue_keys(issues))


# --- validate_topology: shared entity_id -------------------------------------------


def test_validate_topology_shared_entity_same_connection_type_is_warning():
    options = {
        OPT_ROOMS: [_room("balcony", room_type="balcony"), _room("living_room")],
        OPT_ROOM_OPENINGS: [
            _opening("op1", "balcony", "door_window", entity_id="binary_sensor.shared"),
            _opening("op2", "balcony", "door_window", entity_id="binary_sensor.shared"),
        ],
        OPT_ROOM_CONNECTIONS: [
            _connection("c1", "op1", "living_room"),
            _connection("c2", "op2", "living_room"),
        ],
    }
    issues = validate_topology(options)
    matching = [
        issue for issue in issues if issue.key == "topology.entity.binary_sensor.shared.shared"
    ]
    assert len(matching) == 1
    assert matching[0].severity == "warning"
    assert not any(issue.key.endswith(".shared_conflict") for issue in issues)


def test_validate_topology_shared_entity_with_no_connections_is_warning():
    # Two plain windows (never referenced by a Connection) sharing one contact sensor.
    options = {
        OPT_ROOMS: [_room("living_room")],
        OPT_ROOM_OPENINGS: [
            _opening("op1", "living_room", "window", entity_id="binary_sensor.shared"),
            _opening("op2", "living_room", "window", entity_id="binary_sensor.shared"),
        ],
        OPT_ROOM_CONNECTIONS: [],
    }
    issues = validate_topology(options)
    assert any(issue.key == "topology.entity.binary_sensor.shared.shared" for issue in issues)


def test_validate_topology_shared_entity_conflicting_connection_type_is_error():
    options = {
        OPT_ROOMS: [
            _room("living_room", room_type="indoor"),
            _room("hallway", room_type="indoor"),
            _room("garage", room_type="garage"),
        ],
        OPT_ROOM_OPENINGS: [
            _opening("op1", "living_room", "door", entity_id="binary_sensor.shared"),
            _opening("op2", "hallway", "door", entity_id="binary_sensor.shared"),
        ],
        OPT_ROOM_CONNECTIONS: [
            # op1 -> garage: separate. op2 -> hallway's neighbor living_room: indoor. Conflict.
            _connection("c1", "op1", "garage"),
            _connection("c2", "op2", "living_room"),
        ],
    }
    issues = validate_topology(options)
    matching = [
        issue
        for issue in issues
        if issue.key == "topology.entity.binary_sensor.shared.shared_conflict"
    ]
    assert len(matching) == 1
    assert matching[0].severity == "error"
    assert not any(issue.key.endswith(".shared") for issue in issues)


def test_validate_topology_single_entity_not_flagged_as_shared():
    options = {
        OPT_ROOMS: [_room("kitchen")],
        OPT_ROOM_OPENINGS: [_opening("op1", "kitchen", "window", entity_id="binary_sensor.solo")],
        OPT_ROOM_CONNECTIONS: [],
    }
    issues = validate_topology(options)
    assert not any(key.startswith("topology.entity.") for key in _issue_keys(issues))


# --- validate_topology: never raises on malformed options -------------------------


def test_validate_topology_never_raises_on_malformed_options():
    options = {
        OPT_ROOMS: "not-a-list",
        OPT_ROOM_OPENINGS: [{"opening_id": "op1"}, "not-a-dict", None],
        OPT_ROOM_CONNECTIONS: [{"connection_id": "c1"}],
    }
    issues = validate_topology(options)
    assert isinstance(issues, tuple)


def test_validate_topology_empty_options_produces_no_issues():
    assert validate_topology({}) == ()
