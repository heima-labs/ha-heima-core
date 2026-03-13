"""HeimaBehavior base class — all hooks are no-ops by default."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..contracts import ApplyPlan
    from ..snapshot import DecisionSnapshot


class HeimaBehavior:
    """Base class for Heima behaviors.

    Subclass and override only the hooks you need.
    All hooks are no-ops by default so partial implementations are safe.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def behavior_id(self) -> str:
        """Unique stable identifier for this behavior."""
        return type(self).__name__

    # ------------------------------------------------------------------
    # Hooks (called by engine in evaluation cycle order)
    # ------------------------------------------------------------------

    def on_snapshot(self, snapshot: "DecisionSnapshot") -> None:
        """Called after the canonical snapshot is computed.

        Use for: reacting to state, emitting custom events, updating
        behavior-internal state. Must NOT modify snapshot (it is frozen).
        """

    def apply_filter(
        self, plan: "ApplyPlan", snapshot: "DecisionSnapshot"
    ) -> "ApplyPlan":
        """Called after the apply plan is built (and after constraints filter).

        Return the plan (possibly modified) or the same plan unchanged.
        To block a step, return a new ApplyPlan with the step's blocked_by set.
        Default: return plan unchanged.
        """
        return plan

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_options_reloaded(self, options: dict[str, Any]) -> None:
        """Called when integration options are reloaded.

        Use for: re-reading behavior config from options.
        """

    def diagnostics(self) -> dict[str, Any]:
        """Return behavior-specific diagnostics dict."""
        return {}
