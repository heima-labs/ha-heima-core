"""Layer-0 immutable timing definitions, with no scheduling or HA operations."""

from dataclasses import dataclass
from math import isfinite
from typing import Literal, cast
from zoneinfo import ZoneInfo

from .canonical_json import canonical_json_bytes
from .instants import EvidenceInstant, parse_instant


def validate_duration(value: object) -> float:
    """Normalize a positive finite non-boolean duration, including fractions."""
    if type(value) not in (int, float):
        raise TypeError("Duration must be a non-boolean number")
    try:
        seconds = float(cast(int | float, value))
    except OverflowError as error:
        raise ValueError("Duration must be finite") from error
    if not isfinite(seconds) or seconds <= 0:
        raise ValueError("Duration must be positive and finite")
    return seconds


@dataclass(frozen=True, slots=True)
class Window:
    seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "seconds", validate_duration(self.seconds))

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes({"seconds": self.seconds})


@dataclass(frozen=True, slots=True)
class AtJob:
    job_id: str
    owner: str
    due: EvidenceInstant
    label: str
    basis: Literal["elapsed", "wall_clock"]

    def __post_init__(self) -> None:
        _validate_text(self.job_id)
        _validate_text(self.owner)
        _validate_text(self.label)
        parse_instant(self.due)
        if type(self.basis) is not str or self.basis not in ("elapsed", "wall_clock"):
            raise ValueError("Job basis must be elapsed or wall_clock")


@dataclass(frozen=True, slots=True)
class WeeklyRecurrence:
    weekdays: frozenset[int]
    hour: int
    minute: int = 0

    def __post_init__(self) -> None:
        if type(self.weekdays) is not frozenset:
            raise TypeError("Weekdays must be immutable")
        if not self.weekdays:
            raise ValueError("Weekdays must not be empty")
        for day in self.weekdays:
            _validate_civil_component(day, 6)
        _validate_civil_component(self.hour, 23)
        _validate_civil_component(self.minute, 59)

    def matches(self, when: EvidenceInstant, time_zone: ZoneInfo) -> bool:
        """Historical classification, including either DST-fold occurrence.

        The configured installation zone is explicit. This does not compute a
        next due or apply the scheduler's single-firing/gap policy.
        """
        if not isinstance(time_zone, ZoneInfo):
            raise TypeError("A configured ZoneInfo is required")
        local = parse_instant(when).astimezone(time_zone)
        return (
            local.weekday() in self.weekdays
            and local.hour == self.hour
            and local.minute == self.minute
        )


@dataclass(frozen=True, slots=True)
class IntervalRecurrence:
    interval: Window

    def __post_init__(self) -> None:
        if not isinstance(self.interval, Window):
            raise TypeError("Interval recurrence requires Window")
        object.__setattr__(self, "interval", Window(self.interval.seconds))


@dataclass(frozen=True, slots=True)
class CronEntry:
    job_id: str
    owner: str
    pattern: IntervalRecurrence
    label: str

    def __post_init__(self) -> None:
        _validate_text(self.job_id)
        _validate_text(self.owner)
        _validate_text(self.label)
        if not isinstance(self.pattern, IntervalRecurrence):
            raise TypeError("Cron entry requires IntervalRecurrence")


@dataclass(frozen=True, slots=True)
class CalendarWindow:
    start: EvidenceInstant
    end: EvidenceInstant
    summary: str
    source_entity: str

    def __post_init__(self) -> None:
        start = parse_instant(self.start)
        end = parse_instant(self.end)
        if end <= start:
            raise ValueError("Calendar end must follow start")
        _validate_text(self.summary)
        _validate_text(self.source_entity)

    def contains(self, now: EvidenceInstant) -> bool:
        parse_instant(now)
        return self.start <= now < self.end


def _validate_civil_component(value: object, maximum: int) -> None:
    if type(value) is not int:
        raise TypeError("Civil time components must be non-boolean integers")
    if not 0 <= value <= maximum:
        raise ValueError("Civil time component outside its range")


def _validate_text(value: object) -> None:
    if type(value) is not str:
        raise TypeError("Contract text must be str")
