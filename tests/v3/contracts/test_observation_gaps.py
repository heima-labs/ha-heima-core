"""Request clipping of known gap evidence; no completeness inferred from absence."""

from dataclasses import FrozenInstanceError
from datetime import timedelta
from itertools import product

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.history_intervals import HistoryInterval
from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.observation_gaps import (
    ObservationGap,
    clip_observation_gaps,
)

ANCHOR = "2026-10-15T12:00:00.000000+00:00"
REASONS = (
    "clock_discontinuity",
    "continuity_metadata_unknown",
    "process_interruption",
    "queue_overflow",
    "required_stream_unavailable",
)


def instant(us):
    return format_instant(parse_instant(ANCHOR) + timedelta(microseconds=us))


def span(start, end, include_start=True, include_end=True):
    return HistoryInterval(instant(start), instant(end), include_start, include_end)


@pytest.mark.parametrize("reason", REASONS)
@pytest.mark.parametrize(
    "gap_interval,expected",
    [
        (span(-5, -1), ()),
        (span(11, 15), ()),
        (span(-5, 15), (span(0, 10),)),
        (span(2, 8, False, True), (span(2, 8, False, True),)),
        (span(-5, 5, True, False), (span(0, 5, True, False),)),
        (span(5, 15, False, True), (span(5, 10, False, True),)),
    ],
)
def test_request_gap_decision_table_preserves_closed_reason(reason, gap_interval, expected):
    gap = ObservationGap(gap_interval, reason)
    assert clip_observation_gaps(span(0, 10), (gap,)) == tuple(
        ObservationGap(interval, reason) for interval in expected
    )
    assert gap.interval is gap_interval


@pytest.mark.parametrize("at_start", [True, False])
@pytest.mark.parametrize("request_includes,gap_includes", list(product([False, True], repeat=2)))
def test_touching_gap_endpoint_decision_table_and_mcdc(at_start, request_includes, gap_includes):
    query = span(
        0, 10, request_includes if at_start else True, True if at_start else request_includes
    )
    interval = span(-5, 0, True, gap_includes) if at_start else span(10, 15, gap_includes, True)
    result = clip_observation_gaps(query, (ObservationGap(interval, "process_interruption"),))
    expected = (
        (
            ObservationGap(
                span(0 if at_start else 10, 0 if at_start else 10), "process_interruption"
            ),
        )
        if request_includes and gap_includes
        else ()
    )
    assert result == expected


@pytest.mark.parametrize(
    "query,interval,expected",
    [
        (span(0, 0), span(-1, 1), (span(0, 0),)),
        (span(0, 0, False, True), span(-1, 1), ()),
        (span(0, 1, False, False), span(-1, 2), ()),
        (span(0, 2, False, False), span(-1, 3), (span(0, 2, False, False),)),
        (span(0, 10), span(5, 5), (span(5, 5),)),
        (span(0, 10), span(5, 5, True, False), ()),
    ],
)
def test_empty_point_and_microsecond_boundaries(query, interval, expected):
    gap = ObservationGap(interval, "queue_overflow")
    assert clip_observation_gaps(query, (gap,)) == tuple(
        ObservationGap(item, "queue_overflow") for item in expected
    )


def test_independent_gaps_keep_order_reasons_and_multiplicity():
    a = ObservationGap(span(5, 15), "clock_discontinuity")
    b = ObservationGap(span(-5, 5), "process_interruption")
    c = ObservationGap(span(5, 15), "queue_overflow")
    before = (a, b, a, c)
    result = clip_observation_gaps(span(0, 10), before)
    assert result == (
        ObservationGap(span(5, 10), "clock_discontinuity"),
        ObservationGap(span(0, 5), "process_interruption"),
        ObservationGap(span(5, 10), "clock_discontinuity"),
        ObservationGap(span(5, 10), "queue_overflow"),
    )
    assert before == (a, b, a, c)
    assert a.interval == span(5, 15)
    assert b.interval == span(-5, 5)


