"""System clock capture stays at the adapter, with canonical UTC output."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from time import monotonic_ns

import pytest

from custom_components.heima.v3.adapters.ha import clock_source
from custom_components.heima.v3.contracts.instants import parse_instant


def test_exact_adapter_capture_and_immutable_sample(monkeypatch):
    captured = []

    class Wall:
        @staticmethod
        def now(zone):
            captured.append(zone)
            return datetime(2026, 10, 15, 12, 0, 0, 123456, tzinfo=UTC)

    monkeypatch.setattr(clock_source, "datetime", Wall)
    monkeypatch.setattr(clock_source, "monotonic_ns", lambda: 123456789)
    sample = clock_source.SystemClockSource().sample()
    assert captured == [UTC]
    assert sample.wall == "2026-10-15T12:00:00.123456+00:00"
    assert sample.monotonic_ns == 123456789
    with pytest.raises(FrozenInstanceError):
        sample.wall = "changed"


def test_real_host_clock_emits_canonical_wall_and_raw_monotonic():
    before = monotonic_ns()
    sample = clock_source.SystemClockSource().sample()
    after = monotonic_ns()
    assert parse_instant(sample.wall).tzinfo is UTC
    assert before <= sample.monotonic_ns <= after
