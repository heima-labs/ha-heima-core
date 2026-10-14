"""Layer-1 canonical instant shared by every Layer-0 temporal contract."""

import re
from datetime import UTC, datetime
from typing import NewType, cast

EvidenceInstant = NewType("EvidenceInstant", str)
_INSTANT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}\+00:00")


def parse_instant(value: object) -> datetime:
    """Validate exact canonical text and return a temporary UTC datetime."""
    if type(value) is not str:
        raise TypeError("Instant must be canonical text")
    if _INSTANT.fullmatch(value) is None:
        raise ValueError("Instant must have six fractional digits and +00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.isoformat(timespec="microseconds") != value:
        raise ValueError("Instant must not require normalization")
    return parsed


def validate_instant(value: object) -> EvidenceInstant:
    """Return a semantic string type only after format/calendar validation."""
    parse_instant(value)
    return EvidenceInstant(cast(str, value))


def format_instant(value: datetime) -> EvidenceInstant:
    """Explicit producer normalization; never repair a contract-field string."""
    if not isinstance(value, datetime):
        raise TypeError("Producer instant must be datetime")
    if value.utcoffset() is None:
        raise ValueError("Producer instant must have a timezone")
    try:
        text = value.astimezone(UTC).isoformat(timespec="microseconds")
    except (ValueError, OverflowError) as error:
        raise ValueError("Producer instant is outside the supported calendar") from error
    return EvidenceInstant(text)
