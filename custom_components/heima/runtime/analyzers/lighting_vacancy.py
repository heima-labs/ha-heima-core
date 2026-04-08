"""Shared helpers for vacancy-driven room lighting learning."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def median_vacancy_delay_s(confirmed: list[Any]) -> int:
    delays: list[int] = []
    for episode in confirmed:
        origin_ts = getattr(episode, "ts", None)
        followups = getattr(episode, "followup_events", ())
        if origin_ts is None or not followups:
            continue
        first = followups[0]
        first_ts = getattr(first, "ts", None)
        if first_ts is None:
            continue
        if isinstance(first_ts, str):
            try:
                first_ts = datetime.fromisoformat(first_ts)
            except ValueError:
                continue
        delay_s = int((first_ts - origin_ts).total_seconds())
        if delay_s >= 0:
            delays.append(delay_s)
    if not delays:
        return 300
    delays.sort()
    return max(60, delays[len(delays) // 2])
