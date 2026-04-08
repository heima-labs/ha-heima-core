"""Options flow: Notifications step."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from ..const import (
    DEFAULT_ENABLED_EVENT_CATEGORIES,
    DEFAULT_OCCUPANCY_MISMATCH_MIN_DERIVED_ROOMS,
    DEFAULT_OCCUPANCY_MISMATCH_PERSIST_S,
    DEFAULT_OCCUPANCY_MISMATCH_POLICY,
    DEFAULT_SECURITY_MISMATCH_EVENT_MODE,
    DEFAULT_SECURITY_MISMATCH_PERSIST_S,
    DEFAULT_SECURITY_MISMATCH_POLICY,
    EVENT_CATEGORIES_TOGGLEABLE,
    OCCUPANCY_MISMATCH_POLICIES,
    OPT_NOTIFICATIONS,
    SECURITY_MISMATCH_EVENT_MODES,
    SECURITY_MISMATCH_POLICIES,
)
from ._common import (
    _NON_NEGATIVE_INT,
    _object_selector,
    _parse_multiline_items,
    _parse_multiline_mapping,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

try:
    from homeassistant.helpers import config_validation as cv
except ImportError:
    pass


class _NotificationsStepsMixin:
    """Mixin for notifications step."""

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        current = dict(self.options.get(OPT_NOTIFICATIONS, {}))
        if user_input is None:
            return self.async_show_form(
                step_id="notifications", data_schema=self._notifications_schema(current)
            )

        user_input = self._normalize_notifications_payload(user_input)
        self._update_options({OPT_NOTIFICATIONS: user_input})
        return await self.async_step_init()

    def _notifications_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        schema_defaults = dict(defaults)
        schema = vol.Schema(
            {
                vol.Optional("recipients"): _object_selector(),
                vol.Optional("recipient_groups"): _object_selector(),
                vol.Optional("route_targets"): _object_selector(),
                vol.Optional("enabled_event_categories"): cv.multi_select(
                    EVENT_CATEGORIES_TOGGLEABLE
                ),
                vol.Optional(
                    "dedup_window_s", default=defaults.get("dedup_window_s", 60)
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "rate_limit_per_key_s", default=defaults.get("rate_limit_per_key_s", 300)
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "occupancy_mismatch_policy",
                    default=defaults.get(
                        "occupancy_mismatch_policy", DEFAULT_OCCUPANCY_MISMATCH_POLICY
                    ),
                ): vol.In(OCCUPANCY_MISMATCH_POLICIES),
                vol.Optional(
                    "occupancy_mismatch_min_derived_rooms",
                    default=defaults.get(
                        "occupancy_mismatch_min_derived_rooms",
                        DEFAULT_OCCUPANCY_MISMATCH_MIN_DERIVED_ROOMS,
                    ),
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "occupancy_mismatch_persist_s",
                    default=defaults.get(
                        "occupancy_mismatch_persist_s", DEFAULT_OCCUPANCY_MISMATCH_PERSIST_S
                    ),
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "security_mismatch_policy",
                    default=defaults.get(
                        "security_mismatch_policy", DEFAULT_SECURITY_MISMATCH_POLICY
                    ),
                ): vol.In(SECURITY_MISMATCH_POLICIES),
                vol.Optional(
                    "security_mismatch_event_mode",
                    default=defaults.get(
                        "security_mismatch_event_mode",
                        DEFAULT_SECURITY_MISMATCH_EVENT_MODE,
                    ),
                ): vol.In(SECURITY_MISMATCH_EVENT_MODES),
                vol.Optional(
                    "security_mismatch_persist_s",
                    default=defaults.get(
                        "security_mismatch_persist_s", DEFAULT_SECURITY_MISMATCH_PERSIST_S
                    ),
                ): _NON_NEGATIVE_INT,
            }
        )
        defaults_with_categories = dict(schema_defaults)
        defaults_with_categories.setdefault(
            "enabled_event_categories", list(DEFAULT_ENABLED_EVENT_CATEGORIES)
        )
        return self._with_suggested(schema, defaults_with_categories)

    # ---- Normalization ----

    def _normalize_notifications_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        from ..const import EVENT_CATEGORIES_TOGGLEABLE as _ETC

        data = dict(payload)
        data.pop("routes", None)
        data["recipients"] = _parse_multiline_mapping(data.get("recipients"))
        data["recipient_groups"] = _parse_multiline_mapping(data.get("recipient_groups"))
        data["route_targets"] = _parse_multiline_items(data.get("route_targets"))
        recipient_ids = set(data["recipients"])
        normalized_groups: dict[str, list[str]] = {}
        for group_id, members in data["recipient_groups"].items():
            valid_members = [m for m in members if m in recipient_ids]
            if valid_members:
                normalized_groups[group_id] = valid_members
        data["recipient_groups"] = normalized_groups
        data["route_targets"] = [
            t for t in data["route_targets"] if t in recipient_ids or t in normalized_groups
        ]
        categories_present = "enabled_event_categories" in data
        categories = self._normalize_multi_value(data.get("enabled_event_categories"))
        if categories_present:
            data["enabled_event_categories"] = [c for c in categories if c in _ETC]
        else:
            data["enabled_event_categories"] = list(DEFAULT_ENABLED_EVENT_CATEGORIES)
        policy = str(data.get("occupancy_mismatch_policy", DEFAULT_OCCUPANCY_MISMATCH_POLICY))
        if policy not in OCCUPANCY_MISMATCH_POLICIES:
            policy = DEFAULT_OCCUPANCY_MISMATCH_POLICY
        data["occupancy_mismatch_policy"] = policy
        data["occupancy_mismatch_min_derived_rooms"] = int(
            data.get(
                "occupancy_mismatch_min_derived_rooms",
                DEFAULT_OCCUPANCY_MISMATCH_MIN_DERIVED_ROOMS,
            )
        )
        data["occupancy_mismatch_persist_s"] = int(
            data.get("occupancy_mismatch_persist_s", DEFAULT_OCCUPANCY_MISMATCH_PERSIST_S)
        )
        security_policy = str(
            data.get("security_mismatch_policy", DEFAULT_SECURITY_MISMATCH_POLICY)
        )
        if security_policy not in SECURITY_MISMATCH_POLICIES:
            security_policy = DEFAULT_SECURITY_MISMATCH_POLICY
        data["security_mismatch_policy"] = security_policy
        security_mode = str(
            data.get("security_mismatch_event_mode", DEFAULT_SECURITY_MISMATCH_EVENT_MODE)
        )
        if security_mode not in SECURITY_MISMATCH_EVENT_MODES:
            security_mode = DEFAULT_SECURITY_MISMATCH_EVENT_MODE
        data["security_mismatch_event_mode"] = security_mode
        data["security_mismatch_persist_s"] = int(
            data.get("security_mismatch_persist_s", DEFAULT_SECURITY_MISMATCH_PERSIST_S)
        )
        return data
