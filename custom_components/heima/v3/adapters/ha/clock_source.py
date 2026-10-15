"""Host clock capture at the adapter boundary; domain modules never read time."""

from datetime import UTC, datetime
from time import monotonic_ns

from ...contracts.instants import format_instant
from ...runtime.timing_clock import ClockSample


class SystemClockSource:
    def sample(self) -> ClockSample:
        # These are sequential readings, not an atomic pair or interpolated time.
        wall = format_instant(datetime.now(UTC))
        return ClockSample(wall, monotonic_ns())
