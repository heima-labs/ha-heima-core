"""Outcome verification for reaction feedback loops."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .inference.snapshot_store import HouseSnapshot

OutcomeValue = Literal["positive", "negative"]


@dataclass(frozen=True)
class OutcomeSpec:
    """Expected event contract for a verifiable reaction."""

    expected_event_type: str
    timeout_s: float = 900.0
    match_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PendingVerification:
    """Pending verification registered when a reaction fires."""

    reaction_id: str
    expected_event_type: str
    expected_within_s: float
    fired_at_ts: float
    snapshot_at_fire: HouseSnapshot
    match_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutcomeRecord:
    """Resolved outcome for a fired reaction."""

    reaction_id: str
    outcome: OutcomeValue
    fired_at_ts: float
    resolved_at_ts: float
    expected_event_type: str
    context: dict[str, Any]


class OutcomeTracker:
    """Synchronous in-memory tracker for reaction outcome verification."""

    DEFAULT_TIMEOUT_S = 900.0
    DEGRADATION_THRESHOLD = 5
    REACTION_TIMEOUTS: Mapping[str, float] = {
        "PresencePatternReaction": 1800.0,
        "ConsecutiveStateReaction": 600.0,
    }

    def __init__(self, *, now_provider: Callable[[], float] | None = None) -> None:
        self._now_provider = now_provider or time.time
        self._pending: dict[str, PendingVerification] = {}
        self._records: list[OutcomeRecord] = []
        self._negative_streaks: dict[str, int] = {}

    def timeout_for(
        self,
        reaction_type: str,
        *,
        outcome_spec: OutcomeSpec | None = None,
    ) -> float:
        """Return the default verification timeout for a reaction type."""
        if reaction_type in self.REACTION_TIMEOUTS:
            return self.REACTION_TIMEOUTS[reaction_type]
        if outcome_spec is not None:
            return max(float(outcome_spec.timeout_s), 0.0)
        return self.DEFAULT_TIMEOUT_S

    def on_reaction_fired(
        self,
        *,
        reaction_id: str,
        expected_event_type: str,
        snapshot_at_fire: HouseSnapshot,
        fired_at_ts: float | None = None,
        expected_within_s: float | None = None,
        reaction_type: str | None = None,
        outcome_spec: OutcomeSpec | None = None,
    ) -> PendingVerification:
        """Register a pending verification for a fired reaction."""
        timeout_s = (
            max(float(expected_within_s), 0.0)
            if expected_within_s is not None
            else self.timeout_for(reaction_type or reaction_id, outcome_spec=outcome_spec)
        )
        pending = PendingVerification(
            reaction_id=reaction_id,
            expected_event_type=expected_event_type,
            expected_within_s=timeout_s,
            fired_at_ts=self._now_provider() if fired_at_ts is None else float(fired_at_ts),
            snapshot_at_fire=snapshot_at_fire,
            match_data=dict(outcome_spec.match_data) if outcome_spec is not None else {},
        )
        self.register_pending(pending)
        return pending

    def register_pending(self, pending: PendingVerification) -> None:
        """Register or replace the pending verification for a reaction."""
        self._pending[pending.reaction_id] = pending

    def check_pending(self, observed_events: Iterable[Any]) -> tuple[OutcomeRecord, ...]:
        """Resolve pending verifications from observed event types and timeouts."""
        now = self._now_provider()
        events_by_type = _events_by_type(observed_events)
        resolved: list[OutcomeRecord] = []

        for reaction_id, pending in list(self._pending.items()):
            matched_event = _first_matching_event(
                events_by_type.get(pending.expected_event_type, ()),
                pending.match_data,
            )
            if matched_event is not None:
                record = self._resolve(pending, "positive", now, matched_event=matched_event)
            elif now - pending.fired_at_ts >= pending.expected_within_s:
                record = self._resolve(pending, "negative", now)
            else:
                continue

            self._pending.pop(reaction_id, None)
            self._records.append(record)
            resolved.append(record)

        return tuple(resolved)

    def pending(self) -> tuple[PendingVerification, ...]:
        """Return pending verifications in insertion order."""
        return tuple(self._pending.values())

    def records(self) -> tuple[OutcomeRecord, ...]:
        """Return resolved records in insertion order."""
        return tuple(self._records)

    def negative_streak(self, reaction_id: str) -> int:
        """Return consecutive negative outcomes for one reaction."""
        return self._negative_streaks.get(reaction_id, 0)

    def ready_for_degradation(self, reaction_id: str) -> bool:
        """Return whether the reaction reached the degradation threshold."""
        return self.negative_streak(reaction_id) >= self.DEGRADATION_THRESHOLD

    def diagnostics(self) -> dict[str, Any]:
        """Return tracker diagnostics."""
        return {
            "pending_count": len(self._pending),
            "records_count": len(self._records),
            "negative_streaks": dict(self._negative_streaks),
            "degradation_threshold": self.DEGRADATION_THRESHOLD,
            "pending": [asdict(pending) for pending in self._pending.values()],
        }

    def reset(self) -> None:
        """Clear in-memory tracker state."""
        self._pending.clear()
        self._records.clear()
        self._negative_streaks.clear()

    def _resolve(
        self,
        pending: PendingVerification,
        outcome: OutcomeValue,
        resolved_at_ts: float,
        *,
        matched_event: Any | None = None,
    ) -> OutcomeRecord:
        if outcome == "positive":
            self._negative_streaks[pending.reaction_id] = 0
        else:
            self._negative_streaks[pending.reaction_id] = (
                self._negative_streaks.get(pending.reaction_id, 0) + 1
            )

        return OutcomeRecord(
            reaction_id=pending.reaction_id,
            outcome=outcome,
            fired_at_ts=pending.fired_at_ts,
            resolved_at_ts=resolved_at_ts,
            expected_event_type=pending.expected_event_type,
            context={
                "expected_within_s": pending.expected_within_s,
                "elapsed_s": max(resolved_at_ts - pending.fired_at_ts, 0.0),
                "match_data": dict(pending.match_data),
                "snapshot_at_fire": pending.snapshot_at_fire.as_dict(),
                "matched_event": _event_payload(matched_event),
            },
        )


def _events_by_type(observed_events: Iterable[Any]) -> dict[str, list[Any]]:
    events_by_type: dict[str, list[Any]] = {}
    for event in observed_events:
        event_type = _event_type(event)
        if event_type:
            events_by_type.setdefault(event_type, []).append(event)
    return events_by_type


def _first_matching_event(events: Iterable[Any], match_data: Mapping[str, Any]) -> Any | None:
    for event in events:
        if _event_data_matches(event, match_data):
            return event
    return None


def _event_data_matches(event: Any, match_data: Mapping[str, Any]) -> bool:
    if not match_data:
        return True
    data = _event_data(event)
    return all(data.get(key) == value for key, value in match_data.items())


def _event_type(event: Any) -> str:
    if isinstance(event, str):
        return event
    if isinstance(event, Mapping):
        raw = event.get("event_type", event.get("type", ""))
        return str(raw) if raw is not None else ""
    raw = getattr(event, "event_type", None)
    if raw is None:
        raw = getattr(event, "type", "")
    return str(raw) if raw is not None else ""


def _event_data(event: Any) -> Mapping[str, Any]:
    if isinstance(event, Mapping):
        raw = event.get("data", {})
        return raw if isinstance(raw, Mapping) else {}
    raw = getattr(event, "data", {})
    return raw if isinstance(raw, Mapping) else {}


def _event_payload(event: Any | None) -> dict[str, Any] | None:
    if event is None:
        return None
    if isinstance(event, Mapping):
        return dict(event)
    as_dict = getattr(event, "as_dict", None)
    if callable(as_dict):
        raw = as_dict()
        if isinstance(raw, dict):
            return raw
    return {"event_type": _event_type(event)}
