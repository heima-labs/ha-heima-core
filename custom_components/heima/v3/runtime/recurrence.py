"""Single-arm recurrence planning, with explicit execution references and admission."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from ..contracts.deadlines import Unrepresentable, derive_instant
from ..contracts.instants import format_instant, parse_instant
from ..contracts.timing import AtJob, CronEntry, IntervalRecurrence, WeeklyRecurrence
from .clock import ExecutionClockReading
from .timing import AtJobScheduler, JobCallback


def plan_interval_job(entry: CronEntry, now: ExecutionClockReading) -> AtJob | Unrepresentable:
    """Plan one elapsed arm against the captured cycle-instant clock."""
    if not isinstance(entry, CronEntry):
        raise TypeError("Interval planning requires CronEntry")
    if not isinstance(entry.pattern, IntervalRecurrence):
        raise TypeError("Interval planning requires IntervalRecurrence")
    if not isinstance(now, ExecutionClockReading):
        raise TypeError("Interval planning requires paired execution references")
    pattern = IntervalRecurrence(entry.pattern.interval)
    validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
    reading = ExecutionClockReading(now.wall, now.cycle_instant)
    due = derive_instant(reading.cycle_instant, pattern.interval)
    if isinstance(due, Unrepresentable):
        return due
    return AtJob(validated.job_id, validated.owner, due, validated.label, "elapsed")


def register_interval_job(
    scheduler: AtJobScheduler, entry: CronEntry, now: ExecutionClockReading, callback: JobCallback
) -> Unrepresentable | None:
    """Arm one interval, or return its diagnostic input without changing timers.

    Runtime diagnostic publication belongs to the caller. This is one registration,
    not a persistent recurrence service or automatic re-arm lifecycle.
    """
    planned = plan_interval_job(entry, now)
    if isinstance(planned, Unrepresentable):
        return planned
    scheduler.register(planned, now, callback)
    return None


def plan_weekly_job(entry: CronEntry, now: ExecutionClockReading, time_zone: ZoneInfo) -> AtJob:
    """Find the first permitted UTC due strictly after the captured wall reading.

    This plans one arm, without timers, persistence or owner execution. A standing
    recurrence service must also track served occurrences during clock/zone changes.
    """
    if not isinstance(entry, CronEntry):
        raise TypeError("Weekly planning requires CronEntry")
    if not isinstance(entry.pattern, WeeklyRecurrence):
        raise TypeError("Weekly planning requires WeeklyRecurrence")
    if not isinstance(now, ExecutionClockReading):
        raise TypeError("Weekly planning requires paired execution references")
    if not isinstance(time_zone, ZoneInfo):
        raise TypeError("Weekly planning requires the configured ZoneInfo")
    # Revalidate staging shapes before applying calendar arithmetic.
    pattern = WeeklyRecurrence(entry.pattern.weekdays, entry.pattern.hour, entry.pattern.minute)
    validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
    reading = ExecutionClockReading(now.wall, now.cycle_instant)
    wall = parse_instant(reading.wall)
    try:
        local_day = wall.astimezone(time_zone).date()
        # Today through the same weekday next week, inclusive; not a time horizon.
        for offset in range(8):
            day = local_day + timedelta(days=offset)
            if day.weekday() in pattern.weekdays:
                requested = datetime(day.year, day.month, day.day, pattern.hour, pattern.minute)
                due = _civil_due(requested, time_zone)
                if due > wall:
                    return AtJob(
                        validated.job_id,
                        validated.owner,
                        format_instant(due),
                        validated.label,
                        "wall_clock",
                    )
    except OverflowError as error:
        raise ValueError("Weekly due is outside the supported calendar") from error
    raise ValueError("No future weekly due in the supported calendar")


def _civil_due(requested: datetime, time_zone: ZoneInfo) -> datetime:
    first = requested.replace(tzinfo=time_zone, fold=0).astimezone(UTC)
    if first.astimezone(time_zone).replace(tzinfo=None) == requested:
        # Also selects fold=0 if the requested local minute occurs twice.
        return first
    second = requested.replace(tzinfo=time_zone, fold=1).astimezone(UTC)
    lower, upper = sorted((first, second))
    # The imaginary local time maps to opposite sides of the forward gap under
    # the two folds. Locate its first valid instant, not a same-minute roll-forward.
    while upper - lower > timedelta(microseconds=1):
        delta = upper - lower
        microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
        middle = lower + timedelta(microseconds=microseconds // 2)
        if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
            upper = middle
        else:
            lower = middle
    return upper
