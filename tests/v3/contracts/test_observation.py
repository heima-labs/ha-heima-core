"""Closed observation results and conservative required-stream composition."""

from dataclasses import FrozenInstanceError
from enum import StrEnum
from itertools import permutations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.observation import (
    ObservationCoverage,
    combine_observation_coverage,
)

START = "2026-10-15T12:00:00.000000+00:00"
LATER = "2026-10-15T12:00:01.000000+00:00"
REASONS = (
    "clock_discontinuity",
    "continuity_metadata_unknown",
    "process_interruption",
    "queue_overflow",
    "required_stream_unavailable",
)


def complete():
    return ObservationCoverage("complete", (), None)


def missing(reason="required_stream_unavailable", when=START):
    return ObservationCoverage("incomplete", (reason,), when)


class Text(StrEnum):
    COMPLETE = "complete"
    CLOCK = "clock_discontinuity"


@pytest.mark.parametrize(
    "status,reasons,first,error",
    [
        (None, (), None, TypeError),
        (True, (), None, TypeError),
        (Text.COMPLETE, (), None, TypeError),
        ("unknown", (), None, ValueError),
        ("COMPLETE", (), None, ValueError),
        ("complete", [], None, TypeError),
        ("incomplete", ("made_up",), START, ValueError),
        ("incomplete", (Text.CLOCK,), START, TypeError),
        ("incomplete", (1,), START, TypeError),
        ("complete", ("clock_discontinuity",), None, ValueError),
        ("complete", (), START, ValueError),
        ("incomplete", (), START, ValueError),
        ("incomplete", ("clock_discontinuity",), None, ValueError),
        ("incomplete", ("clock_discontinuity", "clock_discontinuity"), START, ValueError),
        ("incomplete", ("queue_overflow", "clock_discontinuity"), START, ValueError),
        ("incomplete", ("clock_discontinuity",), "2026-10-15T12:00:00Z", ValueError),
        ("incomplete", ("clock_discontinuity",), True, TypeError),
    ],
)
def test_rejects_invalid_or_contradictory_result(status, reasons, first, error):
    with pytest.raises(error):
        ObservationCoverage(status, reasons, first)


@pytest.mark.parametrize("reason", REASONS)
def test_every_declared_reason_has_valid_immutable_result(reason):
    result = missing(reason)
    assert (result.status, result.reasons, result.first_incomplete_at) == (
        "incomplete",
        (reason,),
        START,
    )
    with pytest.raises(FrozenInstanceError):
        result.status = "complete"
    with pytest.raises(FrozenInstanceError):
        result.reasons = ()
    with pytest.raises(FrozenInstanceError):
        result.first_incomplete_at = None


@pytest.mark.parametrize(
    "process,streams,status,reasons,first",
    [
        (complete(), (), "complete", (), None),
        (complete(), (complete(),), "complete", (), None),
        (
            missing("clock_discontinuity"),
            (complete(),),
            "incomplete",
            ("clock_discontinuity",),
            START,
        ),
        (complete(), (missing(),), "incomplete", ("required_stream_unavailable",), START),
        (
            missing("queue_overflow", LATER),
            (missing(),),
            "incomplete",
            ("queue_overflow", "required_stream_unavailable"),
            START,
        ),
        (
            missing("queue_overflow"),
            (missing(when=LATER),),
            "incomplete",
            ("queue_overflow", "required_stream_unavailable"),
            START,
        ),
        (
            missing("queue_overflow"),
            (missing("queue_overflow"),),
            "incomplete",
            ("queue_overflow",),
            START,
        ),
        (
            missing("continuity_metadata_unknown"),
            (complete(),),
            "incomplete",
            ("continuity_metadata_unknown",),
            START,
        ),
    ],
)
def test_process_and_required_stream_decision_table(process, streams, status, reasons, first):
    result = combine_observation_coverage(process, streams)
    assert (result.status, result.reasons, result.first_incomplete_at) == (status, reasons, first)


def test_empty_stream_set_cannot_hide_unknown_process_metadata():
    process = missing("continuity_metadata_unknown")
    assert combine_observation_coverage(process) == process
    with pytest.raises(TypeError):
        combine_observation_coverage(None)


@pytest.mark.parametrize("streams", [None, [], [complete()], (None,), ("complete",)])
def test_invalid_required_stream_shape_is_not_treated_as_complete(streams):
    with pytest.raises(TypeError):
        combine_observation_coverage(complete(), streams)


def test_reconstructed_invalid_result_rejected_at_composition_boundary():
    invalid = object.__new__(ObservationCoverage)
    object.__setattr__(invalid, "status", "complete")
    object.__setattr__(invalid, "reasons", ("clock_discontinuity",))
    object.__setattr__(invalid, "first_incomplete_at", START)
    with pytest.raises(ValueError):
        combine_observation_coverage(invalid)
    with pytest.raises(ValueError):
        combine_observation_coverage(complete(), (invalid,))


def test_ordering_never_changes_reasons_or_earliest_missing_instant():
    streams = (missing("queue_overflow", LATER), complete(), missing())
    results = [
        combine_observation_coverage(complete(), tuple(order)) for order in permutations(streams)
    ]
    assert all(result == results[0] for result in results)


coverage_values = st.one_of(
    st.just(complete()),
    st.builds(
        ObservationCoverage,
        st.just("incomplete"),
        st.sets(st.sampled_from(REASONS), min_size=1).map(lambda reasons: tuple(sorted(reasons))),
        st.sampled_from((START, LATER)),
    ),
)


@given(process=coverage_values, streams=st.lists(coverage_values, max_size=10).map(tuple))
def test_composition_is_conservative_idempotent_and_order_independent(process, streams):
    result = combine_observation_coverage(process, streams)
    inputs = (process,) + streams
    incomplete = [item for item in inputs if item.status == "incomplete"]
    assert (result.status == "complete") == (not incomplete)
    if incomplete:
        assert result.first_incomplete_at == min(item.first_incomplete_at for item in incomplete)
        assert set(result.reasons) == {reason for item in incomplete for reason in item.reasons}
        assert result.reasons == tuple(sorted(set(result.reasons)))
    assert combine_observation_coverage(result, (result,)) == result
    assert combine_observation_coverage(process, tuple(reversed(streams))) == result
    assert combine_observation_coverage(result, (complete(),)) == result
