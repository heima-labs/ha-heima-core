"""Whole-prefix accounting, independent audit holes and durable loss declarations."""

from dataclasses import FrozenInstanceError
from datetime import timedelta
from itertools import groupby

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.history_intervals import HistoryInterval
from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.observation_gaps import (
    ObservationGap,
    assess_observation_coverage,
)
from custom_components.heima.v3.storage.continuity_accounting import (
    ContinuityAccountingBarrier,
    DurabilityRange,
    continuity_barrier_accounted,
)

ANCHOR = "2026-01-01T00:00:00.000000+00:00"
OUTCOMES = ("pending", "written", "loss_pending", "loss_declared")


def instant(us):
    return format_instant(parse_instant(ANCHOR) + timedelta(microseconds=us))


def accounted(ranges=(), through=3, previous=0, complete=True, blocked=None):
    return continuity_barrier_accounted(
        ContinuityAccountingBarrier(through, instant(10)),
        ranges,
        previously_accounted_through=previous,
        inventory_complete=complete,
        producer_blocked_at=blocked,
    )


@pytest.mark.parametrize("outcome", OUTCOMES)
@pytest.mark.parametrize("complete", [False, True])
def test_resolution_and_inventory_decision_table(outcome, complete):
    assert accounted((DurabilityRange(1, 3, outcome),), complete=complete) is (
        complete and outcome in ("written", "loss_declared")
    )


@pytest.mark.parametrize("outcome", OUTCOMES)
@pytest.mark.parametrize("position", ["previous", "inside", "future"])
def test_only_obligations_after_previous_prefix_through_barrier_affect_accounting(
    outcome, position
):
    intervals = {
        "previous": (DurabilityRange(1, 1, outcome), DurabilityRange(2, 3, "written")),
        "inside": (DurabilityRange(1, 3, outcome),),
        "future": (DurabilityRange(2, 3, "written"), DurabilityRange(4, 5, outcome)),
    }[position]
    assert accounted(intervals, previous=1) is (
        position != "inside" or outcome in ("written", "loss_declared")
    )


def test_later_fact_acknowledgement_cannot_hide_an_independent_audit_hole():
    fact = DurabilityRange(1, 1, "written")
    later_fact = DurabilityRange(3, 3, "written")
    assert not accounted((fact, later_fact))  # Missing audit evidence is not a written prefix.
    for outcome in ("pending", "loss_pending"):
        audit = DurabilityRange(2, 2, outcome)
        assert not accounted((fact, audit, later_fact))
    assert accounted((fact, DurabilityRange(2, 2, "loss_declared"), later_fact))


def test_intake_boundary_does_not_certify_a_full_cycle_with_later_dag_or_audit_items():
    items = (DurabilityRange(1, 2, "written"), DurabilityRange(3, 3, "pending"))
    assert accounted(items, through=2)
    assert not accounted(items, through=3)


def test_durable_loss_accounting_is_not_written_payload_or_complete_observation():
    assert not accounted((DurabilityRange(1, 3, "loss_pending"),))
    assert accounted((DurabilityRange(1, 3, "loss_declared"),))
    window = HistoryInterval(instant(0), instant(20), True, True)
    loss = ObservationGap(HistoryInterval(instant(5), instant(6), True, True), "queue_overflow")
    coverage = assess_observation_coverage(window, (loss,), metadata_trustworthy=True)
    assert coverage.status == "incomplete"
    assert coverage.reasons == ("queue_overflow",)


@pytest.mark.parametrize(
    "blocked,expected",
    [(None, True), (instant(9), False), (instant(10), False), (instant(11), True)],
)
def test_failed_producer_construction_blocks_at_before_but_not_after_barrier(blocked, expected):
    assert accounted((DurabilityRange(1, 3, "written"),), blocked=blocked) is expected


@pytest.mark.parametrize("through,expected", [(2, True), (3, True), (4, False)])
def test_prefix_last_position_minus_at_plus_one(through, expected):
    assert accounted((DurabilityRange(1, 3, "written"),), through=through) is expected


@pytest.mark.parametrize("previous,expected", [(1, False), (2, True), (3, True)])
def test_previously_proved_prefix_minus_at_plus_one(previous, expected):
    assert accounted((DurabilityRange(3, 3, "written"),), previous=previous) is expected


@pytest.mark.parametrize("first,expected", [(1, True), (2, False), (3, False)])
def test_missing_leading_prefix_cannot_be_hidden_by_a_later_resolved_range(first, expected):
    assert accounted((DurabilityRange(first, 3, "written"),)) is expected


def test_trailing_and_internal_holes_are_unaccounted():
    assert not accounted((DurabilityRange(1, 2, "written"),))
    assert not accounted((DurabilityRange(1, 1, "written"), DurabilityRange(3, 3, "loss_declared")))
    assert not accounted(())


def test_empty_observation_period_can_be_accounted_without_an_invented_fact():
    assert accounted((), through=0)
    assert accounted((), through=3, previous=3)
    assert not accounted((), through=0, complete=False)
    assert not accounted((), through=0, blocked=instant(10))


