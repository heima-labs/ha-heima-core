"""Standing interval rules over the shared single-arm monotonic dispatcher."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..contracts.deadlines import Unrepresentable
from ..contracts.timing import AtJob, CronEntry, IntervalRecurrence
from .clock import ExecutionClockReading
from .job_callbacks import JobCallbackFault, invoke_job_callback
from .recurrence import plan_interval_job
from .timing import AtJobScheduler, JobCallback, JobKey


@dataclass(frozen=True, slots=True)
class IntervalRearmFault:
    entry: CronEntry
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class IntervalDeadlineRejected:
    entry: CronEntry
    deadline: Unrepresentable


type RecurrenceDiagnostic = JobCallbackFault | IntervalRearmFault | IntervalDeadlineRejected


class RecurrenceDiagnosticSink(Protocol):
    def __call__(self, diagnostic: RecurrenceDiagnostic) -> None:
        """Log/publish synchronously without raising; never wait for durable I/O."""


@dataclass(frozen=True, slots=True)
class _Registration:
    entry: CronEntry
    callback: JobCallback


class IntervalRecurrences:
    """Process-local lifecycle; durable standing definitions are supplied by the owner.

    Clock capture, timer dispatch and diagnostics are explicit ports on one event
    loop. A fresh capture follows each callback, so late work is not caught up.
    Admission errors propagate to the caller; accepted rules survive a failed
    replacement. This service cancels only its own registrations during shutdown.
    """

    def __init__(
        self,
        scheduler: AtJobScheduler,
        read_clock: Callable[[], ExecutionClockReading],
        report: RecurrenceDiagnosticSink,
    ) -> None:
        self._scheduler = scheduler
        self._read_clock = read_clock
        self._report = report
        self._registrations: dict[JobKey, _Registration] = {}

    @property
    def entries(self) -> tuple[CronEntry, ...]:
        return tuple(registration.entry for registration in self._registrations.values())

    def register(self, entry: CronEntry, callback: JobCallback) -> Unrepresentable | None:
        if not isinstance(entry, CronEntry):
            raise TypeError("Interval lifecycle requires CronEntry")
        if not isinstance(entry.pattern, IntervalRecurrence):
            raise TypeError("Interval lifecycle requires IntervalRecurrence")
        if not callable(callback):
            raise TypeError("Interval lifecycle requires an owner callback")
        validated = CronEntry(
            entry.job_id, entry.owner, IntervalRecurrence(entry.pattern.interval), entry.label
        )
        now = self._read_clock()
        planned = plan_interval_job(validated, now)
        if isinstance(planned, Unrepresentable):
            self._report(IntervalDeadlineRejected(validated, planned))
            return planned
        registration = _Registration(validated, callback)
        self._arm(registration, planned, now)
        self._registrations[(validated.owner, validated.job_id)] = registration
        return None

    def cancel(self, owner: str, job_id: str) -> None:
        registration = self._registrations.pop((owner, job_id), None)
        if registration is not None:
            self._scheduler.cancel(owner, job_id)

    def stop(self) -> None:
        for owner, job_id in tuple(self._registrations):
            self.cancel(owner, job_id)

    def _arm(self, registration: _Registration, job: AtJob, now: ExecutionClockReading) -> None:
        self._scheduler.register(job, now, lambda fired: self._deliver(registration, fired))

    def _deliver(self, registration: _Registration, job: AtJob) -> None:
        try:
            fault = invoke_job_callback(job, registration.callback)
            if fault is not None:
                self._report(fault)
        finally:
            key = (registration.entry.owner, registration.entry.job_id)
            if self._registrations.get(key) is registration:
                diagnostic = self._rearm(registration)
                if diagnostic is not None:
                    self._report(diagnostic)

    def _rearm(self, registration: _Registration) -> RecurrenceDiagnostic | None:
        try:
            now = self._read_clock()
            planned = plan_interval_job(registration.entry, now)
            if isinstance(planned, Unrepresentable):
                return IntervalDeadlineRejected(registration.entry, planned)
            self._arm(registration, planned, now)
        except Exception as error:
            return IntervalRearmFault(registration.entry, type(error).__qualname__, str(error))
        return None
