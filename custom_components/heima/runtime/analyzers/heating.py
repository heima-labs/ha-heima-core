"""Heating pattern analyzer (P3)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..event_store import EventStore, HeimaEvent
from ..plugin_contracts import BehaviorFinding, pattern_finding
from .base import ReactionProposal
from .learning_diagnostics import build_learning_diagnostics
from .policy import HeatingLearningPolicy

_MIN_EVENTS = 10
_MIN_ECO_SESSIONS = 3
_ECO_AWAY_MINUTES = 120  # 2 hours minimum away
_ECO_REHEAT_WINDOW_MINUTES = 360  # 6 hours after return


@dataclass
class HeatingPatternAnalyzer:
    """Detect heating preferences and eco opportunities from stored heating events."""

    preference_min_events: int = _MIN_EVENTS
    preference_min_weeks: int = 2
    eco_min_sessions: int = _MIN_ECO_SESSIONS
    eco_min_weeks: int = 2
    policy: HeatingLearningPolicy | None = None

    def __post_init__(self) -> None:
        if self.policy is None:
            return
        self.preference_min_events = int(self.policy.preference_min_events)
        self.preference_min_weeks = int(self.policy.preference_min_weeks)
        self.eco_min_sessions = int(self.policy.eco_min_sessions)
        self.eco_min_weeks = int(self.policy.eco_min_weeks)

    @property
    def analyzer_id(self) -> str:
        return "HeatingPatternAnalyzer"

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: Any | None = None,
    ) -> list[BehaviorFinding]:
        del snapshot_store
        proposals = await self._analyze_proposals(event_store)
        return [
            pattern_finding(
                analyzer_id=self.analyzer_id,
                description=proposal.description,
                confidence=proposal.confidence,
                payload=proposal,
            )
            for proposal in proposals
        ]

    async def _analyze_proposals(self, event_store: EventStore) -> list[ReactionProposal]:
        raw_heating = await event_store.async_query(event_type="heating")
        heating_events: list[HeimaEvent] = [e for e in raw_heating if isinstance(e, HeimaEvent)]
        if not heating_events:
            return []
        raw_house_state = await event_store.async_query(event_type="house_state")
        house_state_events: list[HeimaEvent] = [
            e for e in raw_house_state if isinstance(e, HeimaEvent)
        ]

        proposals: list[ReactionProposal] = []
        proposals.extend(self._pattern_b_preference(heating_events))
        proposals.extend(self._pattern_a_eco(heating_events, house_state_events))
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
            if len(temps) < self.preference_min_events:
                continue
            weeks_observed = _weeks_observed(by_state_events[hs])
            if weeks_observed < self.preference_min_weeks:
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
                        "reaction_type": "heating_preference",
                        "house_state": hs,
                        "target_temperature": median,
                        "env_correlations": signal_correlations,
                        "learning_diagnostics": build_learning_diagnostics(
                            pattern_id="heating_preference",
                            analyzer_id=self.analyzer_id,
                            reaction_type="heating_preference",
                            plugin_family="heating",
                            house_state=hs,
                            observations_count=len(temps),
                            weeks_observed=weeks_observed,
                            median_target_temperature=median,
                            spread_c=round(spread, 2),
                            correlated_signal_keys=sorted(signal_correlations.keys()),
                        ),
                        "steps": [],
                    },
                )
            )
        return proposals

    # ---- Pattern A: eco opportunity ----

    def _pattern_a_eco(
        self,
        heating_events: list[HeimaEvent],
        house_state_events: list[HeimaEvent],
    ) -> list[ReactionProposal]:
        """Detect reheating after a verified away session using house-state transitions."""
        if len(heating_events) < self.eco_min_sessions or not house_state_events:
            return []

        eco_weeks_observed = _eco_weeks_observed(house_state_events)
        if eco_weeks_observed < self.eco_min_weeks:
            return []

        eco_sessions = 0
        sorted_heating = sorted(heating_events, key=lambda e: e.ts)
        for away_start, away_end in self._away_sessions(house_state_events):
            baseline = self._latest_temperature_before(sorted_heating, away_end)
            reheated = self._first_user_reheat_after(
                sorted_heating,
                away_end=away_end,
                baseline=baseline,
            )
            if reheated:
                eco_sessions += 1

        if eco_sessions < self.eco_min_sessions:
            return []

        eco_targets = [
            float(event.data["temperature_set"])
            for event in sorted_heating
            if event.context.house_state == "away"
            and event.source == "heima"
            and event.data.get("temperature_set") is not None
        ]
        eco_target_temperature = sorted(eco_targets)[len(eco_targets) // 2] if eco_targets else 16.0

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
                    "reaction_type": "heating_eco",
                    "eco_sessions_observed": eco_sessions,
                    "eco_target_temperature": eco_target_temperature,
                    "learning_diagnostics": build_learning_diagnostics(
                        pattern_id="heating_eco",
                        analyzer_id=self.analyzer_id,
                        reaction_type="heating_eco",
                        plugin_family="heating",
                        eco_sessions_observed=eco_sessions,
                        eco_target_temperature=eco_target_temperature,
                        weeks_observed=eco_weeks_observed,
                    ),
                    "steps": [],
                },
            )
        ]

    def _away_sessions(
        self, house_state_events: list[HeimaEvent]
    ) -> list[tuple[datetime, datetime]]:
        sessions: list[tuple[datetime, datetime]] = []
        active_away_start: datetime | None = None

        for event in sorted(house_state_events, key=lambda e: e.ts):
            ts = self._parse_ts(event.ts)
            if ts is None:
                continue
            from_state = str(event.data.get("from_state", ""))
            to_state = str(event.data.get("to_state", ""))

            if to_state == "away":
                active_away_start = ts
                continue

            if active_away_start is None:
                continue

            if from_state == "away" and to_state != "away":
                away_minutes = (ts - active_away_start).total_seconds() / 60
                if away_minutes >= _ECO_AWAY_MINUTES:
                    sessions.append((active_away_start, ts))
                active_away_start = None

        return sessions

    def _latest_temperature_before(
        self,
        heating_events: list[HeimaEvent],
        ts: datetime,
    ) -> float | None:
        latest_temp: float | None = None
        for event in heating_events:
            event_ts = self._parse_ts(event.ts)
            if event_ts is None:
                continue
            if event_ts >= ts:
                break
            temp = event.data.get("temperature_set")
            if temp is None:
                continue
            latest_temp = float(temp)
        return latest_temp

    def _first_user_reheat_after(
        self,
        heating_events: list[HeimaEvent],
        *,
        away_end: datetime,
        baseline: float | None,
    ) -> bool:
        if baseline is None:
            return False
        deadline = away_end + timedelta(minutes=_ECO_REHEAT_WINDOW_MINUTES)
        for event in heating_events:
            event_ts = self._parse_ts(event.ts)
            if event_ts is None or event_ts < away_end:
                continue
            if event_ts > deadline:
                return False
            if event.source != "user":
                continue
            temp = event.data.get("temperature_set")
            if temp is None:
                continue
            return float(temp) > (baseline + 0.25)
        return False

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

    @staticmethod
    def _parse_ts(ts: str) -> datetime | None:
        try:
            return datetime.fromisoformat(ts).astimezone(UTC)
        except (ValueError, TypeError):
            return None


def _weeks_observed(events: list[HeimaEvent]) -> int:
    weeks: set[tuple[int, int]] = set()
    for event in events:
        ts = HeatingPatternAnalyzer._parse_ts(event.ts)
        if ts is None:
            continue
        iso = ts.isocalendar()
        weeks.add((iso.year, iso.week))
    return len(weeks)


def _eco_weeks_observed(events: list[HeimaEvent]) -> int:
    away_related = [
        event
        for event in events
        if str(event.data.get("from_state", "")) == "away"
        or str(event.data.get("to_state", "")) == "away"
    ]
    return _weeks_observed(away_related)
