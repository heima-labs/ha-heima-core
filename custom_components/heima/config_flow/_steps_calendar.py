"""Options flow: Calendar step."""

# mypy: disable-error-code=attr-defined

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector

from ..const import (
    DEFAULT_CALENDAR_CACHE_TTL_HOURS,
    DEFAULT_CALENDAR_CATEGORY_PRIORITY,
    DEFAULT_CALENDAR_KEYWORDS,
    DEFAULT_CALENDAR_LOOKAHEAD_DAYS,
    OPT_CALENDAR,
)
from ._common import _entity_selector, _object_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


def _keywords_default(calendar_cfg: dict[str, Any]) -> dict[str, list[str]]:
    stored = calendar_cfg.get("calendar_keywords")
    if stored and isinstance(stored, dict):
        return stored
    return dict(DEFAULT_CALENDAR_KEYWORDS)


def _priority_default(calendar_cfg: dict[str, Any]) -> str:
    stored = calendar_cfg.get("category_priority")
    if stored and isinstance(stored, list):
        return ", ".join(stored)
    return ", ".join(DEFAULT_CALENDAR_CATEGORY_PRIORITY)


class _CalendarStepsMixin:
    """Mixin for calendar configuration step."""

    async def async_step_calendar(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        calendar_cfg = dict(self.options.get(OPT_CALENDAR, {}))
        schema = self._calendar_schema(calendar_cfg)

        if user_input is None:
            return self.async_show_form(
                step_id="calendar",
                data_schema=self._with_suggested(
                    schema,
                    {
                        "calendar_entities": calendar_cfg.get("calendar_entities") or [],
                        "lookahead_days": int(
                            calendar_cfg.get("lookahead_days") or DEFAULT_CALENDAR_LOOKAHEAD_DAYS
                        ),
                        "cache_ttl_hours": int(
                            calendar_cfg.get("cache_ttl_hours") or DEFAULT_CALENDAR_CACHE_TTL_HOURS
                        ),
                        "calendar_keywords": _keywords_default(calendar_cfg),
                        "priority_text": _priority_default(calendar_cfg),
                    },
                ),
            )

        entities = user_input.get("calendar_entities") or []
        if isinstance(entities, str):
            entities = [entities] if entities else []

        # calendar_keywords comes from object selector — already a dict
        keywords = user_input.get("calendar_keywords") or {}
        if not isinstance(keywords, dict):
            keywords = {}
        # Normalise values to list[str]
        normalised: dict[str, list[str]] = {}
        for cat, kws in keywords.items():
            cat = str(cat).strip().lower()
            if not cat:
                continue
            if isinstance(kws, list):
                normalised[cat] = [str(k).strip() for k in kws if str(k).strip()]
            elif isinstance(kws, str):
                normalised[cat] = [k.strip() for k in kws.split(",") if k.strip()]

        priority = [
            p.strip().lower()
            for p in str(user_input.get("priority_text") or "").split(",")
            if p.strip()
        ]
        for cat in normalised:
            if cat not in priority:
                priority.append(cat)

        self._update_options(
            {
                OPT_CALENDAR: {
                    "calendar_entities": list(entities),
                    "lookahead_days": int(
                        user_input.get("lookahead_days") or DEFAULT_CALENDAR_LOOKAHEAD_DAYS
                    ),
                    "cache_ttl_hours": int(
                        user_input.get("cache_ttl_hours") or DEFAULT_CALENDAR_CACHE_TTL_HOURS
                    ),
                    "calendar_keywords": normalised,
                    "category_priority": priority,
                }
            }
        )
        return await self.async_step_init()

    def _calendar_menu_summary(self) -> str:
        coordinator = None
        try:
            domain = getattr(getattr(self, "hass", None), "data", {}).get("heima", {})
            if isinstance(domain, dict):
                entry_data = domain.get(getattr(self._config_entry, "entry_id", None), {})
                if isinstance(entry_data, dict):
                    coordinator = entry_data.get("coordinator")
        except Exception:
            coordinator = None

        state = getattr(getattr(coordinator, "engine", None), "_state", None)
        calendar_result = getattr(state, "calendar_result", None) if state is not None else None
        lang = str(self.options.get("language", "it"))
        is_it = lang.startswith("it")

        if calendar_result is not None:
            if bool(getattr(calendar_result, "is_vacation_active", False)):
                return "vacation attiva" if is_it else "vacation active"
            if bool(getattr(calendar_result, "is_office_today", False)):
                return "office oggi" if is_it else "office today"
            if bool(getattr(calendar_result, "is_wfh_today", False)):
                return "WFH oggi" if is_it else "WFH today"
            next_vacation = getattr(calendar_result, "next_vacation", None)
            if next_vacation is not None:
                summary = str(getattr(next_vacation, "summary", "") or "").strip() or "-"
                return f"prossima vacation: {summary}" if is_it else f"next vacation: {summary}"

        calendar = dict(self.options.get(OPT_CALENDAR, {}))
        entities = list(calendar.get("calendar_entities") or [])
        if not entities:
            return "—"
        return f"{len(entities)}: {', '.join(entities)}"

    def _calendar_schema(self, calendar_cfg: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional("calendar_entities"): _entity_selector(["calendar"], multiple=True),
                vol.Optional("lookahead_days"): selector(
                    {"number": {"min": 1, "max": 30, "mode": "box"}}
                ),
                vol.Optional("cache_ttl_hours"): selector(
                    {"number": {"min": 1, "max": 24, "mode": "box"}}
                ),
                vol.Optional("calendar_keywords"): _object_selector(),
                vol.Optional("priority_text"): cv.string,
            }
        )
