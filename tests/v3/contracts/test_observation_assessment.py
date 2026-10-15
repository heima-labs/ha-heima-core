"""Coverage decisions from explicit scope evidence; no store proof inferred."""

from datetime import timedelta
from itertools import permutations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.history_intervals import HistoryInterval
from custom_components.heima.v3.contracts.instants import format_instant, parse_instant
from custom_components.heima.v3.contracts.observation import (
    ObservationCoverage,
    combine_observation_coverage,
)
from custom_components.heima.v3.contracts.observation_gaps import (
    ObservationGap,
    assess_observation_coverage,
    clip_observation_gaps,
)

ANCHOR = "2026-10-15T12:00:00.000000+00:00"
REASONS = (
    "clock_discontinuity",
    "process_interruption",
    "queue_overflow",
    "required_stream_unavailable",
)


def instant(us):
    return format_instant(parse_instant(ANCHOR) + timedelta(microseconds=us))


def span(start, end, include_start=True, include_end=True):
    return HistoryInterval(instant(start), instant(end), include_start, include_end)


def assess(query, gaps=(), trusted=True):
    return assess_observation_coverage(query, gaps, metadata_trustworthy=trusted)


@pytest.mark.parametrize("trusted", [True, False])
@pytest.mark.parametrize("intersects", [True, False])
def test_coverage_trust_and_intersection_decision_table(trusted, intersects):
    gap = ObservationGap(span(2, 5) if intersects else span(11, 15), "queue_overflow")
    result = assess(span(0, 10), (gap,), trusted)
    reasons = ([] if trusted else ["continuity_metadata_unknown"]) + (
        ["queue_overflow"] if intersects else []
    )
    assert result == ObservationCoverage(
        "incomplete" if reasons else "complete",
        tuple(reasons),
        instant(0) if not trusted else instant(2) if intersects else None,
    )


@pytest.mark.parametrize("reason", REASONS)
@pytest.mark.parametrize(
    "interval,expected",
    [
        (span(-5, -1), None),
        (span(11, 15), None),
        (span(-5, 15), 0),
        (span(2, 5), 2),
        (span(2, 5, False, True), 3),
        (span(0, 5, False, True), 1),
    ],
)
def test_known_reason_first_missing_canonical_instant(reason, interval, expected):
    result = assess(span(0, 10), (ObservationGap(interval, reason),))
    assert result == (
        ObservationCoverage("complete", (), None)
        if expected is None
        else ObservationCoverage("incomplete", (reason,), instant(expected))
    )


@pytest.mark.parametrize("include_start", [True, False])
def test_already_open_gap_uses_request_boundary_even_with_excluded_start(include_start):
    gap = ObservationGap(span(-5, 5), "process_interruption")
    assert assess(span(0, 10, include_start, True), (gap,)) == ObservationCoverage(
        "incomplete", ("process_interruption",), instant(0)
    )


@pytest.mark.parametrize("trusted", [True, False])
@pytest.mark.parametrize("intersects", [True, False])
def test_unknown_metadata_reason_uses_request_start_only_when_relevant(trusted, intersects):
    interval = span(5, 8) if intersects else span(11, 15)
    result = assess(
        span(0, 10, False, True),
        (ObservationGap(interval, "continuity_metadata_unknown"),),
        trusted,
    )
    assert result == (
        ObservationCoverage("incomplete", ("continuity_metadata_unknown",), instant(0))
        if intersects or not trusted
        else ObservationCoverage("complete", (), None)
    )


@pytest.mark.parametrize(
    "include_start,include_end", [(False, False), (False, True), (True, False), (True, True)]
)
def test_gap_touching_endpoint_requires_actual_intersection(include_start, include_end):
    gap = ObservationGap(span(-5, 0, True, include_end), "clock_discontinuity")
    result = assess(span(0, 10, include_start, True), (gap,))
    assert result == (
        ObservationCoverage("incomplete", ("clock_discontinuity",), instant(0))
        if include_start and include_end
        else ObservationCoverage("complete", (), None)
    )


def test_reasons_are_distinct_sorted_and_first_is_independent_of_input_order():
    gaps = (
        ObservationGap(span(8, 9), "clock_discontinuity"),
        ObservationGap(span(2, 5), "queue_overflow"),
        ObservationGap(span(5, 6), "queue_overflow"),
    )
    for ordered in permutations(gaps):
        assert assess(span(0, 10), ordered) == ObservationCoverage(
            "incomplete", ("clock_discontinuity", "queue_overflow"), instant(2)
        )


