"""Presence pattern analyzer (P2)."""

from __future__ import annotations

from dataclasses import dataclass

from ..event_store import EventStore, HeimaEvent
from .base import ReactionProposal

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class PresencePatternAnalyzer:
    """Detect repeated arrival windows from stored presence events."""

    min_arrivals: int = 5
    pre_condition_min: int = 20
    window_half_min: int = 15

    @property
    def analyzer_id(self) -> str:
        return "PresencePatternAnalyzer"

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        events = await event_store.async_query(event_type="presence")
        arrivals = [e for e in events if isinstance(e, HeimaEvent) and e.data.get("transition") == "arrive"]
        proposals: list[ReactionProposal] = []
        for weekday in range(7):
            day_samples = sorted(
                e.context.minute_of_day for e in arrivals if e.context.weekday == weekday
            )
            if len(day_samples) < self.min_arrivals:
                continue

            median = day_samples[len(day_samples) // 2]
            p25 = day_samples[len(day_samples) // 4]
            p75 = day_samples[(3 * len(day_samples)) // 4]
            iqr = p75 - p25
            confidence = max(0.3, 1.0 - (iqr / 120.0))

            proposals.append(
                ReactionProposal(
                    analyzer_id=self.analyzer_id,
                    reaction_type="presence_preheat",
                    description=(
                        f"{_WEEKDAY_NAMES[weekday]}: typical arrival around "
                        f"{self._hhmm(median)}"
                        + (f" (± {iqr // 2} min)" if iqr > 0 else "")
                        + "."
                    ),
                    confidence=float(confidence),
                    suggested_reaction_config={
                        "reaction_class": "PresencePatternReaction",
                        "weekday": weekday,
                        "median_arrival_min": median,
                        "window_half_min": self.window_half_min,
                        "pre_condition_min": self.pre_condition_min,
                        "steps": [],
                    },
                )
            )

        return proposals

    @staticmethod
    def _hhmm(minute_of_day: int) -> str:
        hour = minute_of_day // 60
        minute = minute_of_day % 60
        return f"{hour:02d}:{minute:02d}"
