"""Tests for SnapshotBuffer (Phase 7 R0)."""

from __future__ import annotations

import pytest

from custom_components.heima.runtime.snapshot import DecisionSnapshot
from custom_components.heima.runtime.snapshot_buffer import SnapshotBuffer


def _snap(house_state: str = "unknown") -> DecisionSnapshot:
    s = DecisionSnapshot.empty()
    # DecisionSnapshot is frozen; rebuild with the desired house_state
    from dataclasses import replace
    return replace(s, house_state=house_state)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_default_capacity():
    buf = SnapshotBuffer()
    assert buf.capacity == 20


def test_custom_capacity():
    buf = SnapshotBuffer(capacity=5)
    assert buf.capacity == 5


def test_invalid_capacity_raises():
    with pytest.raises(ValueError):
        SnapshotBuffer(capacity=0)


# ---------------------------------------------------------------------------
# Push / history ordering
# ---------------------------------------------------------------------------


def test_empty_buffer_history_is_empty():
    buf = SnapshotBuffer()
    assert buf.history() == []


def test_empty_latest_is_none():
    buf = SnapshotBuffer()
    assert buf.latest() is None


def test_push_single():
    buf = SnapshotBuffer()
    s = _snap("away")
    buf.push(s)
    assert len(buf) == 1
    assert buf.latest() is s


def test_history_oldest_first():
    buf = SnapshotBuffer(capacity=5)
    states = ["away", "home", "sleep"]
    snaps = [_snap(st) for st in states]
    for s in snaps:
        buf.push(s)
    history = buf.history()
    assert [h.house_state for h in history] == states


def test_latest_is_last_pushed():
    buf = SnapshotBuffer(capacity=5)
    snaps = [_snap(st) for st in ["away", "home", "sleep"]]
    for s in snaps:
        buf.push(s)
    assert buf.latest() is snaps[-1]


# ---------------------------------------------------------------------------
# Capacity / eviction
# ---------------------------------------------------------------------------


def test_evicts_oldest_when_full():
    buf = SnapshotBuffer(capacity=3)
    snaps = [_snap(str(i)) for i in range(5)]
    for s in snaps:
        buf.push(s)
    assert len(buf) == 3
    history = buf.history()
    assert history[0] is snaps[2]  # oldest kept
    assert history[-1] is snaps[4]  # newest


def test_length_never_exceeds_capacity():
    buf = SnapshotBuffer(capacity=4)
    for i in range(10):
        buf.push(_snap())
    assert len(buf) <= 4


def test_capacity_one_keeps_only_latest():
    buf = SnapshotBuffer(capacity=1)
    s1 = _snap("away")
    s2 = _snap("home")
    buf.push(s1)
    buf.push(s2)
    assert len(buf) == 1
    assert buf.latest() is s2


# ---------------------------------------------------------------------------
# history() returns a copy
# ---------------------------------------------------------------------------


def test_history_returns_copy():
    buf = SnapshotBuffer(capacity=5)
    buf.push(_snap())
    h1 = buf.history()
    h2 = buf.history()
    assert h1 is not h2


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_empties_buffer():
    buf = SnapshotBuffer(capacity=5)
    for _ in range(3):
        buf.push(_snap())
    buf.clear()
    assert len(buf) == 0
    assert buf.latest() is None
    assert buf.history() == []
