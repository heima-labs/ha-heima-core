"""Explicit bounded gap evidence, without scope selection or durability claims."""

from dataclasses import dataclass

from .history_intervals import HistoryInterval, intersect_history_intervals
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
    request_intersection = intersect_history_intervals(request, request)
    if type(gaps) is not tuple:
        raise TypeError("Observation gaps must be an immutable tuple")
    clipped = []
    for gap in gaps:
        if not isinstance(gap, ObservationGap):
            raise TypeError("Clipping requires ObservationGap inputs")
        validated = ObservationGap(gap.interval, gap.reason)
        if request_intersection is not None:
            overlap = intersect_history_intervals(request_intersection, validated.interval)
            if overlap is not None:
                clipped.append(ObservationGap(overlap, validated.reason))
    return tuple(clipped)
