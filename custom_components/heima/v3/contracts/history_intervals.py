"""Bounded historical interval geometry with explicitly declared endpoints."""

from dataclasses import dataclass

from .instants import EvidenceInstant, parse_instant


@dataclass(frozen=True, slots=True)
class HistoryInterval:
    start: EvidenceInstant
    end: EvidenceInstant
    include_start: bool
    include_end: bool

    def __post_init__(self) -> None:
        start = parse_instant(self.start)
        end = parse_instant(self.end)
        if end < start:
            raise ValueError("History interval end precedes start")
        if type(self.include_start) is not bool:
            raise TypeError("Start inclusion must be boolean")
        if type(self.include_end) is not bool:
            raise TypeError("End inclusion must be boolean")

    @property
    def empty(self) -> bool:
        duration = parse_instant(self.end) - parse_instant(self.start)
        microseconds = (
            duration.days * 86_400 + duration.seconds
        ) * 1_000_000 + duration.microseconds
        excluded = int(not self.include_start) + int(not self.include_end)
        return microseconds < excluded


def intersect_history_intervals(
    left: HistoryInterval, right: HistoryInterval
) -> HistoryInterval | None:
    """Return the exact intersection on EvidenceInstant's microsecond grid.

    Preserve endpoint meaning. This handles bounded geometry only, without choosing
    query conventions, gap scope, trust or whether a boundary has durable proof.
    """
    left = _validated_interval(left)
    right = _validated_interval(right)
    if left.start > right.start:
        start, include_start = left.start, left.include_start
    elif right.start > left.start:
        start, include_start = right.start, right.include_start
    else:
        start = left.start
        include_start = left.include_start and right.include_start
    if left.end < right.end:
        end, include_end = left.end, left.include_end
    elif right.end < left.end:
        end, include_end = right.end, right.include_end
    else:
        end = left.end
        include_end = left.include_end and right.include_end
    if end < start:
        return None
    result = HistoryInterval(start, end, include_start, include_end)
    if result.empty:
        return None
    return result


def _validated_interval(value: HistoryInterval) -> HistoryInterval:
    if not isinstance(value, HistoryInterval):
        raise TypeError("Historical intersection requires HistoryInterval")
    return HistoryInterval(value.start, value.end, value.include_start, value.include_end)
