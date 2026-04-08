"""CalendarDomain: calendar event integration for intent-driven scheduling."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# str alias kept for readability; any category name is valid
CalendarCategory = str


@dataclass(frozen=True)
class CalendarEvent:
    """A classified calendar event."""

    summary: str
    start: datetime
    end: datetime
    all_day: bool
    category: str  # any user-defined or built-in category, or "unknown"
    calendar_entity: str


@dataclass
class CalendarResult:
    """Output of CalendarDomain.compute()."""

    current_events: list[CalendarEvent] = field(default_factory=list)
    upcoming_events: list[CalendarEvent] = field(default_factory=list)
    is_vacation_active: bool = False
    is_wfh_today: bool = False
    is_office_today: bool = False
    next_vacation: CalendarEvent | None = None
    cache_ts: datetime | None = None
    cache_hit: bool = False

    @classmethod
    def empty(cls) -> "CalendarResult":
        return cls()


class CalendarDomain:
    """Reads HA calendar entities and classifies events for Heima domains."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        # Cached upcoming events from calendar.get_events (all entities merged)
        self._cached_events: list[CalendarEvent] = []
        self._cache_ts: datetime | None = None

    def reset(self) -> None:
        """Called on options reload — clears cache."""
        self._cached_events = []
        self._cache_ts = None

    def diagnostics(self) -> dict[str, Any]:
        return {
            "cache_ts": self._cache_ts.isoformat() if self._cache_ts else None,
            "cached_events_count": len(self._cached_events),
            "cached_events": [
                {
                    "summary": e.summary,
                    "start": e.start.isoformat(),
                    "end": e.end.isoformat(),
                    "all_day": e.all_day,
                    "category": e.category,
                    "calendar_entity": e.calendar_entity,
                }
                for e in self._cached_events
            ],
        }

    # ------------------------------------------------------------------
    # Async refresh (called from engine.async_evaluate before compute)
    # ------------------------------------------------------------------

    async def async_maybe_refresh(self, calendar_cfg: dict[str, Any]) -> None:
        """Refresh lookahead cache if stale or empty."""
        entity_ids: list[str] = calendar_cfg.get("calendar_entities") or []
        if not entity_ids:
            return

        cache_ttl_hours: float = float(calendar_cfg.get("cache_ttl_hours") or 2)
        now = datetime.now(timezone.utc)

        if self._cache_ts is not None:
            age = (now - self._cache_ts).total_seconds() / 3600
            if age < cache_ttl_hours:
                return  # still fresh

        lookahead_days: int = int(calendar_cfg.get("lookahead_days") or 7)
        keywords, priority_order = _resolve_classification_config(calendar_cfg)
        end_dt = now + timedelta(days=lookahead_days)

        events: list[CalendarEvent] = []
        for entity_id in entity_ids:
            try:
                response: Any = await self._hass.services.async_call(
                    "calendar",
                    "get_events",
                    {
                        "entity_id": entity_id,
                        "start_date_time": now.isoformat(),
                        "end_date_time": end_dt.isoformat(),
                    },
                    blocking=True,
                    return_response=True,
                )
                entity_data = (response or {}).get(entity_id, {})
                for raw in entity_data.get("events", []):
                    ev = _parse_raw_event(raw, entity_id, keywords, priority_order)
                    if ev is not None:
                        events.append(ev)
            except Exception:
                _LOGGER.warning(
                    "CalendarDomain: failed to fetch events from %s", entity_id, exc_info=True
                )

        self._cached_events = events
        self._cache_ts = now
        _LOGGER.debug(
            "CalendarDomain: cache refreshed, %d events from %d entities",
            len(events),
            len(entity_ids),
        )

    # ------------------------------------------------------------------
    # Sync compute (reads entity states + cache)
    # ------------------------------------------------------------------

    def compute(self, calendar_cfg: dict[str, Any]) -> CalendarResult:
        """Return CalendarResult. Uses entity state for current events, cache for lookahead."""
        entity_ids: list[str] = calendar_cfg.get("calendar_entities") or []
        if not entity_ids:
            return CalendarResult.empty()

        keywords, priority_order = _resolve_classification_config(calendar_cfg)
        now = datetime.now(timezone.utc)
        today = now.date()

        # Current events: read live from entity state
        current_events: list[CalendarEvent] = []
        for entity_id in entity_ids:
            state = self._hass.states.get(entity_id)
            if state is None or state.state != "on":
                continue
            attrs = state.attributes
            summary = str(attrs.get("message") or attrs.get("summary") or "")
            start = _parse_dt_attr(attrs.get("start_time"))
            end = _parse_dt_attr(attrs.get("end_time"))
            all_day = bool(attrs.get("all_day", False))
            if start is None:
                start = now
            if end is None:
                end = now
            category = _classify(summary, keywords, priority_order)
            current_events.append(
                CalendarEvent(
                    summary=summary,
                    start=start,
                    end=end,
                    all_day=all_day,
                    category=category,
                    calendar_entity=entity_id,
                )
            )

        upcoming_events = list(self._cached_events)
        cache_hit = self._cache_ts is not None

        # Merge: all-day events from cache that cover today (not already in current_events)
        current_keys = {(e.summary, e.calendar_entity) for e in current_events}
        all_day_today: list[CalendarEvent] = []
        for ev in upcoming_events:
            if not ev.all_day:
                continue
            if (ev.summary, ev.calendar_entity) in current_keys:
                continue
            ev_start = ev.start.date()
            # all-day end in HA is exclusive (day after), so: start <= today < end
            ev_end = ev.end.date()
            if ev_start <= today < ev_end:
                all_day_today.append(ev)

        today_events = current_events + all_day_today

        is_vacation_active = any(e.category == "vacation" for e in today_events)
        is_office_today = any(e.category == "office" for e in today_events)
        is_wfh_today = any(e.category == "wfh" for e in today_events) and not is_office_today

        next_vacation: CalendarEvent | None = None
        future_vacations = [
            e for e in upcoming_events if e.category == "vacation" and e.start.date() > today
        ]
        if future_vacations:
            next_vacation = min(future_vacations, key=lambda e: e.start)

        return CalendarResult(
            current_events=current_events,
            upcoming_events=upcoming_events,
            is_vacation_active=is_vacation_active,
            is_wfh_today=is_wfh_today,
            is_office_today=is_office_today,
            next_vacation=next_vacation,
            cache_ts=self._cache_ts,
            cache_hit=cache_hit,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _resolve_classification_config(
    calendar_cfg: dict[str, Any],
) -> tuple[dict[str, list[str]], list[str]]:
    """Return (keywords_dict, priority_order) from config, merging with defaults.

    - Built-in categories: user keywords extend (not replace) the defaults.
    - Custom categories: any key in calendar_keywords not in DEFAULT_CALENDAR_KEYWORDS.
    - priority_order: from config if set; defaults to DEFAULT_CALENDAR_CATEGORY_PRIORITY
      extended with any extra categories not already listed.
    """
    from ...const import DEFAULT_CALENDAR_CATEGORY_PRIORITY, DEFAULT_CALENDAR_KEYWORDS

    user_kw: dict[str, Any] = calendar_cfg.get("calendar_keywords") or {}

    # Build keywords dict: built-in first, then custom categories
    merged: dict[str, list[str]] = {}
    for cat, defaults in DEFAULT_CALENDAR_KEYWORDS.items():
        user_list = _coerce_kw_list(user_kw.get(cat))
        merged[cat] = list(dict.fromkeys(defaults + user_list))
    for cat, kw_raw in user_kw.items():
        if cat not in DEFAULT_CALENDAR_KEYWORDS:
            kw_list = _coerce_kw_list(kw_raw)
            if kw_list:
                merged[cat] = kw_list

    # Build priority order
    cfg_priority = calendar_cfg.get("category_priority")
    if cfg_priority and isinstance(cfg_priority, list) and cfg_priority:
        priority_order = [str(c) for c in cfg_priority if str(c)]
    else:
        priority_order = list(DEFAULT_CALENDAR_CATEGORY_PRIORITY)

    # Append any categories in keywords not yet in priority (so they're reachable)
    for cat in merged:
        if cat not in priority_order:
            priority_order.append(cat)

    return merged, priority_order


def _coerce_kw_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(k).strip() for k in value if str(k).strip()]
    if isinstance(value, str):
        return [k.strip() for k in value.split(",") if k.strip()]
    return []


