"""Tests for AR3's engine wiring: _compute_room_topology and CanonicalState exposure."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.room_topology import TopologyGraphCache
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.state_store import CanonicalState


def _fake_engine(cache: TopologyGraphCache | None) -> SimpleNamespace:
    return SimpleNamespace(_state=CanonicalState(), _room_topology_cache=cache)


def test_compute_room_topology_writes_empty_sensor_without_cache():
    fake_engine = _fake_engine(None)
    HeimaEngine._compute_room_topology(fake_engine, options={})
    assert fake_engine._state.get_sensor("rooms.topology") == {}


def test_compute_room_topology_writes_graph_from_cache():
    cache = TopologyGraphCache()
    fake_engine = _fake_engine(cache)
    options = {
        "rooms": [
            {"room_id": "kitchen", "room_type": "indoor"},
            {"room_id": "garage", "room_type": "garage"},
        ],
        "room_openings": [{"opening_id": "op1", "room_id": "kitchen", "type": "door"}],
        "room_connections": [{"connection_id": "c1", "opening_id": "op1", "room_b": "garage"}],
    }
    HeimaEngine._compute_room_topology(fake_engine, options=options)
    payload = fake_engine._state.get_sensor("rooms.topology")
    assert len(payload["connections"]) == 1
    assert payload["connections"][0]["connection_type"] == "separate"


def test_compute_room_topology_reuses_cache_instance():
    cache = TopologyGraphCache()
    fake_engine = _fake_engine(cache)
    options = {
        "rooms": [{"room_id": "kitchen"}],
        "room_openings": [{"opening_id": "op1", "room_id": "kitchen", "type": "door"}],
        "room_connections": [{"connection_id": "c1", "opening_id": "op1", "room_b": "outside"}],
    }
    HeimaEngine._compute_room_topology(fake_engine, options=options)
    first_graph = cache.get_graph(options)

    changed_options = {
        "rooms": [{"room_id": "kitchen"}, {"room_id": "hallway"}],
        "room_openings": [{"opening_id": "op1", "room_id": "kitchen", "type": "door"}],
        "room_connections": [{"connection_id": "c1", "opening_id": "op1", "room_b": "hallway"}],
    }
    HeimaEngine._compute_room_topology(fake_engine, options=changed_options)
    payload = fake_engine._state.get_sensor("rooms.topology")

    # No mark_stale() call in between: the cache never rebuilds, matching the
    # spec's "cached; invalidated only on options/registry change" contract.
    assert (
        payload["connections"][0]["connection_type"] == first_graph.connections[0].connection_type
    )
