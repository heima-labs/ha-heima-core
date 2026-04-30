"""Built-in correlation analyzer placeholder."""

from __future__ import annotations

from typing import Any

from ..event_store import EventStore
from ..plugin_contracts import BehaviorFinding


class CorrelationAnalyzer:
    """Placeholder for Phase B correlation routing integration."""

    @property
    def analyzer_id(self) -> str:
        return "CorrelationAnalyzer"

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: Any | None = None,
    ) -> list[BehaviorFinding]:
        del event_store, snapshot_store
        return []
