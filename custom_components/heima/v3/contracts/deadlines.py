"""Exact canonical-decimal deadline construction (Layer 0 §3.1, CA4-100)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from .canonical_json import canonical_json_bytes
from .instants import EvidenceInstant, format_instant, parse_instant
from .timing import Window


@dataclass(frozen=True, slots=True)
class Unrepresentable:
    """Rejected calendar sum; retained inputs let the owner emit its diagnostic."""

    anchor: EvidenceInstant
    duration: Window


def derive_instant(
    anchor: EvidenceInstant, duration: Window, *, strictly_after: bool = False
) -> EvidenceInstant | Unrepresentable:
    """Return the first microsecond at/after the exact sum, or strictly after it.

    Integer ratio arithmetic avoids both float loss and Decimal context rounding.
    The strict variant belongs to consumers such as Layer-2 source-age expiry.
    """
    start = parse_instant(anchor)
    if not isinstance(duration, Window):
        raise TypeError("Deadline construction requires Window")
    if type(strictly_after) is not bool:
        raise TypeError("Strict deadline selection must be boolean")
    validated = Window(duration.seconds)
    numerator, denominator = Decimal(
        canonical_json_bytes(validated.seconds).decode("ascii")
    ).as_integer_ratio()
    whole, remainder = divmod(numerator * 1_000_000, denominator)
    if strictly_after or remainder:
        whole += 1
    remaining = datetime.max.replace(tzinfo=UTC) - start
    available = (remaining.days * 86_400 + remaining.seconds) * 1_000_000 + remaining.microseconds
    if whole > available:
        return Unrepresentable(anchor, validated)
    return format_instant(start + timedelta(microseconds=whole))
