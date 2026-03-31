"""PresencePatternReaction — learns arrival times and pre-conditions the home."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction

if TYPE_CHECKING:
    from .learning import ILearningBackend


def _minute_of_day(dt: datetime) -> int:
    """Return minutes elapsed since midnight (0–1439)."""
    return dt.hour * 60 + dt.minute


@dataclass
class _ArrivalRecord:
    weekday: int       # 0 = Monday, 6 = Sunday
    minute_of_day: int  # 0–1439 (local time)


class PresencePatternReaction(HeimaReaction):
    """Learns typical daily arrival times and fires pre-conditioning steps.

    On each evaluation cycle the reaction:

    1. **Learns**: if the previous snapshot had `anyone_home=False` and the
       current snapshot has `anyone_home=True`, it records the arrival time
       (local weekday + minute-of-day) from the snapshot timestamp.

    2. **Triggers**: if nobody is currently home, the pattern for today's
       weekday is established (>= `min_arrivals` recorded), and the current
       time is within `pre_condition_min` minutes of the expected arrival
       window, the reaction fires `steps`.

    The expected arrival window is computed as:
        [median_arrival - window_half_min, median_arrival + window_half_min]
    using all recorded arrivals for that weekday.

    Midnight wrap-around is handled: if the pre-conditioning target falls
    after 23:59, the next weekday's window is checked.

    Args:
        steps: ApplyStep instances to inject when pre-conditioning triggers.
        min_arrivals: Minimum arrivals recorded for a weekday before its
                      pattern activates. Default: 5.
        window_half_min: Half-width of the arrival window in minutes.
                         Default: 15 (→ ±15 min around the median).
        pre_condition_min: Lead time before expected arrival to start
                           pre-conditioning. Default: 20.
        max_arrivals: Maximum stored arrival records (oldest evicted when
                      full). Default: 100.
        reaction_id: Optional stable identifier. Defaults to class name.
        learning_backend: Optional ILearningBackend for confidence tracking.
        confidence_threshold: Minimum confidence required to fire. Default: 0.5.
    """

    def __init__(
        self,
        *,
        steps: list[ApplyStep],
        min_arrivals: int = 5,
        window_half_min: int = 15,
        pre_condition_min: int = 20,
        max_arrivals: int = 100,
        reaction_id: str | None = None,
        learning_backend: "ILearningBackend | None" = None,
        confidence_threshold: float = 0.5,
        initial_arrivals: list[_ArrivalRecord] | None = None,
    ) -> None:
        self._steps = list(steps)
        self._min_arrivals = min_arrivals
        self._window_half_min = window_half_min
        self._pre_condition_min = pre_condition_min
        self._max_arrivals = max_arrivals
        self._reaction_id = reaction_id or self.__class__.__name__
        self._backend = learning_backend
        self._confidence_threshold = confidence_threshold
        self._arrivals: list[_ArrivalRecord] = list(initial_arrivals) if initial_arrivals else []
        self._fire_count: int = 0
        self._suppressed_count: int = 0
        self._last_fired_ts: float | None = None

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        # --- Step 1: detect arrival and learn ---
        if len(history) >= 2:
            prev, curr = history[-2], history[-1]
            if not prev.anyone_home and curr.anyone_home:
                self._record_arrival(curr.ts)

        if not history:
            return []

        current = history[-1]

        # No pre-conditioning needed when someone is already home
        if current.anyone_home:
            if self._backend is not None:
                self._backend.observe(self._reaction_id, fired=False, steps=[])
            return []

        # --- Step 2: confidence check ---
        if self._backend is not None:
            if self._backend.confidence(self._reaction_id) < self._confidence_threshold:
                self._suppressed_count += 1
                self._backend.observe(self._reaction_id, fired=False, steps=[])
                return []

        # --- Step 3: pre-conditioning trigger ---
        if not self._should_pre_condition(current.ts):
            if self._backend is not None:
                self._backend.observe(self._reaction_id, fired=False, steps=[])
            return []

        steps = list(self._steps)
        if self._backend is not None:
            self._backend.observe(self._reaction_id, fired=True, steps=steps)
        self._fire_count += 1
        self._last_fired_ts = time.monotonic()
        return steps

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_arrival(self, ts: str) -> None:
        dt = self._parse_ts(ts)
        if dt is None:
            return
        record = _ArrivalRecord(weekday=dt.weekday(), minute_of_day=_minute_of_day(dt))
        if len(self._arrivals) >= self._max_arrivals:
            self._arrivals.pop(0)
        self._arrivals.append(record)

    def _get_typical_window(self, weekday: int) -> tuple[int, int] | None:
        """Return (start, end) minutes-of-day for the given weekday, or None."""
        records = [r for r in self._arrivals if r.weekday == weekday]
        if len(records) < self._min_arrivals:
            return None
        minutes = sorted(r.minute_of_day for r in records)
        median = minutes[len(minutes) // 2]
        return (median - self._window_half_min, median + self._window_half_min)

    def _should_pre_condition(self, ts: str) -> bool:
        dt = self._parse_ts(ts)
        if dt is None:
            return False
        weekday = dt.weekday()
        target = _minute_of_day(dt) + self._pre_condition_min

        if target < 1440:
            window = self._get_typical_window(weekday)
            if window and window[0] <= target <= window[1]:
                return True
        else:
            # Target crosses midnight — check the next weekday
            next_weekday = (weekday + 1) % 7
            target_wrapped = target - 1440
            window = self._get_typical_window(next_weekday)
            if window and window[0] <= target_wrapped <= window[1]:
                return True

        return False

    @staticmethod
    def _parse_ts(ts: str) -> datetime | None:
        try:
            return datetime.fromisoformat(ts).astimezone()
        except (ValueError, OverflowError, OSError):
            return None

    # ------------------------------------------------------------------
    # Inspection helpers (useful in tests and diagnostics)
    # ------------------------------------------------------------------

    def arrivals_for_weekday(self, weekday: int) -> list[int]:
        """Return minutes-of-day for all recorded arrivals on a given weekday."""
        return [r.minute_of_day for r in self._arrivals if r.weekday == weekday]

    def on_options_reloaded(self, options: dict[str, Any]) -> None:
        # Arrival history is in-memory only; no config to reload in v1.
        pass

    def reset_learning_state(self) -> None:
        self._arrivals.clear()
        self._fire_count = 0
        self._suppressed_count = 0
        self._last_fired_ts = None

    def diagnostics(self) -> dict[str, Any]:
        diag: dict[str, Any] = {
            "arrivals_count": len(self._arrivals),
            "arrivals_by_weekday": {
                str(wd): len([r for r in self._arrivals if r.weekday == wd])
                for wd in range(7)
                if any(r.weekday == wd for r in self._arrivals)
            },
            "fire_count": self._fire_count,
            "suppressed_count": self._suppressed_count,
            "last_fired_ts": self._last_fired_ts,
            "min_arrivals": self._min_arrivals,
            "window_half_min": self._window_half_min,
            "pre_condition_min": self._pre_condition_min,
        }
        if self._backend is not None:
            diag["learning"] = self._backend.diagnostics(self._reaction_id)
        return diag


def build_presence_pattern_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> PresencePatternReaction | None:
    """Build a PresencePatternReaction from persisted config."""
    try:
        weekday = int(cfg["weekday"])
        median_min = int(cfg["median_arrival_min"])
        window_half = int(cfg.get("window_half_min", 15))
        pre_cond = int(cfg.get("pre_condition_min", 20))
        min_arrivals = int(cfg.get("min_arrivals", 5))
        steps_raw: list = cfg.get("steps", [])
        steps = [ApplyStep(**s) if isinstance(s, dict) else s for s in steps_raw]
    except (KeyError, TypeError, ValueError):
        return None

    seed = [_ArrivalRecord(weekday=weekday, minute_of_day=median_min) for _ in range(min_arrivals)]
    return PresencePatternReaction(
        steps=steps,
        min_arrivals=min_arrivals,
        window_half_min=window_half,
        pre_condition_min=pre_cond,
        reaction_id=proposal_id,
        initial_arrivals=seed,
    )


def present_presence_pattern_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels_map: dict[str, str],
) -> str | None:
    """Return a human label for persisted presence reactions."""
    weekday_names = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    try:
        weekday = int(cfg["weekday"])
        median_min = int(cfg["median_arrival_min"])
        window_half = int(cfg.get("window_half_min", 0))
        hhmm = f"{median_min // 60:02d}:{median_min % 60:02d}"
        spread = f" (± {window_half} min)" if window_half > 0 else ""
        day = weekday_names[weekday] if 0 <= weekday <= 6 else str(weekday)
        return f"{day}: arrivo alle {hhmm}{spread}"
    except (KeyError, TypeError, ValueError, IndexError):
        return labels_map.get(reaction_id)