def test_no_known_gaps_returns_only_an_empty_evidence_tuple():
    assert clip_observation_gaps(span(0, 10), ()) == ()


@pytest.mark.parametrize(
    "value", ["0001-01-01T00:00:00.000000+00:00", "9999-12-31T23:59:59.999999+00:00"]
)
def test_calendar_extreme_point_clipping(value):
    interval = HistoryInterval(value, value, True, True)
    gap = ObservationGap(interval, "clock_discontinuity")
    assert clip_observation_gaps(interval, (gap,)) == (gap,)


@pytest.mark.parametrize(
    "reason,error", [("unknown", ValueError), (None, TypeError), (1, TypeError)]
)
def test_invalid_reason_rejected_by_construction_and_clipping(reason, error):
    interval = span(0, 10)
    with pytest.raises(error):
        ObservationGap(interval, reason)
    forged = object.__new__(ObservationGap)
    object.__setattr__(forged, "interval", interval)
    object.__setattr__(forged, "reason", reason)
    # Validate even when query is empty or the forged gap is outside the query.
    for query in (span(0, 0, False, False), span(20, 30)):
        with pytest.raises(error):
            clip_observation_gaps(query, (forged,))


@pytest.mark.parametrize("interval", [None, {}, (instant(0), instant(10))])
def test_wrong_interval_type_rejected(interval):
    with pytest.raises(TypeError):
        ObservationGap(interval, "queue_overflow")


@pytest.mark.parametrize(
    "field,value,error", [("start", instant(11), ValueError), ("include_end", 1, TypeError)]
)
def test_reconstructed_nested_interval_is_revalidated(field, value, error):
    malformed = span(0, 10)
    object.__setattr__(malformed, field, value)
    with pytest.raises(error):
        ObservationGap(malformed, "queue_overflow")
    gap = object.__new__(ObservationGap)
    object.__setattr__(gap, "interval", malformed)
    object.__setattr__(gap, "reason", "queue_overflow")
    with pytest.raises(error):
        clip_observation_gaps(span(20, 30), (gap,))


def test_input_shapes_and_immutable_result():
    gap = ObservationGap(span(0, 10), "process_interruption")
    with pytest.raises(FrozenInstanceError):
        gap.reason = "queue_overflow"
    with pytest.raises(FrozenInstanceError):
        gap.interval = span(2, 3)
    for gaps in (None, [], [gap], iter((gap,))):
        with pytest.raises(TypeError):
            clip_observation_gaps(span(0, 10), gaps)
    for query in (None, {}, "interval"):
        with pytest.raises(TypeError):
            clip_observation_gaps(query, ())
    with pytest.raises(TypeError):
        clip_observation_gaps(span(0, 10), (None,))
    with pytest.raises(TypeError):
        clip_observation_gaps(span(0, 0, False, False), (None,))


spans = st.builds(
    lambda bounds, left, right: span(*sorted(bounds), left, right),
    st.tuples(st.integers(-10, 10), st.integers(-10, 10)),
    st.booleans(),
    st.booleans(),
)


def members(interval):
    return {
        n
        for n in range(-10, 11)
        if (
            interval.start < instant(n) or (interval.start == instant(n) and interval.include_start)
        )
        and (instant(n) < interval.end or (instant(n) == interval.end and interval.include_end))
    }


@given(
    query=spans,
    gaps=st.lists(st.builds(ObservationGap, spans, st.sampled_from(REASONS)), max_size=15),
)
def test_property_clipped_evidence_matches_independent_membership_and_is_idempotent(query, gaps):
    selected = tuple(gaps)
    actual = clip_observation_gaps(query, selected)
    expected = [
        (members(gap.interval) & members(query), gap.reason)
        for gap in selected
        if members(gap.interval) & members(query)
    ]
    assert [(members(gap.interval), gap.reason) for gap in actual] == expected
    assert clip_observation_gaps(query, actual) == actual
