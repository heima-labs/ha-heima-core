"""HeimaReaction base class — contributor attivo al piano di apply."""

from __future__ import annotations

from typing import Any

from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot


class HeimaReaction:
    """Base class for reactive behaviors.

    A reaction observes a chronological history of DecisionSnapshot objects
    and may return additional ApplyStep instances to be merged into the
    current evaluation's apply plan.

    The returned steps pass through the existing constraint layer and are
    indistinguishable from domain-generated steps at apply time, except for
    the `source` field (set automatically by the engine dispatcher).

    Subclasses override `evaluate`. All other methods have safe no-op defaults.
    """

    @property
    def reaction_id(self) -> str:
        """Stable identifier for this reaction. Defaults to the class name."""
        return self.__class__.__name__

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        """Return ApplyStep instances to inject into the current plan.

        Args:
            history: Chronological list of recent snapshots (oldest first,
                     newest = most recent). May be empty on the first cycle.

        Returns:
            List of ApplyStep objects. Return [] (default) if the reaction
            does not fire in the current cycle.
        """
        return []

    def scheduled_jobs(self, entry_id: str) -> "dict[str, Any]":
        """Return keyed ScheduledRuntimeJob instances this reaction wants scheduled.

        Called by the engine after each evaluation to sync timed jobs with the
        RuntimeScheduler. Return {} (default) if this reaction has no scheduled jobs.
        """
        return {}

    def on_options_reloaded(self, options: dict[str, Any]) -> None:
        """Called when the config entry options change. No-op by default."""

    def reset_learning_state(self) -> None:
        """Reset reaction-local state that affects learning semantics."""

    def diagnostics(self) -> dict[str, Any]:
        """Return a dict of diagnostic data for this reaction. Empty by default."""
        return {}
