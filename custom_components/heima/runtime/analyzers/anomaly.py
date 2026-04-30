"""Built-in anomaly analyzer placeholder."""

from __future__ import annotations

from typing import Any

from ..event_store import EventStore
from ..plugin_contracts import BehaviorFinding


class AnomalyAnalyzer:
    """Placeholder for Phase B anomaly routing integration."""

    @property
    def analyzer_id(self) -> str:
        return "AnomalyAnalyzer"

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: Any | None = None,
    ) -> list[BehaviorFinding]:
        del event_store, snapshot_store
        return []
