"""Project matched durable clock-gap boundaries into request-scoped coverage."""

from dataclasses import dataclass
from typing import Literal

from ..contracts.history_intervals import HistoryInterval, intersect_history_intervals
from ..contracts.instants import EvidenceInstant, parse_instant
from ..contracts.observation import ObservationCoverage
from ..contracts.observation_gaps import ObservationGap, assess_observation_coverage
from ..runtime.clock import ClockGap


@dataclass(frozen=True, slots=True)
class ClockGapBoundaryReceipt:
    """Matched writer success, never queue admission or a runtime closing intent.

    The future writer owns issuance after durable success. This value validates
    correlation only; constructing it does not write or acknowledge anything.
    """

    gap_id: str
    boundary: Literal["opening", "closing"]
    when: EvidenceInstant
    includes_boundary: bool

    def __post_init__(self) -> None:
        if type(self.gap_id) is not str:
            raise TypeError("Clock gap id must be text")
        if not self.gap_id:
            raise ValueError("Clock gap id must be nonempty")
        if type(self.boundary) is not str:
            raise TypeError("Clock gap boundary must be text")
        if self.boundary not in ("opening", "closing"):
            raise ValueError("Unknown clock gap boundary")
        parse_instant(self.when)
        if type(self.includes_boundary) is not bool:
            raise TypeError("Boundary inclusion must be boolean")


@dataclass(frozen=True, slots=True)
class ClockGapDurability:
    """One independent intent and its exact, possibly out-of-order receipts.

    gap_id is assigned by the owner, not derived from timestamps: simultaneous
    independent corrections can have identical bounds. This is not a SQL schema.
    """

    gap_id: str
    gap: ClockGap
    include_start: bool
    include_end: bool
    opening_receipt: ClockGapBoundaryReceipt | None
    closing_receipt: ClockGapBoundaryReceipt | None

    def __post_init__(self) -> None:
        if not isinstance(self.gap, ClockGap):
            raise TypeError("Durability requires a ClockGap intent")
        if type(self.gap.await_floor_recovery) is not bool:
            raise TypeError("Clock gap end rule must be boolean")
        end = self.gap.start if self.gap.end is None else self.gap.end
        HistoryInterval(self.gap.start, end, self.include_start, self.include_end)
        # Validate the id even if neither boundary has a receipt yet.
        ClockGapBoundaryReceipt(self.gap_id, "opening", self.gap.start, self.include_start)
        self._validate_receipt(self.opening_receipt, "opening", self.gap.start, self.include_start)
        self._validate_receipt(self.closing_receipt, "closing", self.gap.end, self.include_end)

    def _validate_receipt(
        self,
        receipt: ClockGapBoundaryReceipt | None,
        boundary: Literal["opening", "closing"],
        when: EvidenceInstant | None,
        included: bool,
    ) -> None:
        if receipt is None:
            return
        if not isinstance(receipt, ClockGapBoundaryReceipt):
            raise TypeError("Clock gap proof requires a boundary receipt")
        validated = ClockGapBoundaryReceipt(
            receipt.gap_id, receipt.boundary, receipt.when, receipt.includes_boundary
        )
        expected = (
            ClockGapBoundaryReceipt(self.gap_id, boundary, when, included)
            if when is not None
            else None
        )
        if validated != expected:
            raise ValueError("Receipt does not match the clock gap boundary")


def clock_gap_observation_coverage(
    request: HistoryInterval, durability: ClockGapDurability
) -> ObservationCoverage:
    """Return only this gap's restriction, to combine with mandatory process coverage.

    A pending closing intent never bounds a potentially open gap. Only a matching
    closing receipt permits reads after that end to escape this gap's restriction.
    This function does not certify the completeness of the entire timeline.
    """
    requested = intersect_history_intervals(request, request)
    if not isinstance(durability, ClockGapDurability):
        raise TypeError("Clock gap coverage requires explicit durability state")
    state = ClockGapDurability(
        durability.gap_id,
        durability.gap,
        durability.include_start,
        durability.include_end,
        durability.opening_receipt,
        durability.closing_receipt,
    )
    if requested is None:
        return ObservationCoverage("complete", (), None)
    gap = state.gap
    if gap.start > request.end:
        return ObservationCoverage("complete", (), None)
    end = request.end
    include_end = True
    if state.closing_receipt is not None:
        assert gap.end is not None  # A matching closing receipt was validated above.
        end = gap.end
        include_end = state.include_end
    extent = HistoryInterval(gap.start, end, state.include_start, include_end)
    if intersect_history_intervals(request, extent) is None:
        return ObservationCoverage("complete", (), None)
    unknown = state.opening_receipt is None or (
        gap.end is not None and state.closing_receipt is None
    )
    return assess_observation_coverage(
        request,
        (ObservationGap(extent, "clock_discontinuity"),),
        metadata_trustworthy=not unknown,
    )
