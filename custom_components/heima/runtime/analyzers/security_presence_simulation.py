"""Security presence simulation analyzer placeholder."""

from __future__ import annotations

from .base import ReactionProposal
from ..event_store import EventStore


class SecurityPresenceSimulationAnalyzer:
    """No-op analyzer placeholder for the security presence simulation family.

    The first MVP is admin-authored and runtime-driven from accepted lighting reactions.
    Learned proposal generation will be introduced later inside this family.
    """

    analyzer_id = "SecurityPresenceSimulationAnalyzer"

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        return []