@pytest.mark.parametrize("gap_start,expected", [(-1, 0), (0, 1), (1, 2)])
def test_open_gap_start_boundary_before_at_after_request(gap_start, expected):
    gap = ObservationGap(span(gap_start, 5, False, True), "process_interruption")
    assert assess(span(0, 10, False, True), (gap,)).first_incomplete_at == instant(expected)


def test_nonempty_open_lower_boundary_can_reach_maximum_without_overflow():
    maximum = "9999-12-31T23:59:59.999999+00:00"
    previous = "9999-12-31T23:59:59.999998+00:00"
    interval = HistoryInterval(previous, maximum, False, True)
    gap = ObservationGap(interval, "clock_discontinuity")
    assert assess(interval, (gap,)) == ObservationCoverage(
        "incomplete", ("clock_discontinuity",), maximum
    )
    empty = HistoryInterval(maximum, maximum, False, False)
    assert assess(empty, (ObservationGap(empty, "clock_discontinuity"),)).status == "complete"


@pytest.mark.parametrize("trusted", [False, True])
def test_empty_geometry_cannot_infer_metadata_trust(trusted):
    result = assess(span(0, 0, False, False), trusted=trusted)
    assert result == (
        ObservationCoverage("complete", (), None)
        if trusted
        else ObservationCoverage("incomplete", ("continuity_metadata_unknown",), instant(0))
    )


def test_process_and_only_required_streams_compose_without_cross_stream_contamination():
    query = span(0, 10)
    process = assess(query)
    unavailable_valve = assess(query, (ObservationGap(span(2, 8), "required_stream_unavailable"),))
    readable_light = assess(query)
    assert combine_observation_coverage(process, (readable_light,)).status == "complete"
    assert (
        combine_observation_coverage(process, (readable_light, unavailable_valve))
        == unavailable_valve
    )
    unknown_process = assess(query, trusted=False)
    assert combine_observation_coverage(unknown_process, (readable_light,)).status == "incomplete"
    # Source unavailability is independent of trusted process metadata. This
    # calculator does not select or restore older stored values.
    assert combine_observation_coverage(process, (unavailable_valve,)).reasons == (
        "required_stream_unavailable",
    )


@pytest.mark.parametrize("trusted", [None, 0, 1, "true"])
def test_trust_flag_requires_explicit_boolean(trusted):
    with pytest.raises(TypeError):
        assess(span(0, 10), trusted=trusted)


def test_trust_has_no_optimistic_default():
    with pytest.raises(TypeError):
        assess_observation_coverage(span(0, 10), ())


@pytest.mark.parametrize("trusted", [True, False])
def test_malformed_evidence_rejects_even_when_metadata_already_unknown(trusted):
    with pytest.raises(TypeError):
        assess(span(0, 10), [], trusted)
    with pytest.raises(TypeError):
        assess(span(0, 10), (None,), trusted)
    with pytest.raises(TypeError):
        assess(None, (), trusted)
    forged = object.__new__(ObservationGap)
    object.__setattr__(forged, "interval", span(20, 30))
    object.__setattr__(forged, "reason", "unknown")
    with pytest.raises(ValueError):
        assess(span(0, 10), (forged,), trusted)


@given(
    starts=st.lists(st.integers(0, 19), max_size=15),
    trusted=st.booleans(),
    reason=st.sampled_from(REASONS),
)
def test_property_assessment_matches_missing_point_union_and_metadata_override(
    starts, trusted, reason
):
    query = span(0, 20)
    gaps = tuple(ObservationGap(span(n, n + 1, False, True), reason) for n in starts)
    result = assess(query, gaps, trusted)
    missing = {n + 1 for n in starts}
    if not trusted:
        assert result.first_incomplete_at == instant(0)
        assert "continuity_metadata_unknown" in result.reasons
    elif missing:
        assert result == ObservationCoverage("incomplete", (reason,), instant(min(missing)))
    else:
        assert result == ObservationCoverage("complete", (), None)
    assert assess(query, tuple(reversed(gaps)), trusted) == result
    assert assess(query, gaps + gaps, trusted) == result
    if trusted:
        assert clip_observation_gaps(query, gaps) == gaps
