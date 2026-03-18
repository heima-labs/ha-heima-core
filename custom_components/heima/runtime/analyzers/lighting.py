"""Lighting pattern analyzer (P9)."""

from __future__ import annotations

from datetime import UTC, datetime

from ..event_store import EventStore, HeimaEvent
from .base import ReactionProposal

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MIN_OCCURRENCES = 5
_MIN_WEEKS = 2


class LightingPatternAnalyzer:
    """Detect recurring on/off schedule patterns from stored lighting events.

    Pattern key: (room_id, action, weekday)
    Algorithm: same IQR-based confidence as PresencePatternAnalyzer.

    Two-gate minimum:
      - ≥ MIN_OCCURRENCES events per key
      - ≥ MIN_WEEKS distinct ISO weeks represented
        (prevents a single consistent week from generating a spurious proposal)
    """

    @property
    def analyzer_id(self) -> str:
        return "LightingPatternAnalyzer"

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        raw = await event_store.async_query(event_type="lighting")
        events: list[HeimaEvent] = [
            e for e in raw
            if isinstance(e, HeimaEvent) and e.source == "user"
        ]
        if not events:
            return []

        # Group by (room_id, action, weekday)
        groups: dict[tuple[str, str, int], list[HeimaEvent]] = {}
        for e in events:
            room_id = e.data.get("room_id", "")
            action = e.data.get("action", "")
            weekday = e.context.weekday
            if not room_id or action not in ("on", "off"):
                continue
            key = (room_id, action, weekday)
            groups.setdefault(key, []).append(e)

        proposals: list[ReactionProposal] = []
        for (room_id, action, weekday), group in groups.items():
            if len(group) < _MIN_OCCURRENCES:
                continue
            if not self._spans_min_weeks(group):
                continue

            samples = sorted(e.context.minute_of_day for e in group)
            n = len(samples)
            median = samples[n // 2]
            p25 = samples[n // 4]
            p75 = samples[(3 * n) // 4]
            iqr = p75 - p25
            confidence = max(0.3, 1.0 - iqr / 120.0)

            proposals.append(
                ReactionProposal(
                    analyzer_id=self.analyzer_id,
                    reaction_type="lighting_schedule",
                    description=(
                        f"{room_id}: lights {action} every "
                        f"{_WEEKDAY_NAMES[weekday]} around {self._hhmm(median)}"
                        + (f" (± {iqr // 2} min)" if iqr > 0 else "")
                        + "."
                    ),
                    confidence=float(confidence),
                    suggested_reaction_config={
                        "reaction_class": "LightingScheduleReaction",
                        "room_id": room_id,
                        "action": action,
                        "scene": None,
                        "weekday": weekday,
                        "scheduled_min": median,
                        "window_half_min": 10,
                        "house_state_filter": None,
                    },
                )
            )

        return proposals

    @staticmethod
    def _spans_min_weeks(events: list[HeimaEvent]) -> bool:
        """Return True if events span at least MIN_WEEKS distinct ISO calendar weeks."""
        weeks: set[tuple[int, int]] = set()
        for e in events:
            try:
                dt = datetime.fromisoformat(e.ts).astimezone(UTC)
                iso = dt.isocalendar()
                weeks.add((iso.year, iso.week))
            except (ValueError, TypeError):
                pass
        return len(weeks) >= _MIN_WEEKS

    @staticmethod
    def _hhmm(minute_of_day: int) -> str:
        return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"