def _classify(summary: str, keywords: dict[str, list[str]], priority_order: list[str]) -> str:
    """Classify an event by keyword matching. First category in priority_order wins."""
    lower = summary.lower()
    for cat in priority_order:
        for kw in keywords.get(cat, []):
            if kw.lower() in lower:
                return cat
    return "unknown"


def _parse_raw_event(
    raw: dict[str, Any],
    entity_id: str,
    keywords: dict[str, list[str]],
    priority_order: list[str],
) -> CalendarEvent | None:
    """Parse a raw event dict from calendar.get_events response."""
    summary = str(raw.get("summary") or raw.get("message") or "")
    start_raw = raw.get("start")
    end_raw = raw.get("end")
    if start_raw is None or end_raw is None:
        return None

    all_day = False
    start = _parse_dt_or_date(start_raw)
    end = _parse_dt_or_date(end_raw)

    if start is None or end is None:
        return None

    # Detect all-day: raw value is a date string without time component
    if isinstance(start_raw, str) and "T" not in start_raw and ":" not in start_raw:
        all_day = True

    category = _classify(summary, keywords, priority_order)
    return CalendarEvent(
        summary=summary,
        start=start,
        end=end,
        all_day=all_day,
        category=category,
        calendar_entity=entity_id,
    )


def _parse_dt_attr(value: Any) -> datetime | None:
    """Parse a datetime attribute from HA calendar entity state."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        return _parse_dt_or_date(value)
    return None


def _parse_dt_or_date(value: str) -> datetime | None:
    """Parse ISO datetime or date string to UTC datetime."""
    if not value:
        return None
    try:
        # Try datetime first
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    try:
        # Try date-only "YYYY-MM-DD"
        d = date.fromisoformat(value)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    except ValueError:
        return None
