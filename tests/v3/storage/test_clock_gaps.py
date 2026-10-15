"""Clock-gap receipts, pending ends, exact correlation and scoped coverage."""

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from itertools import product

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.history_intervals import HistoryInterval
from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.observation import (
    ObservationCoverage,
    combine_observation_coverage,
)
from custom_components.heima.v3.runtime.clock import ClockGap, CycleClock
from custom_components.heima.v3.storage.clock_gaps import (
    ClockGapBoundaryReceipt,
    ClockGapDurability,
    clock_gap_observation_coverage,
)

ANCHOR = "2026-01-01T00:00:00.000000+00:00"


def instant(us):
    return format_instant(parse_instant(ANCHOR) + timedelta(microseconds=us))


def span(start, end, left=True, right=True):
    return HistoryInterval(instant(start), instant(end), left, right)


def state(end=20, opening=True, closing=False, left=True, right=False, gap_id="gap-a"):
    gap = ClockGap(instant(10), None if end is None else instant(end), False)
    return ClockGapDurability(
        gap_id,
        gap,
        left,
        right,
        ClockGapBoundaryReceipt(gap_id, "opening", gap.start, left) if opening else None,
        ClockGapBoundaryReceipt(gap_id, "closing", gap.end, right) if closing else None,
    )


@pytest.mark.parametrize("opening,closing", list(product([False, True], repeat=2)))
@pytest.mark.parametrize("region", ["before", "inside", "after"])
def test_closed_intent_receipt_decision_table(opening, closing, region):
    query = {"before": span(0, 5), "inside": span(12, 15), "after": span(25, 30)}[region]
    result = clock_gap_observation_coverage(query, state(opening=opening, closing=closing))
    if region == "before" or (region == "after" and closing):
        assert result == ObservationCoverage("complete", (), None)
    else:
        reasons = (
            ("clock_discontinuity",)
            if opening and closing
            else ("clock_discontinuity", "continuity_metadata_unknown")
        )
        assert result == ObservationCoverage("incomplete", reasons, query.start)


@pytest.mark.parametrize("opening", [False, True])
def test_known_open_gap_vs_pending_end_mcdc(opening):
    query = span(25, 30)
    open_result = clock_gap_observation_coverage(query, state(end=None, opening=opening))
    pending_result = clock_gap_observation_coverage(query, state(opening=opening))
    assert open_result == ObservationCoverage(
        "incomplete",
        ("clock_discontinuity",)
        if opening
        else ("clock_discontinuity", "continuity_metadata_unknown"),
        query.start,
    )
    assert pending_result == ObservationCoverage(
        "incomplete", ("clock_discontinuity", "continuity_metadata_unknown"), query.start
    )


def test_queue_admission_or_clock_finish_cannot_certify_the_end():
    cycle = CycleClock(instant(100_000_000))
    first = cycle.next_cycle(instant(90_000_000), 0)
    recovery = cycle.next_cycle(instant(101_000_000), 1_000_000_000)
    ended_intent = first.comparison.gap.finish(recovery)
    query = span(102_000_000, 103_000_000)
    opening = ClockGapBoundaryReceipt("bootstrap-gap", "opening", ended_intent.start, True)
    pending = ClockGapDurability("bootstrap-gap", ended_intent, True, False, opening, None)
    assert clock_gap_observation_coverage(query, pending).status == "incomplete"
    receipt = ClockGapBoundaryReceipt("bootstrap-gap", "closing", ended_intent.end, False)
    confirmed = replace(pending, closing_receipt=receipt)
    assert clock_gap_observation_coverage(query, confirmed).status == "complete"
    assert pending.closing_receipt is None
    assert ended_intent.end == instant(101_000_000)


