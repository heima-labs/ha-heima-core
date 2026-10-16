"""L0 §4.0–4.2: preserve transitions and per-stream horizon predecessors."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.fact_sources import FactSource
from custom_components.heima.v3.contracts.fact_state import fact_identity_key
from custom_components.heima.v3.contracts.house_facts import build_house_fact
from custom_components.heima.v3.contracts.instants import EvidenceInstant, format_instant
from custom_components.heima.v3.contracts.location import Location
from custom_components.heima.v3.contracts.timing import Window
from custom_components.heima.v3.runtime.state_acceptance import (
    AcceptedStateTransition,
    AppendOrder,
)
from custom_components.heima.v3.runtime.state_buffer import StateTransitionBuffer

ANCHOR = datetime(2026, 10, 16, tzinfo=UTC)
SOURCE = FactSource("sensor", "sensor.a", None, None, None, "heima", "origin")


def at(seconds=0, micros=0):
    return format_instant(ANCHOR + timedelta(seconds=seconds, microseconds=micros))


def transition(seconds=0, *, micros=0, cycle=1, ordinal=1, room="a", value="on"):
    fact = build_house_fact(
        fact_type="signal",
        where=Location("room", room_id=room),
        value=value,
        when=at(seconds, micros),
        source=SOURCE,
        confidence=1,
    ).fact
    return AcceptedStateTransition(fact, AppendOrder(cycle, ordinal))


def key(room="a"):
    return fact_identity_key(transition(room=room).fact)


@pytest.mark.parametrize(
    "declared,expected",
    [(1e-7, 900), (899.999999, 900), (900, 900), (900.000001, 900.000001), (3600, 3600)],
)
def test_horizon_default_floor_and_declared_extension(declared, expected):
    buffer = StateTransitionBuffer({key(): Window(declared)})
    assert buffer.effective_horizon(key()) == Window(expected)
    assert buffer.records(key()) == ()


def test_owns_staged_horizons_and_empty_inventory_is_valid():
    declarations = {key(): Window(3600), key("b"): Window(1)}
    buffer = StateTransitionBuffer(declarations)
    declarations.clear()
    assert buffer.effective_horizon(key()) == Window(3600)
    assert buffer.effective_horizon(key("b")) == Window(900)
    assert StateTransitionBuffer({}).maintain(at()) == 0


@pytest.mark.parametrize("invalid", [{"not-key": Window(900)}, {key(): 900}])
def test_invalid_horizon_inputs_rejected(invalid):
    with pytest.raises(TypeError):
        StateTransitionBuffer(invalid)


def test_preserves_equal_time_transitions_and_reader_snapshot_after_eviction():
    buffer = StateTransitionBuffer({key(): Window(900)})
    events = tuple(transition(ordinal=n, value=v) for n, v in enumerate(("on", "off", "on"), 1))
    for event in events:
        buffer.append(event)
    snapshot = buffer.records(key())
    assert snapshot == events
    assert all(a is b for a, b in zip(snapshot, events, strict=True))
    assert buffer.maintain(at(900)) == 2
    assert buffer.records(key()) == (events[-1],)
    assert snapshot == events


@pytest.mark.parametrize("offset,expected", [(-1, 0), (0, 1), (1, 1)])
def test_eviction_boundary_uses_successor_not_old_record(offset, expected):
    buffer = StateTransitionBuffer({key(): Window(900)})
    old, newer = transition(), transition(10, cycle=2, value="off")
    buffer.append(old)
    buffer.append(newer)
    assert buffer.maintain(at(910, offset)) == expected
    assert buffer.records(key()) == ((newer,) if expected else (old, newer))


def test_each_stream_extends_only_its_own_horizon_and_keeps_sparse_predecessor():
    buffer = StateTransitionBuffer({key(): Window(3600), key("b"): Window(900)})
    records = [
        transition(room="a"),
        transition(room="b", ordinal=2),
        transition(10, cycle=2, room="a", value="off"),
        transition(10, cycle=2, ordinal=2, room="b", value="off"),
    ]
    for record in records:
        buffer.append(record)
    assert buffer.maintain(at(1000)) == 1
    assert buffer.records(key()) == (records[0], records[2])
    assert buffer.records(key("b")) == (records[3],)
    assert buffer.maintain(at(4000)) == 1
    assert buffer.records(key()) == (records[2],)
    assert buffer.maintain(at(10_000_000)) == 0
    assert buffer.records(key("b")) == (records[3],)


def test_arbitrarily_old_predecessor_is_kept_until_its_successor_reaches_cutoff():
    buffer = StateTransitionBuffer({key(): Window(900)})
    a, b, c = transition(), transition(5000, cycle=2), transition(5100, cycle=3)
    for record in (a, b, c):
        buffer.append(record)
    assert buffer.maintain(at(5500)) == 0  # window starts at 4600: only a seeds it
    assert buffer.records(key()) == (a, b, c)
    assert buffer.maintain(at(5900)) == 1  # b is exactly at start
    assert buffer.records(key()) == (b, c)


def test_maintenance_is_explicit_and_not_hidden_in_append():
    buffer = StateTransitionBuffer({key(): Window(900)})
    a, b = transition(), transition(10000, cycle=2)
    buffer.append(a)
    buffer.append(b)
    assert buffer.records(key()) == (a, b)
    assert buffer.maintain(at(11000)) == 1


@pytest.mark.parametrize(
    "after",
    [
        transition(cycle=1, ordinal=1),
        transition(cycle=0, ordinal=9),
        transition(cycle=1, ordinal=2, micros=1),
        transition(cycle=2),
        transition(cycle=2, micros=-1),
    ],
)
def test_invalid_order_or_cycle_time_leaves_buffer_unchanged(after):
    buffer = StateTransitionBuffer({key(): Window(900)})
    before = transition()
    buffer.append(before)
    with pytest.raises(ValueError):
        buffer.append(after)
    valid = transition(1, cycle=2)
    buffer.append(valid)
    assert buffer.records(key()) == (before, valid)


def test_gaps_in_order_and_cycles_and_equal_maintenance_instant_are_allowed():
    buffer = StateTransitionBuffer({key(): Window(900)})
    a, b, c = transition(ordinal=3), transition(ordinal=10), transition(1, cycle=10)
    for record in (a, b):
        buffer.append(record)
    assert buffer.maintain(at(1)) == 0
    assert buffer.maintain(at(1)) == 0
    buffer.append(c)
    assert buffer.records(key()) == (a, b, c)


def test_maintenance_and_late_append_reject_backward_clock_before_mutation():
    buffer = StateTransitionBuffer({key(): Window(900)})
    a = transition()
    buffer.append(a)
    buffer.maintain(at(1000))
    for earlier in (at(999, 999999), EvidenceInstant("invalid")):
        with pytest.raises(ValueError):
            buffer.maintain(earlier)
    with pytest.raises(ValueError):
        buffer.append(transition(999, micros=999999, cycle=2))
    b = transition(1000, cycle=2)
    buffer.append(b)
    with pytest.raises(ValueError):
        buffer.maintain(at(999))
    assert buffer.records(key()) == (a, b)


def test_maintenance_cannot_precede_last_append_even_before_first_maintenance():
    buffer = StateTransitionBuffer({key(): Window(900)})
    a = transition(10)
    buffer.append(a)
    with pytest.raises(ValueError):
        buffer.maintain(at(10, -1))
    assert buffer.records(key()) == (a,)


def test_unknown_or_malformed_key_and_nontransition_are_rejected_without_changes():
    buffer = StateTransitionBuffer({key(): Window(900)})
    for operation in (buffer.records, buffer.effective_horizon):
        with pytest.raises(KeyError):
            operation(key("unknown"))
        with pytest.raises(TypeError):
            operation("invalid")
    with pytest.raises(KeyError):
        buffer.append(transition(room="unknown"))
    with pytest.raises(TypeError):
        buffer.append(transition().fact)
    a = transition()
    buffer.append(a)
    assert buffer.records(key()) == (a,)


def test_overflowing_expiration_never_evicts_or_rejects_valid_append():
    buffer = StateTransitionBuffer({key(): Window(1e300)})
    a, b = transition(), transition(1, cycle=2)
    buffer.append(a)
    buffer.append(b)
    assert buffer.maintain(EvidenceInstant("9999-12-31T23:59:59.999999+00:00")) == 0
    assert buffer.records(key()) == (a, b)


@settings(deadline=None)
@given(
    st.lists(st.integers(0, 10000), min_size=1, max_size=40),
    st.integers(0, 10000),
    st.sampled_from([900, 3600]),
)
def test_generated_retention_is_suffix_with_last_predecessor_and_all_later_records(
    times, elapsed, horizon
):
    times = sorted(set(times))
    records = tuple(
        transition(second, cycle=index + 1, value=index) for index, second in enumerate(times)
    )
    now = max(times) + elapsed
    buffer = StateTransitionBuffer({key(): Window(horizon)})
    for record in records:
        buffer.append(record)
    removed = buffer.maintain(at(now))
    result = buffer.records(key())
    assert result
    assert result[-1] is records[-1]
    assert result == records[removed:]
    # A query window still has its final predecessor and every later transition.
    earlier = [record for record in records if record.fact.when <= at(now - horizon)]
    later = [record for record in records if record.fact.when > at(now - horizon)]
    expected = tuple(earlier[-1:] + later)
    assert result == expected
    assert buffer.maintain(at(now)) == 0


def test_fractional_horizon_expiry_uses_canonical_decimal_without_early_eviction():
    buffer = StateTransitionBuffer({key(): Window(900.0000001)})
    a, b = transition(), transition(ordinal=2, value="off")
    buffer.append(a)
    buffer.append(b)
    assert buffer.maintain(at(900)) == 0
    assert buffer.records(key()) == (a, b)
    assert buffer.maintain(at(900, 1)) == 1
    assert buffer.records(key()) == (b,)


def test_append_order_is_global_across_streams_and_failed_append_does_not_consume_it():
    buffer = StateTransitionBuffer({key(): Window(900), key("b"): Window(900)})
    a = transition()
    buffer.append(a)
    with pytest.raises(ValueError):
        buffer.append(transition(room="b"))  # duplicate order, another key
    b = transition(room="b", ordinal=2)
    buffer.append(b)
    assert buffer.records(key()) == (a,)
    assert buffer.records(key("b")) == (b,)
