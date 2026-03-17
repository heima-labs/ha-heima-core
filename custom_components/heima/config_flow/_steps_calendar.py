"""Options flow: Calendar step."""

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
from ._common import _entity_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


def _keywords_to_text(keywords: dict[str, list[str]]) -> str:
    """Serialize keywords dict to multiline text (one category per line)."""
    lines = []
    for cat, kws in keywords.items():
        lines.append(f"{cat}: {', '.join(kws)}")
    return "\n".join(lines)


def _text_to_keywords(text: str) -> dict[str, list[str]]:
    """Parse multiline text back to keywords dict."""
    result: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        cat, _, kw_str = line.partition(":")
        cat = cat.strip().lower()
        kws = [k.strip() for k in kw_str.split(",") if k.strip()]
        if cat and kws:
            result[cat] = kws
    return result


def _priority_to_text(priority: list[str]) -> str:
    return ", ".join(priority)


def _text_to_priority(text: str) -> list[str]:
    return [p.strip().lower() for p in text.split(",") if p.strip()]


def _default_keywords_text(calendar_cfg: dict[str, Any]) -> str:
    stored = calendar_cfg.get("calendar_keywords")
    if stored and isinstance(stored, dict):
        return _keywords_to_text(stored)
    return _keywords_to_text(DEFAULT_CALENDAR_KEYWORDS)


def _default_priority_text(calendar_cfg: dict[str, Any]) -> str:
    stored = calendar_cfg.get("category_priority")
    if stored and isinstance(stored, list):
        return _priority_to_text(stored)
    return _priority_to_text(DEFAULT_CALENDAR_CATEGORY_PRIORITY)


class _CalendarStepsMixin:
    """Mixin for calendar configuration step."""

    async def async_step_calendar(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        calendar_cfg = dict(self.options.get(OPT_CALENDAR, {}))
        schema = self._calendar_schema(calendar_cfg)

        if user_input is None:
            return self.async_show_form(step_id="calendar", data_schema=schema)

        entities = user_input.get("calendar_entities") or []
        if isinstance(entities, str):
            entities = [entities] if entities else []

        keywords = _text_to_keywords(user_input.get("keywords_text") or "")
        priority = _text_to_priority(user_input.get("priority_text") or "")

        # Ensure priority contains at least the categories present in keywords
        for cat in keywords:
            if cat not in priority:
                priority.append(cat)

        self.options[OPT_CALENDAR] = {
            "calendar_entities": list(entities),
            "lookahead_days": int(user_input.get("lookahead_days") or DEFAULT_CALENDAR_LOOKAHEAD_DAYS),
            "cache_ttl_hours": int(user_input.get("cache_ttl_hours") or DEFAULT_CALENDAR_CACHE_TTL_HOURS),
            "calendar_keywords": keywords,
            "category_priority": priority,
        }
        return await self.async_step_init()

    def _calendar_schema(self, calendar_cfg: dict[str, Any]) -> vol.Schema:
        entities = calendar_cfg.get("calendar_entities") or []
        return vol.Schema(
            {
                vol.Optional(
                    "calendar_entities",
                    default=entities,
                ): _entity_selector(["calendar"], multiple=True),
                vol.Optional(
                    "lookahead_days",
                    default=int(calendar_cfg.get("lookahead_days") or DEFAULT_CALENDAR_LOOKAHEAD_DAYS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
                vol.Optional(
                    "cache_ttl_hours",
                    default=int(calendar_cfg.get("cache_ttl_hours") or DEFAULT_CALENDAR_CACHE_TTL_HOURS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                vol.Optional(
                    "keywords_text",
                    default=_default_keywords_text(calendar_cfg),
                ): selector({"text": {"multiline": True}}),
                vol.Optional(
                    "priority_text",
                    default=_default_priority_text(calendar_cfg),
                ): cv.string,
            }
        )