def test_independent_gaps_cannot_share_receipts_even_with_identical_bounds():
    a = state(closing=True)
    b = state(gap_id="gap-b")
    with pytest.raises(ValueError):
        replace(b, closing_receipt=a.closing_receipt)
    query = span(25, 30)
    complete_process = ObservationCoverage("complete", (), None)
    assert (
        combine_observation_coverage(
            complete_process,
            (clock_gap_observation_coverage(query, a), clock_gap_observation_coverage(query, b)),
        ).status
        == "incomplete"
    )
    unknown_process = ObservationCoverage(
        "incomplete", ("continuity_metadata_unknown",), query.start
    )
    assert (
        combine_observation_coverage(
            unknown_process, (clock_gap_observation_coverage(query, a),)
        ).status
        == "incomplete"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("gap_id", "other"),
        ("boundary", "opening"),
        ("when", instant(19)),
        ("includes_boundary", True),
    ],
)
def test_receipt_correlation_rejects_wrong_id_side_instant_or_inclusion(field, value):
    original = state(closing=True)
    wrong = replace(original.closing_receipt, **{field: value})
    with pytest.raises(ValueError):
        replace(original, closing_receipt=wrong)


def test_late_receipt_for_previous_end_cannot_confirm_a_new_end():
    old = state(closing=True)
    with pytest.raises(ValueError):
        replace(old, gap=replace(old.gap, end=instant(21)))
    with pytest.raises(ValueError):
        replace(old, gap=replace(old.gap, start=instant(9)))
    with pytest.raises(ValueError):
        replace(old, gap=replace(old.gap, end=None))


@pytest.mark.parametrize("boundary_included,query_included", list(product([False, True], repeat=2)))
@pytest.mark.parametrize("which", ["opening", "closing"])
def test_durable_boundary_touching_endpoint_inclusions(boundary_included, query_included, which):
    if which == "opening":
        current = state(left=boundary_included, closing=True)
        query = span(0, 10, True, query_included)
        first = instant(10)
    else:
        current = state(right=boundary_included, closing=True)
        query = span(20, 30, query_included, True)
        first = instant(20)
    result = clock_gap_observation_coverage(query, current)
    assert result == (
        ObservationCoverage("incomplete", ("clock_discontinuity",), first)
        if boundary_included and query_included
        else ObservationCoverage("complete", (), None)
    )


@pytest.mark.parametrize(
    "point,expected", [(9, "complete"), (10, "incomplete"), (11, "incomplete")]
)
def test_pending_opening_boundary_microsecond_neighbors(point, expected):
    assert (
        clock_gap_observation_coverage(span(point, point), state(opening=False)).status == expected
    )


@pytest.mark.parametrize("point,expected", [(19, "incomplete"), (20, "complete"), (21, "complete")])
def test_confirmed_excluded_end_microsecond_neighbors(point, expected):
    assert (
        clock_gap_observation_coverage(span(point, point), state(closing=True)).status == expected
    )


def test_empty_request_is_only_no_restriction_from_this_gap():
    result = clock_gap_observation_coverage(span(10, 10, False, False), state(opening=False))
    assert result == ObservationCoverage("complete", (), None)


@pytest.mark.parametrize(
    "value", ["0001-01-01T00:00:00.000000+00:00", "9999-12-31T23:59:59.999999+00:00"]
)
def test_open_gap_projection_at_calendar_extremes(value):
    gap = ClockGap(value, None, True)
    receipt = ClockGapBoundaryReceipt("gap", "opening", value, True)
    current = ClockGapDurability("gap", gap, True, False, receipt, None)
    query = HistoryInterval(value, value, True, True)
    assert clock_gap_observation_coverage(query, current) == ObservationCoverage(
        "incomplete", ("clock_discontinuity",), value
    )


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("gap_id", None, TypeError),
        ("gap_id", "", ValueError),
        ("boundary", "unknown", ValueError),
        ("boundary", None, TypeError),
        ("when", "invalid", ValueError),
        ("includes_boundary", 1, TypeError),
    ],
)
def test_receipt_validation(field, value, error):
    fields = {
        "gap_id": "gap",
        "boundary": "opening",
        "when": instant(10),
        "includes_boundary": True,
    }
    fields[field] = value
    with pytest.raises(error):
        ClockGapBoundaryReceipt(**fields)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("gap_id", "", ValueError),
        ("gap", None, TypeError),
        ("include_start", 1, TypeError),
        ("include_end", None, TypeError),
        ("opening_receipt", True, TypeError),
        ("closing_receipt", True, TypeError),
    ],
)
def test_durability_validation(field, value, error):
    with pytest.raises(error):
        replace(state(), **{field: value})


