"""Observation coverage values and composition for a single historical request."""

from dataclasses import dataclass
from typing import Literal, get_args

from .instants import EvidenceInstant, parse_instant

type ObservationCoverageStatus = Literal["complete", "incomplete"]
type ObservationGapReason = Literal[
    "clock_discontinuity",
    "continuity_metadata_unknown",
    "process_interruption",
    "queue_overflow",
    "required_stream_unavailable",
]

_GAP_REASONS = frozenset(get_args(ObservationGapReason.__value__))


@dataclass(frozen=True, slots=True)
class ObservationCoverage:
    status: ObservationCoverageStatus
    reasons: tuple[ObservationGapReason, ...]
    first_incomplete_at: EvidenceInstant | None

    def __post_init__(self) -> None:
        if type(self.status) is not str:
            raise TypeError("Observation status must be text")
        if self.status not in ("complete", "incomplete"):
            raise ValueError("Unknown observation status")
        if type(self.reasons) is not tuple:
            raise TypeError("Observation reasons must be an immutable tuple")
        for reason in self.reasons:
            if type(reason) is not str:
                raise TypeError("Observation reason must be text")
            if reason not in _GAP_REASONS:
                raise ValueError("Unknown observation gap reason")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("Observation reasons must be distinct and ASCII-sorted")
        if self.status == "complete":
            if self.reasons:
                raise ValueError("Complete observation cannot have gap reasons")
            if self.first_incomplete_at is not None:
                raise ValueError("Complete observation cannot have an incomplete instant")
        else:
            if not self.reasons:
                raise ValueError("Incomplete observation requires a gap reason")
            if self.first_incomplete_at is None:
                raise ValueError("Incomplete observation requires its first missing instant")
            parse_instant(self.first_incomplete_at)


def combine_observation_coverage(
    process: ObservationCoverage, required_streams: tuple[ObservationCoverage, ...] = ()
) -> ObservationCoverage:
    """Combine already request-clipped coverage; process metadata is mandatory.

    The caller selects only required streams and computes their interval coverage,
    including endpoint semantics and pending durable boundaries. This function
    neither reads storage nor certifies an acknowledgement or retention coverage.
    """
    process = _validated_coverage(process)
    if type(required_streams) is not tuple:
        raise TypeError("Required-stream coverage must be an immutable tuple")
    reasons = set(process.reasons)
    first = process.first_incomplete_at
    for stream in required_streams:
        validated = _validated_coverage(stream)
        reasons.update(validated.reasons)
        candidate = validated.first_incomplete_at
        if candidate is not None:
            if first is None:
                first = candidate
            else:
                first = min(first, candidate)
    if first is None:
        return ObservationCoverage("complete", (), None)
    return ObservationCoverage("incomplete", tuple(sorted(reasons)), first)


def _validated_coverage(value: ObservationCoverage) -> ObservationCoverage:
    if not isinstance(value, ObservationCoverage):
        raise TypeError("Coverage composition requires ObservationCoverage")
    return ObservationCoverage(value.status, value.reasons, value.first_incomplete_at)
