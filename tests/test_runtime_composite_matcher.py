"""Tests for reusable runtime composite matcher utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.heima.runtime.reactions.composite import (
    RuntimeCompositeMatcher,
    RuntimeCompositePatternSpec,
    RuntimeCompositeSignalSpec,
)


def test_runtime_composite_matcher_marks_ready_on_primary_only_pattern():
    hass = MagicMock()
    states = {"sensor.bathroom_humidity": "55"}
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state=states[eid]) if eid in states else None
    matcher = RuntimeCompositeMatcher(hass)
    spec = RuntimeCompositePatternSpec(
        primary=RuntimeCompositeSignalSpec(
            name="humidity",
            entity_ids=("sensor.bathroom_humidity",),
            threshold=8.0,
        ),
        correlation_window_s=600,
    )
    t1 = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 20, 8, 5, tzinfo=timezone.utc)

    first = matcher.observe(now=t1, pending_since=None, spec=spec)
    assert first.ready is False

    states["sensor.bathroom_humidity"] = "64"
    second = matcher.observe(now=t2, pending_since=first.pending_since, spec=spec)
    assert second.primary_triggered is True
    assert second.ready is True


def test_runtime_composite_matcher_waits_for_required_corroboration():
    hass = MagicMock()
    states = {
        "sensor.bathroom_humidity": "55",
        "sensor.bathroom_temperature": "21.0",
    }
    hass.states.get.side_effect = lambda eid: SimpleNamespace(state=states[eid]) if eid in states else None
    matcher = RuntimeCompositeMatcher(hass)
    spec = RuntimeCompositePatternSpec(
        primary=RuntimeCompositeSignalSpec(
            name="humidity",
            entity_ids=("sensor.bathroom_humidity",),
            threshold=8.0,
        ),
        corroborations=(
            RuntimeCompositeSignalSpec(
                name="temperature",
                entity_ids=("sensor.bathroom_temperature",),
                threshold=0.8,
                required=True,
            ),
        ),
        correlation_window_s=600,
    )
    t1 = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 20, 8, 2, tzinfo=timezone.utc)
    t3 = datetime(2026, 3, 20, 8, 4, tzinfo=timezone.utc)

    initial = matcher.observe(now=t1, pending_since=None, spec=spec)
    states["sensor.bathroom_humidity"] = "64"
    after_primary = matcher.observe(now=t2, pending_since=initial.pending_since, spec=spec)
    assert after_primary.primary_triggered is True
    assert after_primary.ready is False
    assert after_primary.pending_since == t2

    states["sensor.bathroom_temperature"] = "22.0"
    after_corroboration = matcher.observe(
        now=t3,
        pending_since=after_primary.pending_since,
        spec=spec,
    )
    assert after_corroboration.corroborations_triggered["temperature"] is True
    assert after_corroboration.ready is True