def test_nested_reconstructed_inputs_are_validated_before_any_early_complete_result():
    malformed = state()
    object.__setattr__(malformed.gap, "await_floor_recovery", 1)
    for query in (span(0, 5), span(0, 0, False, False)):
        with pytest.raises(TypeError):
            clock_gap_observation_coverage(query, malformed)
    malformed = state(closing=True)
    object.__setattr__(malformed.closing_receipt, "when", "invalid")
    with pytest.raises(ValueError):
        clock_gap_observation_coverage(span(0, 5), malformed)
    with pytest.raises(TypeError):
        clock_gap_observation_coverage(None, state())
    with pytest.raises(TypeError):
        clock_gap_observation_coverage(span(0, 5), None)


def test_receipts_and_durability_snapshots_are_immutable():
    current = state(closing=True)
    with pytest.raises(FrozenInstanceError):
        current.closing_receipt.when = instant(21)
    with pytest.raises(FrozenInstanceError):
        current.closing_receipt = None


@given(st.integers(0, 35), st.integers(0, 35), st.booleans())
def test_property_receipts_never_expand_incompleteness_or_erase_a_real_gap(a, b, opening):
    query = span(*sorted((a, b)))
    pending = clock_gap_observation_coverage(query, state(opening=opening))
    confirmed = clock_gap_observation_coverage(query, state(closing=True))
    if pending.status == "complete":
        assert confirmed.status == "complete"
    missing_points = {p for p in range(min(a, b), max(a, b) + 1) if 10 <= p < 20}
    assert (confirmed.status == "incomplete") == bool(missing_points)
    assert "continuity_metadata_unknown" not in confirmed.reasons
    if min(a, b) >= 20:
        assert confirmed.status == "complete"


def test_ca4102_forward_gap_receipt_does_not_close_the_older_frozen_gap():
    cycle = CycleClock(instant(100_000_000))
    first = cycle.next_cycle(instant(90_000_000), 0)
    second = cycle.next_cycle(instant(94_000_000), 1_000_000_000)
    old_gap = first.comparison.gap
    new_gap = second.comparison.gap
    old_state = ClockGapDurability(
        "old",
        old_gap,
        True,
        False,
        ClockGapBoundaryReceipt("old", "opening", old_gap.start, True),
        None,
    )
    new_state = ClockGapDurability(
        "new",
        new_gap,
        True,
        False,
        ClockGapBoundaryReceipt("new", "opening", new_gap.start, True),
        ClockGapBoundaryReceipt("new", "closing", new_gap.end, False),
    )
    query = span(100_000_003, 100_000_004)
    assert clock_gap_observation_coverage(query, new_state).status == "complete"
    old_result = clock_gap_observation_coverage(query, old_state)
    assert old_result == ObservationCoverage("incomplete", ("clock_discontinuity",), query.start)
    assert (
        combine_observation_coverage(
            ObservationCoverage("complete", (), None),
            (old_result, clock_gap_observation_coverage(query, new_state)),
        ).status
        == "incomplete"
    )
    assert old_gap.end is None


@pytest.mark.parametrize("end", ["invalid", instant(9)])
def test_pending_end_is_validated_without_a_closing_receipt(end):
    bad_gap = ClockGap(instant(10), end, False)
    with pytest.raises(ValueError):
        replace(state(opening=False), gap=bad_gap)
    reconstructed = state(opening=False)
    object.__setattr__(reconstructed, "gap", bad_gap)
    for query in (span(0, 5), span(0, 0, False, False)):
        with pytest.raises(ValueError):
            clock_gap_observation_coverage(query, reconstructed)