def test_huge_batched_sequence_range_does_not_enumerate_items():
    count = 2**63 + 1
    assert accounted((DurabilityRange(1, count, "written"),), through=count)
    assert not accounted((DurabilityRange(2, count, "written"),), through=count)


@pytest.mark.parametrize("a,b", [(1, 1), (1, 2), (2, 3)])
def test_overlapping_duplicate_or_out_of_order_ranges_reject_even_after_barrier(a, b):
    with pytest.raises(ValueError):
        accounted((DurabilityRange(1, 2, "written"), DurabilityRange(a, b, "written")))
    with pytest.raises(ValueError):
        accounted((DurabilityRange(5, 6, "written"), DurabilityRange(a, b, "written")))


@pytest.mark.parametrize("value,error", [(False, TypeError), (1.0, TypeError), (-1, ValueError)])
def test_barrier_and_previous_prefix_sequence_validation(value, error):
    with pytest.raises(error):
        ContinuityAccountingBarrier(value, instant(10))
    with pytest.raises(error):
        accounted(previous=value)


@pytest.mark.parametrize(
    "first,last,error",
    [(0, 1, ValueError), (2, 1, ValueError), (True, 2, TypeError), (1, None, TypeError)],
)
def test_range_shape_boundaries(first, last, error):
    with pytest.raises(error):
        DurabilityRange(first, last, "written")


@pytest.mark.parametrize(
    "outcome,error", [(None, TypeError), (1, TypeError), ("queued", ValueError)]
)
def test_closed_outcome_contract(outcome, error):
    with pytest.raises(error):
        DurabilityRange(1, 1, outcome)


@pytest.mark.parametrize("value", [None, 0, 1, "true"])
def test_inventory_completeness_is_an_explicit_boolean(value):
    with pytest.raises(TypeError):
        accounted((DurabilityRange(1, 3, "written"),), complete=value)


def test_invalid_snapshot_shapes_and_clocks_reject():
    with pytest.raises(ValueError):
        accounted(previous=4)
    with pytest.raises(ValueError):
        accounted(blocked="invalid")
    with pytest.raises(ValueError):
        ContinuityAccountingBarrier(0, "invalid")
    with pytest.raises(TypeError):
        accounted([])
    with pytest.raises(TypeError):
        accounted((None,))
    with pytest.raises(TypeError):
        continuity_barrier_accounted(
            None,
            (),
            previously_accounted_through=0,
            inventory_complete=True,
            producer_blocked_at=None,
        )


@pytest.mark.parametrize("first", [1, 5])
def test_malformed_nested_evidence_is_not_hidden_by_unknown_inventory_or_future_position(first):
    forged = object.__new__(DurabilityRange)
    object.__setattr__(forged, "first_sequence", first)
    object.__setattr__(forged, "last_sequence", first)
    object.__setattr__(forged, "outcome", "unknown")
    with pytest.raises(ValueError):
        accounted((forged,), complete=False)


def test_snapshot_types_are_immutable_and_revalidated():
    barrier = ContinuityAccountingBarrier(3, instant(10))
    with pytest.raises(FrozenInstanceError):
        barrier.through_sequence = 4
    interval = DurabilityRange(1, 3, "written")
    with pytest.raises(FrozenInstanceError):
        interval.outcome = "pending"
    object.__setattr__(barrier, "observed_at", "invalid")
    with pytest.raises(ValueError):
        continuity_barrier_accounted(
            barrier,
            (),
            previously_accounted_through=0,
            inventory_complete=True,
            producer_blocked_at=None,
        )


@given(st.lists(st.sampled_from(OUTCOMES), max_size=30), st.data())
def test_property_grouped_ranges_match_per_item_accounting_without_accepting_holes(outcomes, data):
    target = data.draw(st.integers(0, len(outcomes)))
    previous = data.draw(st.integers(0, target))
    ranges = []
    offset = 1
    for outcome, group in groupby(outcomes):
        count = len(list(group))
        ranges.append(DurabilityRange(offset, offset + count - 1, outcome))
        offset += count
    expected = all(value in ("written", "loss_declared") for value in outcomes[previous:target])
    assert accounted(tuple(ranges), through=target, previous=previous) is expected
    if target > previous:
        # Omit one still-needed item, leaving later acknowledgements intact.
        missing = data.draw(st.integers(previous + 1, target))
        sparse = tuple(
            DurabilityRange(index, index, value)
            for index, value in enumerate(outcomes, 1)
            if index != missing
        )
        assert not accounted(sparse, through=target, previous=previous)


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_range_straddling_an_already_proved_barrier_has_no_new_obligation(outcome):
    assert accounted((DurabilityRange(1, 2, outcome),), through=1, previous=1)


def test_empty_straddling_range_does_not_skip_validation_of_later_snapshot_entries():
    with pytest.raises(TypeError):
        accounted((DurabilityRange(1, 2, "written"), None), through=1, previous=1)
