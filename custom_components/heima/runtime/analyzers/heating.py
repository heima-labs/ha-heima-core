"""Heating pattern analyzer (P3)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..event_store import EventStore, HeimaEvent
from .base import ReactionProposal

_MIN_EVENTS = 10
_MIN_ECO_SESSIONS = 3
_ECO_AWAY_MINUTES = 120  # 2 hours minimum away


class HeatingPatternAnalyzer:
    """Detect heating preferences and eco opportunities from stored heating events."""

    @property
    def analyzer_id(self) -> str:
        return "HeatingPatternAnalyzer"

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        raw = await event_store.async_query(event_type="heating")
        events: list[HeimaEvent] = [e for e in raw if isinstance(e, HeimaEvent)]
        if not events:
            return []

        proposals: list[ReactionProposal] = []
        proposals.extend(self._pattern_b_preference(events))
        proposals.extend(self._pattern_a_eco(events))
        return proposals

    # ---- Pattern B: temperature preference per house_state ----

    def _pattern_b_preference(self, events: list[HeimaEvent]) -> list[ReactionProposal]:
        # Only user-initiated setpoints reflect actual preference (see spec §0.5)
        user_events = [e for e in events if e.source == "user"]

        by_state: dict[str, list[float]] = defaultdict(list)
        by_state_events: dict[str, list[HeimaEvent]] = defaultdict(list)
        for e in user_events:
            temp = e.data.get("temperature_set")
            if temp is None:
                continue
            hs = e.context.house_state
            by_state[hs].append(float(temp))
            by_state_events[hs].append(e)

        proposals = []
        for hs, temps in by_state.items():
            if len(temps) < _MIN_EVENTS:
                continue
            s = sorted(temps)
            median = s[len(s) // 2]
            spread = max(s) - min(s)
            confidence = max(0.3, 1.0 - spread / 5.0)

            signal_correlations = self._compute_signal_correlations(by_state_events[hs])

            proposals.append(
                ReactionProposal(
                    analyzer_id=self.analyzer_id,
                    reaction_type="heating_preference",
                    description=(
                        f"Typical heating setpoint for '{hs}': {median:.1f}°C "
                        f"(spread {spread:.1f}°C, {len(temps)} observations)."
                    ),
                    confidence=confidence,
                    suggested_reaction_config={
                        "reaction_class": "HeatingPreferenceReaction",
                        "house_state": hs,
                        "target_temperature": median,
                        "env_correlations": signal_correlations,
                        "steps": [],
                    },
                )
            )
        return proposals

    # ---- Pattern A: eco opportunity ----

    def _pattern_a_eco(self, events: list[HeimaEvent]) -> list[ReactionProposal]:
        """Detect sessions where user raised setpoint after a long away period."""
        if len(events) < _MIN_ECO_SESSIONS:
            return []

        eco_sessions = 0
        prev_house_state: str | None = None
        prev_ts: str | None = None

        for e in events:
            hs = e.context.house_state
            if prev_house_state is None:
                prev_house_state = hs
                prev_ts = e.ts
                continue

            if prev_house_state == "away" and hs != "away" and e.source == "user":
                if prev_ts is not None:
                    from datetime import UTC, datetime
                    try:
                        t0 = datetime.fromisoformat(prev_ts).astimezone(UTC)
                        t1 = datetime.fromisoformat(e.ts).astimezone(UTC)
                        away_minutes = (t1 - t0).total_seconds() / 60
                        if away_minutes >= _ECO_AWAY_MINUTES:
                            eco_sessions += 1
                    except (ValueError, TypeError):
                        pass

            prev_house_state = hs
            prev_ts = e.ts

        if eco_sessions < _MIN_ECO_SESSIONS:
            return []

        return [
            ReactionProposal(
                analyzer_id=self.analyzer_id,
                reaction_type="heating_eco",
                description=(
                    f"Observed {eco_sessions} sessions where you raised heating after "
                    f"being away for >{_ECO_AWAY_MINUTES // 60}h. "
                    "Consider an explicit eco heating branch."
                ),
                confidence=0.7,
                suggested_reaction_config={
                    "reaction_class": "HeatingEcoReaction",
                    "eco_sessions_observed": eco_sessions,
                    "steps": [],
                },
            )
        ]

    # ---- Signal correlation ----

    def _compute_signal_correlations(self, events: list[HeimaEvent]) -> dict[str, Any]:
        """For numeric signal keys with enough data, compute low/high bucket median setpoints."""
        if not events:
            return {}

        key_values: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for e in events:
            temp = e.data.get("temperature_set")
            if temp is None:
                continue
            for k, v in e.context.signals.items():
                try:
                    key_values[k].append((float(v), float(temp)))
                except (ValueError, TypeError):
                    pass

        correlations: dict[str, Any] = {}
        for key, pairs in key_values.items():
            if len(pairs) < _MIN_EVENTS:
                continue
            env_vals = sorted(p[0] for p in pairs)
            p33 = env_vals[len(env_vals) // 3]
            p67 = env_vals[2 * len(env_vals) // 3]

            low_temps = [p[1] for p in pairs if p[0] <= p33]
            high_temps = [p[1] for p in pairs if p[0] >= p67]
            if not low_temps or not high_temps:
                continue

            low_median = sorted(low_temps)[len(low_temps) // 2]
            high_median = sorted(high_temps)[len(high_temps) // 2]
            delta = abs(high_median - low_median)
            if delta < 0.5:
                continue

            correlations[key] = {
                "low_env_median_setpoint": low_median,
                "high_env_median_setpoint": high_median,
                "delta": round(delta, 2),
            }

        return correlations
