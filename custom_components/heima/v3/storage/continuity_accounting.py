"""Pure accounting of a complete accepted prefix, without advancing a watermark."""

from dataclasses import dataclass
from typing import Literal

from ..contracts.instants import EvidenceInstant, parse_instant


def _sequence(value: int, minimum: int) -> None:
    if type(value) is not int:
        raise TypeError("Accounting sequence must be a non-boolean integer")
    if value < minimum:
        raise ValueError("Accounting sequence is below its minimum")


@dataclass(frozen=True, slots=True)
class ContinuityAccountingBarrier:
    """Full chosen acceptance boundary in one coordinator's process-local namespace.

    Every accepted fact, independent audit and continuity item receives a sequence.
    The owner chooses the full boundary; an intake ordinal is not its substitute.
    This is an internal accounting snapshot, not AppendOrder or a persisted schema.
    """

    through_sequence: int
    observed_at: EvidenceInstant

    def __post_init__(self) -> None:
        _sequence(self.through_sequence, 0)
        parse_instant(self.observed_at)


@dataclass(frozen=True, slots=True)
class DurabilityRange:
    """Inclusive sequence range with one verified accounting outcome.

    written means every item committed; loss_declared means every item's loss has
    a durable declaration, not that its payload was written. The future owner must
    obtain matched receipts before constructing either resolved outcome. A range
    cannot be inferred from the minimum and maximum of sparse acknowledgements.
    """

    first_sequence: int
    last_sequence: int
    outcome: Literal["pending", "written", "loss_pending", "loss_declared"]

    def __post_init__(self) -> None:
        _sequence(self.first_sequence, 1)
        _sequence(self.last_sequence, self.first_sequence)
        if type(self.outcome) is not str:
            raise TypeError("Durability outcome must be text")
        if self.outcome not in ("pending", "written", "loss_pending", "loss_declared"):
            raise ValueError("Unknown durability outcome")


def continuity_barrier_accounted(
    barrier: ContinuityAccountingBarrier,
    ranges: tuple[DurabilityRange, ...],
    *,
    previously_accounted_through: int,
    inventory_complete: bool,
    producer_blocked_at: EvidenceInstant | None,
) -> bool:
    """Check the prefix proof needed by a future continuity-watermark transaction.

    The previous prefix must already have verified accounting in this coordinator's
    namespace. All later accepted items through the barrier need contiguous resolved
    evidence. Sorted disjoint ranges may batch proof without retaining payloads.
    Unknown inventory or a known failed audit construction also blocks the barrier.
    This check neither issues receipts nor writes/advances the durable watermark;
    overall observation coverage and global-overflow closure remain separate checks.
    """
    if not isinstance(barrier, ContinuityAccountingBarrier):
        raise TypeError("Accounting requires a continuity barrier")
    barrier = ContinuityAccountingBarrier(barrier.through_sequence, barrier.observed_at)
    _sequence(previously_accounted_through, 0)
    if previously_accounted_through > barrier.through_sequence:
        raise ValueError("Previous accounting prefix exceeds the chosen barrier")
    if type(inventory_complete) is not bool:
        raise TypeError("Accounting inventory completeness must be boolean")
    if producer_blocked_at is not None:
        parse_instant(producer_blocked_at)
    if type(ranges) is not tuple:
        raise TypeError("Accounting ranges must be an immutable tuple")
    ready = inventory_complete
    if producer_blocked_at is not None:
        if producer_blocked_at <= barrier.observed_at:
            ready = False
    cursor = previously_accounted_through
    previous_end = 0
    for item in ranges:
        if not isinstance(item, DurabilityRange):
            raise TypeError("Accounting requires DurabilityRange inputs")
        interval = DurabilityRange(item.first_sequence, item.last_sequence, item.outcome)
        if interval.first_sequence <= previous_end:
            raise ValueError("Accounting ranges must be ordered and disjoint")
        previous_end = interval.last_sequence
        if interval.last_sequence <= previously_accounted_through:
            continue
        if interval.first_sequence > barrier.through_sequence:
            continue
        start = max(interval.first_sequence, previously_accounted_through + 1)
        end = min(interval.last_sequence, barrier.through_sequence)
        if end < start:
            continue
        if start != cursor + 1:
            ready = False
        cursor = end
        if interval.outcome in ("pending", "loss_pending"):
            ready = False
    return ready and cursor == barrier.through_sequence
