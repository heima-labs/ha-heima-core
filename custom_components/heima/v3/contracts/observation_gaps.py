"""Explicit bounded gap evidence, without scope selection or durability claims."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from .history_intervals import HistoryInterval, intersect_history_intervals
from .instants import format_instant, parse_instant
from .observation import ObservationCoverage, ObservationGapReason


@dataclass(frozen=True, slots=True)
class ObservationGap:
    """One known gap with caller-declared endpoints in a caller-selected scope.

    This is a calculation input, not a persisted record or proof of acknowledgement.
    Independent corrections may have identical bounds and must remain distinguishable
    by their owner; clipping neither merges nor deduplicates them.
    """

    interval: HistoryInterval
    reason: ObservationGapReason

    def __post_init__(self) -> None:
        if not isinstance(self.interval, HistoryInterval):
            raise TypeError("Observation gap requires a HistoryInterval")
        # Reuse the authoritative geometry and closed-reason validators, including
        # reconstructed inputs; no second reason list or endpoint convention.
        intersect_history_intervals(self.interval, self.interval)
        ObservationCoverage("incomplete", (self.reason,), self.interval.start)


def clip_observation_gaps(
    request: HistoryInterval, gaps: tuple[ObservationGap, ...]
) -> tuple[ObservationGap, ...]:
    """Clip known gaps to one request, preserving input order and multiplicity.

    The caller selects the process/required-stream scope and supplies bounded gap
    extents explicitly. An empty result says only that these known gaps do not
    intersect: it cannot certify complete observation, trustworthy metadata, a
    durable end, stream availability or retention. Open ends and uncertain boundary
    extents must be resolved conservatively by the future timeline owner.
    """
    return tuple(
        ObservationGap(overlap, gap.reason) for gap, overlap in _gap_intersections(request, gaps)
    )


def assess_observation_coverage(
    request: HistoryInterval,
    gaps: tuple[ObservationGap, ...],
    *,
    metadata_trustworthy: bool,
) -> ObservationCoverage:
    """Assess one selected scope from exhaustive bounded evidence supplied by its owner.

    Supply original extents, not pre-clipped gaps: an earlier opening affects the
    conservative first boundary. Trust includes the owner's durable-boundary checks. This
    pure calculation cannot obtain or acknowledge that proof. Assess the process
    and each required stream separately, then use combine_observation_coverage.
    Pending/open extents, availability and overflow validity belong to the evidence
    producer; they must not be omitted to obtain an optimistic complete result.
    """
    if type(metadata_trustworthy) is not bool:
        raise TypeError("Continuity metadata trust must be boolean")
    reasons: set[ObservationGapReason] = set()
    first = None
    for gap, overlap in _gap_intersections(request, gaps):
        reasons.add(gap.reason)
        if gap.interval.start < request.start:
            # §4.4 explicitly uses the request boundary for an already open gap.
            candidate = request.start
        elif overlap.include_start:
            candidate = overlap.start
        else:
            # A nonempty intersection with an excluded start has a representable
            # first microsecond inside it, even at the calendar's upper boundary.
            candidate = format_instant(parse_instant(overlap.start) + timedelta(microseconds=1))
        first = candidate if first is None else min(first, candidate)
    if not metadata_trustworthy:
        reasons.add("continuity_metadata_unknown")
    if "continuity_metadata_unknown" in reasons:
        # Unknown continuity uses the request start, never a guessed missing event.
        first = request.start
    if first is None:
        return ObservationCoverage("complete", (), None)
    return ObservationCoverage("incomplete", tuple(sorted(reasons)), first)


def _gap_intersections(
    request: HistoryInterval, gaps: tuple[ObservationGap, ...]
) -> Iterator[tuple[ObservationGap, HistoryInterval]]:
    """Retain the original opening for §4.4's already-open-gap boundary rule."""
    request_intersection = intersect_history_intervals(request, request)
    if type(gaps) is not tuple:
        raise TypeError("Observation gaps must be an immutable tuple")
    for gap in gaps:
        if not isinstance(gap, ObservationGap):
            raise TypeError("Clipping requires ObservationGap inputs")
        validated = ObservationGap(gap.interval, gap.reason)
        if request_intersection is not None:
            overlap = intersect_history_intervals(request_intersection, validated.interval)
            if overlap is not None:
                yield validated, overlap
