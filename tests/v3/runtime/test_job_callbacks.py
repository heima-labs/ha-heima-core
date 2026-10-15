"""Shared owner fault isolation and one-shot dispatcher integration."""

from dataclasses import FrozenInstanceError

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.timing import AtJob
from custom_components.heima.v3.runtime.clock import ExecutionClockReading
from custom_components.heima.v3.runtime.job_callbacks import (
    JobCallbackFault,
    invoke_job_callback,
    isolate_job_callback,
)
from custom_components.heima.v3.runtime.timing import AtJobScheduler

NOW = "2026-10-14T12:00:00.000000+00:00"
JOB = AtJob("id", "owner", "2026-10-14T12:00:01.000000+00:00", "label", "elapsed")


def test_success_invokes_owner_once_without_diagnostic():
    delivered = []
    assert invoke_job_callback(JOB, delivered.append) is None
    faults = []
    isolate_job_callback(delivered.append, faults.append)(JOB)
    assert delivered == [JOB, JOB]
    assert faults == []


@pytest.mark.parametrize("exception", [ValueError("bad owner input"), RuntimeError("owner failed")])
def test_fault_preserves_job_type_and_message_without_exception_reference(exception):
    def fail(job):
        assert job is JOB
        raise exception

    fault = invoke_job_callback(JOB, fail)
    assert fault == JobCallbackFault(JOB, type(exception).__qualname__, str(exception))
    assert isinstance(fault.message, str)
    with pytest.raises(FrozenInstanceError):
        fault.message = "changed"
    faults = []
    isolate_job_callback(fail, faults.append)(JOB)
    assert faults == [fault]


@pytest.mark.parametrize("exception", [KeyboardInterrupt(), SystemExit(3)])
def test_process_control_is_not_converted_into_owner_diagnostic(exception):
    def stop(job):
        raise exception

    faults = []
    with pytest.raises(type(exception)) as raised:
        isolate_job_callback(stop, faults.append)(JOB)
    assert raised.value is exception
    assert faults == []


def test_infrastructure_sink_failure_is_not_swallowed():
    def owner(job):
        raise ValueError("owner error")

    def sink(fault):
        raise RuntimeError("diagnostic infrastructure failed")

    with pytest.raises(RuntimeError, match="diagnostic infrastructure failed"):
        isolate_job_callback(owner, sink)(JOB)


@pytest.mark.parametrize("callback,report", [(None, lambda fault: None), (lambda job: None, None)])
def test_wrapper_rejects_missing_boundary_ports(callback, report):
    with pytest.raises(TypeError):
        isolate_job_callback(callback, report)


class Timer:
    def __init__(self):
        self.handles = []

    def call_later(self, seconds, callback):
        handle = Handle(callback)
        self.handles.append(handle)
        return handle


class Handle:
    def __init__(self, callback):
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def test_failing_one_shot_is_consumed_once_and_other_owner_continues():
    timer = Timer()
    scheduler = AtJobScheduler(timer)
    faults = []
    delivered = []

    def failing(job):
        raise ValueError("one-shot failed")

    now = ExecutionClockReading(NOW, NOW)
    scheduler.register(JOB, now, isolate_job_callback(failing, faults.append))
    other = AtJob("id", "other", JOB.due, "other label", "elapsed")
    scheduler.register(other, now, isolate_job_callback(delivered.append, faults.append))
    timer.handles[0].callback()
    timer.handles[0].callback()
    timer.handles[1].callback()
    assert faults == [JobCallbackFault(JOB, "ValueError", "one-shot failed")]
    assert delivered == [other]
    assert scheduler.pending_jobs == ()


@given(message=st.text(), fails=st.booleans())
def test_fault_boundary_preserves_arbitrary_owner_message_and_single_delivery(message, fails):
    delivered = []
    faults = []

    def callback(job):
        delivered.append(job)
        if fails:
            raise ValueError(message)

    isolate_job_callback(callback, faults.append)(JOB)
    assert delivered == [JOB]
    assert faults == ([JobCallbackFault(JOB, "ValueError", message)] if fails else [])
