"""One owner callback fault boundary, reusable by one-shot and recurring jobs."""

from collections.abc import Callable
from dataclasses import dataclass

from ..contracts.timing import AtJob
from .timing import JobCallback


@dataclass(frozen=True, slots=True)
class JobCallbackFault:
    job: AtJob
    error_type: str
    message: str


def invoke_job_callback(job: AtJob, callback: JobCallback) -> JobCallbackFault | None:
    """Consume an ordinary owner exception; infrastructure reporting stays outside.

    No exception/traceback is retained in the returned diagnostic. Process control
    exceptions (BaseException) still propagate.
    """
    try:
        callback(job)
    except Exception as error:
        return JobCallbackFault(job, type(error).__qualname__, str(error))
    return None


def isolate_job_callback(
    callback: JobCallback, report: Callable[[JobCallbackFault], None]
) -> JobCallback:
    """Wrap an owner for the shared dispatcher; report must log/publish without raising."""
    if not callable(callback):
        raise TypeError("Fault isolation requires an owner callback")
    if not callable(report):
        raise TypeError("Fault isolation requires a diagnostic sink")

    def isolated(job: AtJob) -> None:
        fault = invoke_job_callback(job, callback)
        if fault is not None:
            report(fault)

    return isolated
